"""
Aplicacion Celery: ejecuta la inferencia pesada (Whisper ASR y Gemini) fuera del proceso web.
Colas: 'asr' (un unico proceso con el modelo Whisper cargado) y 'llm' (llamadas a Gemini, I/O).
Sin Redis configurado las tareas se ejecutan en linea (CELERY_TASK_ALWAYS_EAGER).
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('ai_triage')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
