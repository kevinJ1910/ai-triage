import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from patients.models import Patient
from triage.models import TriageSession

User = get_user_model()

@pytest.mark.django_db
class TestTriageSessions:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="doctor_triage@hospital.com",
            password="Password123!",
            role="medico",
            is_verified=True
        )
        self.client.force_authenticate(user=self.user)
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

    def test_override_justification_action(self):
        session = TriageSession.objects.create(
            patient=self.patient,
            level=3,
            ai_level=3,
            final_level=3,
            justification="Justificacion generada por IA"
        )
        response = self.client.patch(f"/api/triage/sessions/{session.id}/override_level/", {
            "justification": "Criterio medico actualizado: Dolor pleuritico con antecedentes relevantes.",
            "override_reason": "Edicion de justificacion clinica por medico"
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        session.refresh_from_db()
        assert session.justification == "Criterio medico actualizado: Dolor pleuritico con antecedentes relevantes."
        assert session.final_level == 3

    def test_evaluation_metrics_empty(self):
        response = self.client.get("/api/triage/sessions/evaluation_metrics/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["total_triages"] == 0
        # Sin sesiones no se inventan valores de demostracion
        assert response.data["concordance_rate"] is None
        assert response.data["cohen_kappa"] is None
        assert response.data["symptom_retention"] is None
        assert response.data["kappa_interpretation"] == "Sin datos suficientes"

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
        assert response.data["kappa_type"] == "quadratic_weighted"
        assert response.data["confusion_matrix"][1][1] == 1  # IA 2 -> medico 2
        assert response.data["confusion_matrix"][1][2] == 1  # IA 2 -> medico 3
        assert response.data["overtriage_rate"] == 50.0
        assert response.data["undertriage_rate"] == 0.0

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
        # Sin asignacion real no se inventa ubicacion
        assert first_patient["assigned_box"] == ""
        assert first_patient["status"] == "Pendiente de Box"

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

    def test_unauthenticated_requests_blocked(self):
        unauth_client = APIClient()
        session = TriageSession.objects.create(
            patient=self.patient,
            level=3,
            ai_level=3,
            final_level=3,
            justification="Sesion para prueba auth"
        )
        # Mutaciones sin auth son bloqueadas con 401
        res_override = unauth_client.patch(
            f"/api/triage/sessions/{session.id}/override_level/",
            data={"final_level": 2},
            format="json"
        )
        assert res_override.status_code == status.HTTP_401_UNAUTHORIZED

        res_box = unauth_client.post(
            f"/api/triage/sessions/{session.id}/assign_box/",
            data={"box_name": "BOX-01"},
            format="json"
        )
        assert res_box.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_reads_blocked(self):
        unauth_client = APIClient()
        for url in (
            "/api/triage/sessions/emr_patients/",
            "/api/triage/sessions/evaluation_metrics/",
            "/api/triage/sessions/fhir_logs/",
        ):
            assert unauth_client.get(url).status_code == status.HTTP_401_UNAUTHORIZED, url

    def test_generic_crud_routes_not_exposed(self):
        session = TriageSession.objects.create(
            patient=self.patient, level=3, ai_level=3, final_level=3, justification="No borrable"
        )
        assert self.client.delete(f"/api/triage/sessions/{session.id}/").status_code == status.HTTP_404_NOT_FOUND
        assert self.client.put(
            f"/api/triage/sessions/{session.id}/", {"final_level": 1}, format="json"
        ).status_code == status.HTTP_404_NOT_FOUND
        assert TriageSession.objects.filter(id=session.id).exists()

    def test_override_denied_without_edit_permission(self):
        nurse = User.objects.create_user(
            email="enfermera_triage@hospital.com", password="Password123!", role="enfermero", is_verified=True
        )
        assert nurse.permissions.can_edit_symptoms is False
        nurse_client = APIClient()
        nurse_client.force_authenticate(user=nurse)
        session = TriageSession.objects.create(
            patient=self.patient, level=4, ai_level=4, final_level=4, justification="Inicial"
        )
        response = nurse_client.patch(
            f"/api/triage/sessions/{session.id}/override_level/", {"final_level": 1}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        session.refresh_from_db()
        assert session.final_level == 4

    def _mock_analysis(self, mocker, **patient):
        result = {
            "patientInfo": {"documentId": "CC-TRIAGE-001", **patient},
            "entities": {"symptoms": ["Tos"], "medications": [], "vitals": [], "history": []},
            "triage": {"level": 4, "justification": "Cuadro leve"},
            "confidence": 0.9,
            "engine_used": "Motor de Reglas Clínico (Christus Sinergia)",
        }
        mocker.patch("triage.views.analyze_triage_transcript", return_value=result)

    def test_analyze_does_not_overwrite_existing_patient_data(self, mocker):
        self._mock_analysis(mocker, name="Nombre Alucinado", phone="3001112233", birthDate="1990-01-31")
        response = self.client.post("/api/triage/sessions/analyze/", {"transcript": "tos leve"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        self.patient.refresh_from_db()
        assert self.patient.full_name == "Alejandro Morales"  # no se sobrescribe
        assert self.patient.phone == "3001112233"  # campo vacio: se completa
        assert str(self.patient.birth_date) == "1990-01-31"

    def test_analyze_ignores_malformed_birth_date_and_out_of_range_level(self, mocker):
        self._mock_analysis(mocker, birthDate="31/01/1990")
        response = self.client.post(
            "/api/triage/sessions/analyze/", {"transcript": "tos leve", "final_level": 9}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["final_level"] == 4
        self.patient.refresh_from_db()
        assert self.patient.birth_date is None

    def test_analyze_rolls_back_everything_if_audit_fails(self, mocker):
        self._mock_analysis(mocker)
        mocker.patch("triage.views.AuditLog.objects.create", side_effect=RuntimeError("audit down"))
        client = APIClient(raise_request_exception=False)
        client.force_authenticate(user=self.user)
        response = client.post("/api/triage/sessions/analyze/", {"transcript": "tos leve"}, format="json")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert TriageSession.objects.count() == 0

    def test_history_returns_own_sessions_with_transcript(self):
        from triage.models import Transcription
        own = TriageSession.objects.create(
            user=self.user, patient=self.patient, level=2, ai_level=3, final_level=2,
            justification="Ajustado", final_symptoms=["Dolor toracico"],
            clinical_entities={"symptoms": ["dolor"], "medications": ["asa"], "assigned_box": "BOX-01"},
        )
        Transcription.objects.create(
            triage_session=own, session_uuid="u1", full_text="Medico: que le pasa\nPaciente: me duele el pecho",
            model_used="test",
        )
        other_user = User.objects.create_user(email="otro@hospital.com", password="Password123!", role="medico")
        TriageSession.objects.create(user=other_user, patient=self.patient, level=5, ai_level=5, final_level=5)

        response = self.client.get("/api/triage/sessions/history/")
        assert response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in response.data] == [str(own.id)]
        item = response.data[0]
        assert item["patientName"] == "Alejandro Morales"
        assert item["transcript"][1] == {"speaker": "Paciente", "text": "me duele el pecho"}
        assert item["analysisResult"]["triage"]["level"] == 2
        assert item["analysisResult"]["triage"]["ai_level"] == 3
        assert item["analysisResult"]["entities"]["symptoms"] == ["Dolor toracico"]
        assert "assigned_box" not in item["analysisResult"]["entities"]

    def test_history_admin_sees_all_and_anonymous_blocked(self):
        TriageSession.objects.create(user=self.user, patient=self.patient, level=3, ai_level=3, final_level=3)
        admin = User.objects.create_user(email="admin_h@hospital.com", password="Password123!", role="admin")
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin)
        assert len(admin_client.get("/api/triage/sessions/history/").data) == 1
        assert APIClient().get("/api/triage/sessions/history/").status_code == status.HTTP_401_UNAUTHORIZED

    def test_dates_are_reported_in_local_timezone(self):
        from django.utils import timezone
        from datetime import datetime, timezone as dt_tz
        session = TriageSession.objects.create(
            patient=self.patient, level=3, ai_level=3, final_level=3, justification="tz"
        )
        utc_noon = datetime(2026, 1, 15, 12, 0, tzinfo=dt_tz.utc)
        TriageSession.objects.filter(id=session.id).update(created_at=utc_noon)
        response = self.client.get("/api/triage/sessions/evaluation_metrics/")
        # America/Bogota = UTC-5
        assert response.data["recent_evaluations"][0]["date"] == "2026-01-15 07:00"
        assert timezone.get_current_timezone_name() == "America/Bogota"

    def test_analyze_transcript_action_creates_session(self, mocker):
        mock_result = {
            "patientInfo": {
                "name": "Carlos Ruiz",
                "documentId": "1020304050",
                "gender": "male"
            },
            "entities": {
                "symptoms": ["Fiebre alta", "Tos seca"],
                "medications": ["Paracetamol"],
                "vitals": ["38.5 C"],
                "history": []
            },
            "triage": {
                "level": 3,
                "justification": "Sindrome febril agudo sin signos de alarma respiratoria"
            },
            "confidence": 0.92
        }
        mocker.patch("triage.views.analyze_triage_transcript", return_value=mock_result)

        response = self.client.post(
            "/api/triage/sessions/analyze/",
            data={"transcript": "Paciente Carlos Ruiz refiere fiebre alta de 38.5 C y tos seca"},
            format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "session_id" in response.data
        assert response.data["ai_level"] == 3
        assert response.data["final_level"] == 3
        assert response.data["is_level_modified"] is False

    def test_analyze_blank_transcript_returns_400(self):
        response = self.client.post("/api/triage/sessions/analyze/", {"transcript": "   "}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert TriageSession.objects.count() == 0

    def test_analyze_silent_audio_returns_422(self, mocker):
        from django.core.files.uploadedfile import SimpleUploadedFile
        engine = mocker.patch("triage.views.WhisperEngine")
        engine.return_value.transcribe_chunk.return_value = {"text": "  "}
        audio = SimpleUploadedFile("audio.webm", b"\x00\x01", content_type="audio/webm")
        response = self.client.post("/api/triage/sessions/analyze/", {"audio": audio}, format="multipart")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert TriageSession.objects.count() == 0

