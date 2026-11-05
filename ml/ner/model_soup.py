"""
Fusion en espacio de pesos (Model Soup — Wortsman et al., ICML 2022) para checkpoints de RoBERTa NER.

Permite combinar multiples checkpoints ajustados desde la misma inicializacion preentrenada
(p. ej. los 5 folds de validacion cruzada o barridos de hiperparametros lr/seed) en un unico
archivo `model.safetensors`, mejorando generalizacion y calibracion con coste de inferencia 1x
(cero latencia adicional en `backend/triage/ner_model.py`).

Modos soportados:
  - `uniform`: media aritmetica exacta en float64 de todos los tensores flotantes.
  - `greedy` : ordena los checkpoints por micro-F1 en `dev` y agrega iterativamente cada candidato
               solo si `F1(promedio(soup + candidato)) >= mejor_F1_actual`.

Funciona con `numpy`/`torch` acelerado en GPU/Colab/Docker y degrada limpiamente a `array`/`struct`
de la libreria estandar en entornos ligeros sin `numpy`.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    import numpy as _np
except ImportError:  # pragma: no cover - entornos ligeros sin numpy
    _np = None

_ST_TYPES = {
    # code: (array_typecode_or_struct, byte_size, is_float)
    "F64": ("d", 8, True),
    "F32": ("f", 4, True),
    "I64": ("q", 8, False),
    "I32": ("i", 4, False),
    "I16": ("h", 2, False),
    "I8": ("b", 1, False),
    "U8": ("B", 1, False),
}


@dataclass(frozen=True)
class TensorBox:
    """Representacion agnostica de tensor para entornos sin numpy (compatible con `.safetensors`)."""
    dtype: str  # codigo safetensors: 'F32', 'F64', 'I64', ...
    shape: Tuple[int, ...]
    values: Tuple[Any, ...]

    @property
    def is_floating(self) -> bool:
        return _ST_TYPES[self.dtype][2]

    def to_list(self) -> List[Any]:
        return list(self.values)


INFERENCE_SIDE_FILES = (
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
    "ner_labels.json",
    "training_config.json",
)


@dataclass(frozen=True)
class SoupResult:
    mode: str
    weights: Dict[str, Any]
    best_score: Optional[float]
    selected: List[str]
    individual_scores: Dict[str, float]
    history: List[Dict[str, object]]


def make_tensor(values: Sequence[Any], shape: Optional[Sequence[int]] = None, dtype: str = "F32") -> Any:
    """Crea un tensor (`np.ndarray` si `numpy` existe, o `TensorBox` stdlib en caso contrario)."""
    flat = list(values)
    inferred_shape = tuple(shape) if shape is not None else (len(flat),)
    expected = math.prod(inferred_shape) if inferred_shape else 1
    if len(flat) != expected:
        raise ValueError(f"Longitud {len(flat)} incompatible con shape {inferred_shape}")
    if _np is not None:
        np_map = {"F64": _np.float64, "F32": _np.float32, "I64": _np.int64, "I32": _np.int32, "I16": _np.int16,
                  "I8": _np.int8, "U8": _np.uint8}
        return _np.array(flat, dtype=np_map[dtype]).reshape(inferred_shape)
    cast = float if _ST_TYPES[dtype][2] else int
    return TensorBox(dtype=dtype, shape=inferred_shape, values=tuple(cast(x) for x in flat))


def tensor_flat_list(tensor: Any) -> List[Any]:
    if isinstance(tensor, TensorBox):
        return list(tensor.values)
    if _np is not None and isinstance(tensor, _np.ndarray):
        return tensor.reshape(-1).tolist()
    raise TypeError(f"Tipo de tensor no soportado: {type(tensor)}")


def _tensor_meta(tensor: Any) -> Tuple[str, Tuple[int, ...], bool]:
    if isinstance(tensor, TensorBox):
        return tensor.dtype, tensor.shape, tensor.is_floating
    if _np is not None and isinstance(tensor, _np.ndarray):
        np_to_st = {
            _np.dtype("float64"): "F64",
            _np.dtype("float32"): "F32",
            _np.dtype("float16"): "F16",
            _np.dtype("int64"): "I64",
            _np.dtype("int32"): "I32",
            _np.dtype("int16"): "I16",
            _np.dtype("int8"): "I8",
            _np.dtype("uint8"): "U8",
        }
        base = tensor.dtype.newbyteorder("=")
        if base not in np_to_st:
            raise ValueError(f"dtype numpy no soportado: {tensor.dtype}")
        code = np_to_st[base]
        return code, tuple(int(d) for d in tensor.shape), bool(_np.issubdtype(base, _np.floating))
    raise TypeError(f"Tipo de tensor no soportado: {type(tensor)}")


def _clone_tensor(tensor: Any) -> Any:
    if isinstance(tensor, TensorBox):
        return TensorBox(dtype=tensor.dtype, shape=tensor.shape, values=tensor.values)
    return tensor.copy()


def read_safetensors(path: Path) -> Dict[str, Any]:
    """Lee un archivo `.safetensors` estandar usando `numpy` si esta disponible o `array` stdlib."""
    raw = Path(path).read_bytes()
    if len(raw) < 8:
        raise ValueError(f"Archivo safetensors truncado: {path}")
    (header_len,) = struct.unpack("<Q", raw[:8])
    header_end = 8 + header_len
    if header_end > len(raw):
        raise ValueError(f"Cabecera safetensors invalida en {path}")
    header = json.loads(raw[8:header_end].decode("utf-8"))
    body = memoryview(raw)[header_end:]

    tensors: Dict[str, Any] = {}
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        code = meta["dtype"]
        shape = tuple(int(d) for d in meta["shape"])
        start, end = meta["data_offsets"]
        segment = bytes(body[start:end])

        if _np is not None:
            np_codes = {
                "F64": "<f8", "F32": "<f4", "F16": "<f2",
                "I64": "<i8", "I32": "<i4", "I16": "<i2", "I8": "<i1", "U8": "<u1", "BOOL": "?",
            }
            if code not in np_codes:
                raise ValueError(f"Tipo safetensors no soportado '{code}' en '{name}'")
            arr = _np.frombuffer(segment, dtype=_np.dtype(np_codes[code])).reshape(shape).copy()
            if sys.byteorder != "little" and arr.dtype.itemsize > 1:
                arr = arr.byteswap().view(arr.dtype.newbyteorder("="))
            tensors[name] = arr
        else:
            if code not in _ST_TYPES:
                raise ValueError(f"Tipo safetensors '{code}' requiere numpy instalado.")
            typecode, _, _ = _ST_TYPES[code]
            arr_std = array.array(typecode)
            arr_std.frombytes(segment)
            if sys.byteorder != "little" and arr_std.itemsize > 1:
                arr_std.byteswap()
            tensors[name] = TensorBox(dtype=code, shape=shape, values=tuple(arr_std))
    return tensors


def write_safetensors(
    path: Path,
    tensors: Mapping[str, Any],
    metadata: Optional[Mapping[str, str]] = None,
) -> Path:
    """Escribe un diccionario de tensores en formato binario `.safetensors` compatible con Hugging Face."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    header: Dict[str, object] = {}
    if metadata:
        header["__metadata__"] = {str(k): str(v) for k, v in metadata.items()}

    chunks: List[bytes] = []
    offset = 0
    for name in sorted(tensors.keys()):
        t = tensors[name]
        code, shape, _ = _tensor_meta(t)
        if _np is not None and isinstance(t, _np.ndarray):
            np_le = {
                "F64": "<f8", "F32": "<f4", "F16": "<f2",
                "I64": "<i8", "I32": "<i4", "I16": "<i2", "I8": "<i1", "U8": "<u1",
            }[code]
            buf = _np.ascontiguousarray(t).astype(_np.dtype(np_le), copy=False).tobytes(order="C")
        else:
            typecode, _, is_flt = _ST_TYPES[code]
            cast = float if is_flt else int
            arr_std = array.array(typecode, [cast(v) for v in t.values])
            if sys.byteorder != "little" and arr_std.itemsize > 1:
                arr_std.byteswap()
            buf = arr_std.tobytes()

        header[name] = {
            "dtype": code,
            "shape": list(shape),
            "data_offsets": [offset, offset + len(buf)],
        }
        chunks.append(buf)
        offset += len(buf)

    header_bytes = json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    pad = (8 - (len(header_bytes) % 8)) % 8
    if pad:
        header_bytes += b" " * pad

    with target.open("wb") as handle:
        handle.write(struct.pack("<Q", len(header_bytes)))
        handle.write(header_bytes)
        for chunk in chunks:
            handle.write(chunk)
    return target


