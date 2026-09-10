import base64
import hashlib
from cryptography.fernet import Fernet
from django.conf import settings

def get_fernet_cipher():
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)

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
    if cleaned.startswith("AIza") or "AQ." in cleaned:
        return "gemini"
    elif cleaned.startswith("sk-ant-"):
        return "anthropic"
    elif cleaned.startswith("sk-proj-") or (cleaned.startswith("sk-") and len(cleaned) > 35):
        return "openai"
    elif "deepseek" in cleaned.lower():
        return "deepseek"
    return "custom"
