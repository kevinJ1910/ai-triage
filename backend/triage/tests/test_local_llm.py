import json

import httpx
import pytest

from triage import local_llm
from triage.ai_analyzer import LLMUnavailableError, analyze_triage_transcript
from triage.clinical_cache import ClinicalQueryCache

REAL_CLIENT = httpx.Client

LLM_OUTPUT = {
    "patientInfo": {"name": "[NOMBRE]", "gender": "female"},
    "entities": {"symptoms": ["cefalea"], "medications": [], "vitals": [], "history": []},
    "triage": {"level": 4, "name": "Consulta Prioritaria", "attention_time": "Hasta 120 minutos",
               "justification": "Cefalea sin signos de alarma"},
    "confidence": 0.8,
}


def _completion(content, model="qwen2.5:7b-instruct-q4_K_M"):
    return {"model": model, "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 250, "total_tokens": 1150}}


@pytest.fixture
def local_server(monkeypatch, mocker):
    """Servidor compatible con OpenAI simulado con httpx.MockTransport; guarda las peticiones recibidas."""
    ClinicalQueryCache.clear()
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://llm-local:11434/v1/")
    monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)
    state = {"requests": [], "handler": lambda request: httpx.Response(200, json=_completion(json.dumps(LLM_OUTPUT)))}

    def transport(request):
        state["requests"].append(request)
        return state["handler"](request)

    mocker.patch("triage.local_llm.httpx.Client",
                 side_effect=lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(transport)))
    return state


@pytest.mark.django_db
class TestLocalLLMAdapter:
    def test_chat_json_sends_schema_and_returns_telemetry(self, local_server):
        call = local_llm.chat_json("qwen", "sistema", "usuario", schema={"type": "object"})
        request = local_server["requests"][0]
        assert str(request.url) == "http://llm-local:11434/v1/chat/completions"
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["schema"] == {"type": "object"}
        assert [m["role"] for m in body["messages"]] == ["system", "user"]
        assert call["prompt_tokens"] == 900 and call["total_tokens"] == 1150
        assert call["model_version"] == "qwen2.5:7b-instruct-q4_K_M"

    def test_analysis_with_local_model_is_validated_and_pseudonymized(self, local_server, mocker):
        gemini = mocker.patch("triage.ai_analyzer.genai.Client")
        res = analyze_triage_transcript("Mi nombre es Laura Martinez, tengo dolor de cabeza leve",
                                        use_cache=False, model="local:qwen", include_raw=True)
        gemini.assert_not_called()
        assert res["engine_used"] == "LLM local (qwen) + Christus Sinergia"
        assert res["llm_provider"] == "local"
        assert res["triage"]["level"] == 4
        assert res["patientInfo"]["name"] == "Laura Martinez"
        assert "llm_raw" in res
        body = json.loads(local_server["requests"][0].content)
        assert body["model"] == "qwen"
        assert "Laura" not in body["messages"][1]["content"]

    def test_percentage_confidence_is_normalized_without_touching_the_level(self, local_server):
        output = {**LLM_OUTPUT, "confidence": 95}
        local_server["handler"] = lambda request: httpx.Response(200, json=_completion(json.dumps(output)))
        res = analyze_triage_transcript("dolor de cabeza leve", use_cache=False, model="local:qwen")
        assert res["confidence"] == pytest.approx(0.95)
        assert res["output_coerced"] == ["confidence"]
        assert res["triage"]["level"] == 4
        output["confidence"] = 250
        local_server["handler"] = lambda request: httpx.Response(200, json=_completion(json.dumps(output)))
        res = analyze_triage_transcript("dolor de cabeza leve", use_cache=False, model="local:qwen")
        assert res["engine_used"].startswith("Motor de Reglas")

    def test_active_local_engine_never_falls_back_to_gemini(self, local_server, mocker):
        from system_settings.models import SystemConfiguration
        config = SystemConfiguration.get_solo()
        config.active_llm_engine = 'local'
        config.save()
        mocker.patch("triage.ai_analyzer._resolve_gemini_api_key", return_value="test-key")
        gemini = mocker.patch("triage.ai_analyzer.genai.Client")
        local_server["handler"] = lambda request: httpx.Response(200, json=_completion("{no es json"))

        res = analyze_triage_transcript("dolor de cabeza leve", use_cache=False)

        gemini.assert_not_called()
        assert res["engine_used"].startswith("Motor de Reglas")
        assert "esquema" in res["warning"]
        assert json.loads(local_server["requests"][0].content)["model"] == local_llm.DEFAULT_MODEL

    def test_timeout_falls_back_to_rules(self, local_server):
        def timeout(request):
            raise httpx.ReadTimeout("timeout", request=request)
        local_server["handler"] = timeout
        res = analyze_triage_transcript("dolor de cabeza leve", use_cache=False, model="local:qwen")
        assert res["engine_used"].startswith("Motor de Reglas")
        with pytest.raises(httpx.ReadTimeout):
            analyze_triage_transcript("dolor de cabeza leve", use_cache=False, model="local:qwen", strict_llm=True)

    def test_without_base_url_uses_rules_or_raises_in_strict_mode(self, monkeypatch):
        monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
        res = analyze_triage_transcript("dolor de cabeza leve", use_cache=False, model="local:qwen")
        assert "LOCAL_LLM_BASE_URL" in res["warning"]
        with pytest.raises(LLMUnavailableError):
            analyze_triage_transcript("dolor de cabeza leve", use_cache=False, model="local:qwen", strict_llm=True)

    def test_vault_key_is_sent_as_bearer(self, local_server):
        from system_settings.models import APIKeyCredential
        cred = APIKeyCredential(provider='custom', name='Servidor local')
        cred.set_key("sk-local-123456")
        cred.provider = 'custom'
        cred.save()
        local_llm.chat_json("qwen", "s", "u", schema={})
        assert local_server["requests"][0].headers["Authorization"] == "Bearer sk-local-123456"


