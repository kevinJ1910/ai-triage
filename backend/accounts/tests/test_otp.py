from datetime import timedelta
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import AuthVerificationCode

User = get_user_model()

@pytest.mark.django_db
class TestOTPAndVerification:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="doctor.unverified@hospital.com",
            password="InitialPassword123!",
            first_name="Andres",
            last_name="Castro",
            role="medico",
            is_verified=False
        )

    def test_verify_code_success(self):
        otp = AuthVerificationCode.objects.create(
            user=self.user,
            code="123456",
            code_type="registration",
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        response = self.client.post("/api/auth/verify-code/", {
            "email": self.user.email,
            "code": "123456"
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

        self.user.refresh_from_db()
        assert self.user.is_verified is True
        otp.refresh_from_db()
        assert otp.is_used is True

    def test_verify_code_wrong_code(self):
        AuthVerificationCode.objects.create(
            user=self.user,
            code="123456",
            code_type="registration",
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        response = self.client.post("/api/auth/verify-code/", {
            "email": self.user.email,
            "code": "999999"
        }, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_code_expired(self):
        AuthVerificationCode.objects.create(
            user=self.user,
            code="654321",
            code_type="registration",
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = self.client.post("/api/auth/verify-code/", {
            "email": self.user.email,
            "code": "654321"
        }, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_resend_code_success(self):
        AuthVerificationCode.objects.create(
            user=self.user,
            code="111111",
            code_type="registration",
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        response = self.client.post("/api/auth/resend-code/", {
            "email": self.user.email
        }, format="json")
        assert response.status_code == status.HTTP_200_OK

        codes = AuthVerificationCode.objects.filter(user=self.user, code_type="registration", is_used=False)
        assert codes.count() >= 1

    def test_password_reset_flow(self):
        # Usuario previamente verificado
        self.user.is_verified = True
        self.user.save()

        # 1. Solicitar recuperacion
        req_res = self.client.post("/api/auth/password-reset/request/", {
            "email": self.user.email
        }, format="json")
        assert req_res.status_code == status.HTTP_200_OK

        reset_code = AuthVerificationCode.objects.filter(
            user=self.user,
            code_type="password_reset",
            is_used=False
        ).first()
        assert reset_code is not None

        # 2. Confirmar cambio con codigo
        new_pw = "BrandNewPassword789!"
        confirm_res = self.client.post("/api/auth/password-reset/confirm/", {
            "email": self.user.email,
            "code": reset_code.code,
            "new_password": new_pw,
            "confirm_password": new_pw
        }, format="json")
        assert confirm_res.status_code == status.HTTP_200_OK

        # 3. Validar login con la nueva contrasena
        login_res = self.client.post("/api/auth/login/", {
            "email": self.user.email,
            "password": new_pw
        }, format="json")
        assert login_res.status_code == status.HTTP_200_OK