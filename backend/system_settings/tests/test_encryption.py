import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from system_settings.models import SystemConfiguration, APIKeyCredential
from system_settings.crypto import encrypt_secret, decrypt_secret, mask_api_key, detect_key_provider

User = get_user_model()

@pytest.mark.django_db
class TestSystemSettingsAndEncryption:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin.config@hospital.com",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="Config",
            role="admin",
            is_verified=True
        )
        self.nurse = User.objects.create_user(
            email="enfermero.junior@hospital.com",
            password="NursePassword123!",
            first_name="Pedro",
            last_name="Gomez",
            role="enfermero",
            is_verified=True
        )

    def test_crypto_helpers(self):
        secret = "AIzaSySecretToken_1234567890"
        encrypted = encrypt_secret(secret)
        assert encrypted != secret
        decrypted = decrypt_secret(encrypted)
        assert decrypted == secret

        masked = mask_api_key(secret)
        assert secret not in masked
        assert masked.startswith("...")
        assert masked.endswith(secret[-4:])

        assert detect_key_provider("AIzaSyExampleKey") == "gemini"
        assert detect_key_provider("sk-ant-api03-example") == "custom"
        assert detect_key_provider("sk-example-openai-key-long-enough-35-chars") == "custom"

    def test_dedicated_encryption_key_keeps_legacy_ciphertexts_readable(self, settings):
        from cryptography.fernet import Fernet
        settings.FIELD_ENCRYPTION_KEY = ''
        legacy_cipher = encrypt_secret("AIzaSyLegacyKey000")

        settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
        new_cipher = encrypt_secret("AIzaSyNewKey111")
        # Las llaves antiguas (derivadas de SECRET_KEY) siguen descifrandose
        assert decrypt_secret(legacy_cipher) == "AIzaSyLegacyKey000"
        assert decrypt_secret(new_cipher) == "AIzaSyNewKey111"

        # Rotar SECRET_KEY ya no afecta a lo cifrado con la clave dedicada
        settings.SECRET_KEY = "otra-secret-key-rotada"
        assert decrypt_secret(new_cipher) == "AIzaSyNewKey111"

    def test_api_key_credential_model(self):
        key_cred = APIKeyCredential(name="Test Gemini Prod")
        key_cred.set_key("AIzaSyMyUltraSecretKey998877")
        key_cred.save()

        assert key_cred.encrypted_key != "AIzaSyMyUltraSecretKey998877"
        assert key_cred.get_key() == "AIzaSyMyUltraSecretKey998877"
        assert key_cred.provider == "gemini"
        assert key_cred.masked_key.startswith("...")
        assert key_cred.masked_key.endswith("8877")

    def test_system_config_get_authenticated(self):
        self.client.force_authenticate(user=self.nurse)
        response = self.client.get("/api/config/")
        assert response.status_code == status.HTTP_200_OK
        assert "config" in response.data
        assert "available_options" in response.data

    @pytest.mark.parametrize("published, label", [
        ({"model_loaded": True, "device": "cuda", "compute_type": "float16", "model_size": "large-v3-turbo"}, "GPU CUDA (NVIDIA)"),
        ({"model_loaded": True, "device": "cpu", "compute_type": "int8", "model_size": "small"}, "CPU (INT8)"),
        (None, "ASR sin iniciar"),
    ])
    def test_runtime_status_reports_asr_worker_device(self, published, label):
        from django.core.cache import cache
        from django.test import override_settings
        from transcription.tasks import ASR_STATUS_KEY
        cache.delete(ASR_STATUS_KEY)
        if published:
            cache.set(ASR_STATUS_KEY, published)
        self.client.force_authenticate(user=self.admin)
        with override_settings(CELERY_TASK_ALWAYS_EAGER=False):
            response = self.client.get("/api/config/")
        runtime = response.data["runtime_status"]
        assert runtime["hardware_device"] == label
        assert runtime["cuda_available"] is (label.startswith("GPU"))
        assert runtime["asr_model_in_use"] == (published or {}).get("model_size")
        cache.delete(ASR_STATUS_KEY)

    def test_vocabulary_sync_requires_config_permission(self):
        self.client.force_authenticate(user=self.nurse)
        denied = self.client.post("/api/config/vocabulary/sync/", {"type": "snomed"}, format="json")
        assert denied.status_code == status.HTTP_403_FORBIDDEN

        self.client.force_authenticate(user=self.admin)
        allowed = self.client.post("/api/config/vocabulary/sync/", {"type": "snomed"}, format="json")
        assert allowed.status_code == status.HTTP_200_OK

    def test_system_config_update_admin_allowed(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/config/", {
            "active_asr_model": "large-v3",
            "active_llm_engine": "gemini-3.5-flash-lite"
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        config = SystemConfiguration.get_solo()
        assert config.active_asr_model == "large-v3"
        assert config.active_llm_engine == "gemini-3.5-flash-lite"

    def test_system_config_asr_reload_after_warm_health_check_uses_stub(self):
        from transcription.whisper_engine import WhisperEngine

        health = self.client.get("/api/health_check/")
        assert health.status_code == status.HTTP_200_OK
        assert WhisperEngine._instance is not None

        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/config/", {
            "active_asr_model": "large-v3",
            "active_llm_engine": "gemini-3.5-flash-lite",
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["asr_reload"] == "encolada"
        assert WhisperEngine._instance.model_size_used == "large-v3"
        assert WhisperEngine._instance.model.__class__.__name__ == "_StubWhisperModel"

    def test_system_config_update_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.nurse)
        response = self.client.post("/api/config/", {
            "active_asr_model": "tiny"
        }, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_and_delete_api_key_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        post_res = self.client.post("/api/config/keys/", {
            "name": "Servidor local",
            "api_key": "sk-proj-1234567890abcdef1234567890abcdef12",
            "provider": "custom"
        }, format="json")
        assert post_res.status_code == status.HTTP_201_CREATED
        key_id = post_res.data["credential"]["id"]

        del_res = self.client.delete(f"/api/config/keys/{key_id}/")
        assert del_res.status_code == status.HTTP_200_OK
        assert not APIKeyCredential.objects.filter(id=key_id).exists()

    def test_create_api_key_whitespace_provider_triggers_autodetection(self):
        self.client.force_authenticate(user=self.admin)
        post_res = self.client.post("/api/config/keys/", {
            "name": "Gemini Auto Key",
            "api_key": "AIzaSyDummyGeminiKey12345678901234567890",
            "provider": "   "
        }, format="json")
        assert post_res.status_code == status.HTTP_201_CREATED
        assert post_res.data["credential"]["provider"] == "gemini"

    def test_create_api_key_invalid_provider_rejected(self):
        self.client.force_authenticate(user=self.admin)
        post_res = self.client.post("/api/config/keys/", {
            "name": "Invalid Provider Key",
            "api_key": "sk-proj-1234567890abcdef1234567890abcdef12",
            "provider": "unsupported_provider_xyz"
        }, format="json")
        assert post_res.status_code == status.HTTP_400_BAD_REQUEST

    def test_engine_status_reports_motors_without_secrets(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyEngineStatusKey1234567890")
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/config/engines/")
        assert response.status_code == status.HTTP_200_OK
        assert set(response.data) == {"inference_mode", "asr", "ner", "llm", "local_llm"}
        assert response.data["llm"]["configured"] is True
        assert "AIzaSyEngineStatusKey1234567890" not in str(response.data)

        self.client.force_authenticate(user=None)
        assert self.client.get("/api/config/engines/").status_code == status.HTTP_401_UNAUTHORIZED

    def test_engine_status_reflects_catalog_mode_and_asr_reload(self, mocker):
        from django.core.cache import cache
        from transcription.tasks import ASR_STATUS_KEY
        mocker.patch("triage.ner_model.get_ner_status", return_value={"model_loaded": True, "source": "/m/ai_triage_ner"})
        self.client.force_authenticate(user=self.admin)
        assert self.client.get("/api/config/engines/").data["ner"]["active"] is True

        reload_request = mocker.patch("transcription.tasks.request_asr_reload", return_value=True)
        response = self.client.post("/api/config/", {"active_ner_model": "catalogo"}, format="json")
        assert response.data["asr_reload"] is None  # el NER no necesita recargar nada
        reload_request.assert_not_called()
        ner = self.client.get("/api/config/engines/").data["ner"]
        assert ner["model_loaded"] is True and ner["active"] is False and ner["mode"] == "catalogo"

        response = self.client.post("/api/config/", {"active_asr_model": "base"}, format="json")
        assert response.data["asr_reload"] == "encolada"
        reload_request.assert_called_once()
        cache.set(ASR_STATUS_KEY, {"model_loaded": True, "model_size": "small", "device": "cpu", "loading": True})
        mocker.patch("transcription.tasks.worker_mode", return_value=True)
        asr = self.client.get("/api/config/engines/").data["asr"]
        assert asr["loading"] is True and asr["configured"] == "base"

    def test_sync_environment_api_keys_registers_env_vars(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestFromEnv1234567890")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-TestFromEnv1234567890abcdef")
        monkeypatch.setenv("GROQ_API_KEY", "gsk_TestDynamicFromEnv1234567890")

        self.client.force_authenticate(user=self.admin)
        get_res = self.client.get("/api/config/")
        assert get_res.status_code == status.HTTP_200_OK

        api_keys = get_res.data["api_keys"]
        key_names = [k["name"] for k in api_keys]
        assert any("Google Gemini (Entorno .env)" in name for name in key_names)
        assert any("Openai (Entorno .env)" in name for name in key_names)
        assert any("Groq (Entorno .env)" in name for name in key_names)

        gemini_cred = APIKeyCredential.objects.filter(provider="gemini").first()
        assert gemini_cred is not None
        assert gemini_cred.get_key() == "AIzaSyTestFromEnv1234567890"
        assert gemini_cred.masked_key.endswith("7890")