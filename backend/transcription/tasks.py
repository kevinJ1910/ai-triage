"""
Tareas Celery de transcripcion y normalizacion.
transcribe_audio_chunk va a la cola 'asr' (worker con el modelo Whisper cargado una sola vez);
normalize_clinical_text_task va a la cola 'llm' (ver CELERY_TASK_ROUTES).
"""
import base64
import logging
import os

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


@shared_task
def transcribe_audio_chunk(audio_b64: str, session_id: str) -> dict:
    return WhisperEngine().transcribe_chunk(base64.b64decode(audio_b64), session_id)


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
    cache.set(ASR_STATUS_KEY, {**previous, "loading": True, "model_size": WhisperEngine.configured_model_size()},
              timeout=None)
    status = WhisperEngine().reload()
    cache.set(ASR_STATUS_KEY, status, timeout=None)
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
    status = WhisperEngine().get_status()
    cache.set(ASR_STATUS_KEY, status, timeout=None)
    logger.info(f"Worker ASR listo: {status}")


@worker_shutdown.connect
def _clear_whisper_status(**_kwargs):
    if os.getenv('WHISPER_PRELOAD', 'False') == 'True':
        cache.delete(ASR_STATUS_KEY)
