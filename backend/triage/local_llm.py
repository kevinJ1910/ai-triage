"""
Cliente del LLM local: cualquier servidor compatible con la API de OpenAI (Ollama, llama.cpp server, LM Studio).

Es el segundo motor de triaje, para comparar con Gemini y para despliegues en los que los datos no deben salir
del servidor. Usa salida estructurada (response_format json_schema) con el mismo TriageOutputSchema.

Configuracion (entorno):
    LOCAL_LLM_BASE_URL         p. ej. http://llm-local:11434 (sin /v1). Vacio = motor local no configurado.
    LOCAL_LLM_MODEL            modelo por defecto (qwen2.5:7b-instruct-q4_K_M).
    LOCAL_LLM_TIMEOUT_SECONDS  tiempo maximo por peticion; en CPU una respuesta tarda minutos.
    LOCAL_LLM_API_KEY          clave opcional; tiene prioridad la del proveedor 'custom' de la boveda.
"""
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_MODEL = 'qwen2.5:7b-instruct-q4_K_M'
STATUS_CACHE_KEY = 'local_llm:status'
STATUS_TTL_SECONDS = 30


def base_url() -> str:
    url = os.getenv('LOCAL_LLM_BASE_URL', '').strip().rstrip('/')
    return url[:-3] if url.endswith('/v1') else url


def configured() -> bool:
    return bool(base_url())


def default_model() -> str:
    return os.getenv('LOCAL_LLM_MODEL', '').strip() or DEFAULT_MODEL


def timeout_seconds() -> float:
    return float(os.getenv('LOCAL_LLM_TIMEOUT_SECONDS', '300'))


def _api_key() -> str:
    try:
        from system_settings.models import APIKeyCredential
        cred = APIKeyCredential.objects.filter(provider='custom', is_active=True).first()
        if cred:
            return cred.get_key()
    except Exception as err:
        logger.debug(f"No se pudo leer la clave del servidor local: {err}")
    return os.getenv('LOCAL_LLM_API_KEY', '').strip()


def _headers() -> Dict[str, str]:
    key = _api_key()
    return {'Authorization': f'Bearer {key}'} if key else {}


def chat_json(model: str, system_instruction: str, user_prompt: str, schema: Dict[str, Any],
              temperature: float = 0.1, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    """
    Pide una respuesta JSON que cumpla schema. Devuelve el texto y la telemetria con la misma forma que
    la llamada a Gemini. Lanza la excepcion de httpx si el servidor falla o no responde.
    """
    if not configured():
        raise RuntimeError("LOCAL_LLM_BASE_URL no esta configurada")
    payload = {
        'model': model,
        'temperature': temperature,
        'messages': [
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': user_prompt},
        ],
        'response_format': {
            'type': 'json_schema',
            'json_schema': {'name': 'triage', 'schema': schema, 'strict': True},
        },
    }
    start = time.perf_counter()
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout_seconds())
    try:
        response = client.post(f"{base_url()}/v1/chat/completions", json=payload, headers=_headers())
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()
    usage = data.get('usage') or {}
    prompt_tokens = int(usage.get('prompt_tokens') or 0)
    completion_tokens = int(usage.get('completion_tokens') or 0)
    return {
        'text': data['choices'][0]['message']['content'],
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'thoughts_tokens': 0,
        'total_tokens': int(usage.get('total_tokens') or prompt_tokens + completion_tokens),
        'model_version': data.get('model') or model,
        'latency_ms': round((time.perf_counter() - start) * 1000),
    }


def get_status(refresh: bool = False, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    """Estado del servidor local, cacheado unos segundos. Nunca incluye la URL ni la clave."""
    model = default_model()
    if not configured():
        return {'configured': False, 'reachable': False, 'model': model, 'model_available': False}
    if not refresh:
        cached = cache.get(STATUS_CACHE_KEY)
        if cached is not None:
            return cached
    status = {'configured': True, 'reachable': False, 'model': model, 'model_available': False}
    owns_client = client is None
    client = client or httpx.Client(timeout=2.0)
    try:
        response = client.get(f"{base_url()}/v1/models", headers=_headers())
        response.raise_for_status()
        names = {item.get('id') for item in (response.json().get('data') or []) if isinstance(item, dict)}
        status['reachable'] = True
        status['model_available'] = model in names
    except Exception as err:
        logger.info(f"Servidor LLM local no disponible: {err}")
    finally:
        if owns_client:
            client.close()
    cache.set(STATUS_CACHE_KEY, status, timeout=STATUS_TTL_SECONDS)
    return status
