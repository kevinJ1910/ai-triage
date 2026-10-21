"""
Ejecucion de tareas Celery desde vistas sincronas.
La vista encola la tarea en el worker y espera su resultado con un tiempo maximo, de modo que
el contrato HTTP no cambia pero la inferencia (Whisper, Gemini) no consume CPU del proceso web.
En modo eager (sin Redis) la tarea se ejecuta en linea.
"""
import logging

from celery.exceptions import TimeoutError as CeleryTimeoutError
from kombu.exceptions import OperationalError

try:
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - redis siempre esta instalado con celery[redis]
    RedisError = OSError

logger = logging.getLogger(__name__)

# Reintentos cortos al publicar: si Redis no responde, la vista debe degradar rapido.
_PUBLISH_RETRY_POLICY = {'max_retries': 2, 'interval_start': 0, 'interval_step': 0.5, 'interval_max': 1}


class TaskUnavailable(Exception):
    """El worker no recibio la tarea o no respondio a tiempo."""


def run_task(task, *args, timeout: int, **kwargs):
    """
    Encola `task` y devuelve su resultado. Las excepciones lanzadas por la propia tarea se propagan;
    un broker caido o un worker que no responde en `timeout` segundos lanza TaskUnavailable.
    """
    try:
        # expires: si la cola esta atascada, el worker descarta la tarea en vez de procesarla tarde.
        async_result = task.apply_async(
            args=args, kwargs=kwargs, expires=timeout, retry=True, retry_policy=_PUBLISH_RETRY_POLICY
        )
    except (OperationalError, RedisError, ConnectionError, OSError) as exc:
        logger.error(f"No se pudo encolar {task.name}: {exc}")
        raise TaskUnavailable('broker no disponible') from exc

    try:
        return async_result.get(timeout=timeout)
    except CeleryTimeoutError as exc:
        logger.error(f"{task.name} no respondio en {timeout}s")
        raise TaskUnavailable('worker sin respuesta') from exc
    except (OperationalError, RedisError, ConnectionError) as exc:
        logger.error(f"Se perdio la conexion esperando {task.name}: {exc}")
        raise TaskUnavailable('backend de resultados no disponible') from exc
