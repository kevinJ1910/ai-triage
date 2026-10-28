import os
import sys
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')
load_dotenv(BASE_DIR.parent / '.env')

# FIX-SEC-001: SECRET_KEY sin fallback inseguro.
_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    if 'test' in sys.argv or 'pytest' in sys.modules:
        _secret_key = 'test-insecure-key-only-for-testing-purposes'
    else:
        raise RuntimeError(
            "SECRET_KEY no esta configurada en las variables de entorno. "
            "Configure SECRET_KEY en el archivo .env antes de iniciar el servidor."
        )
SECRET_KEY = _secret_key

# Clave dedicada para cifrar credenciales en BD (system_settings.crypto). Si no se define,
# se deriva de SECRET_KEY (comportamiento historico). Generar con:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = os.getenv('FIELD_ENCRYPTION_KEY', '').strip()

# Seguro por defecto: DEBUG solo se activa explicitamente (DEBUG=True en .env de desarrollo).
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# FIX-SEC-002: ALLOWED_HOSTS via variable de entorno. Sin comodin '*' en produccion.
_allowed_hosts_raw = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_raw.split(',') if h.strip()]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    # FIX-SEC-003: Lista negra de tokens JWT para invalidar refresh tokens rotados.
    'rest_framework_simplejwt.token_blacklist',
    'transcription',
    'accounts',
    'patients',
    'triage',
    'system_settings',
]

AUTH_USER_MODEL = 'accounts.User'

# FIX-SEC-004: Rate limiting global para prevenir brute-force en auth y OTP.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '300/minute',
        'auth': '10/minute',
        'otp': '5/minute',
    }
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Sirve /static/ (CSS y JS del Django Admin) sin depender de DEBUG ni de un servidor aparte.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-co'
# Se almacena en UTC (USE_TZ) y se presenta en hora de Colombia.
TIME_ZONE = os.getenv('TIME_ZONE', 'America/Bogota')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# En desarrollo y en tests los estaticos se sirven desde las apps sin ejecutar collectstatic.
WHITENOISE_USE_FINDERS = DEBUG or 'pytest' in sys.modules
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',') if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = DEBUG

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# FIX-SEC-003: BLACKLIST_AFTER_ROTATION habilitado para invalidar tokens rotados.
SIMPLE_JWT = {
    # Access token corto (solo en memoria del cliente); el refresh vive en cookie httpOnly.
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_MINUTES', '15'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# --- HTTPS detras de nginx ---
# nginx termina TLS y siempre sobrescribe X-Forwarded-Proto; el backend no se expone al host,
# por lo que el cliente no puede falsear la cabecera. Con esto request.is_secure() es fiable.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# La redireccion HTTP->HTTPS la hace nginx; activarla aqui romperia el healthcheck interno por HTTP.
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False') == 'True'
# HSTS lo emite nginx (HSTS_MAX_AGE). Solo definirlo aqui si se despliega sin ese proxy.
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0'))
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# Cookies solo por HTTPS fuera de DEBUG (sobrescribible si el despliegue usa HTTP en red local).
SECURE_COOKIES = os.getenv('SECURE_COOKIES', str(not DEBUG)) == 'True'
SESSION_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SECURE = SECURE_COOKIES
JWT_COOKIE_SECURE = os.getenv('JWT_COOKIE_SECURE', str(SECURE_COOKIES)) == 'True'

# Origenes HTTPS desde los que se aceptan formularios con CSRF (Django Admin), p. ej. https://localhost:8443
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()
]

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', '127.0.0.1')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 1025))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False').lower() in ('true', '1', 't')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'AI-Triage <no-reply@hospital.com>')

# FIX-TEC-007: Logging centralizado — elimina FileHandler manual en cada modulo.
_log_dir = BASE_DIR / 'logs'
_log_dir.mkdir(exist_ok=True)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {name} {levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': str(_log_dir / 'backend_debug.log'),
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'DEBUG',
    },
}