def load_checkpoint_weights(checkpoint: Path) -> Dict[str, Any]:
    """Carga un checkpoint desde directorio Hugging Face o archivo `.safetensors` / `.bin`."""
    ckpt = Path(checkpoint)
    if ckpt.is_dir():
        st_path = ckpt / "model.safetensors"
        if st_path.exists():
            return read_safetensors(st_path)
        bin_path = ckpt / "pytorch_model.bin"
        if bin_path.exists():
            return _load_torch_bin(bin_path)
        raise FileNotFoundError(f"No se encontro model.safetensors ni pytorch_model.bin en {ckpt}")
    if ckpt.suffix == ".safetensors":
        return read_safetensors(ckpt)
    if ckpt.suffix in (".bin", ".pt", ".pth"):
        return _load_torch_bin(ckpt)
    raise ValueError(f"Formato de checkpoint no reconocido: {ckpt}")


def _load_torch_bin(path: Path) -> Dict[str, Any]:
    import torch

    state = torch.load(str(path), map_location="cpu", weights_only=True)
    return {k: v.detach().cpu().numpy().copy() for k, v in state.items()}


def validate_compatible_state_dicts(state_dicts: Sequence[Mapping[str, Any]]) -> None:
    if not state_dicts:
        raise ValueError("Se requiere al menos un checkpoint para construir un Model Soup.")
    ref_keys = set(state_dicts[0].keys())
    ref_shapes = {k: _tensor_meta(v)[1] for k, v in state_dicts[0].items()}
    for idx, sd in enumerate(state_dicts[1:], start=1):
        keys = set(sd.keys())
        if keys != ref_keys:
            missing = sorted(ref_keys - keys)[:5]
            extra = sorted(keys - ref_keys)[:5]
            raise ValueError(
                f"Claves incompatibles en el checkpoint #{idx}: faltan={missing}, sobran={extra}"
            )
        for k in ref_keys:
            cur_shape = _tensor_meta(sd[k])[1]
            if cur_shape != ref_shapes[k]:
                raise ValueError(
                    f"Forma incompatible para '{k}' en checkpoint #{idx}: {cur_shape} != {ref_shapes[k]}"
                )


def uniform_soup(state_dicts: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """
    Promedio aritmetico uniforme en precision float64 de todos los parametros en coma flotante.
    Los buffers enteros (p. ej. `position_ids`) se conservan intactos del primer checkpoint.
    """
    validate_compatible_state_dicts(state_dicts)
    if len(state_dicts) == 1:
        return {k: _clone_tensor(v) for k, v in state_dicts[0].items()}

    count = float(len(state_dicts))
    merged: Dict[str, Any] = {}
    for key, first in state_dicts[0].items():
        code, shape, is_flt = _tensor_meta(first)
        if not is_flt:
            merged[key] = _clone_tensor(first)
            continue
        if _np is not None and isinstance(first, _np.ndarray):
            acc = _np.zeros(first.shape, dtype=_np.float64)
            for sd in state_dicts:
                acc += sd[key].astype(_np.float64, copy=False)
            acc /= count
            merged[key] = acc.astype(first.dtype)
        else:
            n_elems = len(first.values)
            sums = [0.0] * n_elems
            for sd in state_dicts:
                vals = sd[key].values
                for i in range(n_elems):
                    sums[i] += float(vals[i])
            if code == "F32":
                # Redondeo IEEE-754 exacto a float32
                f32 = array.array("f", [s / count for s in sums])
                merged[key] = TensorBox(dtype=code, shape=shape, values=tuple(f32))
            else:
                merged[key] = TensorBox(dtype=code, shape=shape, values=tuple(s / count for s in sums))
    return merged


def greedy_soup(
    candidates: Sequence[Tuple[str, Mapping[str, Any]]],
    eval_fn: Callable[[Dict[str, Any]], float],
) -> SoupResult:
    """
    Greedy Soup (Wortsman et al., ICML 2022, Algoritmo 1):
      1. Evalua cada checkpoint individualmente en `dev`.
      2. Ordena los candidatos de mayor a menor metrica de validacion.
      3. Inicializa la sopa con el mejor modelo individual y prueba agregar cada candidato restante,
         reteniendolo solo si la metrica del promedio de pesos iguala o supera el maximo alcanzado.
    """
    if not candidates:
        raise ValueError("Se requiere al menos un candidato para greedy_soup.")
    validate_compatible_state_dicts([weights for _, weights in candidates])

    individual_scores: Dict[str, float] = {}
    scored_candidates: List[Tuple[float, int, str, Mapping[str, Any]]] = []
    for idx, (name, weights) in enumerate(candidates):
        score = float(eval_fn({k: _clone_tensor(v) for k, v in weights.items()}))
        individual_scores[name] = score
        scored_candidates.append((score, -idx, name, weights))

    scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)

    best_score, _, first_name, first_weights = scored_candidates[0]
    selected_names = [first_name]
    selected_weights = [first_weights]
    current_soup = {k: _clone_tensor(v) for k, v in first_weights.items()}
    history: List[Dict[str, object]] = [
        {"step": 1, "candidate": first_name, "trial_score": round(best_score, 6), "kept": True}
    ]

    for step_idx, (indiv_score, _, cand_name, cand_weights) in enumerate(scored_candidates[1:], start=2):
        trial_soup = uniform_soup([*selected_weights, cand_weights])
        trial_score = float(eval_fn(trial_soup))
        kept = trial_score >= best_score
        if kept:
            selected_names.append(cand_name)
            selected_weights.append(cand_weights)
            current_soup = trial_soup
            best_score = trial_score
        history.append(
            {
                "step": step_idx,
                "candidate": cand_name,
                "individual_score": round(indiv_score, 6),
                "trial_score": round(trial_score, 6),
                "kept": kept,
            }
        )

    return SoupResult(
        mode="greedy",
        weights=current_soup,
        best_score=best_score,
        selected=selected_names,
        individual_scores=individual_scores,
        history=history,
    )


def export_soup_checkpoint(
    result: SoupResult,
    output_dir: Path,
    reference_checkpoint_dir: Optional[Path] = None,
    extra_metadata: Optional[Mapping[str, object]] = None,
) -> Path:
    """Guarda `model.safetensors`, `soup_manifest.json` y copia el tokenizador/configuracion para inferencia."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_safetensors(
        out / "model.safetensors",
        result.weights,
        metadata={
            "format": "pt",
            "soup_mode": result.mode,
            "ingredients": ",".join(result.selected),
        },
    )
    if reference_checkpoint_dir and Path(reference_checkpoint_dir).is_dir():
        ref_dir = Path(reference_checkpoint_dir)
        for fname in INFERENCE_SIDE_FILES:
            src = ref_dir / fname
            if src.exists() and src.resolve() != (out / fname).resolve():
                shutil.copy2(src, out / fname)

    manifest = {
        "mode": result.mode,
        "selected_checkpoints": result.selected,
        "num_selected": len(result.selected),
        "best_validation_score": round(result.best_score, 6) if result.best_score is not None else None,
        "individual_scores": {k: round(v, 6) for k, v in result.individual_scores.items()},
        "history": result.history,
        **(dict(extra_metadata) if extra_metadata else {}),
    }
    (out / "soup_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def build_roberta_dev_evaluator(
    reference_checkpoint: Path,
    corpus_path: Path,
    split: str = "dev",
    metric: str = "f1",
) -> Callable[[Dict[str, Any]], float]:
    """Construye `eval_fn(weights) -> micro_F1` reutilizando el pipeline oficial de `ml/ner/train_ner.py`."""
    if split != "dev":
        raise ValueError(
            "La seleccion de Model Soup solo esta permitida sobre el split 'dev'. "
            "El split 'test' permanece congelado para evaluacion final unica."
        )
    import numpy as np
    import torch

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ner_data import corpus_to_documents  # noqa: E402
    from train_ner import evaluate, load_tokenizer, new_model  # noqa: E402

    docs = corpus_to_documents(corpus_path, split="dev")
    tokenizer = load_tokenizer(str(reference_checkpoint))
    model = new_model(str(reference_checkpoint))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    def _eval(weights: Dict[str, Any]) -> float:
        state_tensors = {}
        for k, v in weights.items():
            arr = v if isinstance(v, np.ndarray) else np.array(v.values).reshape(v.shape)
            state_tensors[k] = torch.from_numpy(arr).to(device)
        model.load_state_dict(state_tensors, strict=True)
        report = evaluate(model, tokenizer, docs)
        return float(report["micro"][metric] or 0.0)

    return _eval


def main(argv: Optional[Sequence[str]] = None) -> SoupResult:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("uniform", "greedy"), default="greedy")
    parser.add_argument("--checkpoints", nargs="+", type=Path, required=True, help="Rutas a carpetas o .safetensors.")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "backend/triage/benchmark/corpus_entidades.json",
    )
    parser.add_argument("--split", default="dev", help="Solo 'dev' permitido en modo greedy.")
    parser.add_argument("--metric", choices=("f1", "precision", "recall"), default="f1")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output" / "ai_triage_ner_roberta_soup",
    )
    opts = parser.parse_args(argv)

    if opts.mode == "greedy" and opts.split != "dev":
        parser.error("Prohibido usar --split != 'dev' en modo greedy: el conjunto 'test' esta congelado.")

    loaded: List[Tuple[str, Dict[str, Any]]] = [
        (ckpt.name, load_checkpoint_weights(ckpt)) for ckpt in opts.checkpoints
    ]
    ckpt_by_name = {ckpt.name: ckpt for ckpt in opts.checkpoints}

    if opts.mode == "uniform":
        merged = uniform_soup([w for _, w in loaded])
        result = SoupResult(
            mode="uniform",
            weights=merged,
            best_score=None,
            selected=[name for name, _ in loaded],
            individual_scores={},
            history=[],
        )
        ref_dir = opts.checkpoints[0] if opts.checkpoints[0].is_dir() else opts.checkpoints[0].parent
    else:
        ref_ckpt = opts.checkpoints[0]
        eval_fn = build_roberta_dev_evaluator(ref_ckpt, opts.corpus, split=opts.split, metric=opts.metric)
        result = greedy_soup(loaded, eval_fn)
        best_first = ckpt_by_name[result.selected[0]]
        ref_dir = best_first if best_first.is_dir() else best_first.parent

    export_soup_checkpoint(
        result,
        opts.output,
        reference_checkpoint_dir=ref_dir,
        extra_metadata={"split": opts.split, "metric": opts.metric},
    )
    print(
        json.dumps(
            {
                "mode": result.mode,
                "selected": result.selected,
                "best_score": result.best_score,
                "output": str(opts.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return result


if __name__ == "__main__":
    main()
