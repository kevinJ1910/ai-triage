from django.db import models
from django.conf import settings
from patients.models import Patient

class TriageSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='triage_sessions')
    level = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)], help_text="Triage level 1-5")
    justification = models.TextField()
    clinical_entities = models.JSONField(default=dict, help_text="Symptoms, vitals, history, medications")
    confidence_score = models.FloatField(null=True, blank=True, help_text="AI confidence score if provided")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Triage {self.level} - {self.patient.document_id} ({self.created_at.strftime('%Y-%m-%d')})"

class Transcription(models.Model):
    triage_session = models.OneToOneField(TriageSession, on_delete=models.CASCADE, related_name='transcription')
    session_uuid = models.CharField(max_length=100)
    full_text = models.TextField()
    model_used = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transcription for {self.triage_session}"

class FHIRRecord(models.Model):
    triage_session = models.OneToOneField(TriageSession, on_delete=models.CASCADE, related_name='fhir_record')
    fhir_resource_id = models.CharField(max_length=100)
    payload_sent = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FHIR {self.fhir_resource_id}"
