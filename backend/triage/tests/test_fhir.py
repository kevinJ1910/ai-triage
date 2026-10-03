import json
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from triage.models import FHIRMessageLog, FHIRRecord, TriageSession
from patients.models import Patient

User = get_user_model()

@pytest.mark.django_db
class TestFHIRIntegration:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="fhir_tester@hospital.com", password="Password123!", role="medico", is_verified=True
        )
        self.client.force_authenticate(user=self.user)
        self.patient = Patient.objects.create(
            document_id="CC-FHIR-01",
            full_name="Patricia Beltran",
            gender="female"
        )
        self.session = TriageSession.objects.create(
            patient=self.patient,
            level=2,
            ai_level=2,
            final_level=2,
            justification="Caso agudo"
        )

    def test_fhir_message_log_creation(self):
        log = FHIRMessageLog.objects.create(
            session=self.session,
            resource_type="Bundle",
            direction="OUTBOUND",
            status_code=201,
            fhir_resource_id="enc-live-9999",
            validation_status="VALID",
            validation_details="Validacion HL7 FHIR R4 superada",
            payload={"resourceType": "Bundle", "type": "transaction"}
        )
        assert log.id is not None
        assert log.session == self.session
        assert log.validation_status == "VALID"

    def test_fhir_logs_endpoint(self):
        FHIRMessageLog.objects.create(
            session=self.session,
            resource_type="Bundle",
            direction="OUTBOUND",
            status_code=201,
            fhir_resource_id="enc-test-1234",
            validation_status="VALID",
            validation_details="Bundle correcto",
            payload={"entry": []}
        )
        response = self.client.get("/api/triage/sessions/fhir_logs/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        first_log = response.data[0]
        assert first_log["fhir_resource_id"] == "enc-test-1234"
        assert first_log["validation_status"] == "VALID"

    def test_fhir_sync_post_valid_bundle(self):
        bundle_payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": f"pat-{self.session.id}-test",
                        "name": [{"text": "Patricia Beltran"}]
                    }
                },
                {
                    "resource": {
                        "resourceType": "Encounter",
                        "id": f"enc-{self.session.id}-test",
                        "status": "arrived",
                        "class": {"code": "EMER", "display": "Emergencia"}
                    }
                }
            ]
        }
        response = self.client.post(
            "/api/fhir/",
            data=json.dumps(bundle_payload),
            content_type="application/json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["message"] == "Resource created"

        # Validar persistencia en BD
        log_entry = FHIRMessageLog.objects.filter(session=self.session).first()
        assert log_entry is not None
        assert log_entry.status_code == 201

    def test_fhir_sync_rejects_structurally_invalid_bundle(self):
        bundle_payload = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {"resource": {"resourceType": "Encounter", "id": f"enc-{self.session.id}-x"}},  # sin status ni class
                {"resource": {"resourceType": "Observation", "code": {"text": "Nivel"}}},  # sin status
            ]
        }
        response = self.client.post("/api/fhir/", data=json.dumps(bundle_payload), content_type="application/json")
        assert response.status_code == 422
        details = response.json()["details"]
        assert "Encounter.status" in details
        assert "Encounter.class" in details
        assert "Observation.status" in details

        log_entry = FHIRMessageLog.objects.get(session=self.session)
        assert log_entry.validation_status == "ERROR"
        assert log_entry.status_code == 422
        assert not FHIRRecord.objects.filter(triage_session=self.session).exists()

    def test_fhir_sync_rejects_unknown_bundle_type(self):
        response = self.client.post(
            "/api/fhir/",
            data=json.dumps({"resourceType": "Bundle", "type": "inventado", "entry": []}),
            content_type="application/json"
        )
        assert response.status_code == 422

    def test_fhir_endpoints_require_authentication(self):
        anon = APIClient()
        assert anon.get("/api/triage/sessions/fhir_logs/").status_code == status.HTTP_401_UNAUTHORIZED
        res = anon.post("/api/fhir/", data=json.dumps({"resourceType": "Bundle"}), content_type="application/json")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert FHIRMessageLog.objects.count() == 0

    def test_fhir_sync_post_invalid_json(self):
        response = self.client.post(
            "/api/fhir/",
            data="Invalid JSON String",
            content_type="application/json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST