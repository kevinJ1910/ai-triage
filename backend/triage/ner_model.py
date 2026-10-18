"""
Motor NER (RoBERTa biomedico-clinico ajustado en ml/ner/) para el analisis de triaje.

Se activa solo donde NER_MODEL_PATH esta definido (en Docker, el worker LLM): una carpeta con el modelo
exportado por el notebook o el id de un repositorio de Hugging Face Hub (privado: HF_TOKEN). Corre en CPU,
asi que no depende de la GPU ni del override de docker-compose.gpu.yml. Si falta torch, la ruta o el modelo
no carga, get_engine() devuelve None y el analisis sigue con el catalogo y el motor de reglas.
"""
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

NER_STATUS_KEY = "ner:engine_status"
MAX_LENGTH = 512
STRIDE = 128


def decode_spans(offsets: Sequence[Tuple[int, int]], label_ids: Sequence[int], scores: Sequence[float],
                 id2label: Dict[int, str]) -> List[Dict[str, Any]]:
    """
    Spans de caracter desde etiquetas BIO por token. La confianza del span es la media de la probabilidad
    del token predicho. Un I- sin B- previo abre entidad, como en ml/ner/ner_data.spans_from_bio.
    """
    spans: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    def close():
        if current:
            current["score"] = round(sum(current.pop("_scores")) / current.pop("_n"), 4)
            spans.append(current)

    for (start, end), label_id, score in zip(offsets, label_ids, scores):
        if start == end:
            continue
        label = id2label[int(label_id)]
        if label == "O":
            close()
            current = None
            continue
        prefix, etype = label.split("-", 1)
        if current and prefix == "I" and current["label"] == etype:
            current["end"] = end
            current["_scores"].append(score)
            current["_n"] += 1
        else:
            close()
            current = {"start": start, "end": end, "label": etype, "_scores": [score], "_n": 1}
    close()
    return spans


# Igual que ml/ner/ner_data.FUNCTION_WORDS: nunca son una mencion por si solas.
FUNCTION_WORDS = frozenset({
    'a', 'al', 'como', 'con', 'de', 'del', 'el', 'en', 'es', 'esta', 'está', 'la', 'las', 'le', 'les', 'lo', 'los',
    'me', 'mi', 'muy', 'ni', 'no', 'o', 'para', 'pero', 'por', 'que', 'se', 'si', 'su', 'te', 'un', 'una', 'unas',
    'unos', 'y', 'ya',
})


