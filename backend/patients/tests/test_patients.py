from datetime import date
import pytest
from django.db import IntegrityError
from patients.models import Patient

@pytest.mark.django_db
class TestPatientModel:
    def test_create_patient_success(self):
        patient = Patient.objects.create(
            document_id="CC-12345678",
            full_name="Maria Angelica Fernandez",
            birth_date=date(1985, 4, 12),
            gender="female",
            phone="+573105554321",
            insurance="SURA EPS"
        )
        assert patient.id is not None
        assert str(patient) == "Maria Angelica Fernandez (CC-12345678)"
        assert patient.insurance == "SURA EPS"

    def test_create_patient_duplicate_document_fails(self):
        Patient.objects.create(
            document_id="CC-DUPLICATE",
            full_name="Paciente Uno",
            gender="male"
        )
        with pytest.raises(IntegrityError):
            Patient.objects.create(
                document_id="CC-DUPLICATE",
                full_name="Paciente Dos",
                gender="female"
            )

    def test_patient_ordering(self):
        p1 = Patient.objects.create(document_id="CC-ORD-1", full_name="Primero")
        p2 = Patient.objects.create(document_id="CC-ORD-2", full_name="Segundo")
        patients = list(Patient.objects.filter(document_id__startswith="CC-ORD-"))
        assert patients[0] == p2
        assert patients[1] == p1