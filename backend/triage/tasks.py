"""
Tareas Celery de triaje (cola 'llm'): la llamada a Gemini se hace en el worker, no en el proceso web.
"""
from celery import shared_task
from django.conf import settings

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
