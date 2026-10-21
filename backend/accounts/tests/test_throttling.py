import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


@pytest.mark.django_db
class TestAuthThrottling:
    def setup_method(self):
        self.client = APIClient()
        User.objects.create_user(
            email="victima@hospital.com", password="SecurePassword123!", role="medico", is_verified=True
        )

    def test_login_is_limited_to_10_attempts_per_minute(self):
        payload = {"email": "victima@hospital.com", "password": "contrasena-incorrecta"}
        codes = [self.client.post("/api/auth/login/", payload, format="json").status_code for _ in range(11)]
        assert codes[:10] == [status.HTTP_401_UNAUTHORIZED] * 10
        assert codes[10] == status.HTTP_429_TOO_MANY_REQUESTS

    def test_password_reset_confirm_is_limited_to_5_attempts_per_minute(self):
        payload = {"email": "victima@hospital.com", "code": "000000", "new_password": "NuevaClave123!"}
        codes = [
            self.client.post("/api/auth/password-reset/confirm/", payload, format="json").status_code
            for _ in range(6)
        ]
        assert status.HTTP_429_TOO_MANY_REQUESTS not in codes[:5]
        assert codes[5] == status.HTTP_429_TOO_MANY_REQUESTS
