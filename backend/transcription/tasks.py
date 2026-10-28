"""
Tareas Celery de transcripcion y normalizacion.
transcribe_audio_chunk va a la cola 'asr' (worker con el modelo Whisper cargado una sola vez);
normalize_clinical_text_task va a la cola 'llm' (ver CELERY_TASK_ROUTES).
"""
import base64
import logging
import os
import threading
from typing import Optional

from celery import shared_task
from celery.signals import worker_ready, worker_shutdown
from django.conf import settings
from django.core.cache import cache

from core.task_runner import run_task
from .normalizer import normalize_clinical_text
from .whisper_engine import WhisperEngine

logger = logging.getLogger(__name__)

# Estado del motor publicado por el worker ASR para que el health check web lo lea sin cargar el modelo.
ASR_STATUS_KEY = "asr:engine_status"
_heartbeat_stop = threading.Event()
_heartbeat_thread: Optional[threading.Thread] = None


def publish_asr_status(status: Optional[dict] = None, timeout: Optional[int] = None) -> dict:
    """Publica el estado actual del motor ASR en Redis con expiracion TTL."""
    payload = status if status is not None else WhisperEngine().get_status()
    ttl = timeout if timeout is not None else int(getattr(settings, "ASR_STATUS_TTL", 90))
    cache.set(ASR_STATUS_KEY, payload, timeout=ttl)
    return payload


def _heartbeat_loop(stop_event: threading.Event, interval: float) -> None:
    """Renueva periodicamente el TTL de asr:engine_status mientras el worker ASR siga vivo."""
    while not stop_event.wait(interval):
        try:
            current = cache.get(ASR_STATUS_KEY)
            if isinstance(current, dict) and current.get("loading"):
                continue
            publish_asr_status()
        except Exception as exc:
            logger.warning(f"Fallo al renovar latido del worker ASR: {exc}")


def start_asr_heartbeat() -> None:
    """Inicia el hilo demonio de latido periodico en el proceso del worker ASR."""
    global _heartbeat_thread
    if _heartbeat_thread is not None and _heartbeat_thread.is_alive():
        return
    interval = max(1.0, float(getattr(settings, "ASR_HEARTBEAT_INTERVAL", 30)))
    _heartbeat_stop.clear()
    _heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(_heartbeat_stop, interval),
        name="asr-redis-heartbeat",
        daemon=True,
    )
    _heartbeat_thread.start()


def stop_asr_heartbeat() -> None:
    """Detiene el hilo de latido periodico al apagar el worker ASR."""
    global _heartbeat_thread
    _heartbeat_stop.set()
    if _heartbeat_thread is not None and _heartbeat_thread.is_alive():
        _heartbeat_thread.join(timeout=2.0)
    _heartbeat_thread = None


@shared_task
def transcribe_audio_chunk(audio_b64: str, session_id: str) -> dict:
    result = WhisperEngine().transcribe_chunk(base64.b64decode(audio_b64), session_id)
    if worker_mode():
        publish_asr_status()
    return result


@shared_task
def reload_asr_model() -> dict:
    """
    Recarga Whisper con el modelo de Configuracion y publica el estado. La encola la vista de configuracion
    cuando cambia el motor ASR; corre en el worker ASR, que procesa las tareas de una en una.
    """
    if not worker_mode() and WhisperEngine._instance is None:
        # En linea y sin modelo cargado todavia: se cargara con la configuracion nueva al primer uso.
        return {"model_loaded": False, "detail": "modelo aun no cargado"}
    previous = cache.get(ASR_STATUS_KEY) or {}
    loading_ttl = max(int(getattr(settings, "ASR_STATUS_TTL", 90)), 300)
    publish_asr_status(
        {**previous, "loading": True, "model_size": WhisperEngine.configured_model_size()},
        timeout=loading_ttl,
    )
    status = WhisperEngine().reload()
    publish_asr_status(status)
    logger.info(f"Modelo ASR recargado: {status}")
    return status


def request_asr_reload() -> bool:
    """Encola la recarga sin esperarla (la carga o descarga del modelo puede tardar). False si no hay broker."""
    try:
        reload_asr_model.apply_async(retry=False)
        return True
    except Exception as exc:
        logger.warning(f"No se pudo encolar la recarga del modelo ASR: {exc}")
        return False


@shared_task
def normalize_clinical_text_task(raw_text: str, custom_instruction: str = "") -> dict:
    return normalize_clinical_text(raw_text, custom_instruction)


def transcribe_audio(audio_bytes: bytes, session_id: str) -> dict:
    """Transcribe en el worker ASR y espera el resultado (en linea si no hay broker)."""
    audio_b64 = base64.b64encode(audio_bytes).decode('ascii')
    return run_task(transcribe_audio_chunk, audio_b64, session_id, timeout=settings.ASR_TASK_TIMEOUT)


def worker_mode() -> bool:
    """True si la inferencia corre en workers separados; False si se ejecuta en el proceso web."""
    return not settings.CELERY_TASK_ALWAYS_EAGER


def get_asr_status(load: bool = True) -> dict:
    """
    Estado del motor ASR. En modo worker se lee lo publicado por worker-asr (nunca carga el modelo
    en el proceso web). En modo en linea, load=False evita cargar Whisper solo para consultarlo.
    """
    if not worker_mode():
        if load or WhisperEngine._instance is not None:
            return {**WhisperEngine().get_status(), **({"loading": True} if cache.get(ASR_STATUS_KEY, {}).get("loading") else {})}
        return {"model_loaded": False, "device": "unknown", "detail": "modelo aun no cargado"}
    status = cache.get(ASR_STATUS_KEY)
    return status or {"model_loaded": False, "device": "unavailable", "detail": "worker ASR sin publicar estado"}


@worker_ready.connect
def _preload_whisper(**_kwargs):
    # Solo el worker ASR (WHISPER_PRELOAD=True) carga el modelo; el worker LLM no lo necesita.
    if os.getenv('WHISPER_PRELOAD', 'False') != 'True':
        return
    status = publish_asr_status()
    start_asr_heartbeat()
    logger.info(f"Worker ASR listo: {status}")


@worker_shutdown.connect
def _clear_whisper_status(**_kwargs):
    if os.getenv('WHISPER_PRELOAD', 'False') == 'True':
        stop_asr_heartbeat()
        cache.delete(ASR_STATUS_KEY)
