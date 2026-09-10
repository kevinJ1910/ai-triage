import secrets
from datetime import timedelta
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, AuthVerificationCode, UserPermission, AuditLog
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    VerifyCodeSerializer,
    ResendCodeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    CustomTokenObtainPairSerializer,
    UserPermissionSerializer
)
from .emails import send_verification_email, send_password_reset_email
from .throttles import AuthThrottle, OTPThrottle

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "Registro exitoso. Se ha enviado un codigo de verificacion a tu correo.",
                "email": user.email,
                "requires_verification": True
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = VerifyCodeSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            otp = serializer.validated_data['otp']

            otp.is_used = True
            otp.save()

            user.is_verified = True
            user.save()

            # Emitir JWT de sesion inmediatamente
            refresh = RefreshToken.for_user(user)
            user_data = UserSerializer(user).data

            AuditLog.objects.create(
                user=user,
                action='EMAIL_VERIFIED',
                resource=f'User/{user.id}',
                status='SUCCESS',
                details='Cuenta verificada satisfactoriamente via OTP.'
            )

            return Response({
                "message": "Correo verificado exitosamente. Bienvenido a AI-Triage.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": user_data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResendCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = ResendCodeSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Invalidar codigos anteriores
            AuthVerificationCode.objects.filter(user=user, code_type='registration', is_used=False).update(is_used=True)

            code = ''.join(secrets.choice('0123456789') for _ in range(6))
            AuthVerificationCode.objects.create(
                user=user,
                code=code,
                code_type='registration',
                expires_at=timezone.now() + timedelta(minutes=15)
            )

            send_verification_email(user, code)
            return Response({"message": "Nuevo codigo OTP enviado a tu correo."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            AuthVerificationCode.objects.filter(user=user, code_type='password_reset', is_used=False).update(is_used=True)

            code = ''.join(secrets.choice('0123456789') for _ in range(6))
            AuthVerificationCode.objects.create(
                user=user,
                code=code,
                code_type='password_reset',
                expires_at=timezone.now() + timedelta(minutes=15)
            )

            send_password_reset_email(user, code)

            AuditLog.objects.create(
                user=user,
                action='PASSWORD_RESET_REQUEST',
                resource=f'User/{user.id}',
                status='SUCCESS',
                details='Peticion de recuperacion de clave generada.'
            )

            return Response({
                "message": "Codigo de restablecimiento enviado a tu correo.",
                "email": user.email
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            otp = serializer.validated_data['otp']
            new_password = serializer.validated_data['new_password']

            otp.is_used = True
            otp.save()

            user.set_password(new_password)
            user.save()

            AuditLog.objects.create(
                user=user,
                action='PASSWORD_RESET_SUCCESS',
                resource=f'User/{user.id}',
                status='SUCCESS',
                details='Contrasena reestablecida exitosamente con OTP.'
            )

            return Response({"message": "Contrasena actualizada con exito. Ya puedes iniciar sesion."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

# RBAC y Auditoria Views
class UserListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Admins ven todos los usuarios, otros roles solo ven informacion basica
        users = User.objects.all().select_related('permissions').order_by('id')
        data = UserSerializer(users, many=True).data
        return Response(data)

from core.validation import validate_payload, UserPermissionUpdateSchema

class UserPermissionUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, user_id):
        if not (request.user.role == 'admin' or request.user.is_superuser):
            return Response({"detail": "Permiso denegado. Solo administradores pueden modificar roles y permisos."}, status=status.HTTP_403_FORBIDDEN)

        try:
            validate_payload(UserPermissionUpdateSchema, request.data)
        except Exception as e:
            return Response(getattr(e, 'detail', {"detail": str(e)}), status=status.HTTP_400_BAD_REQUEST)

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        perm, _ = UserPermission.objects.get_or_create(user=target_user)
        serializer = UserPermissionSerializer(perm, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            AuditLog.objects.create(
                user=request.user,
                action='RBAC_PERMISSION_CHANGE',
                resource=f'UserPermission/{target_user.id}',
                status='SUCCESS',
                details=f"Permisos modificados para {target_user.email}: {request.data}"
            )

            return Response(UserSerializer(target_user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AuditLogListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get('limit', 50))
        logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:limit]
        data = [{
            "id": log.id,
            "timestamp": log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "user": log.user.full_name if log.user else 'Sistema/Anonimo',
            "user_email": log.user.email if log.user else 'N/A',
            "role": log.user.role if log.user else 'system',
            "action": log.action,
            "resource": log.resource,
            "status": log.status,
            "ip_address": log.ip_address,
            "details": log.details
        } for log in logs]
        return Response(data)
