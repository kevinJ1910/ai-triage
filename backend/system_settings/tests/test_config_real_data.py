import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from system_settings.models import SystemConfiguration
from transcription.terminology import catalog_summary, cie10_catalog, snomed_catalog


@pytest.fixture
def admin_client():
    user = get_user_model().objects.create_user(
        email='admin_cfg@hospital.com', password='Password123!', role='admin', is_verified=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestRealConfigData:
    def test_vocabularies_come_from_the_local_catalogs(self, admin_client):
        data = admin_client.get('/api/config/').json()
        assert data['vocabularies']['snomed']['total_terms'] == len(snomed_catalog()['codigos'])
        assert data['vocabularies']['icd10']['total_terms'] == len(cie10_catalog()['codigos'])
        assert data['vocabularies']['icd10']['status'] == 'SUBCONJUNTO'
        assert data['catalog']['errores'] == []
        assert 'ner_status' in data['runtime_status']

    def test_only_working_engines_are_offered(self, admin_client):
        options = admin_client.get('/api/config/').json()['available_options']
        assert {o['id'] for o in options['llm_engines']} <= {'gemini-2.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.8-flash', 'local'}
        assert {o['id'] for o in options['ner_models']} == {'auto', 'catalogo'}

    def test_engines_without_backend_are_rejected(self, admin_client):
        response = admin_client.post('/api/config/', {'active_llm_engine': 'gpt-4o'}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_sync_validates_and_reloads_the_catalog(self, admin_client):
        check = admin_client.post('/api/config/vocabulary/sync/', {'type': 'snomed', 'action': 'check_update'},
                                  format='json').json()
        assert check['errors'] == [] and check['total_terms'] == len(snomed_catalog()['codigos'])
        sync = admin_client.post('/api/config/vocabulary/sync/', {'type': 'icd10'}, format='json').json()
        assert sync['message'].startswith('Catalogo recargado') and sync['total_terms'] == len(cie10_catalog()['codigos'])

    def test_catalog_summary_counts(self):
        summary = catalog_summary()
        assert summary['conceptos'] >= 300 and summary['formas_de_superficie'] >= 1000


@pytest.mark.django_db
class TestNerSwitch:
    def test_catalog_option_disables_roberta(self, monkeypatch):
        from triage import ner_model
        from triage.ai_analyzer import analyze_triage_transcript

        class Engine:
            source = 'x'

            def extract(self, text):
                raise AssertionError('no debe llamarse')

        monkeypatch.setattr(ner_model, 'get_engine', lambda: Engine())
        monkeypatch.setenv('GEMINI_API_KEY', '')
        config = SystemConfiguration.get_solo()
        config.active_ner_model = 'catalogo'
        config.save()
        result = analyze_triage_transcript('tengo fiebre', use_cache=False, allow_llm=False)
        assert result['ner_engine'] is None
