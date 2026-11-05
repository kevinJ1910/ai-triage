import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from patients.models import Patient
from triage.ai_analyzer import EntitiesSchema, TriageOutputSchema, analyze_triage_transcript
from triage.clinical_cache import ClinicalQueryCache
from triage.fhir_validation import validate_fhir_bundle
from triage.models import TriageSession

NEW_KEYS = ('diagnoses', 'allergies', 'negated_findings')


class TestEntitiesSchema:
    def test_new_keys_default_to_empty_lists(self):
        entities = EntitiesSchema.model_validate({'symptoms': ['tos']}).model_dump()
        assert all(entities[key] == [] for key in NEW_KEYS)

    def test_llm_output_without_new_keys_is_still_valid(self):
        result = TriageOutputSchema.model_validate({
            'patientInfo': {}, 'entities': {'symptoms': ['tos']},
            'triage': {'level': 4, 'name': 'Consulta Prioritaria', 'attention_time': 'Direccionamiento a su EPS',
                       'justification': 'x'},
        })
        assert result.entities.allergies == []

    def test_cache_fingerprint_includes_schema_version(self, monkeypatch):
        before = ClinicalQueryCache.generate_fingerprint('tos y fiebre')
        monkeypatch.setattr('triage.clinical_cache.RESULT_SCHEMA_VERSION', 99)
        assert ClinicalQueryCache.generate_fingerprint('tos y fiebre') != before


@pytest.mark.django_db
class TestFallbackEntities:
    def test_rules_fallback_returns_every_entity_key(self, monkeypatch):
        monkeypatch.setenv('GEMINI_API_KEY', '')
        result = analyze_triage_transcript('tengo tos, sin fiebre', use_cache=False, allow_llm=False)
        entities = result['entities']
        assert all(key in entities for key in ('symptoms', 'vitals', 'medications', 'history', *NEW_KEYS))
        assert entities['symptoms'] == ['tos']
        assert entities['negated_findings'] == ['fiebre']


@pytest.mark.django_db
class TestHistoryExposesNewEntities:
    def test_history_includes_new_keys(self):
        user = get_user_model().objects.create_user(
            email='hist_entities@hospital.com', password='Password123!', role='medico', is_verified=True)
        patient = Patient.objects.create(document_id='CC-ENT-01', full_name='Ana Ruiz')
        TriageSession.objects.create(
            user=user, patient=patient, level=3, ai_level=3, final_level=3,
            clinical_entities={'symptoms': ['ronchas'], 'allergies': ['penicilina'],
                               'diagnoses': ['urticaria'], 'negated_findings': ['disnea']},
        )
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get('/api/triage/sessions/history/')
        assert response.status_code == status.HTTP_200_OK
        entities = response.data[0]['analysisResult']['entities']
        assert entities['allergies'] == ['penicilina']
        assert entities['diagnoses'] == ['urticaria']
        assert entities['negated_findings'] == ['disnea']


def _bundle(*resources):
    return {'resourceType': 'Bundle', 'type': 'collection', 'entry': [{'resource': r} for r in resources]}


class TestFHIRValidationOfNewResources:
    def test_allergy_intolerance_requires_patient(self):
        ok, detail = validate_fhir_bundle(_bundle({'resourceType': 'AllergyIntolerance', 'code': {'text': 'penicilina'}}))
        assert not ok and 'AllergyIntolerance.patient' in detail

    def test_valid_allergy_and_refuted_condition(self):
        allergy = {
            'resourceType': 'AllergyIntolerance', 'patient': {'reference': 'Patient/p1'},
            'clinicalStatus': {'coding': [{'code': 'active'}]},
            'verificationStatus': {'coding': [{'code': 'unconfirmed'}]},
        }
        refuted = {'resourceType': 'Condition', 'subject': {'reference': 'Patient/p1'},
                   'verificationStatus': {'coding': [{'code': 'refuted'}]}}
        ok, detail = validate_fhir_bundle(_bundle(allergy, refuted))
        assert ok, detail

    def test_rejects_unknown_verification_status(self):
        condition = {'resourceType': 'Condition', 'subject': {'reference': 'Patient/p1'},
                     'verificationStatus': {'coding': [{'code': 'negado'}]}}
        ok, detail = validate_fhir_bundle(_bundle(condition))
        assert not ok and 'verificationStatus' in detail