def drop_function_word_spans(text: str, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Quita los spans formados solo por palabras funcionales («una», «al»), como en ml/ner."""
    return [s for s in spans
            if not all(w in FUNCTION_WORDS for w in re.findall(r"\w+", text[s["start"]:s["end"]].lower()))]


def snap_to_words(text: str, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extiende los spans hasta palabras completas, como ml/ner/ner_data.snap_to_words: el modelo etiqueta
    subtokens y a veces corta una palabra («itando» por «vomitando»). Si dos spans se pisan, se unen si
    tienen la misma etiqueta (con la confianza media) y, si no, gana el mas largo.
    """
    snapped: List[Dict[str, Any]] = []
    for span in sorted(spans, key=lambda s: (s["start"], s["end"])):
        start, end = span["start"], span["end"]
        while start > 0 and text[start - 1].isalnum() and text[start].isalnum():
            start -= 1
        while end < len(text) and text[end].isalnum() and text[end - 1].isalnum():
            end += 1
        current = {**span, "start": start, "end": end}
        if snapped and start < snapped[-1]["end"]:
            previous = snapped[-1]
            if previous["label"] == span["label"]:
                previous["end"] = max(previous["end"], end)
                previous["score"] = round((previous["score"] + span["score"]) / 2, 4)
            elif end - start > previous["end"] - previous["start"]:
                snapped[-1] = {**current, "start": min(start, previous["start"])}
            continue
        snapped.append(current)
    return snapped


# Archivos del modelo que se descargan del Hub (no la carpeta analisis/ ni training_args.bin, que no hacen falta).
HUB_MODEL_FILES = [
    "config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
    "vocab.json", "merges.txt", "ner_labels.json", "training_config.json", "metrics.json",
]


def _looks_local(source: str) -> bool:
    return source.startswith((".", "/", "~")) or os.sep in source or ":" in source[:3]


def _resolve_model_folder(source: str, token: Optional[str], revision: Optional[str]) -> str:
    """
    Carpeta local del modelo. Un id del Hub (usuario/repo) se descarga primero a la cache de Hugging Face
    (volumen ner_model_cache en Docker; solo la primera vez o al cambiar de version): asi el respaldo del
    tokenizador, que lee vocab.json y merges.txt del disco, funciona igual que con una carpeta local.
    """
    if _looks_local(source):
        folder = os.path.expanduser(source)
        if not os.path.isdir(folder):
            # Ruta local ausente (p. ej. el modelo aun no se ha copiado): falla sin intentar el Hub.
            raise FileNotFoundError(f"no existe la carpeta del modelo {source}")
        return folder
    from huggingface_hub import snapshot_download
    return snapshot_download(repo_id=source, revision=revision, token=token, allow_patterns=HUB_MODEL_FILES)


def _load_tokenizer(source: str, token: Optional[str]):
    """
    Tokenizador del modelo. Si el tokenizer.json lo escribio una version de tokenizers mas nueva que la del
    backend (transformers 5 en Colab), se reconstruye el mismo BPE desde vocab.json y merges.txt.
    """
    from transformers import AutoTokenizer, RobertaTokenizerFast
    try:
        return AutoTokenizer.from_pretrained(source, use_fast=True, token=token)
    except Exception as err:
        folder = os.path.expanduser(source)
        vocab, merges = os.path.join(folder, "vocab.json"), os.path.join(folder, "merges.txt")
        if not (os.path.isfile(vocab) and os.path.isfile(merges)):
            raise
        logger.info(f"tokenizer.json no compatible ({err}); se reconstruye desde vocab.json y merges.txt")
        # Las opciones del entrenamiento (p. ej. add_prefix_space) cambian los ids: se leen de tokenizer_config.json.
        config_path = os.path.join(folder, "tokenizer_config.json")
        config = json.load(open(config_path, encoding="utf-8")) if os.path.isfile(config_path) else {}
        options = {k: config[k] for k in ("add_prefix_space", "trim_offsets", "model_max_length") if k in config}
        return RobertaTokenizerFast(vocab_file=vocab, merges_file=merges, **options)


class NEREngine:
    """Singleton thread-safe: el worker LLM usa un pool de hilos y el modelo se carga una sola vez."""
    _instance: Optional["NEREngine"] = None
    _lock = threading.Lock()
    _failed_source: Optional[str] = None

    def __init__(self, source: str):
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer


        start = time.perf_counter()
        token = os.getenv("HF_TOKEN") or None
        # Version fija del repositorio del Hub (commit o etiqueta), para que todos usen el mismo modelo.
        revision = getattr(settings, "NER_MODEL_REVISION", "") or None
        folder = _resolve_model_folder(source, token, revision)
        torch.set_num_threads(getattr(settings, "NER_CPU_THREADS", 2))
        self.source = source
        self.revision = revision
        self.tokenizer = _load_tokenizer(folder, token)
        self.model = AutoModelForTokenClassification.from_pretrained(folder)
        self.model.eval()
        self.id2label = {int(k): v for k, v in self.model.config.id2label.items()}
        self._torch = torch
        self._infer_lock = threading.Lock()
        self.load_seconds = round(time.perf_counter() - start, 2)
        logger.info(f"Modelo NER cargado desde '{source}' en {self.load_seconds}s")

    @classmethod
    def get(cls) -> Optional["NEREngine"]:
        source = getattr(settings, "NER_MODEL_PATH", "") or ""
        if not source:
            return None
        if cls._instance is not None and cls._instance.source == source:
            return cls._instance
        if cls._failed_source == source:
            return None
        with cls._lock:
            if cls._instance is None or cls._instance.source != source:
                try:
                    cls._instance = cls(source)
                    cls._failed_source = None
                except Exception as err:
                    # No se reintenta en cada consulta: un modelo ausente no debe anadir latencia al triaje.
                    logger.warning(f"NER no disponible ({source}): {err}. Se usa el catalogo y las reglas.")
                    cls._failed_source = source
                    cls._instance = None
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None
            cls._failed_source = None

    def extract(self, text: str) -> List[Dict[str, Any]]:
        """Entidades del texto: [{'start', 'end', 'label', 'score', 'text'}], en orden de aparicion."""
        if not text.strip():
            return []
        torch = self._torch
        encoded = self.tokenizer(text, truncation=True, max_length=MAX_LENGTH, stride=STRIDE,
                                 return_overflowing_tokens=True, return_offsets_mapping=True, padding=True,
                                 return_tensors="pt")
        offsets = encoded.pop("offset_mapping").tolist()
        encoded.pop("overflow_to_sample_mapping", None)
        with self._infer_lock, torch.no_grad():
            probabilities = torch.softmax(self.model(**encoded).logits, dim=-1)
        # En los solapes entre ventanas manda el token mas alejado del borde de su ventana.
        best: Dict[Tuple[int, int], Tuple[int, int, float]] = {}
        for window, window_offsets in enumerate(offsets):
            scores, label_ids = probabilities[window].max(dim=-1)
            real = [i for i, (s, e) in enumerate(window_offsets) if s != e]
            for rank, i in enumerate(real):
                margin = min(rank, len(real) - 1 - rank)
                key = tuple(window_offsets[i])
                if key not in best or margin > best[key][0]:
                    best[key] = (margin, int(label_ids[i]), float(scores[i]))
        ordered = sorted(best.items())
        spans = decode_spans([k for k, _ in ordered], [v[1] for _, v in ordered], [v[2] for _, v in ordered],
                             self.id2label)
        spans = drop_function_word_spans(text, snap_to_words(text, spans))
        for span in spans:
            span["text"] = text[span["start"]:span["end"]]
        return spans

    def get_status(self) -> Dict[str, Any]:
        return {"model_loaded": True, "source": self.source, "device": "cpu", "load_seconds": self.load_seconds,
                "labels": sorted({label.split("-", 1)[-1] for label in self.id2label.values() if label != "O"})}


def get_engine() -> Optional[NEREngine]:
    return NEREngine.get()


def engine_label() -> Optional[str]:
    """Identificador corto del modelo activo, para la huella de la cache y la salida (ner_engine)."""
    engine = get_engine()
    if not engine:
        return None
    # La version forma parte de la etiqueta: al cambiar de modelo no se sirven triajes cacheados con el anterior.
    revision = f"@{engine.revision}" if getattr(engine, "revision", None) else ""
    return f"roberta:{os.path.basename(str(engine.source).rstrip('/'))}{revision}"


def get_ner_status() -> Dict[str, Any]:
    """Estado publicado por el worker LLM (health check) o, en modo en linea, el del proceso actual."""
    published = cache.get(NER_STATUS_KEY)
    if published:
        return published
    if not getattr(settings, "NER_MODEL_PATH", ""):
        return {"model_loaded": False, "detail": "NER_MODEL_PATH no definido: se usan el catalogo y las reglas"}
    if NEREngine._instance is not None:
        return NEREngine._instance.get_status()
    return {"model_loaded": False, "detail": "modelo aun no cargado o no disponible"}


def publish_status() -> Dict[str, Any]:
    engine = get_engine()
    status = engine.get_status() if engine else {
        "model_loaded": False, "source": getattr(settings, "NER_MODEL_PATH", ""), "detail": "no se pudo cargar"}
    cache.set(NER_STATUS_KEY, status, timeout=None)
    return status
