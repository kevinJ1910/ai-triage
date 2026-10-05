import re
import time
import hashlib
from typing import Dict, Any, Optional

from django.core.cache import cache

from .clinical_protocol import _normalize_text

# Palabras cortas que invierten o modifican el sentido clinico y nunca se descartan.
_SEMANTIC_SHORT_WORDS = {"no", "sin", "ni", "nunca", "nada", "niega", "poco", "muy", "mas", "ya"}

# Campos que identifican al paciente: jamas se guardan en cache ni se comparten entre casos.
_PATIENT_SCOPED_KEYS = ("patientInfo",)

_ENTRY_KEY = "clinical_cache:entry:{}"
# Indice {huella: expira_en} para contar entradas vigentes y poder limpiarlas sin listar claves.
_INDEX_KEY = "clinical_cache:index"
_COUNTER_KEYS = {
    "hits": "clinical_cache:hits",
    "misses": "clinical_cache:misses",
    "tokens_saved": "clinical_cache:tokens_saved",
}
_MAX_ENTRIES = 5000


def _incr(name: str, amount: int = 1) -> None:
    key = _COUNTER_KEYS[name]
    cache.add(key, 0, timeout=None)
    try:
        cache.incr(key, amount)
    except ValueError:
        # La clave expiro o fue borrada entre add e incr: se reinicia el contador.
        cache.set(key, amount, timeout=None)


class ClinicalQueryCache:
    """
    Cache semantico y canonico de consultas de triaje clinico.
    Evita invocar el LLM para cuadros clinicos identicos o equivalentes,
    reduciendo a 0 el consumo de tokens y respondiendo en pocos milisegundos.

    Vive en la cache de Django (Redis en Docker), compartida por el proceso web y los workers,
    de modo que las entradas y la telemetria son las mismas en todos los procesos.
    Solo almacena la parte clinica del resultado (triaje, entidades, confianza);
    los datos del paciente deben extraerse de nuevo en cada consulta.
    """

    @staticmethod
    def _bucket(value: Optional[float], thresholds) -> str:
        """Clasifica un signo vital en un rango; 'na' si no fue reportado."""
        if value is None:
            return "na"
        for limit, label in thresholds:
            if value < limit:
                return label
        return "top"

    @classmethod
    def generate_fingerprint(cls, cleaned_transcript: str, structured_vitals: Optional[Dict[str, Any]] = None) -> str:
        """
        Genera una firma hash representativa del cuadro clinico.
        Conserva el orden de las palabras y las negaciones ("no", "sin"), porque
        "no tiene dolor de pecho" y "tiene dolor de pecho" son cuadros distintos.
        Los signos vitales ausentes se codifican como 'na', nunca como normales.
        """
        norm_text = _normalize_text(cleaned_transcript)
        tokens = re.findall(r"[a-z0-9]+", norm_text)
        words = [w for w in tokens if len(w) > 3 or w in _SEMANTIC_SHORT_WORDS]

        v = structured_vitals or {}
        vitals_repr = "|".join([
            "bp:" + cls._bucket(v.get("bp_sys"), [(90, "low"), (140, "norm"), (180, "high")]),
            "sat:" + cls._bucket(v.get("spo2"), [(90, "crit"), (93, "mod"), (101, "norm")]),
            "hr:" + cls._bucket(v.get("heart_rate"), [(50, "low"), (100, "norm"), (130, "high")]),
            "rr:" + cls._bucket(v.get("respiratory_rate"), [(12, "low"), (21, "norm"), (30, "high")]),
            "t:" + cls._bucket(v.get("temperature"), [(36.0, "low"), (38.0, "norm"), (39.5, "high")]),
        ])

        canonical_str = " ".join(words) + "||" + vitals_repr
        return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()

    @classmethod
    def get(cls, fingerprint: str) -> Optional[Dict[str, Any]]:
        """Recupera el resultado de clasificacion cacheado si no ha expirado."""
        entry = cache.get(_ENTRY_KEY.format(fingerprint))
        if entry is None:
            _incr("misses")
            return None

        _incr("hits")
        _incr("tokens_saved", entry.get("estimated_tokens", 850))
        # La cache serializa los valores: el resultado ya es una copia independiente.
        result = entry["data"]
        result["cached"] = True
        result["engine_used"] = "Cache Semántico de Consultas"
        result["tokens_used"] = 0
        return result

    @classmethod
    def set(cls, fingerprint: str, result: Dict[str, Any], ttl_seconds: int = 86400, estimated_tokens: int = 850) -> None:
        """Almacena el resultado validado en cache con tiempo de vida (TTL)."""
        now = time.time()
        clinical_only = {k: v for k, v in result.items() if k not in _PATIENT_SCOPED_KEYS}
        cache.set(
            _ENTRY_KEY.format(fingerprint),
            {"data": clinical_only, "estimated_tokens": estimated_tokens},
            timeout=ttl_seconds,
        )

        # El indice solo alimenta la telemetria: una escritura concurrente perdida no afecta al triaje.
        index = {fp: exp for fp, exp in cls._index().items() if exp > now}
        index[fingerprint] = now + ttl_seconds
        if len(index) > _MAX_ENTRIES:
            oldest = sorted(index, key=index.get)[:len(index) - _MAX_ENTRIES]
            cache.delete_many([_ENTRY_KEY.format(fp) for fp in oldest])
            for fp in oldest:
                index.pop(fp)
        cache.set(_INDEX_KEY, index, timeout=None)

    @classmethod
    def _index(cls) -> Dict[str, float]:
        return cache.get(_INDEX_KEY) or {}

    @classmethod
    def clear(cls) -> None:
        """Limpia todo el almacenamiento del cache y reinicia metricas."""
        cache.delete_many([_ENTRY_KEY.format(fp) for fp in cls._index()] + [_INDEX_KEY, *_COUNTER_KEYS.values()])

    @classmethod
    def stats(cls) -> Dict[str, Any]:
        """Retorna telemetria de uso del cache semantico."""
        counters = cache.get_many(list(_COUNTER_KEYS.values()))
        hits = counters.get(_COUNTER_KEYS["hits"], 0)
        misses = counters.get(_COUNTER_KEYS["misses"], 0)
        total_requests = hits + misses
        now = time.time()
        return {
            "hits": hits,
            "misses": misses,
            "total_requests": total_requests,
            "hit_rate_pct": round((hits / total_requests) * 100, 1) if total_requests > 0 else 0.0,
            "cached_items_count": sum(1 for exp in cls._index().values() if exp > now),
            "estimated_tokens_saved": counters.get(_COUNTER_KEYS["tokens_saved"], 0),
        }
