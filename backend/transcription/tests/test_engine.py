import json
import time
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from transcription.whisper_engine import WhisperEngine

class TestWhisperEngineAndEndpoints:
    def setup_method(self):
        self.client = APIClient()
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