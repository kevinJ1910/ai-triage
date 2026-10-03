import json
import time
from unittest.mock import patch
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from transcription.whisper_engine import WhisperEngine

User = get_user_model()


@pytest.mark.django_db
class TestWhisperEngineAndEndpoints:
    def setup_method(self):
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

    def test_prune_inactive_sessions_ttl(self):
        now = time.time()
        # Simular sesion antigua de hace 2000 segundos y sesion activa reciente
        with self.engine._session_lock:
            self.engine._session_contexts["expired-sid-1"] = "Contexto antiguo"
            self.engine._session_timestamps["expired-sid-1"] = now - 2000

            self.engine._session_contexts["active-sid-1"] = "Contexto activo reciente"
            self.engine._session_timestamps["active-sid-1"] = now - 10

        self.engine._prune_inactive_sessions(max_age_seconds=1800, max_sessions=50)

        with self.engine._session_lock:
            assert "expired-sid-1" not in self.engine._session_contexts
            assert "expired-sid-1" not in self.engine._session_timestamps
            assert "active-sid-1" in self.engine._session_contexts
            assert "active-sid-1" in self.engine._session_timestamps

    def test_prune_inactive_sessions_max_limit(self):
        now = time.time()
        with self.engine._session_lock:
            self.engine._session_contexts.clear()
            self.engine._session_timestamps.clear()
            for i in range(10):
                sid = f"session-limit-{i}"
                self.engine._session_contexts[sid] = f"Contexto {i}"
                self.engine._session_timestamps[sid] = now + i

        # Reducir limite a 4 sesiones
        self.engine._prune_inactive_sessions(max_age_seconds=99999, max_sessions=4)

        with self.engine._session_lock:
            assert len(self.engine._session_timestamps) == 4
            # Deben quedar las 4 mas recientes (indices 6, 7, 8, 9)
            assert "session-limit-9" in self.engine._session_timestamps
            assert "session-limit-0" not in self.engine._session_timestamps

    def test_reset_session(self):
        sid = "reset-test-uuid"
        with self.engine._session_lock:
            self.engine._session_contexts[sid] = "Conversacion clinica"
            self.engine._session_timestamps[sid] = time.time()

        self.engine.reset_session(sid)

        with self.engine._session_lock:
            assert sid not in self.engine._session_contexts
            assert sid not in self.engine._session_timestamps

    def test_engine_get_status(self):
        info = self.engine.get_status()
        assert "model_size" in info
        assert "device" in info
        assert "active_sessions_count" in info

    def test_health_check_endpoint(self):
        response = self.client.get("/api/health_check/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "model_size" in data

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

    def test_whisper_engine_constructor_failure_redacts_details(self):
        with patch("transcription.views.WhisperEngine", side_effect=RuntimeError("GPU driver missing CudaLib.so")):
            res_health = self.client.get("/api/health_check/")
            assert res_health.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data_health = res_health.json()
            assert data_health["status"] == "unhealthy"
            assert data_health["error"] == "Whisper Engine could not be initialized"
            assert "details" not in data_health
            assert "GPU driver missing CudaLib.so" not in res_health.content.decode()

            audio_file = SimpleUploadedFile("chunk.wav", b"RIFFfakeaudiobytes123456", content_type="audio/wav")
            res_transcribe = self.client.post(
                "/api/transcribe/",
                {"audio": audio_file, "session_id": "err-session-uuid"},
                format="multipart"
            )
            assert res_transcribe.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data_transcribe = res_transcribe.json()
            assert data_transcribe["error"] == "Whisper Engine could not be initialized"
            assert "details" not in data_transcribe
            assert "GPU driver missing CudaLib.so" not in res_transcribe.content.decode()

            res_reset = self.client.post(
                "/api/transcribe/reset/",
                {"session_id": "err-session-uuid"}
            )
            assert res_reset.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data_reset = res_reset.json()
            assert data_reset["error"] == "Whisper Engine is not initialized"
            assert "details" not in data_reset
            assert "GPU driver missing CudaLib.so" not in res_reset.content.decode()

    def test_transcribe_chunk_failure_path_redacts_details(self):
        audio_file = SimpleUploadedFile("chunk.wav", b"RIFFfakeaudiobytes123456", content_type="audio/wav")
        with patch("transcription.views.WhisperEngine") as mock_cls:
            mock_cls.return_value.transcribe_chunk.side_effect = RuntimeError("Internal core dump stack trace")
            response = self.client.post(
                "/api/transcribe/",
                {"audio": audio_file, "session_id": "err-session-uuid"},
                format="multipart"
            )
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data == {"error": "Internal transcription failure"}
            assert "details" not in data
            assert "Internal core dump stack trace" not in response.content.decode()

    def test_reset_session_failure_path_redacts_details(self):
        with patch("transcription.views.WhisperEngine") as mock_cls:
            mock_cls.return_value.reset_session.side_effect = RuntimeError("Sensitive memory lock deadlock")
            response = self.client.post(
                "/api/transcribe/reset/",
                {"session_id": "err-session-uuid"}
            )
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data == {"error": "Failed to reset session"}
            assert "details" not in data
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
        with patch("transcription.views.WhisperEngine") as mock_cls:
            mock_cls.return_value.get_status.side_effect = RuntimeError("Hardware GPU driver crash")
            response = self.client.get("/api/health_check/")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert data == {"status": "unhealthy", "error": "Failed to get Whisper Engine status"}
            assert "details" not in data
            assert "Hardware GPU driver crash" not in response.content.decode()