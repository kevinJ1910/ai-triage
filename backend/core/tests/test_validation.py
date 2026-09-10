import pytest
from rest_framework import serializers
from core.validation import (
    validate_payload,
    LoginSchema,
    RegisterSchema,
    VerifyCodeSchema,
    TriageOverrideSchema,
    UserPermissionUpdateSchema,
    SystemConfigUpdateSchema,
    FHIRSyncSchema
)

class TestPydanticValidationLayer:
    def test_login_schema_valid(self):
        result = validate_payload(LoginSchema, {"email": "doctor@hospital.com", "password": "password123"})
        assert result.email == "doctor@hospital.com"
        assert result.password == "password123"

    def test_login_schema_invalid_email(self):
        with pytest.raises(serializers.ValidationError):
            validate_payload(LoginSchema, {"email": "not-a-valid-email", "password": "password123"})

    def test_register_schema_password_mismatch(self):
        with pytest.raises(serializers.ValidationError):
            validate_payload(RegisterSchema, {
                "email": "medico@hospital.com",
                "password": "Password123!",
                "confirm_password": "DifferentPassword123!",
                "first_name": "Juan",
                "last_name": "Perez",
                "document_id": "DOC-123"
            })

    def test_verify_code_non_digit_rejected(self):
        with pytest.raises(serializers.ValidationError):
            validate_payload(VerifyCodeSchema, {
                "email": "medico@hospital.com",
                "code": "12A456"
            })

    def test_verify_code_invalid_length(self):
        with pytest.raises(serializers.ValidationError):
            validate_payload(VerifyCodeSchema, {
                "email": "medico@hospital.com",
                "code": "123"
            })

    def test_triage_override_level_range(self):
        # Valid level
        result = validate_payload(TriageOverrideSchema, {"final_level": 3, "override_reason": "Clinica"})
        assert result.final_level == 3

        # Invalid level 0
        with pytest.raises(serializers.ValidationError):
            validate_payload(TriageOverrideSchema, {"final_level": 0})

        # Invalid level 6
        with pytest.raises(serializers.ValidationError):
            validate_payload(TriageOverrideSchema, {"final_level": 6})

        # Non-integer level
        with pytest.raises(serializers.ValidationError):
            validate_payload(TriageOverrideSchema, {"final_level": "grave"})

    def test_permission_update_boolean_types(self):
        # Valid booleans
        result = validate_payload(UserPermissionUpdateSchema, {"can_use_transcriber": True, "can_view_fhir": False})
        assert result.can_use_transcriber is True
        assert result.can_view_fhir is False

        # Invalid boolean
        with pytest.raises(serializers.ValidationError):
            validate_payload(UserPermissionUpdateSchema, {"can_use_transcriber": "not-a-bool"})

    def test_system_config_timeout_constraints(self):
        # Valid timeout
        result = validate_payload(SystemConfigUpdateSchema, {"session_timeout_seconds": 3600})
        assert result.session_timeout_seconds == 3600

        # Out of bounds timeout (< 10s)
        with pytest.raises(serializers.ValidationError):
            validate_payload(SystemConfigUpdateSchema, {"session_timeout_seconds": 2})

    def test_fhir_sync_flexible_payload(self):
        # Valid bundle with flexible dynamic entry items
        payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "p-1"}},
                {"resource": {"resourceType": "Observation", "value": {"any_custom_key": 123}}}
            ]
        }
        result = validate_payload(FHIRSyncSchema, payload)
        assert result.resourceType == "Bundle"
        assert len(result.entry) == 2
