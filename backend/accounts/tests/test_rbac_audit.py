import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import UserPermission, AuditLog

User = get_user_model()

@pytest.mark.django_db
class TestRBACAndAudit:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin.security@hospital.com",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="Master",
            role="admin",
            is_verified=True
        )
        self.doctor = User.objects.create_user(
            email="doctor.junior@hospital.com",
            password="DoctorPassword123!",
            first_name="Juan",
            last_name="Perez",
            role="medico",
            is_verified=True
        )
        # Permisos creados automaticamente en create_user
        UserPermission.objects.filter(user=self.doctor).update(
            can_use_transcriber=True,
            can_edit_symptoms=True,
            can_manage_config=False
        )

    def test_user_list_authenticated(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/security/users/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2
        emails = [u["email"] for u in response.data]
        assert "doctor.junior@hospital.com" in emails

    def test_admin_can_update_permissions(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(f"/api/security/users/{self.doctor.id}/permissions/", {
            "can_manage_config": True,
            "can_edit_symptoms": False
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["permissions"]["can_manage_config"] is True
        assert response.data["permissions"]["can_edit_symptoms"] is False

        perm = UserPermission.objects.get(user=self.doctor)
        assert perm.can_manage_config is True
        assert perm.can_edit_symptoms is False

    def test_non_admin_cannot_update_permissions(self):
        self.client.force_authenticate(user=self.doctor)
        response = self.client.patch(f"/api/security/users/{self.admin.id}/permissions/", {
            "can_manage_config": False
        }, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_permission_change_creates_audit_log(self):
        self.client.force_authenticate(user=self.admin)
        initial_log_count = AuditLog.objects.filter(action="RBAC_PERMISSION_CHANGE").count()

        self.client.patch(f"/api/security/users/{self.doctor.id}/permissions/", {
            "can_use_transcriber": False
        }, format="json")

        new_log_count = AuditLog.objects.filter(action="RBAC_PERMISSION_CHANGE").count()
        assert new_log_count == initial_log_count + 1

        last_log = AuditLog.objects.filter(action="RBAC_PERMISSION_CHANGE").first()
        assert last_log.user == self.admin
        assert f"UserPermission/{self.doctor.id}" in last_log.resource

    def test_audit_logs_list(self):
        AuditLog.objects.create(
            user=self.admin,
            action="SYSTEM_CHECK",
            resource="System/Health",
            status="SUCCESS",
            details="Verificacion rutinaria de integridad"
        )
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/security/audit-logs/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        actions = [log["action"] for log in response.data]
        assert "SYSTEM_CHECK" in actions