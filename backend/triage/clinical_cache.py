import time
import hashlib
import threading
from typing import Dict, Any, Optional
from .clinical_protocol import _normalize_text


class ClinicalQueryCache:
    """
    Cache semantico y canonico de consultas de triaje clinico.
    Evita invocar el LLM para cuadros clinicos identicos o equivalentes,
    reduciendo a 0 el consumo de tokens y respondiendo en < 3 ms.
    """
    _lock = threading.Lock()
    _store: Dict[str, Dict[str, Any]] = {}
    _hits: int = 0
    _misses: int = 0
    _tokens_saved: int = 0

    @classmethod
    def generate_fingerprint(cls, cleaned_transcript: str, structured_vitals: Optional[Dict[str, Any]] = None) -> str:
        """
        Genera una firma hash criptografica representativa del cuadro clinico.
        Normaliza palabras clave, elimina ruido menor y agrupa rangos de constantes vitales.
        """
        norm_text = _normalize_text(cleaned_transcript)
        # Extraer palabras significativas ordenadas
        words = sorted(list(set(re_word for re_word in norm_text.split() if len(re_word) > 3)))

        vitals_repr = ""
        if structured_vitals:
            # Agrupar valores en categorias para preservar generalizacion
            bp_sys = structured_vitals.get("bp_sys", 120)
            bp_cat = "crit_high" if bp_sys >= 180 else "high" if bp_sys >= 140 else "norm"
            sat = structured_vitals.get("spo2", 98)
            sat_cat = "hypox_crit" if sat < 90 else "hypox_mod" if sat < 93 else "norm"
            vitals_repr = f"|bp:{bp_cat}|sat:{sat_cat}"

        canonical_str = " ".join(words) + vitals_repr
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
                    # Devolver copia del payload anotado como cache
                    result = dict(entry["data"])
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

            cls._store[fingerprint] = {
                "data": result,
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
