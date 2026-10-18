import base64
import hashlib
from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings

def _legacy_secret_key_fernet() -> Fernet:
    """Clave historica derivada de SECRET_KEY."""
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)

def get_fernet_cipher() -> MultiFernet:
    """
    Cifra con FIELD_ENCRYPTION_KEY si esta definida; descifra con ella o con la clave
    historica derivada de SECRET_KEY, para que las llaves ya guardadas sigan siendo legibles.
    """
    ciphers = []
    dedicated = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
    if dedicated:
        ciphers.append(Fernet(dedicated.encode()))
    ciphers.append(_legacy_secret_key_fernet())
    return MultiFernet(ciphers)

def encrypt_secret(plain_text: str) -> str:
    if not plain_text:
        return ""
    cipher = get_fernet_cipher()
    return cipher.encrypt(plain_text.strip().encode('utf-8')).decode('utf-8')

def decrypt_secret(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    cipher = get_fernet_cipher()
    return cipher.decrypt(cipher_text.encode('utf-8')).decode('utf-8')

def mask_api_key(key: str) -> str:
    if not key:
        return ""
    cleaned = key.strip()
    if len(cleaned) <= 6:
        return "..." + cleaned[-2:]
    return "..." + cleaned[-4:]

def detect_key_provider(key: str) -> str:
    cleaned = key.strip()
    # El triaje solo llama a Gemini; cualquier otra clave se registra como servidor local.
    if cleaned.startswith("AIza") or "AQ." in cleaned:
        return "gemini"
    return "custom"
