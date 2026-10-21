from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from datetime import timedelta

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email debe ser especificado')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        
        if not hasattr(user, 'permissions'):
            UserPermission.create_defaults_for_role(user)
            
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('admin', 'Administrador'),
        ('medico', 'Medico'),
        ('enfermero', 'Enfermero'),
    )
    email = models.EmailField(unique=True, max_length=255)
    first_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=150, blank=True, default='')
    document_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    phone = models.CharField(max_length=50, blank=True, default='')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='medico')
    is_verified = models.BooleanField(default=False, help_text="Indica si el correo fue verificado con codigo OTP")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else self.email.split('@')[0]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

class AuthVerificationCode(models.Model):
    CODE_TYPE_CHOICES = (
        ('registration', 'Registro'),
        ('password_reset', 'Recuperacion de Contrasena'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_codes')
    code = models.CharField(max_length=6, db_index=True)
    code_type = models.CharField(max_length=20, choices=CODE_TYPE_CHOICES, default='registration')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'code', 'is_used'], name='auth_code_lookup_idx'),
        ]

    def is_valid(self):
        return (not self.is_used) and (timezone.now() <= self.expires_at)

    def __str__(self):
        return f"{self.user.email} - {self.code} ({self.code_type})"

class UserPermission(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='permissions')
    can_use_transcriber = models.BooleanField(default=True, help_text="Permiso para usar transcriptor ASR en vivo")
    can_edit_symptoms = models.BooleanField(default=True, help_text="Permiso para modificar sintomas y cambiar nivel de triaje")
    can_register_patients = models.BooleanField(default=True, help_text="Permiso para crear y registrar pacientes")
    can_view_emr = models.BooleanField(default=True, help_text="Permiso para ver historial clinico HCE")
    can_view_fhir = models.BooleanField(default=True, help_text="Permiso para auditar interoperabilidad FHIR")
    can_manage_config = models.BooleanField(default=False, help_text="Permiso de administracion de modelos y llaves API")

    @classmethod
    def create_defaults_for_role(cls, user):
        role = getattr(user, 'role', 'medico')
        is_admin = (role == 'admin' or user.is_superuser)
        is_nurse = (role == 'enfermero')
        
        return cls.objects.create(
            user=user,
            can_use_transcriber=True,
            can_edit_symptoms=not is_nurse,
            can_register_patients=True,
            can_view_emr=True,
            can_view_fhir=is_admin or not is_nurse,
            can_manage_config=is_admin
        )

    def __str__(self):
        return f"Permisos para {self.user.email}"

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=50, db_index=True)
    resource = models.CharField(max_length=150)
    status = models.CharField(max_length=20, default='SUCCESS')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp'], name='audit_log_time_idx'),
            models.Index(fields=['action', '-timestamp'], name='audit_log_action_idx'),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.user} - {self.action} ({self.status})"
