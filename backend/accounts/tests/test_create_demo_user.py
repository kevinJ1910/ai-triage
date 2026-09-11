import os
from io import StringIO
import pytest
from django.core.management import call_command
from django.contrib.auth import get_user_model

@pytest.mark.django_db
class TestCreateDemoUserCommand:
    def setup_method(self):
        self.User = get_user_model()
        self.admin_email = 'admin@hospital.com'
        self.nurse_email = 'enfermeria@hospital.com'

    def test_default_skip_in_non_dev(self, monkeypatch, settings):
        settings.DEBUG = False
        monkeypatch.setenv('CREATE_DEMO_USERS', 'False')
        monkeypatch.setenv('RESET_DEMO_PASSWORDS', 'False')

        out = StringIO()
        call_command('create_demo_user', stdout=out)
        output = out.getvalue()

        assert "omitida en entorno no-dev" in output
        assert not self.User.objects.filter(email=self.admin_email).exists()
        assert not self.User.objects.filter(email=self.nurse_email).exists()

    def test_opt_in_creation_via_env(self, monkeypatch, settings):
        settings.DEBUG = False
        monkeypatch.setenv('CREATE_DEMO_USERS', 'True')
        monkeypatch.setenv('DEMO_ADMIN_PASSWORD', 'SecureAdminPass2026!')
        monkeypatch.setenv('DEMO_NURSE_PASSWORD', 'SecureNursePass2026!')

        out = StringIO()
        call_command('create_demo_user', stdout=out)
        output = out.getvalue()

        assert "Usuario admin creado exitosamente" in output
        assert "Usuario enfermeria creado exitosamente" in output

        admin_user = self.User.objects.get(email=self.admin_email)
        nurse_user = self.User.objects.get(email=self.nurse_email)

        assert admin_user.check_password('SecureAdminPass2026!')
        assert nurse_user.check_password('SecureNursePass2026!')
        assert admin_user.is_verified is True
        assert nurse_user.is_verified is True
        assert hasattr(admin_user, 'permissions')
        assert hasattr(nurse_user, 'permissions')

    def test_opt_in_creation_via_debug_with_generated_passwords(self, monkeypatch, settings):
        settings.DEBUG = True
        monkeypatch.setenv('CREATE_DEMO_USERS', 'False')
        monkeypatch.delenv('DEMO_ADMIN_PASSWORD', raising=False)
        monkeypatch.delenv('DEMO_NURSE_PASSWORD', raising=False)

        out = StringIO()
        call_command('create_demo_user', stdout=out)
        output = out.getvalue()

        assert "Generada contrasena de un solo uso" in output
        assert self.User.objects.filter(email=self.admin_email).exists()
        assert self.User.objects.filter(email=self.nurse_email).exists()

    def test_remediation_of_weak_passwords_in_production(self, monkeypatch, settings):
        # Simular entorno produccion (no dev, creacion deshabilitada)
        settings.DEBUG = False
        monkeypatch.setenv('CREATE_DEMO_USERS', 'False')
        monkeypatch.setenv('DEMO_ADMIN_PASSWORD', 'FixedRemediatedPass123!')
        monkeypatch.setenv('DEMO_NURSE_PASSWORD', 'FixedRemediatedPass456!')

        # Crear usuarios existentes con claves debiles conocidas
        admin = self.User.objects.create_user(
            email=self.admin_email,
            password='admin',
            role='admin'
        )
        nurse = self.User.objects.create_user(
            email=self.nurse_email,
            password='enfermero123',
            role='enfermero'
        )

        assert admin.check_password('admin')
        assert nurse.check_password('enfermero123')

        out = StringIO()
        call_command('create_demo_user', stdout=out)
        output = out.getvalue()

        assert "remediada" in output.lower() or "actualizada" in output.lower()

        admin.refresh_from_db()
        nurse.refresh_from_db()

        # Las claves debiles ya no deben ser validas
        assert not admin.check_password('admin')
        assert not nurse.check_password('enfermero123')

        # Deben haber tomado la clave remediada segura
        assert admin.check_password('FixedRemediatedPass123!')
        assert nurse.check_password('FixedRemediatedPass456!')

    def test_reset_passwords_argument(self, monkeypatch, settings):
        settings.DEBUG = False
        monkeypatch.setenv('CREATE_DEMO_USERS', 'False')
        monkeypatch.setenv('DEMO_ADMIN_PASSWORD', 'ForceResetAdminPass!')
        monkeypatch.setenv('DEMO_NURSE_PASSWORD', 'ForceResetNursePass!')

        # Usuarios con contrasenas personalizadas previas
        admin = self.User.objects.create_user(
            email=self.admin_email,
            password='CustomStrongInitialPass1!',
            role='admin'
        )
        nurse = self.User.objects.create_user(
            email=self.nurse_email,
            password='CustomStrongInitialPass2!',
            role='enfermero'
        )

        out = StringIO()
        call_command('create_demo_user', reset_passwords=True, stdout=out)

        admin.refresh_from_db()
        nurse.refresh_from_db()

        assert admin.check_password('ForceResetAdminPass!')
        assert nurse.check_password('ForceResetNursePass!')
