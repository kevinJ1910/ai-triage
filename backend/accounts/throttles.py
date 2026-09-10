"""
Clases de throttle especificas para endpoints de autenticacion y OTP.
Previenen ataques de brute-force sobre login, registro y verificacion de codigos.
"""
from rest_framework.throttling import AnonRateThrottle


class AuthThrottle(AnonRateThrottle):
    """Limite de 10 peticiones por minuto para endpoints de autenticacion."""
    scope = 'auth'


class OTPThrottle(AnonRateThrottle):
    """Limite de 5 peticiones por minuto para endpoints de verificacion OTP."""
    scope = 'otp'
