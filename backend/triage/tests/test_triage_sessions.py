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
        assert response.data["severity_drift"] == 0.5
        assert response.data["distribution_ai"][2] == 2
        assert response.data["distribution_physician"][3] == 1

    def test_evaluation_metrics_aggregates_tokens_cache_and_retention(self):
        TriageSession.objects.create(
            patient=self.patient, level=3, ai_level=3, final_level=3, justification="a",
            ai_symptoms=["Tos", "Fiebre"], final_symptoms=["tos"], total_tokens=120, is_cached=True,
        )
        TriageSession.objects.create(
            patient=self.patient, level=4, ai_level=4, final_level=4, justification="b",
            ai_symptoms=[], final_symptoms=["cefalea"], total_tokens=80,
        )
        data = self.client.get("/api/triage/sessions/evaluation_metrics/").data
        assert data["total_tokens_consumed"] == 200
        assert data["cached_triages_count"] == 1
        # (1/2 + 1) / 2: sin sintomas de la IA la retencion cuenta como completa
        assert data["symptom_retention"] == 75.0

    def test_evaluation_metrics_query_count_does_not_grow_with_sessions(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                assert self.client.get("/api/triage/sessions/evaluation_metrics/").status_code == status.HTTP_200_OK
            return len(ctx.captured_queries)

        TriageSession.objects.bulk_create([
            TriageSession(patient=self.patient, level=3, ai_level=3, final_level=3, justification="x")
            for _ in range(3)
        ])
        few = count_queries()
        TriageSession.objects.bulk_create([
            TriageSession(patient=self.patient, level=2, ai_level=3, final_level=2, justification="y", reference_level=2)
            for _ in range(40)
        ])
        assert count_queries() == few

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
        assert session.assigned_box == "BOX-03"
        assert session.care_status == "En Atencion"
        # La ubicacion ya no se mezcla con las entidades clinicas
        assert session.clinical_entities == {"vitals": {"fc": "88"}}

        listed = self.client.get("/api/triage/sessions/emr_patients/").data[0]
        assert listed["assigned_box"] == "BOX-03"
        assert listed["status"] == "En Atencion"

    def test_box_migration_moves_entities_to_columns(self):
        import importlib
        from django.apps import apps
        migration = importlib.import_module("triage.migrations.0006_triagesession_assigned_box_care_status")
        legacy = TriageSession.objects.create(
            patient=self.patient, level=2, ai_level=2, final_level=2, justification="Legado",
            clinical_entities={"symptoms": ["dolor"], "assigned_box": "REAN-01", "status": "En Atencion"},
        )
        untouched = TriageSession.objects.create(
            patient=self.patient, level=4, ai_level=4, final_level=4, justification="Sin box",
            clinical_entities={"symptoms": ["tos"]},
        )

        migration.entities_to_fields(apps, None)
        legacy.refresh_from_db()
        untouched.refresh_from_db()
        assert (legacy.assigned_box, legacy.care_status) == ("REAN-01", "En Atencion")
        assert legacy.clinical_entities == {"symptoms": ["dolor"]}
        assert (untouched.assigned_box, untouched.care_status) == ("", "Pendiente de Box")

        migration.fields_to_entities(apps, None)
        legacy.refresh_from_db()
        untouched.refresh_from_db()
        assert legacy.clinical_entities["assigned_box"] == "REAN-01"
        assert "assigned_box" not in untouched.clinical_entities

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
        mocker.patch("triage.tasks.analyze_triage_transcript", return_value=result)

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
        mocker.patch("triage.tasks.analyze_triage_transcript", return_value=mock_result)

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

    def test_history_keeps_protocol_criteria_and_engine(self):
        from triage.models import Transcription
        session = TriageSession.objects.create(user=self.user, patient=self.patient, level=2, ai_level=2, final_level=2,
                                               justification="J", rag_context=["c2_chest_pain_sca"])
        Transcription.objects.create(triage_session=session, session_uuid="h-1", full_text="dolor", model_used="Motor de reglas")
        result = self.client.get("/api/triage/sessions/history/").data[0]["analysisResult"]
        assert result["engine_used"] == "Motor de reglas"
        assert [c["id"] for c in result["rag_criteria"]] == ["c2_chest_pain_sca"]

    def test_analyze_describes_retrieved_protocol_criteria(self, mocker):
        mocker.patch("triage.tasks.analyze_triage_transcript", return_value={
            "patientInfo": {}, "entities": {"symptoms": ["dolor toracico"]},
            "triage": {"level": 2, "justification": "Sospecha de SCA"},
            "rag_context": ["c2_chest_pain_sca", "id_inexistente"],
        })
        response = self.client.post("/api/triage/sessions/analyze/", {"transcript": "dolor toracico"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        criteria = response.data["analysis"]["rag_criteria"]
        assert [c["id"] for c in criteria] == ["c2_chest_pain_sca"]
        assert criteria[0]["level"] == 2 and criteria[0]["criterion"]

    def test_analyze_blank_transcript_returns_400(self):
        response = self.client.post("/api/triage/sessions/analyze/", {"transcript": "   "}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert TriageSession.objects.count() == 0

    def test_analyze_silent_audio_returns_422(self, mocker):
        from django.core.files.uploadedfile import SimpleUploadedFile
        engine = mocker.patch("transcription.tasks.WhisperEngine")
        engine.return_value.transcribe_chunk.return_value = {"text": "  "}
        audio = SimpleUploadedFile("audio.webm", b"\x00\x01", content_type="audio/webm")
        response = self.client.post("/api/triage/sessions/analyze/", {"audio": audio}, format="multipart")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert TriageSession.objects.count() == 0

    def test_evaluation_metrics_hides_patient_identity_without_emr_permission(self):
        TriageSession.objects.create(
            patient=self.patient, level=2, ai_level=2, final_level=2, justification="Caso"
        )
        response = self.client.get("/api/triage/sessions/evaluation_metrics/")
        assert response.data["recent_evaluations"][0]["patient"] == "Alejandro Morales"

        self.user.permissions.can_view_emr = False
        self.user.permissions.save()
        response = self.client.get("/api/triage/sessions/evaluation_metrics/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["recent_evaluations"][0]["patient"] == f"Paciente #{self.patient.id}"

    def _blind_case(self, author=None, ai_level=3, final_level=2):
        from triage.models import Transcription
        session = TriageSession.objects.create(
            user=author, patient=self.patient, level=final_level, ai_level=ai_level,
            final_level=final_level, justification="Justificacion de la IA"
        )
        Transcription.objects.create(
            triage_session=session, session_uuid="blind-1", full_text="dolor toracico opresivo", model_used="test"
        )
        return session

    def _other_doctor(self):
        doctor = User.objects.create_user(
            email="adjudicador@hospital.com", password="Password123!", role="medico", is_verified=True
        )
        client = APIClient()
        client.force_authenticate(user=doctor)
        return doctor, client

    def test_blind_review_queue_hides_levels_and_own_cases(self):
        self._blind_case(author=self.user)
        _, client = self._other_doctor()

        response = client.get("/api/triage/sessions/blind_review_queue/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pending_total"] == 1
        case = response.data["results"][0]
        assert case["transcript"] == "dolor toracico opresivo"
        for hidden in ("ai_level", "final_level", "level", "justification", "rag_context", "name"):
            assert hidden not in case

        # El autor del triaje no ve su propio caso en la cola
        own = self.client.get("/api/triage/sessions/blind_review_queue/")
        assert own.data["pending_total"] == 0

    def test_reference_level_is_recorded_once_and_audited(self):
        from accounts.models import AuditLog
        session = self._blind_case(author=self.user)
        doctor, client = self._other_doctor()
        url = f"/api/triage/sessions/{session.id}/reference_level/"

        response = client.post(url, {"reference_level": 1}, format="json")
        assert response.status_code == status.HTTP_200_OK
        session.refresh_from_db()
        assert session.reference_level == 1
        assert session.reference_by == doctor
        # El nivel de referencia no altera la concordancia IA vs medico tratante
        assert session.final_level == 2 and session.ai_level == 3
        assert AuditLog.objects.filter(action="TRIAGE_REFERENCE").count() == 1

        again = client.post(url, {"reference_level": 4}, format="json")
        assert again.status_code == status.HTTP_409_CONFLICT
        session.refresh_from_db()
        assert session.reference_level == 1

    def test_reference_level_rejects_author_invalid_level_and_nurse(self):
        session = self._blind_case(author=self.user)
        url = f"/api/triage/sessions/{session.id}/reference_level/"
        assert self.client.post(url, {"reference_level": 2}, format="json").status_code == status.HTTP_403_FORBIDDEN

        _, client = self._other_doctor()
        assert client.post(url, {"reference_level": 7}, format="json").status_code == status.HTTP_400_BAD_REQUEST

        nurse = User.objects.create_user(
            email="enfermera_ref@hospital.com", password="Password123!", role="enfermero", is_verified=True
        )
        nurse_client = APIClient()
        nurse_client.force_authenticate(user=nurse)
        assert nurse_client.post(url, {"reference_level": 2}, format="json").status_code == status.HTTP_403_FORBIDDEN
        session.refresh_from_db()
        assert session.reference_level is None

    def test_justification_rating_only_after_reference_once_and_by_adjudicator(self):
        from accounts.models import AuditLog
        session = self._blind_case(author=self.user)
        doctor, client = self._other_doctor()
        rating_url = f"/api/triage/sessions/{session.id}/justification_rating/"
        scores = {"clarity": 4, "relevance": 5, "fidelity": 3}

        # Antes de fijar la referencia no se puede valorar (la justificacion revelaria el nivel de la IA)
        assert client.post(rating_url, scores, format="json").status_code == status.HTTP_403_FORBIDDEN

        reference = client.post(f"/api/triage/sessions/{session.id}/reference_level/", {"reference_level": 2}, format="json")
        assert reference.data["justification"] == "Justificacion de la IA"

        # Fuera de la escala 1-5 se rechaza; el autor del triaje no puede valorar
        assert client.post(rating_url, {**scores, "clarity": 6}, format="json").status_code == status.HTTP_400_BAD_REQUEST
        assert self.client.post(rating_url, scores, format="json").status_code == status.HTTP_403_FORBIDDEN

        assert client.post(rating_url, scores, format="json").status_code == status.HTTP_200_OK
        session.refresh_from_db()
        assert (session.justification_clarity, session.justification_relevance, session.justification_fidelity) == (4, 5, 3)
        assert AuditLog.objects.filter(action="TRIAGE_JUSTIFICATION_RATING").count() == 1
        assert client.post(rating_url, scores, format="json").status_code == status.HTTP_409_CONFLICT

    def test_evaluation_metrics_reports_justification_ratings(self):
        from django.utils import timezone
        empty = self.client.get("/api/triage/sessions/evaluation_metrics/").data["justification_ratings"]
        assert empty == {"n": 0, "clarity": None, "relevance": None, "fidelity": None}
        for clarity in (3, 4):
            TriageSession.objects.create(
                patient=self.patient, level=3, ai_level=3, final_level=3, justification="J",
                justification_clarity=clarity, justification_relevance=5, justification_fidelity=4,
                justification_rated_at=timezone.now())
        ratings = self.client.get("/api/triage/sessions/evaluation_metrics/").data["justification_ratings"]
        assert ratings == {"n": 2, "clarity": 3.5, "relevance": 5.0, "fidelity": 4.0}

    def test_benchmark_results_summarizes_saved_runs(self, tmp_path, settings, mocker):
        import json
        results = tmp_path / "resultados"
        results.mkdir()
        (results / "test_hibrido.json").write_text(json.dumps({
            "engine": "hibrido", "model": "gemini", "split": "test", "match": "relaxed", "corpus": "C:/ruta/privada.json",
            "entities": {"micro": {"precision": 0.8, "recall": 0.7, "f1": 0.75}, "micro_f1_ci95": [0.7, 0.8],
                         "macro_f1": 0.7, "by_type": {"symptoms": {"f1": 0.8}},
                         "negation": {"negation_accuracy": 0.9}, "normalization": {"cie10_accuracy": 0.85}},
            "triage": {"n": 10, "cohen_kappa": 0.6, "cohen_kappa_ci95": [0.4, 0.8]},
            "cases": [{"id": "B1", "transcript": "texto del caso"}],
        }), encoding="utf-8")
        (results / "roto.json").write_text("{no es json", encoding="utf-8")
        asr = tmp_path / "data" / "asr"
        asr.mkdir(parents=True)
        (asr / "manifest.json").write_text("[]", encoding="utf-8")
        (asr / "resultado_small_cpu.json").write_text(json.dumps({
            "model_size": "small", "device": "cpu", "chunk_seconds": 4, "initial_prompt": True,
            "global": {"audios": 40, "wer": 0.12}, "por_condicion": {"ruido": {"wer": 0.2}}, "audios": [{"id": "a"}],
        }), encoding="utf-8")
        mocker.patch("triage.benchmark_results.RESULTS_DIR", results)
        settings.BASE_DIR = tmp_path

        data = self.client.get("/api/triage/sessions/benchmark_results/").data
        [run] = data["extraction"]
        assert run["name"] == "test_hibrido" and run["cases"] == 1
        assert run["entities"]["f1"] == 0.75 and run["entities"]["by_type"] == {"symptoms": 0.8}
        assert run["triage"]["cohen_kappa_ci95"] == [0.4, 0.8]
        # Solo cifras agregadas: ni casos ni rutas del equipo
        assert "corpus" not in run and "texto del caso" not in json.dumps(data)
        [asr_run] = data["asr"]
        assert asr_run["global"]["wer"] == 0.12 and asr_run["by_condition"] == {"ruido": {"wer": 0.2}}
        assert "audios" not in asr_run

    def test_evaluation_metrics_reports_reference_validation(self):
        session = self._blind_case(author=self.user, ai_level=3, final_level=2)
        TriageSession.objects.create(patient=self.patient, level=4, ai_level=4, final_level=4, justification="Sin referencia")
        TriageSession.objects.filter(pk=session.pk).update(reference_level=2)

        response = self.client.get("/api/triage/sessions/evaluation_metrics/")
        ref = response.data["reference_validation"]
        assert ref["referenced_count"] == 1
        assert ref["ai_vs_reference"]["n"] == 1
        assert ref["ai_vs_reference"]["undertriage_rate"] == 100.0
        assert ref["physician_vs_reference"]["exact_agreement"] == 100.0

    def test_analyze_falls_back_to_rules_when_worker_unavailable(self, mocker):
        from core.task_runner import TaskUnavailable
        mocker.patch("triage.tasks.run_task", side_effect=TaskUnavailable("worker sin respuesta"))
        resolve_key = mocker.patch("triage.ai_analyzer._resolve_gemini_api_key", return_value="test-key")

        response = self.client.post(
            "/api/triage/sessions/analyze/",
            {"transcript": "paciente inconsciente, no respira"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["ai_level"] == 1
        assert "no respondió" in response.data["warning"]
        assert "Reglas" in response.data["engine_used"]
        # El respaldo no intenta llamar a Gemini desde el proceso web
        resolve_key.assert_not_called()

    def test_release_box_frees_patient_and_audits(self):
        from accounts.models import AuditLog
        session = TriageSession.objects.create(
            patient=self.patient,
            level=2,
            ai_level=2,
            final_level=2,
            assigned_box="BOX-02",
            care_status="En Atencion",
            justification="Paciente para liberar"
        )
        response = self.client.post(
            f"/api/triage/sessions/{session.id}/release_box/",
            {"status": "Alta Medica"},
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        session.refresh_from_db()
        assert session.assigned_box == ""
        assert session.care_status == "Alta Medica"
        assert AuditLog.objects.filter(action="EMR_BOX_RELEASED").count() == 1

    def test_boxes_census_and_management_lifecycle(self):
        # 1. Consultar censo inicial
        census_res = self.client.get("/api/triage/sessions/boxes_census/")
        assert census_res.status_code == status.HTTP_200_OK
        assert "boxes" in census_res.data
        assert "summary" in census_res.data
        assert census_res.data["summary"]["total"] >= 10

        # 2. Crear nuevo box personalizado
        create_res = self.client.post(
            "/api/triage/sessions/manage_boxes/",
            {
                "action": "create",
                "code": "BOX-TEST-99",
                "area": "Urgencias Pediatria",
                "type": "Cuna Hospitalaria",
                "equipment": "Monitor neonatal"
            },
            format="json"
        )
        assert create_res.status_code == status.HTTP_201_CREATED
        assert create_res.data["box"]["code"] == "BOX-TEST-99"

        # 3. Cambiar estado operativo (ej. desinfeccion)
        state_res = self.client.post(
            "/api/triage/sessions/manage_boxes/",
            {"action": "update_state", "code": "BOX-TEST-99", "state": "En Desinfeccion"},
            format="json"
        )
        assert state_res.status_code == status.HTTP_200_OK

        # 4. Actualizar/Editar datos del box (area, tipo, equipamiento)
        edit_res = self.client.post(
            "/api/triage/sessions/manage_boxes/",
            {
                "action": "update",
                "code": "BOX-TEST-99",
                "area": "Reanimacion",
                "type": "Box Vital",
                "equipment": "Monitor neonatal, Carro de paro"
            },
            format="json"
        )
        assert edit_res.status_code == status.HTTP_200_OK

        # 5. Verificar en el censo que aparece con los nuevos valores y en desinfeccion
        updated_census = self.client.get("/api/triage/sessions/boxes_census/")
        box_item = next(b for b in updated_census.data["boxes"] if b["code"] == "BOX-TEST-99")
        assert box_item["status"] == "En Desinfeccion"
        assert box_item["area"] == "Reanimacion"
        assert box_item["type"] == "Box Vital"
        assert "Carro de paro" in box_item["equipment"]

        # 6. Eliminar box personalizado
        del_res = self.client.post(
            "/api/triage/sessions/manage_boxes/",
            {"action": "delete", "code": "BOX-TEST-99"},
            format="json"
        )
        assert del_res.status_code == status.HTTP_200_OK

    def test_update_care_status_and_evolution_notes(self):
        from accounts.models import AuditLog
        session = TriageSession.objects.create(
            patient=self.patient,
            level=3,
            ai_level=3,
            final_level=3,
            care_status="En Espera",
            justification="Paciente prueba estado"
        )
        url = f"/api/triage/sessions/{session.id}/update_care_status/"
        response = self.client.post(
            url,
            {
                "status": "En Atencion",
                "evolution_notes": "Paciente canalizado, recibiendo analgesia IV."
            },
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        session.refresh_from_db()
        assert session.care_status == "En Atencion"
        assert session.clinical_entities.get("evolution_notes") == "Paciente canalizado, recibiendo analgesia IV."
        assert AuditLog.objects.filter(action="EMR_CARE_STATUS_UPDATED").count() == 1

