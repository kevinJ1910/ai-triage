"""
Corredor reanudable de las evaluaciones con LLM (evaluate_extraction y evaluate_benchmark).

- Checkpoint: un JSONL por corrida en benchmark/resultados/crudos/<run_id>.jsonl, con una linea por caso
  evaluado (prediccion, salida cruda del LLM, modelo exacto, tokens y latencia). Al reanudar se saltan los
  casos ya evaluados con el mismo transcript; las metricas se recalculan siempre desde el checkpoint.
- Cuota: limitador de peticiones por minuto, tope de llamadas por tanda y deteccion de la cuota diaria
  agotada (la corrida se detiene limpiamente y se reanuda con el mismo comando).
- Un caso cuyo LLM falla no se escribe: queda pendiente. Nunca se mezcla una respuesta del motor de reglas
  con las del modelo evaluado.

No se usa ClinicalQueryCache: su huella canonica agrupa cuadros equivalentes (dos casos distintos podrian
recibir la misma respuesta) y no distingue modelo ni version del prompt.
"""
import hashlib
import json
import logging
import os
import platform
import re
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / 'benchmark' / 'resultados'
RAW_DIR = RESULTS_DIR / 'crudos'

# USD por millon de tokens, plan de pago estandar (no Batch). La salida incluye los tokens de razonamiento.
PRICES_CHECKED_AT = '2026-10-18'
PRICES_SOURCE = 'https://ai.google.dev/gemini-api/docs/pricing'
PRICES = {
    'gemini-2.5-flash': {'input': 0.30, 'output': 2.50},
    'gemini-3.5-flash-lite': {'input': 0.30, 'output': 2.50},
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '-', value).strip('-')


def is_local_model(model: Optional[str]) -> bool:
    return bool(model) and (model == 'local' or model.startswith('local:'))


def privacy_label(engine: str, model: Optional[str]) -> str:
    """Si el texto clinico sale del servidor."""
    if not model or is_local_model(model):
        return 'local (los datos no salen del servidor)'
    return 'nube (texto seudonimizado)'


@dataclass(frozen=True)
class RunSpec:
    engine: str
    split: str
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    rule_hint: bool = True
    rag: bool = True
    tag: str = ''

    @property
    def run_id(self) -> str:
        parts = [self.split, self.engine]
        if self.model:
            parts.append(_slug(self.model))
        if self.prompt_version:
            parts.append(f'p{self.prompt_version}')
        if not self.rule_hint:
            parts.append('sin-pauta')
        if not self.rag:
            parts.append('sin-rag')
        if self.tag:
            parts.append(_slug(self.tag))
        return '_'.join(parts)


