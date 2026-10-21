import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from core.task_runner import TaskUnavailable
from transcription.tasks import ASR_STATUS_KEY
from transcription.whisper_engine import (
    WhisperEngine, append_session_context, get_session_context, reset_session_context,
)

User = get_user_model()


@pytest.mark.django_db
class TestWhisperEngineAndEndpoints:
    def setup_method(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="asr_tester@hospital.com", password="Password123!", role="medico", is_verified=True
        )
        self.client.force_authenticate(user=self.user)
        self.engine = WhisperEngine()

    def test_singleton_pattern(self):
        engine1 = WhisperEngine()
        engine2 = WhisperEngine()
        assert engine1 is engine2

    def test_session_context_lives_in_shared_cache(self):
        append_session_context("sid-1", "dolor toracico")
        append_session_context("sid-1", "desde hace una hora")
        assert get_session_context("sid-1") == "dolor toracico desde hace una hora"
        assert get_session_context("sid-2") == ""

        reset_session_context("sid-1")
        assert get_session_context("sid-1") == ""

    @override_settings(ASR_SESSION_TTL=1234)
    def test_session_context_expires_and_is_bounded(self, mocker):
        spy = mocker.spy(cache, "set")
        append_session_context("sid-long", "x" * 5000)
        assert spy.call_args.kwargs["timeout"] == 1234
        assert len(get_session_context("sid-long")) == 2000

    def test_transcribe_chunk_continues_session_from_cache(self, monkeypatch):
        fake_model = MagicMock()
        fake_model.transcribe.return_value = (
            [SimpleNamespace(text="me duele el pecho")],
            SimpleNamespace(language="es", language_probability=0.99),
        )
        monkeypatch.setattr(self.engine, "model", fake_model)
        append_session_context("sid-chunk", "paciente de 60 anos")

        result = self.engine.transcribe_chunk(b"fake-audio", "sid-chunk")

        assert result["text"] == "me duele el pecho"
        assert "paciente de 60 anos" in fake_model.transcribe.call_args.kwargs["initial_prompt"]
        assert get_session_context("sid-chunk") == "paciente de 60 anos me duele el pecho"

    def test_whisper_loop_is_collapsed_and_kept_out_of_the_context(self, monkeypatch):
        # Caso real del 17-10-2026: el bucle pasaba al prompt del siguiente fragmento y se perpetuaba.
        fake_model = MagicMock()
        fake_model.transcribe.return_value = (
            [SimpleNamespace(text="me ha dado que " * 20)],
            SimpleNamespace(language="es", language_probability=0.99),
        )
        monkeypatch.setattr(self.engine, "model", fake_model)
        append_session_context("sid-loop", "Buenas tardes")

        result = self.engine.transcribe_chunk(b"fake-audio", "sid-loop")

        assert result["text"] == "me ha dado que"
        assert result["repetition_filtered"] is True
        assert get_session_context("sid-loop") == "Buenas tardes"
        # Escala de temperaturas: Whisper reintenta cuando la salida es demasiado repetitiva.
        assert fake_model.transcribe.call_args.kwargs["temperature"][0] == 0.0
        assert len(fake_model.transcribe.call_args.kwargs["temperature"]) > 1
        assert fake_model.transcribe.call_args.kwargs["compression_ratio_threshold"] == 2.4

    @pytest.mark.parametrize("text,expected,repeated", [
        ("soy el profesional de ertes, " * 30, "soy el profesional de ertes", True),
        ("tos tos tos tos tos", "tos", True),
        ("Subtítulos por la comunidad de Amara.org", "", True),
        ("Me duele la cabeza. Gracias por ver el video.", "Me duele la cabeza", True),
        ("me duele, me duele mucho el pecho", "me duele, me duele mucho el pecho", False),
        ("no, no, no puedo respirar", "no, no, no puedo respirar", False),
        ("fiebre de 38, fiebre alta desde ayer y fiebre en la noche",
         "fiebre de 38, fiebre alta desde ayer y fiebre en la noche", False),
    ])
    def test_clean_transcript(self, text, expected, repeated):
        from transcription.whisper_engine import clean_transcript
        assert clean_transcript(text) == (expected, repeated)

    def test_engine_get_status_does_not_expose_sessions(self):
        append_session_context("secret-session-id", "texto")
        info = self.engine.get_status()
        assert {"model_size", "device", "compute_type", "model_loaded"} <= set(info)
        assert "secret-session-id" not in json.dumps(info)

    def test_health_check_inline_mode(self):
        response = self.client.get("/api/health_check/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["inference_mode"] == "inline"
        assert "device" in data["asr"]

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_health_check_worker_mode_reads_published_status_without_loading_model(self):
        cache.set(ASR_STATUS_KEY, {"model_loaded": True, "device": "cuda", "model_size": "large-v3-turbo"})
        with patch("transcription.tasks.WhisperEngine") as engine_cls:
            response = self.client.get("/api/health_check/")
        engine_cls.assert_not_called()
        data = response.json()
        assert data["status"] == "healthy"
        assert data["inference_mode"] == "worker"
        assert data["asr"]["device"] == "cuda"

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_health_check_worker_mode_without_asr_worker_is_degraded(self):
        response = self.client.get("/api/health_check/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "degraded"

    def test_transcribe_runs_engine_through_task(self):
        audio_file = SimpleUploadedFile("chunk.wav", b"RIFFfakeaudiobytes123456", content_type="audio/wav")
        with patch("transcription.tasks.WhisperEngine") as engine_cls:
            engine_cls.return_value.transcribe_chunk.return_value = {"text": "hola", "session_id": "s-1"}
            response = self.client.post(
                "/api/transcribe/", {"audio": audio_file, "session_id": "s-1"}, format="multipart"
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["text"] == "hola"
        engine_cls.return_value.transcribe_chunk.assert_called_once_with(b"RIFFfakeaudiobytes123456", "s-1")

    def test_transcribe_encodes_audio_for_the_broker(self):
        with patch("transcription.tasks.run_task", return_value={"text": "ok"}) as run_task:
            from transcription.tasks import transcribe_audio
            transcribe_audio(b"\x00\xffaudio", "s-2")
        audio_b64 = run_task.call_args.args[1]
        assert base64.b64decode(audio_b64) == b"\x00\xffaudio"

    def test_normalize_text_colloquial_symptoms(self):
        payload = {
            "raw_text": "Doctor, vengo porque siento que me aprieta el pecho y me falta el aire"
        }
        response = self.client.post(
            "/api/transcribe/normalize/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "normalized_text" in data
        assert "mappings" in data
        assert len(data["mappings"]) >= 2

        raw_terms = [m["raw_term"].lower() for m in data["mappings"]]
        assert any("aprieta el pecho" in rt for rt in raw_terms)
        assert any("falta el aire" in rt for rt in raw_terms)

        medical_terms = [m["medical_term"].lower() for m in data["mappings"]]
        assert any("opresi" in mt for mt in medical_terms)
        assert any("disnea" in mt for mt in medical_terms)

    def test_normalize_falls_back_to_rules_when_worker_unavailable(self):
        with patch("transcription.views.run_task", side_effect=TaskUnavailable("worker sin respuesta")):
            response = self.client.post(
                "/api/transcribe/normalize/",
                data=json.dumps({"raw_text": "tengo calentura y mareo"}),
                content_type="application/json",
            )
        assert response.status_code == status.HTTP_200_OK
        assert {m["raw_term"] for m in response.json()["mappings"]} == {"calentura", "mareo"}

    def test_worker_unavailable_returns_503_without_details(self):
        audio_file = SimpleUploadedFile("chunk.wav", b"RIFFfakeaudiobytes123456", content_type="audio/wav")
        with patch("transcription.views.transcribe_audio", side_effect=TaskUnavailable("broker no disponible")):
            response = self.client.post(
                "/api/transcribe/", {"audio": audio_file, "session_id": "err-session-uuid"}, format="multipart"
            )
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json() == {"error": "Whisper Engine could not be initialized"}

    def test_transcribe_chunk_failure_path_redacts_details(self):
        audio_file = SimpleUploadedFile("chunk.wav", b"RIFFfakeaudiobytes123456", content_type="audio/wav")
        with patch("transcription.tasks.WhisperEngine") as mock_cls:
            mock_cls.return_value.transcribe_chunk.side_effect = RuntimeError("Internal core dump stack trace")
            response = self.client.post(
                "/api/transcribe/",
                {"audio": audio_file, "session_id": "err-session-uuid"},
                format="multipart"
            )
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data == {"error": "Internal transcription failure"}
            assert "Internal core dump stack trace" not in response.content.decode()

    def test_reset_session_does_not_load_engine(self):
        append_session_context("sid-reset", "contexto")
        with patch("transcription.tasks.WhisperEngine") as engine_cls:
            response = self.client.post("/api/transcribe/reset/", {"session_id": "sid-reset"})
        assert response.status_code == status.HTTP_200_OK
        engine_cls.assert_not_called()
        assert get_session_context("sid-reset") == ""

    def test_reset_session_failure_path_redacts_details(self):
        with patch("transcription.views.reset_session_context", side_effect=RuntimeError("Sensitive memory lock deadlock")):
            response = self.client.post(
                "/api/transcribe/reset/",
                {"session_id": "err-session-uuid"}
            )
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data == {"error": "Failed to reset session"}
            assert "Sensitive memory lock deadlock" not in response.content.decode()

    def test_asr_endpoints_require_authentication(self):
        anon = APIClient()
        audio_file = SimpleUploadedFile("chunk.wav", b"RIFFfakeaudiobytes123456", content_type="audio/wav")
        assert anon.post("/api/transcribe/", {"audio": audio_file}, format="multipart").status_code == status.HTTP_401_UNAUTHORIZED
        assert anon.post("/api/transcribe/reset/", {"session_id": "x"}).status_code == status.HTTP_401_UNAUTHORIZED
        assert anon.post(
            "/api/transcribe/normalize/", data=json.dumps({"raw_text": "dolor"}), content_type="application/json"
        ).status_code == status.HTTP_401_UNAUTHORIZED
        # El health check sigue publico para el healthcheck de Docker
        assert anon.get("/api/health_check/").status_code == status.HTTP_200_OK

    def test_transcribe_denied_without_transcriber_permission(self):
        self.user.permissions.can_use_transcriber = False
        self.user.permissions.save()
        audio_file = SimpleUploadedFile("chunk.wav", b"RIFFfakeaudiobytes123456", content_type="audio/wav")
        response = self.client.post("/api/transcribe/", {"audio": audio_file}, format="multipart")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_health_check_failure_path_redacts_details(self):
        with patch("transcription.views.get_asr_status", side_effect=RuntimeError("Hardware GPU driver crash")):
            response = self.client.get("/api/health_check/")
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data == {"status": "unhealthy", "error": "Whisper Engine could not be initialized"}
            assert "Hardware GPU driver crash" not in response.content.decode()


@pytest.mark.django_db
class TestWhisperModelSelection:
    def _init_engine(self, mocker):
        model_cls = mocker.patch("transcription.whisper_engine.WhisperModel")
        engine = object.__new__(WhisperEngine)  # instancia aislada, sin tocar el singleton
        engine._initialize()
        return engine, model_cls

    @override_settings(WHISPER_MODEL_SIZE="small", WHISPER_DEVICE="cpu", WHISPER_COMPUTE_TYPE="int8")
    def test_auto_uses_model_from_environment(self, mocker):
        from system_settings.models import SystemConfiguration
        assert SystemConfiguration.get_solo().active_asr_model == "auto"
        engine, model_cls = self._init_engine(mocker)
        assert model_cls.call_args.args[0] == "small"
        assert model_cls.call_args.kwargs["device"] == "cpu"
        assert engine.get_status()["model_size"] == "small"

    @override_settings(WHISPER_MODEL_SIZE="small", WHISPER_DEVICE="cpu", WHISPER_COMPUTE_TYPE="int8")
    def test_reload_applies_new_config_without_restarting(self, mocker):
        from system_settings.models import SystemConfiguration
        engine, model_cls = self._init_engine(mocker)
        assert engine.get_status()["model_size"] == "small"
        cfg = SystemConfiguration.get_solo()
        cfg.active_asr_model = "base"
        cfg.save()
        status = engine.reload()
        assert model_cls.call_args.args[0] == "base"
        assert status["model_size"] == "base" and status["model_loaded"] is True
        assert status["requested"] == "base"

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_reload_task_publishes_loading_then_new_status(self, mocker):
        from transcription.tasks import reload_asr_model
        cache.set(ASR_STATUS_KEY, {"model_loaded": True, "model_size": "small"})
        published = []
        mocker.patch("transcription.tasks.cache.set", side_effect=lambda key, value, timeout=None: published.append(value))
        engine = mocker.patch("transcription.tasks.WhisperEngine")
        engine.configured_model_size.return_value = "base"
        engine.return_value.reload.return_value = {"model_loaded": True, "model_size": "base"}
        assert reload_asr_model() == {"model_loaded": True, "model_size": "base"}
        assert published[0]["loading"] is True and published[0]["model_size"] == "base"
        assert published[-1] == {"model_loaded": True, "model_size": "base"}

    @override_settings(WHISPER_MODEL_SIZE="small")
    def test_explicit_admin_choice_overrides_environment(self, mocker):
        from system_settings.models import SystemConfiguration
        cfg = SystemConfiguration.get_solo()
        cfg.active_asr_model = "medium"
        cfg.save()
        _, model_cls = self._init_engine(mocker)
        assert model_cls.call_args.args[0] == "medium"


@pytest.mark.django_db
class TestNormalizerGemini:
    def test_gemini_call_has_request_timeout(self, mocker):
        from triage.ai_analyzer import GEMINI_REQUEST_TIMEOUT
        from transcription import normalizer
        mocker.patch.object(normalizer, "_resolve_gemini_key", return_value="test-key")
        client_cls = mocker.patch("google.genai.Client")
        client_cls.return_value.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps({"normalized_text": "disnea", "summary": "s", "mappings": []})
        )

        result = normalizer.normalize_clinical_text("me falta el aire")

        assert result["normalized_text"] == "disnea"
        assert client_cls.call_args.kwargs["http_options"] == {"timeout": GEMINI_REQUEST_TIMEOUT * 1000}

    def test_gemini_timeout_falls_back_to_catalog(self, mocker):
        from transcription import normalizer
        mocker.patch.object(normalizer, "_resolve_gemini_key", return_value="test-key")
        client_cls = mocker.patch("google.genai.Client")
        client_cls.return_value.models.generate_content.side_effect = TimeoutError("deadline exceeded")

        result = normalizer.normalize_clinical_text("me falta el aire")

        assert [m["raw_term"] for m in result["mappings"]] == ["me falta el aire"]
        assert result["layers"]["llm"] == 0

    def test_gemini_response_outside_contract_falls_back_to_catalog(self, mocker):
        from transcription import normalizer
        mocker.patch.object(normalizer, "_resolve_gemini_key", return_value="test-key")
        client_cls = mocker.patch("google.genai.Client")
        client_cls.return_value.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps({"normalized_text": "disnea", "mappings": [{"raw_term": "falta el aire"}]})
        )

        result = normalizer.normalize_clinical_text("me falta el aire")

        assert result["mappings"][0]["code"] == "R06.0"
        assert result["mappings"][0]["source"] == "diccionario"

    def test_gemini_call_sends_response_schema(self, mocker):
        from transcription import normalizer
        mocker.patch.object(normalizer, "_resolve_gemini_key", return_value="test-key")
        client_cls = mocker.patch("google.genai.Client")
        client_cls.return_value.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps({"normalized_text": "disnea", "summary": "s", "mappings": []})
        )

        normalizer.normalize_clinical_text("me falta el aire")

        config = client_cls.return_value.models.generate_content.call_args.kwargs["config"]
        assert "mappings" in config["response_schema"]["properties"]
