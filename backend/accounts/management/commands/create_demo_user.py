import os
import secrets
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from accounts.models import UserPermission

class Command(BaseCommand):
    help = 'Creates demo users (Admin and Nurse) if they do not exist, or updates weak legacy passwords'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help='Fuerza la actualizacion de contrasenas de usuarios demo a los valores configurados en entorno o generados',
        )

    def _resolve_password(self, env_var_name: str, user_label: str) -> str:
        secret = os.getenv(env_var_name)
        if secret and secret.strip():
            return secret.strip()
        generated = secrets.token_urlsafe(16) + "!A1"
        self.stdout.write(self.style.WARNING(
            f"Variable {env_var_name} no configurada. Generada contrasena de un solo uso para {user_label}: {generated}"
        ))
        return generated

    def handle(self, *args, **kwargs):
        User = get_user_model()
        reset_requested = (
            kwargs.get('reset_passwords', False)
            or os.getenv('RESET_DEMO_PASSWORDS', 'False').lower() in ('true', '1', 'yes')
        )

        admin_email = os.getenv('DEMO_ADMIN_EMAIL', 'admin@hospital.com')
        nurse_email = os.getenv('DEMO_NURSE_EMAIL', 'enfermeria@hospital.com')

        # 1. Fase de remediacion incondicional: corregir usuarios existentes con contrasenas debiles conocidas
        existing_admin = User.objects.filter(email=admin_email).first()
        if existing_admin:
            existing_admin.is_verified = True
            if existing_admin.check_password('admin') or reset_requested:
                admin_pass = self._resolve_password('DEMO_ADMIN_PASSWORD', admin_email)
                existing_admin.set_password(admin_pass)
                self.stdout.write(self.style.WARNING(f"Contrasena de {admin_email} actualizada a valor seguro."))
            existing_admin.save()
            if not hasattr(existing_admin, 'permissions'):
                UserPermission.create_defaults_for_role(existing_admin)
            self.stdout.write(self.style.SUCCESS(f"Usuario {admin_email} verificado."))

        existing_nurse = User.objects.filter(email=nurse_email).first()
        if existing_nurse:
            existing_nurse.is_verified = True
            if existing_nurse.check_password('enfermero123') or existing_nurse.check_password('admin') or reset_requested:
                nurse_pass = self._resolve_password('DEMO_NURSE_PASSWORD', nurse_email)
                existing_nurse.set_password(nurse_pass)
                self.stdout.write(self.style.WARNING(f"Contrasena de {nurse_email} actualizada a valor seguro."))
            existing_nurse.save()
            if not hasattr(existing_nurse, 'permissions'):
                UserPermission.create_defaults_for_role(existing_nurse)
            self.stdout.write(self.style.SUCCESS(f"Usuario {nurse_email} verificado."))

        # 2. Fase de creacion opt-in: restringida a CREATE_DEMO_USERS=True o settings.DEBUG=True
        create_demo = os.getenv('CREATE_DEMO_USERS', 'False').lower() in ('true', '1', 'yes')
        debug_mode = getattr(settings, 'DEBUG', False)

        if not (create_demo or debug_mode):
            self.stdout.write(self.style.WARNING("Creacion de usuarios demo omitida en entorno no-dev (opt-in requerido)."))
            return

        # Si no existian, crearlos con credenciales resueltas
        if not existing_admin:
            admin_pass = self._resolve_password('DEMO_ADMIN_PASSWORD', admin_email)
            admin_user = User.objects.create(
                email=admin_email,
                first_name='Dr. Carlos',
                last_name='Rodriguez',
                document_id='ADM-8492',
                phone='+57 300 123 4567',
                role='admin',
                is_staff=True,
                is_superuser=True,
                is_verified=True
            )
            admin_user.set_password(admin_pass)
            admin_user.save()
            UserPermission.create_defaults_for_role(admin_user)
            self.stdout.write(self.style.SUCCESS(f"Usuario admin creado exitosamente: {admin_email}"))

        if not existing_nurse:
            nurse_pass = self._resolve_password('DEMO_NURSE_PASSWORD', nurse_email)
            nurse_user = User.objects.create(
                email=nurse_email,
                first_name='Enf. Laura',
                last_name='Martinez',
                document_id='ENF-1023',
                phone='+57 311 987 6543',
                role='enfermero',
                is_staff=False,
                is_superuser=False,
                is_verified=True
            )
            nurse_user.set_password(nurse_pass)
            nurse_user.save()
            UserPermission.create_defaults_for_role(nurse_user)
            self.stdout.write(self.style.SUCCESS(f"Usuario enfermeria creado exitosamente: {nurse_email}"))
