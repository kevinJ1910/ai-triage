import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()

@pytest.mark.django_db
class TestAuthEndpoints:
    def setup_method(self):
        self.client = APIClient()
        self.user_password = "SecurePassword123!"
        self.user = User.objects.create_user(
            email="testuser@hospital.com",
            password=self.user_password,
            first_name="Carlos",
            last_name="Gomez",
            role="medico",
            is_verified=True,
            is_active=True
        )

    def test_login_success(self):
        response = self.client.post("/api/auth/login/", {
            "email": "testuser@hospital.com",
            "password": self.user_password
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        # El refresh token nunca viaja en el cuerpo: solo en cookie httpOnly
        assert "refresh" not in response.data
        cookie = response.cookies["ai_triage_refresh"]
        assert cookie["httponly"]
        assert cookie["samesite"] == "Strict"
        assert cookie["path"] == "/api/auth/"
        assert response.data["user"]["email"] == "testuser@hospital.com"
        assert response.data["user"]["role"] == "medico"

    def _login(self):
        return self.client.post("/api/auth/login/", {
            "email": "testuser@hospital.com",
            "password": self.user_password
        }, format="json")

    def test_refresh_with_cookie_rotates_token(self):
        login = self._login()
        old_refresh = login.cookies["ai_triage_refresh"].value

        response = self.client.post("/api/auth/refresh/")
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" not in response.data
        new_refresh = response.cookies["ai_triage_refresh"].value
        assert new_refresh and new_refresh != old_refresh

        # El refresh anterior queda en lista negra tras la rotacion
        self.client.cookies["ai_triage_refresh"] = old_refresh
        assert self.client.post("/api/auth/refresh/").status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_without_cookie_is_unauthorized(self):
        assert self.client.post("/api/auth/refresh/").status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_blacklists_refresh_and_clears_cookie(self):
        login = self._login()
        refresh = login.cookies["ai_triage_refresh"].value

        response = self.client.post("/api/auth/logout/")
        assert response.status_code == status.HTTP_200_OK
        assert response.cookies["ai_triage_refresh"].value == ""

        self.client.cookies["ai_triage_refresh"] = refresh
        assert self.client.post("/api/auth/refresh/").status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_invalid_password(self):
        response = self.client.post("/api/auth/login/", {
            "email": "testuser@hospital.com",
            "password": "WrongPassword!"
        }, format="json")
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED]

    def test_login_unregistered_email(self):
        response = self.client.post("/api/auth/login/", {
            "email": "nonexistent@hospital.com",
            "password": self.user_password
        }, format="json")
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED]

    def test_register_success(self):
        payload = {
            "email": "newdoctor@hospital.com",
            "password": "NewSecurePassword456!",
            "confirm_password": "NewSecurePassword456!",
            "first_name": "Laura",
            "last_name": "Perez",
            "role": "medico",
            "document_id": "DOC-998877",
            "phone": "+573001234567"
        }
        response = self.client.post("/api/auth/register/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert "email" in response.data or "message" in response.data
        created_user = User.objects.get(email="newdoctor@hospital.com")
        assert created_user.first_name == "Laura"
        assert created_user.role == "medico"
        assert created_user.document_id == "DOC-998877"

    def test_register_password_mismatch(self):
        payload = {
            "email": "mismatch@hospital.com",
            "password": "NewSecurePassword456!",
            "confirm_password": "DifferentPassword789!",
            "first_name": "Laura",
            "last_name": "Perez",
            "role": "medico"
        }
        response = self.client.post("/api/auth/register/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "confirm_password" in response.data

    def test_register_duplicate_email(self):
        payload = {
            "email": "testuser@hospital.com",
            "password": "AnyPassword123!",
            "confirm_password": "AnyPassword123!",
            "first_name": "Carlos",
            "last_name": "Gomez",
            "role": "medico"
        }
        response = self.client.post("/api/auth/register/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_profile_me_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == "testuser@hospital.com"
        assert response.data["first_name"] == "Carlos"
        assert "permissions" in response.data

    def test_user_profile_me_unauthenticated(self):
        response = self.client.get("/api/auth/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED