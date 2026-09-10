import secrets
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, AuthVerificationCode, UserPermission, AuditLog
from .emails import send_verification_email, send_password_reset_email
from core.validation import (
    validate_payload,
    RegisterSchema,
    LoginSchema,
    VerifyCodeSchema,
    ResendCodeSchema,
    PasswordResetRequestSchema,
    PasswordResetConfirmSchema,
)

class UserPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPermission
        fields = [
            'can_use_transcriber',
            'can_edit_symptoms',
            'can_register_patients',
            'can_view_emr',
            'can_view_fhir',
            'can_manage_config',
        ]

class UserSerializer(serializers.ModelSerializer):
    permissions = UserPermissionSerializer(read_only=True)
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'document_id',
            'phone',
            'role',
            'is_verified',
            'permissions',
            'date_joined',
        ]

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'document_id',
            'phone',
            'role',
            'password',
            'confirm_password',
        ]

    def validate(self, data):
        validate_payload(RegisterSchema, getattr(self, 'initial_data', data))
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Las contrasenas no coinciden"})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        
        user = User(
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            document_id=validated_data.get('document_id'),
            phone=validated_data.get('phone', ''),
            role=validated_data.get('role', 'medico'),
            is_verified=False,
            is_active=True
        )
        user.set_password(password)
        user.save()

        # Generar codigo OTP de 6 digitos
        code = ''.join(secrets.choice('0123456789') for _ in range(6))
        AuthVerificationCode.objects.create(
            user=user,
            code=code,
            code_type='registration',
            expires_at=timezone.now() + timedelta(minutes=15)
        )

        # Enviar correo via SMTP local (Mailpit)
        send_verification_email(user, code)

        # Auditoria
        AuditLog.objects.create(
            user=user,
            action='USER_REGISTER_REQUEST',
            resource=f'User/{user.id}',
            status='SUCCESS',
            details='Registro inicial. Codigo OTP de verificacion enviado.'
        )

        return user

class VerifyCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, data):
        validate_payload(VerifyCodeSchema, getattr(self, 'initial_data', data))
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Usuario no encontrado"})

        otp = AuthVerificationCode.objects.filter(
            user=user,
            code=data['code'],
            code_type='registration',
            is_used=False
        ).order_by('-created_at').first()

        if not otp:
            raise serializers.ValidationError({"code": "Codigo de verificacion invalido"})

        if not otp.is_valid():
            raise serializers.ValidationError({"code": "El codigo de verificacion ha expirado"})

        data['user'] = user
        data['otp'] = otp
        return data

class ResendCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, data):
        validate_payload(ResendCodeSchema, getattr(self, 'initial_data', data))
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Usuario no encontrado"})

        if user.is_verified:
            raise serializers.ValidationError({"email": "Este usuario ya se encuentra verificado"})

        data['user'] = user
        return data

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, data):
        validate_payload(PasswordResetRequestSchema, getattr(self, 'initial_data', data))
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "No existe un usuario con este correo electronico"})
        data['user'] = user
        return data

class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(min_length=6)
    confirm_password = serializers.CharField(min_length=6)

    def validate(self, data):
        validate_payload(PasswordResetConfirmSchema, getattr(self, 'initial_data', data))
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Las contrasenas no coinciden"})

        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Usuario no encontrado"})

        otp = AuthVerificationCode.objects.filter(
            user=user,
            code=data['code'],
            code_type='password_reset',
            is_used=False
        ).order_by('-created_at').first()

        if not otp or not otp.is_valid():
            raise serializers.ValidationError({"code": "Codigo de autorizacion invalido o expirado"})

        data['user'] = user
        data['otp'] = otp
        return data

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        validate_payload(LoginSchema, getattr(self, 'initial_data', attrs))
        data = super().validate(attrs)

        if not self.user.is_verified and not self.user.is_superuser:
            raise serializers.ValidationError({
                "detail": "Tu cuenta requiere verificacion de correo previa. Introduce tu codigo OTP.",
                "code": "account_not_verified",
                "email": self.user.email
            })

        user_data = UserSerializer(self.user).data
        data['user'] = user_data

        # Registrar log de auditoria
        request = self.context.get('request')
        ip_addr = None
        if request:
            ip_addr = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
            if ip_addr and ',' in ip_addr:
                ip_addr = ip_addr.split(',')[0].strip()

        AuditLog.objects.create(
            user=self.user,
            action='LOGIN',
            resource='Auth/Session',
            status='SUCCESS',
            ip_address=ip_addr,
            details=f"Inicio de sesion exitoso como {self.user.role}"
        )

        return data
