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
        assert detect_key_provider("sk-ant-api03-example") == "anthropic"
        assert detect_key_provider("sk-example-openai-key-long-enough-35-chars") == "openai"

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

    def test_system_config_update_admin_allowed(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/config/", {
            "active_asr_model": "large-v3",
            "active_llm_engine": "gemini-1.5-pro"
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        config = SystemConfiguration.get_solo()
        assert config.active_asr_model == "large-v3"
        assert config.active_llm_engine == "gemini-1.5-pro"

    def test_system_config_update_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.nurse)
        response = self.client.post("/api/config/", {
            "active_asr_model": "tiny"
        }, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_and_delete_api_key_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        post_res = self.client.post("/api/config/keys/", {
            "name": "OpenAI Backup",
            "api_key": "sk-proj-1234567890abcdef1234567890abcdef12",
            "provider": "openai"
        }, format="json")
        assert post_res.status_code == status.HTTP_201_CREATED
        key_id = post_res.data["credential"]["id"]

        del_res = self.client.delete(f"/api/config/keys/{key_id}/")
        assert del_res.status_code == status.HTTP_200_OK
        assert not APIKeyCredential.objects.filter(id=key_id).exists()