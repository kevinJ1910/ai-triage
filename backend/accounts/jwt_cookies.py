"""
Refresh token JWT en cookie httpOnly.
El access token (vida corta) viaja en el cuerpo y el cliente lo guarda solo en memoria;
el refresh token nunca es accesible desde JavaScript, asi que un XSS no puede robarlo.
"""
from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

REFRESH_COOKIE_NAME = 'ai_triage_refresh'
REFRESH_COOKIE_PATH = '/api/auth/'


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
        httponly=True,
        secure=settings.JWT_COOKIE_SECURE,
        samesite='Strict',
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, samesite='Strict')


def move_refresh_to_cookie(response: Response) -> Response:
    """Saca 'refresh' del cuerpo de una respuesta exitosa y lo coloca en la cookie httpOnly."""
    if response.status_code < 400 and isinstance(response.data, dict) and 'refresh' in response.data:
        set_refresh_cookie(response, response.data.pop('refresh'))
    return response


class CookieTokenRefreshView(APIView):
    """Renueva el access token usando el refresh token de la cookie (rota y vuelve a fijar la cookie)."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not refresh:
            return Response({"detail": "Sesion no iniciada."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = TokenRefreshSerializer(data={'refresh': refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken):
            response = Response({"detail": "Sesion expirada."}, status=status.HTTP_401_UNAUTHORIZED)
            clear_refresh_cookie(response)
            return response

        return move_refresh_to_cookie(Response(dict(serializer.validated_data), status=status.HTTP_200_OK))


class LogoutView(APIView):
    """Invalida (blacklist) el refresh token de la cookie y la elimina."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # Ya expirado o invalido: basta con borrar la cookie
        response = Response({"detail": "Sesion cerrada."}, status=status.HTTP_200_OK)
        clear_refresh_cookie(response)
        return response
