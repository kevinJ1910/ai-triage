from django.db import models
from django.utils import timezone
from .crypto import encrypt_secret, decrypt_secret, mask_api_key, detect_key_provider

class SystemConfiguration(models.Model):
    ASR_CHOICES = (
        ('large-v3-turbo', 'Faster-Whisper (large-v3-turbo)'),
        ('large-v3', 'Whisper Large V3'),
        ('medium', 'Faster-Whisper (medium)'),
        ('small', 'Faster-Whisper (small)'),
        ('base', 'Faster-Whisper (base)'),
        ('tiny', 'Faster-Whisper (tiny)'),
    )
    LLM_CHOICES = (
        ('gemini-2.5-flash', 'Gemini 2.5 Flash'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
        ('gpt-4o-mini', 'GPT-4o-mini'),
        ('gpt-4o', 'GPT-4o'),
        ('claude-3-5-sonnet', 'Claude 3.5 Sonnet'),
    )
    NER_CHOICES = (
        ('ClinicalBERT (v2.1 - Recomendado)', 'ClinicalBERT (v2.1 - Recomendado)'),
        ('BioBERT (v1.5 - Legacy)', 'BioBERT (v1.5 - Legacy)'),
        ('PubMedBERT (Experimental)', 'PubMedBERT (Experimental)'),
    )

    active_asr_model = models.CharField(max_length=50, choices=ASR_CHOICES, default='large-v3-turbo')
    active_llm_engine = models.CharField(max_length=50, choices=LLM_CHOICES, default='gemini-2.5-flash')
    active_ner_model = models.CharField(max_length=60, choices=NER_CHOICES, default='ClinicalBERT (v2.1 - Recomendado)')
    snomed_version = models.CharField(max_length=100, default='SNOMED CT (Edicion en Espanol)')
    snomed_updated_at = models.DateTimeField(default=timezone.now)
    icd10_version = models.CharField(max_length=100, default='ICD-10 (CIE-10)')
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
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic Claude'),
        ('deepseek', 'DeepSeek'),
        ('custom', 'Personalizado / Local'),
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
