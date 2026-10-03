import re
import copy
import time
import hashlib
import threading
from typing import Dict, Any, Optional
from .clinical_protocol import _normalize_text

# Palabras cortas que invierten o modifican el sentido clinico y nunca se descartan.
_SEMANTIC_SHORT_WORDS = {"no", "sin", "ni", "nunca", "nada", "niega", "poco", "muy", "mas", "ya"}

# Campos que identifican al paciente: jamas se guardan en cache ni se comparten entre casos.
_PATIENT_SCOPED_KEYS = ("patientInfo",)


class ClinicalQueryCache:
    """
    Cache semantico y canonico de consultas de triaje clinico.
    Evita invocar el LLM para cuadros clinicos identicos o equivalentes,
    reduciendo a 0 el consumo de tokens y respondiendo en < 3 ms.

    Solo almacena la parte clinica del resultado (triaje, entidades, confianza);
    los datos del paciente deben extraerse de nuevo en cada consulta.
    """
    _lock = threading.Lock()
    _store: Dict[str, Dict[str, Any]] = {}
    _hits: int = 0
    _misses: int = 0
    _tokens_saved: int = 0

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
        now = time.time()
        with cls._lock:
            entry = cls._store.get(fingerprint)
            if entry:
                if now < entry["expires_at"]:
                    cls._hits += 1
                    saved = entry.get("estimated_tokens", 850)
                    cls._tokens_saved += saved
                    # Copia profunda: quien llama puede mutar el resultado sin alterar la cache
                    result = copy.deepcopy(entry["data"])
                    result["cached"] = True
                    result["engine_used"] = "Cache Semántico de Consultas"
                    result["tokens_used"] = 0
                    return result
                else:
                    del cls._store[fingerprint]

            cls._misses += 1
            return None

    @classmethod
    def set(cls, fingerprint: str, result: Dict[str, Any], ttl_seconds: int = 86400, estimated_tokens: int = 850) -> None:
        """Almacena el resultado validado en cache con tiempo de vida (TTL)."""
        now = time.time()
        with cls._lock:
            # Limpieza preventiva si el cache excede 5000 entradas
            if len(cls._store) > 5000:
                cls._prune_expired(now)

            clinical_only = {k: copy.deepcopy(v) for k, v in result.items() if k not in _PATIENT_SCOPED_KEYS}
            cls._store[fingerprint] = {
                "data": clinical_only,
                "expires_at": now + ttl_seconds,
                "estimated_tokens": estimated_tokens
            }

    @classmethod
    def _prune_expired(cls, now: float) -> None:
        """Elimina entradas expiradas para prevenir fugas de memoria."""
        expired_keys = [k for k, v in cls._store.items() if now >= v["expires_at"]]
        for k in expired_keys:
            del cls._store[k]

    @classmethod
    def clear(cls) -> None:
        """Limpia todo el almacenamiento del cache y reinicia metricas."""
        with cls._lock:
            cls._store.clear()
            cls._hits = 0
            cls._misses = 0
            cls._tokens_saved = 0

    @classmethod
    def stats(cls) -> Dict[str, Any]:
        """Retorna telemetria de uso del cache semantico."""
        with cls._lock:
            total_requests = cls._hits + cls._misses
            hit_rate = round((cls._hits / total_requests) * 100, 1) if total_requests > 0 else 0.0
            return {
                "hits": cls._hits,
                "misses": cls._misses,
                "total_requests": total_requests,
                "hit_rate_pct": hit_rate,
                "cached_items_count": len(cls._store),
                "estimated_tokens_saved": cls._tokens_saved
            }
