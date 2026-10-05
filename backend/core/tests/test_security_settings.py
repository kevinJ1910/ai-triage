from django.conf import settings
from django.test import RequestFactory


class TestSecuritySettings:
    def test_forwarded_proto_from_nginx_marks_request_secure(self):
        factory = RequestFactory()
        assert factory.get("/api/health_check/", HTTP_X_FORWARDED_PROTO="https").is_secure()
        assert not factory.get("/api/health_check/", HTTP_X_FORWARDED_PROTO="http").is_secure()

    def test_cookies_follow_secure_cookies_flag(self):
        assert settings.SESSION_COOKIE_SECURE is settings.SECURE_COOKIES
        assert settings.CSRF_COOKIE_SECURE is settings.SECURE_COOKIES

    def test_django_security_headers_on_api_responses(self, client):
        response = client.get("/api/health_check/")
        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["X-Frame-Options"] == "DENY"
        assert response["Referrer-Policy"] == "same-origin"
