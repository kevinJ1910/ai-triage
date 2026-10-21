"""
Tareas Celery de triaje (cola 'llm'): la llamada a Gemini se hace en el worker, no en el proceso web.
"""
import logging
import os

from celery import shared_task
from celery.signals import worker_ready, worker_shutdown
from django.conf import settings
from django.core.cache import cache

from core.task_runner import TaskUnavailable, run_task
from .ai_analyzer import analyze_triage_transcript


@shared_task
def analyze_transcript(transcript: str, use_cache: bool = True) -> dict:
    return analyze_triage_transcript(transcript, use_cache=use_cache)


def analyze_with_worker(transcript: str) -> dict:
    """
    Analiza en el worker y espera el resultado. Si el worker no responde, aplica el motor de reglas
    en linea: el analisis nunca devuelve error al clinico por un fallo de la infraestructura de IA.
    """
    try:
        return run_task(analyze_transcript, transcript, timeout=settings.LLM_TASK_TIMEOUT)
    except TaskUnavailable:
        return analyze_triage_transcript(transcript, allow_llm=False)


logger = logging.getLogger(__name__)


@worker_ready.connect
def _preload_ner(**_kwargs):
    # Solo el worker LLM (NER_PRELOAD=True) carga RoBERTa al arrancar, para no anadir la carga al primer triaje.
    if os.getenv('NER_PRELOAD', 'False') != 'True':
        return
    from .ner_model import publish_status
    logger.info(f"NER del worker LLM: {publish_status()}")


@worker_shutdown.connect
def _clear_ner_status(**_kwargs):
    if os.getenv('NER_PRELOAD', 'False') == 'True':
        from .ner_model import NER_STATUS_KEY
        cache.delete(NER_STATUS_KEY)