class Checkpoint:
    """JSONL de una corrida. Cada append se escribe y se sincroniza a disco: una interrupcion no pierde casos."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.records: Dict[str, Dict[str, Any]] = {}
        if self.path.exists():
            for number, line in enumerate(self.path.read_text(encoding='utf-8').splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    # Linea truncada por una interrupcion durante la escritura: el caso se repite.
                    logger.warning(f"{self.path.name}: linea {number} invalida, se ignora")
                    continue
                self.records[str(record['id'])] = record

    def is_done(self, case_id: str, transcript_sha256: str) -> bool:
        record = self.records.get(str(case_id))
        return bool(record) and record.get('transcript_sha256') == transcript_sha256

    def get(self, case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        sha = sha256_text(case['transcript'])
        return self.records[str(case['id'])] if self.is_done(case['id'], sha) else None

    def append(self, record: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + '\n')
            fh.flush()
            os.fsync(fh.fileno())
        self.records[str(record['id'])] = record

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()
        self.records = {}


class QuotaExhausted(RuntimeError):
    """La cuota diaria del proveedor se agoto: hay que reanudar en otro momento."""


_DAILY_MARKERS = ('perday', 'per_day', 'per day', 'daily')


def classify_llm_error(err: BaseException) -> str:
    """'daily_quota', 'rate_limit', 'transient' u 'other', a partir del texto del error del proveedor."""
    text = str(err).lower()
    is_429 = '429' in text or 'resource_exhausted' in text or 'quota' in text or 'rate limit' in text
    if is_429 and any(marker in text for marker in _DAILY_MARKERS):
        return 'daily_quota'
    if is_429:
        return 'rate_limit'
    if any(marker in text for marker in ('503', '500', 'unavailable', 'overloaded', 'timeout', 'timed out',
                                         'deadline', 'connection')):
        return 'transient'
    return 'other'


def retry_delay_seconds(err: BaseException, default: float) -> float:
    """Usa el retryDelay que sugiere el proveedor (p. ej. 'retryDelay': '37s') si es mayor que el valor por defecto."""
    match = re.search(r"retry[_ ]?delay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", str(err), re.I)
    if match:
        return max(default, float(match.group(1)) + 1.0)
    return default


class RateLimiter:
    """Separa las llamadas al menos 60/rpm segundos (mas un margen); rpm=0 desactiva el limite."""

    def __init__(self, rpm: float = 0.0, min_interval: float = 0.0, margin: float = 0.1,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        by_rpm = (60.0 / rpm) * (1 + margin) if rpm else 0.0
        self.interval = max(by_rpm, min_interval)
        self._clock = clock
        self._sleep = sleep
        self._last: Optional[float] = None

    def wait(self) -> None:
        if self.interval and self._last is not None:
            remaining = self.interval - (self._clock() - self._last)
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()


@dataclass
class RunOutcome:
    evaluated: int = 0
    skipped: int = 0
    calls: int = 0
    pending: List[str] = field(default_factory=list)
    stopped: Optional[str] = None  # None, 'daily_quota', 'rate_limit' o 'max_calls'


def run_pending(cases: Iterable[Dict[str, Any]], checkpoint: Checkpoint,
                evaluate: Callable[[Dict[str, Any]], Dict[str, Any]], limiter: Optional[RateLimiter] = None,
                max_calls: Optional[int] = None, retries: int = 2, retry_wait: float = 60.0,
                sleep: Callable[[float], None] = time.sleep,
                log: Callable[[str], None] = lambda message: None) -> RunOutcome:
    """
    Evalua los casos que faltan en el checkpoint. evaluate(case) devuelve el registro del caso o lanza la
    excepcion del LLM. Los errores de cuota por minuto y los transitorios se reintentan; si tras los reintentos
    sigue el 429, o el proveedor dice que la cuota diaria se agoto, la corrida se detiene.
    """
    limiter = limiter or RateLimiter()
    outcome = RunOutcome()
    cases = list(cases)
    for index, case in enumerate(cases, start=1):
        case_id = str(case['id'])
        sha = sha256_text(case['transcript'])
        if checkpoint.is_done(case_id, sha):
            outcome.skipped += 1
            continue
        if outcome.stopped:
            outcome.pending.append(case_id)
            continue
        attempts = 0
        while True:
            if max_calls is not None and outcome.calls >= max_calls:
                outcome.stopped = 'max_calls'
                outcome.pending.append(case_id)
                break
            limiter.wait()
            outcome.calls += 1
            attempts += 1
            try:
                record = evaluate(case)
            except Exception as err:
                kind = classify_llm_error(err)
                if kind == 'daily_quota':
                    log(f"[{index}/{len(cases)}] {case_id}: cuota diaria agotada ({err})")
                    outcome.stopped = 'daily_quota'
                    outcome.pending.append(case_id)
                    break
                if attempts <= retries:
                    delay = retry_delay_seconds(err, retry_wait)
                    log(f"[{index}/{len(cases)}] {case_id}: {kind} ({err}); reintento en {delay:.0f} s")
                    sleep(delay)
                    continue
                if kind == 'rate_limit':
                    # El 429 persiste tras los reintentos: en la practica es la cuota diaria.
                    log(f"[{index}/{len(cases)}] {case_id}: 429 persistente, se detiene la corrida")
                    outcome.stopped = 'rate_limit'
                else:
                    log(f"[{index}/{len(cases)}] {case_id}: fallo del LLM ({err}); queda pendiente")
                outcome.pending.append(case_id)
                break
            record = {
                'id': case_id, 'transcript_sha256': sha, **record, 'attempts': attempts,
                'timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            }
            checkpoint.append(record)
            outcome.evaluated += 1
            log(f"[{index}/{len(cases)}] {case_id} -> nivel {record.get('predicted_level')} "
                f"({record.get('latency_ms')} ms)")
            break
    return outcome


def _model_prices(model: Optional[str]) -> Optional[Dict[str, float]]:
    if not model:
        return None
    name = model.split('/')[-1]
    for key, prices in PRICES.items():
        if name == key or name.startswith(key + '-'):
            return prices
    return None


def estimate_cost(model: Optional[str], prompt_tokens: int, completion_tokens: int, thoughts_tokens: int = 0
                  ) -> Optional[float]:
    """Costo en USD con la tabla PRICES. 0 para reglas y LLM local (sin costo por token); None si no hay precio."""
    if not model or is_local_model(model):
        return 0.0
    prices = _model_prices(model)
    if prices is None:
        return None
    return (prompt_tokens * prices['input'] + (completion_tokens + thoughts_tokens) * prices['output']) / 1_000_000


def _percentile(values: List[float], fraction: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))]


def performance_summary(records: List[Dict[str, Any]], model: Optional[str]) -> Dict[str, Any]:
    latencies = [r.get('latency_ms') or 0 for r in records]
    tokens = {key: [int(r.get(key) or 0) for r in records]
              for key in ('prompt_tokens', 'completion_tokens', 'thoughts_tokens', 'total_tokens')}
    cost = estimate_cost(model, sum(tokens['prompt_tokens']), sum(tokens['completion_tokens']),
                         sum(tokens['thoughts_tokens']))
    return {
        'latency_ms_mean': round(statistics.mean(latencies)) if latencies else None,
        'latency_ms_p50': _percentile(latencies, 0.5),
        'latency_ms_p95': _percentile(latencies, 0.95),
        **{f'{key}_mean': round(statistics.mean(values), 1) if values else None for key, values in tokens.items()},
        'tokens_mean': round(statistics.mean(tokens['total_tokens']), 1) if records else None,
        'tokens_total': sum(tokens['total_tokens']),
        'cost_usd': round(cost, 4) if cost is not None else None,
        'cost_usd_per_1000': round(cost / len(records) * 1000, 2) if cost is not None and records else None,
        'llm_failures': 0,
        'retried_cases': sum((r.get('attempts') or 1) > 1 for r in records),
        # Casos con un campo de formato corregido antes de validar (p. ej. confianza en porcentaje).
        'coerced_cases': sum(bool(r.get('output_coerced')) for r in records),
    }


def _git_commit() -> Optional[str]:
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=5,
                              cwd=Path(__file__).resolve().parent).stdout.strip() or None
    except Exception:
        return None


def run_metadata(spec: RunSpec, records: List[Dict[str, Any]], *, corpus: Path, tier: Optional[str],
                 hardware: Optional[str], policy: Optional[str] = None,
                 prompt_sha256: Optional[str] = None, temperature: Optional[float] = None) -> Dict[str, Any]:
    """Metadatos de reproducibilidad de la corrida. No incluye rutas del equipo."""
    return {
        'run_id': spec.run_id,
        'engine': spec.engine,
        'model': spec.model,
        'model_versions': sorted({r['model_version'] for r in records if r.get('model_version')}),
        'prompt_version': spec.prompt_version,
        'prompt_sha256': prompt_sha256,
        'rule_hint': spec.rule_hint,
        'rag': spec.rag,
        'policy': policy,
        'temperature': temperature,
        # No se fija thinking_config: cada modelo usa su configuracion por defecto, que se registra asi.
        # Gemini 2.5 Flash y Gemma 4 razonan por defecto; Qwen2.5 no tiene modo de razonamiento.
        'thinking': 'por defecto del modelo' if spec.model else None,
        'tier': tier,
        'privacy': privacy_label(spec.engine, spec.model),
        'corpus': Path(corpus).name,
        'corpus_sha256': file_sha256(corpus) if Path(corpus).exists() else None,
        'git_commit': _git_commit(),
        'platform': platform.platform(),
        'processor': platform.processor() or platform.machine(),
        'python': platform.python_version(),
        'hardware': hardware,
        'prices': {'checked_at': PRICES_CHECKED_AT, 'source': PRICES_SOURCE,
                   'usd_per_million': _model_prices(spec.model)} if _model_prices(spec.model) else None,
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