# --- Redis: cache compartida entre procesos y cola de tareas (Celery) ---
# En pytest nunca se usa Redis: tareas en linea y cache en memoria, aunque el .env defina REDIS_HOST.
_TESTING = 'pytest' in sys.modules or 'test' in sys.argv
_redis_host = '' if _TESTING else os.getenv('REDIS_HOST', '').strip()
REDIS_BASE_URL = f"redis://{_redis_host}:{os.getenv('REDIS_PORT', '6379')}" if _redis_host else ''

if REDIS_BASE_URL:
    # Cache clinica, contexto ASR por sesion y contadores de throttling compartidos por web y workers.
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': f'{REDIS_BASE_URL}/1',
            'KEY_PREFIX': 'ai_triage',
        }
    }
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

CELERY_BROKER_URL = f'{REDIS_BASE_URL}/0' if REDIS_BASE_URL else 'memory://'
CELERY_RESULT_BACKEND = f'{REDIS_BASE_URL}/0' if REDIS_BASE_URL else 'cache+memory://'
# Sin broker real las tareas corren en el proceso web (desarrollo local y tests).
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', str(not REDIS_BASE_URL)) == 'True'
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_EXPIRES = 3600
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ROUTES = {
    'transcription.tasks.transcribe_audio_chunk': {'queue': 'asr'},
    'transcription.tasks.reload_asr_model': {'queue': 'asr'},
    'transcription.tasks.normalize_clinical_text_task': {'queue': 'llm'},
    'triage.tasks.*': {'queue': 'llm'},
}
# Tiempo maximo que la peticion web espera al worker antes de degradar (segundos).
ASR_TASK_TIMEOUT = int(os.getenv('ASR_TASK_TIMEOUT', '90'))
LLM_TASK_TIMEOUT = int(os.getenv('LLM_TASK_TIMEOUT', '100'))
# Vida del contexto de transcripcion por sesion (prompt de continuidad de Whisper).
ASR_SESSION_TTL = int(os.getenv('ASR_SESSION_TTL', '1800'))
# TTL y latido periodico en Redis para el estado publicado por worker-asr (mitiga P-05 ante muerte abrupta).
ASR_STATUS_TTL = int(os.getenv('ASR_STATUS_TTL', '90'))
ASR_HEARTBEAT_INTERVAL = int(os.getenv('ASR_HEARTBEAT_INTERVAL', '30'))

# --- Whisper ASR Configuration ---
WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'small')
WHISPER_DEVICE = os.getenv('WHISPER_DEVICE', 'auto')
WHISPER_COMPUTE_TYPE = os.getenv('WHISPER_COMPUTE_TYPE', 'default')
WHISPER_CPU_THREADS = int(os.getenv('WHISPER_CPU_THREADS', '4'))
WHISPER_BEAM_SIZE = int(os.getenv('WHISPER_BEAM_SIZE', '1'))
WHISPER_USE_HOTWORDS = os.getenv('WHISPER_USE_HOTWORDS', 'True').lower() in ('true', '1', 'yes')
WHISPER_AUDIO_NORMALIZE = os.getenv('WHISPER_AUDIO_NORMALIZE', 'True').lower() in ('true', '1', 'yes')

# --- NER clinico (RoBERTa ajustado en ml/ner/; ver triage/ner_model.py) ---
# Carpeta del modelo exportado o id de un repositorio de Hugging Face Hub. Vacio = sin NER (catalogo y reglas).
NER_MODEL_PATH = os.getenv('NER_MODEL_PATH', '')
# Commit o etiqueta del repositorio del Hub cuando NER_MODEL_PATH es un id (vacio: la ultima version).
NER_MODEL_REVISION = os.getenv('NER_MODEL_REVISION', '')
NER_CPU_THREADS = int(os.getenv('NER_CPU_THREADS', '2'))
# Una entidad del modelo con menos confianza solo se conserva si el catalogo o el LLM la confirman.
NER_MIN_SCORE = float(os.getenv('NER_MIN_SCORE', '0.6'))

