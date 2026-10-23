import httpx
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from system_settings.models import APIKeyCredential, SystemConfiguration

REAL_CLIENT = httpx.Client


@pytest.fixture
def admin_client():
    user = get_user_model().objects.create_user(
        email='admin_local@hospital.com', password='Password123!', role='admin', is_verified=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def local_server(monkeypatch, mocker):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://llm-local:11434")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen2.5:7b-instruct-q4_K_M")
    state = {"up": True}

    def handler(request):
        if not state["up"]:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"data": [{"id": "qwen2.5:7b-instruct-q4_K_M"}]})

    mocker.patch("triage.local_llm.httpx.Client",
                 side_effect=lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(handler)))
    return state


@pytest.mark.django_db
class TestLocalEngineConfig:
    def test_local_engine_is_offered_and_accepted(self, admin_client, local_server):
        options = admin_client.get('/api/config/').json()['available_options']['llm_engines']
        assert any(o['id'] == 'local' for o in options)
        response = admin_client.post('/api/config/', {'active_llm_engine': 'local'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert SystemConfiguration.get_solo().active_llm_engine == 'local'

    def test_engine_status_reports_local_server(self, admin_client, local_server):
        config = SystemConfiguration.get_solo()
        config.active_llm_engine = 'local'
        config.save()
        data = admin_client.get('/api/config/engines/').json()
        assert data['llm'] == {"provider": "local", "configured": True, "model": "qwen2.5:7b-instruct-q4_K_M"}
        assert data['local_llm']['reachable'] is True and data['local_llm']['model_available'] is True

    def test_engine_status_when_local_server_is_down(self, admin_client, local_server):
        local_server["up"] = False
        config = SystemConfiguration.get_solo()
        config.active_llm_engine = 'local'
        config.save()
        data = admin_client.get('/api/config/engines/').json()
        assert data['llm']['configured'] is False
        assert data['local_llm'] == {"configured": True, "reachable": False,
                                     "model": "qwen2.5:7b-instruct-q4_K_M", "model_available": False, "models": []}

    def test_status_never_exposes_url_or_key(self, admin_client, local_server):
        cred = APIKeyCredential(provider='custom', name='Servidor local')
        cred.set_key('sk-secreta-local-987654')
        cred.provider = 'custom'
        cred.save()
        body = admin_client.get('/api/config/engines/').content.decode()
        body += admin_client.get('/api/config/').content.decode()
        assert 'llm-local:11434' not in body
        assert 'sk-secreta-local-987654' not in body

    def test_gemini_status_unchanged(self, admin_client, monkeypatch):
        monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
        data = admin_client.get('/api/config/engines/').json()
        assert data['llm']['provider'] == 'gemini'
        assert data['local_llm']['configured'] is False

    def test_installed_models_are_offered_and_the_choice_is_saved(self, admin_client, local_server):
        data = admin_client.get('/api/config/').json()
        assert data['available_options']['local_llm_models'] == ['qwen2.5:7b-instruct-q4_K_M']
        response = admin_client.post('/api/config/', {'active_llm_engine': 'local',
                                                      'local_llm_model': 'gemma4:e4b-it-qat'}, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert SystemConfiguration.get_solo().local_llm_model == 'gemma4:e4b-it-qat'
        engines = admin_client.get('/api/config/engines/').json()
        assert engines['llm']['model'] == 'gemma4:e4b-it-qat'
        assert engines['local_llm']['model_available'] is False

    def test_invalid_local_model_name_is_rejected(self, admin_client):
        response = admin_client.post('/api/config/', {'local_llm_model': 'gemma; rm -rf'}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
