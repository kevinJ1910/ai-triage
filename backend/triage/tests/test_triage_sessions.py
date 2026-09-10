import pytest
from rest_framework.test import APIClient
from rest_framework import status
from patients.models import Patient
from triage.models import TriageSession

@pytest.mark.django_db
class TestTriageSessions:
    def setup_method(self):
        self.client = APIClient()
        self.patient = Patient.objects.create(
            document_id="CC-TRIAGE-001",
            full_name="Alejandro Morales",
            gender="male"
        )

    def test_triage_session_save_concordance(self):
        # 1. Total concordancia
        s1 = TriageSession.objects.create(
            patient=self.patient,
            level=3,
            ai_level=3,
            final_level=3,
            justification="Dolor abdominal moderado"
        )
        assert s1.agreement_score == 1.0
        assert s1.is_level_modified is False

        # 2. Modificacion por el medico
        s2 = TriageSession.objects.create(
            patient=self.patient,
            level=2,
            ai_level=2,
            final_level=3,
            justification="Ajuste a urgencia menor"
        )
        assert s2.agreement_score == 0.75
        assert s2.is_level_modified is True

        # 3. Maxima discrepancia (Nivel 1 vs Nivel 5)
        s3 = TriageSession.objects.create(
            patient=self.patient,
            level=5,
            ai_level=1,
            final_level=5,
            justification="Discrepancia critica"
        )
        assert s3.agreement_score == 0.0
        assert s3.is_level_modified is True

    def test_override_level_action(self):
        session = TriageSession.objects.create(
            patient=self.patient,
            level=4,
            ai_level=4,
            final_level=4,
            justification="Inicial nivel 4"
        )
        response = self.client.patch(f"/api/triage/sessions/{session.id}/override_level/", {
            "final_level": 2,
            "override_reason": "Paciente presenta bradicardia subita",
            "final_symptoms": ["Dolor toracico", "Bradicardia"]
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        session.refresh_from_db()
        assert session.final_level == 2
        assert session.level == 2
        assert session.is_level_modified is True
        assert session.agreement_score == 0.5
        assert "Bradicardia" in session.final_symptoms

    def test_evaluation_metrics_empty(self):
        response = self.client.get("/api/triage/sessions/evaluation_metrics/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_triages"] == 0
        assert "concordance_rate" in response.data
        assert "cohen_kappa" in response.data

    def test_evaluation_metrics_with_data(self):
        TriageSession.objects.create(
            patient=self.patient,
            level=2,
            ai_level=2,
            final_level=2,
            justification="Caso 1"
        )
        TriageSession.objects.create(
            patient=self.patient,
            level=3,
            ai_level=2,
            final_level=3,
            justification="Caso 2 modificado"
        )
        response = self.client.get("/api/triage/sessions/evaluation_metrics/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_triages"] == 2
        assert response.data["modified_count"] == 1
        assert response.data["unmodified_count"] == 1
        assert 0.0 <= response.data["concordance_rate"] <= 100.0

    def test_emr_patients_endpoint(self):
        TriageSession.objects.create(
            patient=self.patient,
            level=2,
            ai_level=2,
            final_level=2,
            justification="Atencion inmediata en box",
            clinical_entities={"vitals": {"fc": "110", "ta": "140/90"}}
        )
        response = self.client.get("/api/triage/sessions/emr_patients/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        first_patient = response.data[0]
        assert first_patient["name"] == "Alejandro Morales"
        assert first_patient["document_id"] == "CC-TRIAGE-001"
        assert "assigned_box" in first_patient

    def test_assign_box_endpoint_success(self):
        session = TriageSession.objects.create(
            patient=self.patient,
            level=3,
            ai_level=3,
            final_level=3,
            justification="Paciente para box 3",
            clinical_entities={"vitals": {"fc": "88"}}
        )
        response = self.client.post(
            f"/api/triage/sessions/{session.id}/assign_box/",
            data={"box_name": "BOX-03"},
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["assigned_box"] == "BOX-03"
        assert response.data["status"] == "En Atencion"

        session.refresh_from_db()
        assert session.clinical_entities["assigned_box"] == "BOX-03"
        assert session.clinical_entities["status"] == "En Atencion"

    def test_assign_box_endpoint_invalid_name(self):
        session = TriageSession.objects.create(
            patient=self.patient,
            level=3,
            ai_level=3,
            final_level=3,
            justification="Paciente para box invalido"
        )
        response = self.client.post(
            f"/api/triage/sessions/{session.id}/assign_box/",
            data={"box_name": ""},
            format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST