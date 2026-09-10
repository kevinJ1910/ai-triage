import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserPermission

class Command(BaseCommand):
    help = 'Creates demo users (Admin and Nurse) if they do not exist'

    def handle(self, *args, **kwargs):
        create_demo = os.getenv('CREATE_DEMO_USERS', 'True').lower() in ('true', '1', 'yes')
        debug_mode = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')
        if not (create_demo or debug_mode):
            self.stdout.write(self.style.WARNING("Creacion de usuarios demo omitida en entorno no-dev."))
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
            admin_user.save()
            if not hasattr(admin_user, 'permissions'):
                UserPermission.create_defaults_for_role(admin_user)
            self.stdout.write(self.style.WARNING(f"Usuario {admin_email} actualizado y verificado."))

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
            nurse_user.save()
            if not hasattr(nurse_user, 'permissions'):
                UserPermission.create_defaults_for_role(nurse_user)
