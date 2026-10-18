from django.db import models
from django.utils import timezone
from .crypto import encrypt_secret, decrypt_secret, mask_api_key, detect_key_provider

class SystemConfiguration(models.Model):
    ASR_CHOICES = (
        # 'auto': cada equipo usa su WHISPER_MODEL_SIZE (small en CPU, large-v3-turbo con GPU).
        ('auto', 'Segun entorno (WHISPER_MODEL_SIZE)'),
        ('large-v3-turbo', 'Faster-Whisper (large-v3-turbo)'),
        ('large-v3', 'Whisper Large V3'),
        ('medium', 'Faster-Whisper (medium)'),
        ('small', 'Faster-Whisper (small)'),
        ('base', 'Faster-Whisper (base)'),
        ('tiny', 'Faster-Whisper (tiny)'),
    )
    LLM_CHOICES = (
        ('gemini-2.5-flash', 'Gemini 2.5 Flash'),
        ('gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite'),
        ('gemini-3.8-flash', 'Gemini 3.8 Flash'),
        # Servidor propio compatible con OpenAI (Ollama, llama.cpp): LOCAL_LLM_BASE_URL y LOCAL_LLM_MODEL.
        # Si falla, se aplica el motor de reglas, nunca Gemini: los datos no salen del servidor.
        ('local', 'LLM local (servidor compatible con OpenAI)'),
    )
    # 'auto' usa RoBERTa (NER_MODEL_PATH) si el worker lo cargo; 'catalogo' lo desactiva (catalogo + LLM).
    NER_CHOICES = (
        ('auto', 'RoBERTa clinico + catalogo (si el modelo esta cargado)'),
        ('catalogo', 'Solo catalogo terminologico y LLM'),
    )

    active_asr_model = models.CharField(max_length=50, choices=ASR_CHOICES, default='auto')
    active_llm_engine = models.CharField(max_length=50, choices=LLM_CHOICES, default='gemini-2.5-flash')
    active_ner_model = models.CharField(max_length=60, choices=NER_CHOICES, default='auto')
    snomed_version = models.CharField(max_length=100, default='SNOMED CT International Edition')
    snomed_updated_at = models.DateTimeField(default=timezone.now)
    icd10_version = models.CharField(max_length=100, default='CIE-10 (OMS)')
    icd10_updated_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return f"Configuracion [ASR: {self.active_asr_model}, LLM: {self.active_llm_engine}]"

class APIKeyCredential(models.Model):
    PROVIDER_CHOICES = (
        ('gemini', 'Google Gemini'),
        ('custom', 'Servidor local'),
    )

    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default='gemini')
    name = models.CharField(max_length=100)
    encrypted_key = models.TextField()
    masked_key = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def set_key(self, plain_key: str):
        if not self.provider or self.provider == 'custom':
            self.provider = detect_key_provider(plain_key)
        self.encrypted_key = encrypt_secret(plain_key)
        self.masked_key = mask_api_key(plain_key)

    def get_key(self) -> str:
        return decrypt_secret(self.encrypted_key)

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()}) - {self.masked_key}"
