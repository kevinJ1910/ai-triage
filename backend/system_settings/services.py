import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from django.conf import settings
from .models import APIKeyCredential
from .crypto import detect_key_provider

logger = logging.getLogger(__name__)

def sync_environment_api_keys():
    """
    Sincroniza automaticamente las variables de entorno relacionadas con llaves API
    (GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY o cualquier *_API_KEY)
    hacia el modelo cifrado APIKeyCredential para que sean inmediatamente visibles
    y referenciables en el panel de administracion y componentes de IA.
    """
    try:
        base_dir = getattr(settings, 'BASE_DIR', Path('.'))
        root_env = base_dir.parent / '.env'
        backend_env = base_dir / '.env'

        if root_env.exists():
            load_dotenv(root_env, override=False)
        if backend_env.exists():
            load_dotenv(backend_env, override=False)

        known_keys = {
            'GEMINI_API_KEY': ('Google Gemini (Entorno .env)', 'gemini'),
            'OPENAI_API_KEY': ('OpenAI (Entorno .env)', 'openai'),
            'ANTHROPIC_API_KEY': ('Anthropic Claude (Entorno .env)', 'anthropic'),
            'DEEPSEEK_API_KEY': ('DeepSeek (Entorno .env)', 'deepseek'),
        }

        # 1. Sincronizar llaves estandar definidas en .env
        for env_var, (default_name, default_provider) in known_keys.items():
            val = os.getenv(env_var, '').strip().strip('\'"')
            if val and len(val) >= 4:
                _upsert_env_key(default_name, default_provider, val)

        # 2. Sincronizar llaves dinamicas adicionales (*_API_KEY)
        for k, v in os.environ.items():
            if k.endswith('_API_KEY') and k not in known_keys:
                raw_val = v.strip().strip('\'"')
                if raw_val and len(raw_val) >= 4:
                    prefix = k[:-8].replace('_', ' ').title()
                    provider = detect_key_provider(raw_val)
                    name = f"{prefix} (Entorno .env)"
                    _upsert_env_key(name, provider, raw_val)

    except Exception as e:
        logger.warning(f"No fue posible sincronizar llaves API desde .env: {e}")

def _upsert_env_key(name: str, provider: str, secret_key: str):
    try:
        cred = APIKeyCredential.objects.filter(name=name).first()
        if not cred:
            cred = APIKeyCredential.objects.filter(provider=provider, name__contains='(Entorno .env)').first()

        if cred:
            try:
                current_decrypted = cred.get_key()
            except Exception:
                current_decrypted = ""

            if current_decrypted != secret_key:
                cred.set_key(secret_key)
                cred.name = name
                cred.provider = provider
                cred.is_active = True
                cred.save()
        else:
            cred = APIKeyCredential(name=name, provider=provider, is_active=True)
            cred.set_key(secret_key)
            cred.save()
    except Exception as e:
        logger.debug(f"Error guardando llave {name}: {e}")
