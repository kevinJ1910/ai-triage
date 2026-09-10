from django.db import models
from django.conf import settings
from patients.models import Patient

class TriageSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='triage_sessions')
    level = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)], help_text="Triage level 1-5")
    ai_level = models.IntegerField(default=5, help_text="Initial level suggested by AI model")
    final_level = models.IntegerField(default=5, help_text="Final level confirmed or adjusted by physician")
    is_level_modified = models.BooleanField(default=False, help_text="True if physician modified AI level")
    justification = models.TextField()
    clinical_entities = models.JSONField(default=dict, help_text="Symptoms, vitals, history, medications")
    ai_symptoms = models.JSONField(default=list, blank=True, help_text="List of symptoms initially extracted by AI")
    final_symptoms = models.JSONField(default=list, blank=True, help_text="List of symptoms validated by physician")
    confidence_score = models.FloatField(null=True, blank=True, help_text="AI confidence score if provided")
    agreement_score = models.FloatField(default=1.0, help_text="Physician-AI agreement score between 0.0 and 1.0")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='triage_sess_created_idx'),
            models.Index(fields=['final_level', '-created_at'], name='triage_sess_level_idx'),
            models.Index(fields=['is_level_modified', '-created_at'], name='triage_sess_mod_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.ai_level:
            self.ai_level = self.level or 5
        if not self.final_level:
            self.final_level = self.level or 5
        self.level = self.final_level
        self.is_level_modified = (self.final_level != self.ai_level)
        dist = abs(self.final_level - self.ai_level)
        self.agreement_score = max(0.0, 1.0 - (dist / 4.0))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Triage {self.final_level} (AI: {self.ai_level}) - {self.patient.document_id} ({self.created_at.strftime('%Y-%m-%d')})"

class Transcription(models.Model):
    triage_session = models.OneToOneField(TriageSession, on_delete=models.CASCADE, related_name='transcription')
    session_uuid = models.CharField(max_length=100, db_index=True)
    full_text = models.TextField()
    model_used = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transcription for {self.triage_session}"

class FHIRRecord(models.Model):
    triage_session = models.OneToOneField(TriageSession, on_delete=models.CASCADE, related_name='fhir_record')
    fhir_resource_id = models.CharField(max_length=100, db_index=True)
    payload_sent = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FHIR {self.fhir_resource_id}"

class FHIRMessageLog(models.Model):
    DIRECTION_CHOICES = [
        ('OUTBOUND', 'Hacia Servidor FHIR'),
        ('INBOUND', 'Desde Servidor Externo'),
    ]
    STATUS_CHOICES = [
        ('VALID', 'Valido'),
        ('WARNING', 'Advertencia'),
        ('ERROR', 'Error de Esquema'),
    ]

    session = models.ForeignKey(TriageSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='fhir_logs')
    resource_type = models.CharField(max_length=50, default='Bundle')
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default='OUTBOUND')
    status_code = models.IntegerField(default=201, db_index=True)
    fhir_resource_id = models.CharField(max_length=100, blank=True, db_index=True)
    validation_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='VALID')
    validation_details = models.TextField(blank=True, default='HL7 FHIR R4 Bundle schema validation passed.')
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='fhir_log_created_idx'),
            models.Index(fields=['direction', '-created_at'], name='fhir_log_dir_idx'),
            models.Index(fields=['status_code'], name='fhir_log_status_idx'),
        ]

    def __str__(self):
        return f"[{self.direction}] {self.resource_type} ({self.status_code}) - {self.created_at.strftime('%H:%M:%S')}"