@pytest.mark.django_db
class TestLocalLLMStatus:
    def test_not_configured(self, monkeypatch):
        # settings.py carga el .env del equipo: la prueba no debe depender de su LOCAL_LLM_MODEL.
        monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)
        assert local_llm.get_status() == {"configured": False, "reachable": False,
                                          "model": local_llm.DEFAULT_MODEL, "model_available": False, "models": []}

    def test_reachable_reports_model_availability_and_is_cached(self, local_server):
        local_server["handler"] = lambda request: httpx.Response(
            200, json={"data": [{"id": local_llm.DEFAULT_MODEL}, {"id": "llama3.1:8b"}]})
        status = local_llm.get_status()
        assert status == {"configured": True, "reachable": True, "model": local_llm.DEFAULT_MODEL,
                          "model_available": True, "models": ["llama3.1:8b", local_llm.DEFAULT_MODEL]}
        local_llm.get_status()
        assert len(local_server["requests"]) == 1

    def test_unreachable(self, local_server):
        def refused(request):
            raise httpx.ConnectError("refused", request=request)
        local_server["handler"] = refused
        status = local_llm.get_status(refresh=True)
        assert status["configured"] is True and status["reachable"] is False

    def test_model_chosen_in_configuration_wins_over_environment(self, local_server, mocker):
        from system_settings.models import SystemConfiguration
        local_server["handler"] = lambda request: httpx.Response(
            200, json={"data": [{"id": local_llm.DEFAULT_MODEL}, {"id": "gemma4:e4b-it-qat"}]})
        config = SystemConfiguration.get_solo()
        config.local_llm_model = 'gemma4:e4b-it-qat'
        config.save()
        status = local_llm.get_status()
        assert status["model"] == 'gemma4:e4b-it-qat' and status["model_available"] is True

        config.active_llm_engine = 'local'
        config.save()
        local_server["handler"] = lambda request: httpx.Response(200, json=_completion(json.dumps(LLM_OUTPUT)))
        mocker.patch("triage.ai_analyzer.genai.Client")
        res = analyze_triage_transcript("dolor de cabeza leve", use_cache=False)
        assert res["engine_used"] == "LLM local (gemma4:e4b-it-qat) + Christus Sinergia"
        assert json.loads(local_server["requests"][-1].content)["model"] == 'gemma4:e4b-it-qat'
