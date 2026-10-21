import re
import time
import copy
import hashlib
from typing import Dict, Any, Optional, Tuple

from django.core.cache import cache

from .clinical_protocol import _normalize_text
from transcription.terminology import find_concepts, fold

# Palabras cortas que invierten o modifican el sentido clinico y nunca se descartan.
_SEMANTIC_SHORT_WORDS = {"no", "sin", "ni", "nunca", "nada", "niega", "poco", "muy", "mas", "ya", "bajo", "alto"}

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
_MAX_ENTRIES = 10000

# Cache L1 en memoria de proceso (ultrarrapido < 0.1ms)
_L1_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}
_L1_MAX_SIZE = 1000


def _incr(name: str, amount: int = 1) -> None:
    key = _COUNTER_KEYS[name]
    cache.add(key, 0, timeout=None)
    try:
        cache.incr(key, amount)
    except ValueError:
        cache.set(key, amount, timeout=None)


# Subir al cambiar las claves del resultado (v2: diagnoses, allergies y negated_findings; v3: normalized_terms;
# v4: ner_engine y ner_spans).
RESULT_SCHEMA_VERSION = 4

class ClinicalQueryCache:
    """
    Cache semantico y canonico de consultas de triaje clinico.
    Evita invocar el LLM para cuadros clinicos identicos o semanticamente equivalentes,
    reduciendo a 0 el consumo de tokens y respondiendo en tiempo sub-milisegundo.

    Arquitectura L1/L2:
    - Nivel 1 (L1): Diccionario LRU en memoria local (< 0.1 ms).
    - Nivel 2 (L2): Cache distribuida en Redis compartida entre gunicorn y workers celery (< 2 ms).
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
    def generate_fingerprint(cls, cleaned_transcript: str, structured_vitals: Optional[Dict[str, Any]] = None,
                             variant: str = "") -> str:
        """
        Genera una firma hash representativa del cuadro clinico.
        Aplica lematizacion canonica para agrupar expresiones semanticamente identicas
        (ej. 'dolor de cabeza' y 'cefalea' producen el mismo fingerprint),
        preservando el orden y las negaciones ('no', 'sin', 'niega').
        """
        norm_text = _normalize_text(cleaned_transcript)

        # Canonicalizacion con el catalogo terminologico: cada sinonimo se sustituye por un token
        # unico de su concepto ('dolor de cabeza' y 'cefalea' -> t_cefalea).
        for match in reversed(find_concepts(norm_text)):
            token = "t_" + re.sub(r"[^a-z0-9]+", "_", fold(match.concept.term)).strip("_")
            norm_text = f"{norm_text[:match.start]} {token} {norm_text[match.end:]}"

        tokens = re.findall(r"[a-z0-9_]+", norm_text)
        words = [w for w in tokens if len(w) > 3 or w in _SEMANTIC_SHORT_WORDS]

        v = structured_vitals or {}
        vitals_repr = "|".join([
            "bp:" + cls._bucket(v.get("bp_sys"), [(90, "low"), (140, "norm"), (180, "high")]),
            "sat:" + cls._bucket(v.get("spo2"), [(90, "crit"), (93, "mod"), (101, "norm")]),
            "hr:" + cls._bucket(v.get("heart_rate"), [(50, "low"), (100, "norm"), (130, "high")]),
            "rr:" + cls._bucket(v.get("respiratory_rate"), [(12, "low"), (21, "norm"), (30, "high")]),
            "t:" + cls._bucket(v.get("temperature"), [(36.0, "low"), (38.0, "norm"), (39.5, "high")]),
            "glu:" + cls._bucket(v.get("glucose"), [(70, "low"), (140, "norm"), (250, "high")]),
            "eva:" + cls._bucket(v.get("eva"), [(4, "mild"), (7, "mod"), (11, "sev")]),
        ])

        # La version del esquema de salida invalida las entradas guardadas con una forma anterior.
        # variant distingue configuraciones que cambian el resultado (p. ej. el modelo NER activo).
        canonical_str = f"v{RESULT_SCHEMA_VERSION}|{variant}||" + " ".join(words) + "||" + vitals_repr
        return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()

    @classmethod
    def get(cls, fingerprint: str) -> Optional[Dict[str, Any]]:
        """Recupera el resultado de clasificacion cacheado consultando L1 y L2."""
        now = time.time()

        # 1. Chequeo rapido L1 (Memoria de proceso)
        if fingerprint in _L1_CACHE:
            entry_data, exp_time = _L1_CACHE[fingerprint]
            if exp_time > now:
                _incr("hits")
                _incr("tokens_saved", entry_data.get("estimated_tokens", 850))
                res = copy.deepcopy(entry_data["data"])
                res["cached"] = True
                res["engine_used"] = "Cache Semántico de Consultas (L1 In-Memory)"
                res["tokens_used"] = 0
                return res
            else:
                _L1_CACHE.pop(fingerprint, None)

        # 2. Chequeo L2 (Redis)
        entry = cache.get(_ENTRY_KEY.format(fingerprint))
        if entry is None:
            _incr("misses")
            return None

        _incr("hits")
        _incr("tokens_saved", entry.get("estimated_tokens", 850))

        # Poblar L1
        if len(_L1_CACHE) < _L1_MAX_SIZE:
            _L1_CACHE[fingerprint] = (copy.deepcopy(entry), now + 3600)

        result = copy.deepcopy(entry["data"])
        result["cached"] = True
        result["engine_used"] = "Cache Semántico de Consultas"
        result["tokens_used"] = 0
        return result

    @classmethod
    def set(cls, fingerprint: str, result: Dict[str, Any], ttl_seconds: int = 86400, estimated_tokens: int = 850) -> None:
        """Almacena el resultado validado en cache L1 y L2 con tiempo de vida (TTL)."""
        now = time.time()
        clinical_only = copy.deepcopy({k: v for k, v in result.items() if k not in _PATIENT_SCOPED_KEYS})
        entry = {"data": clinical_only, "estimated_tokens": estimated_tokens}

        # Guardar en L1
        if len(_L1_CACHE) >= _L1_MAX_SIZE:
            _L1_CACHE.pop(next(iter(_L1_CACHE)))
        _L1_CACHE[fingerprint] = (entry, now + ttl_seconds)

        # Guardar en L2
        cache.set(
            _ENTRY_KEY.format(fingerprint),
            entry,
            timeout=ttl_seconds,
        )

        # Gestion del indice para telemetria
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
        _L1_CACHE.clear()
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
