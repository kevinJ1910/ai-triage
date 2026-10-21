"""
Resumen de los resultados reproducibles para el panel de evaluacion.

Lee los JSON que guardan `evaluate_extraction`/`evaluate_benchmark` en `triage/benchmark/resultados/` y
`evaluate_asr` en `data/asr/` (o copiados a `resultados/`). Solo se devuelven las cifras agregadas: nunca
los casos ni las transcripciones, y nunca rutas del equipo donde se ejecuto la evaluacion.
"""
import json
import logging
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / 'benchmark' / 'resultados'


def _asr_dir() -> Path:
    return Path(settings.BASE_DIR) / 'data' / 'asr'


def _modified(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=dt_timezone.utc).isoformat()


def _summarize_extraction(name: str, data: Dict[str, Any], path: Path) -> Dict[str, Any]:
    entities = data.get('entities') or {}
    triage = data.get('triage') or {}
    micro = entities.get('micro') or {}
    return {
        "name": name,
        "updated_at": _modified(path),
        "engine": data.get('engine'),
        "model": data.get('model'),
        "ner_engine": data.get('ner_engine'),
        "split": data.get('split'),
        "match": data.get('match'),
        "cases": len(data.get('cases') or []) or triage.get('n'),
        "entities": {
            "precision": micro.get('precision'),
            "recall": micro.get('recall'),
            "f1": micro.get('f1'),
            "f1_ci95": entities.get('micro_f1_ci95'),
            "macro_f1": entities.get('macro_f1'),
            "by_type": {key: (value or {}).get('f1') for key, value in (entities.get('by_type') or {}).items()},
            "negation_accuracy": (entities.get('negation') or {}).get('negation_accuracy'),
            "cie10_accuracy": (entities.get('normalization') or {}).get('cie10_accuracy'),
        } if entities else None,
        "triage": {
            "n": triage.get('n'),
            "exact_agreement": triage.get('exact_agreement'),
            "cohen_kappa": triage.get('cohen_kappa'),
            "cohen_kappa_ci95": triage.get('cohen_kappa_ci95'),
            "critical_sensitivity": triage.get('critical_sensitivity'),
            "critical_sensitivity_ci95": triage.get('critical_sensitivity_ci95'),
            "undertriage_rate": triage.get('undertriage_rate'),
            "overtriage_rate": triage.get('overtriage_rate'),
        } if triage else None,
        "performance": data.get('performance'),
    }


def _summarize_asr(name: str, data: Dict[str, Any], path: Path) -> Dict[str, Any]:
    return {
        "name": name,
        "updated_at": _modified(path),
        "model_size": data.get('model_size'),
        "device": data.get('device'),
        "chunk_seconds": data.get('chunk_seconds'),
        "initial_prompt": data.get('initial_prompt'),
        "global": data.get('global'),
        "by_condition": data.get('por_condicion'),
    }


def _read(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as err:
        logger.warning(f"No se pudo leer el resultado {path.name}: {err}")
        return None
    return data if isinstance(data, dict) else None


def load_results(results_dir: Optional[Path] = None, asr_dir: Optional[Path] = None) -> Dict[str, List[Dict[str, Any]]]:
    extraction, asr = [], []
    paths = sorted((results_dir or RESULTS_DIR).glob('*.json'))
    asr_folder = asr_dir or _asr_dir()
    if asr_folder.is_dir():
        paths += sorted(p for p in asr_folder.glob('*.json') if p.name != 'manifest.json')
    for path in paths:
        data = _read(path)
        if data is None:
            continue
        if 'global' in data and 'model_size' in data:
            asr.append(_summarize_asr(path.stem, data, path))
        elif 'entities' in data or 'triage' in data:
            extraction.append(_summarize_extraction(path.stem, data, path))
    return {"extraction": extraction, "asr": asr}
