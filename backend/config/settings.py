import os
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
    import sys
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

LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',') if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = DEBUG

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# FIX-SEC-003: BLACKLIST_AFTER_ROTATION habilitado para invalidar tokens rotados.
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

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

# --- Whisper ASR Configuration ---
WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'large-v3-turbo')
WHISPER_DEVICE = os.getenv('WHISPER_DEVICE', 'auto')
WHISPER_COMPUTE_TYPE = os.getenv('WHISPER_COMPUTE_TYPE', 'default')
WHISPER_CPU_THREADS = int(os.getenv('WHISPER_CPU_THREADS', '4'))
WHISPER_BEAM_SIZE = int(os.getenv('WHISPER_BEAM_SIZE', '1'))

