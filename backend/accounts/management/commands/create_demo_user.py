import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserPermission

class Command(BaseCommand):
    help = 'Creates demo users (Admin and Nurse) if they do not exist, or updates weak legacy passwords'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help='Fuerza la actualizacion de contrasenas de usuarios demo a los valores configurados en entorno',
        )

    def handle(self, *args, **kwargs):
        create_demo = os.getenv('CREATE_DEMO_USERS', 'False').lower() in ('true', '1', 'yes')
        debug_mode = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')
        reset_requested = (
            kwargs.get('reset_passwords', False)
            or os.getenv('RESET_DEMO_PASSWORDS', 'False').lower() in ('true', '1', 'yes')
        )

        if not (create_demo or debug_mode or reset_requested):
            self.stdout.write(self.style.WARNING("Creacion de usuarios demo omitida en entorno no-dev (opt-in requerido)."))
            return

        User = get_user_model()
        
        # 1. Admin / Medico Principal
        admin_email = os.getenv('DEMO_ADMIN_EMAIL', 'admin@hospital.com')
        admin_pass = os.getenv('DEMO_ADMIN_PASSWORD', 'AdminHospital2026!')
        admin_user, created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                'first_name': 'Dr. Carlos',
                'last_name': 'Rodriguez',
                'document_id': 'ADM-8492',
                'phone': '+57 300 123 4567',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True
            }
        )
        if created:
            admin_user.set_password(admin_pass)
            admin_user.save()
            UserPermission.create_defaults_for_role(admin_user)
            self.stdout.write(self.style.SUCCESS(f"Usuario admin creado exitosamente: {admin_email}"))
        else:
            admin_user.is_verified = True
            if not admin_user.first_name:
                admin_user.first_name = 'Dr. Carlos'
                admin_user.last_name = 'Rodriguez'

            # Remediar contrasena debil predeterminada antigua ("admin") o peticion explicita de reset
            if admin_user.check_password('admin') or reset_requested:
                admin_user.set_password(admin_pass)
                self.stdout.write(self.style.WARNING(f"Contrasena de {admin_email} actualizada a valor seguro."))

            admin_user.save()
            if not hasattr(admin_user, 'permissions'):
                UserPermission.create_defaults_for_role(admin_user)
            self.stdout.write(self.style.SUCCESS(f"Usuario {admin_email} verificado."))

        # 2. Personal de Enfermeria
        nurse_email = os.getenv('DEMO_NURSE_EMAIL', 'enfermeria@hospital.com')
        nurse_pass = os.getenv('DEMO_NURSE_PASSWORD', 'Enfermeria2026!')
        nurse_user, n_created = User.objects.get_or_create(
            email=nurse_email,
            defaults={
                'first_name': 'Enf. Laura',
                'last_name': 'Martinez',
                'document_id': 'ENF-1023',
                'phone': '+57 311 987 6543',
                'role': 'enfermero',
                'is_staff': False,
                'is_superuser': False,
                'is_verified': True
            }
        )
        if n_created:
            nurse_user.set_password(nurse_pass)
            nurse_user.save()
            UserPermission.create_defaults_for_role(nurse_user)
            self.stdout.write(self.style.SUCCESS(f"Usuario enfermeria creado exitosamente: {nurse_email}"))
        else:
            nurse_user.is_verified = True
            # Remediar contrasenas debiles predeterminadas antiguas ("enfermero123" / "admin") o reset explicito
            if nurse_user.check_password('enfermero123') or nurse_user.check_password('admin') or reset_requested:
                nurse_user.set_password(nurse_pass)
                self.stdout.write(self.style.WARNING(f"Contrasena de {nurse_email} actualizada a valor seguro."))

            nurse_user.save()
            if not hasattr(nurse_user, 'permissions'):
                UserPermission.create_defaults_for_role(nurse_user)
            self.stdout.write(self.style.SUCCESS(f"Usuario {nurse_email} verificado."))
