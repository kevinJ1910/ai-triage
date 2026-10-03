import pytest
from pydantic import ValidationError
from triage.input_pipeline import ClinicalTranscriptCompressor
from triage.clinical_rag import ClinicalKnowledgeRAG
from triage.clinical_cache import ClinicalQueryCache
from triage.ai_analyzer import (
    TriageOutputSchema,
    PatientInfoSchema,
    EntitiesSchema,
    TriageDetailsSchema,
    analyze_triage_transcript
)


class TestClinicalTranscriptCompressor:
    """Pruebas del pipeline de compresion y extraccion de constantes vitales."""

    def test_clean_filler_words_and_repetition(self):
        noisy_text = "ehhh buenas tardes doctor este... pues mmm tengo digamos que dolor de cabeza y tos tos tos"
        cleaned = ClinicalTranscriptCompressor.clean_filler_words(noisy_text)
        assert "ehhh" not in cleaned
        assert "este" not in cleaned
        assert "mmm" not in cleaned
        assert "dolor de cabeza y tos" in cleaned

    def test_extract_vitals_blood_pressure_and_saturation(self):
        transcript = "El paciente tiene tension de 150 sobre 95 y esta saturando al 88 por ciento con pulso de 105"
        compact, structured = ClinicalTranscriptCompressor.extract_vitals(transcript)
        assert any("PA: 150/95 mmHg" in v for v in compact)
        assert any("SpO2: 88%" in v for v in compact)
        assert any("FC: 105 lpm" in v for v in compact)
        assert structured["bp_sys"] == 150
        assert structured["bp_dia"] == 95
        assert structured["spo2"] == 88
        assert structured["heart_rate"] == 105

    def test_extract_temperature_and_respiratory_rate(self):
        transcript = "Tiene temperatura de 38.8 grados y respiraciones de 26 por minuto"
        compact, structured = ClinicalTranscriptCompressor.extract_vitals(transcript)
        assert any("T: 38.8°C" in v for v in compact)
        assert any("FR: 26 rpm" in v for v in compact)
        assert structured["temperature"] == 38.8
        assert structured["respiratory_rate"] == 26

    def test_detect_red_flags(self):
        critical_text = "Paciente con dolor en el pecho opresivo que se le va al brazo y dificultad respiratoria severa"
        flags = ClinicalTranscriptCompressor.detect_red_flags(critical_text)
        assert any("Sospecha Síndrome Coronario Agudo" in f for f in flags)
        assert any("Insuficiencia Respiratoria Aguda" in f for f in flags)

    def test_process_pipeline_stats(self):
        raw = "ehhh este... mire doctor tengo fiebre de 38.5 y tos tos desde hace tres dias"
        result = ClinicalTranscriptCompressor.process(raw)
        assert result["cleaned_transcript"]
        assert result["reduction_percentage"] > 0
        assert len(result["compact_vitals"]) >= 1


class TestClinicalKnowledgeRAG:
    """Pruebas del motor de recuperacion contextual semantica."""

    def test_retrieve_cardiac_criteria(self):
        query = "Paciente de 58 anos con fuerte dolor toracico opresivo e infarto previo"
        retrieved = ClinicalKnowledgeRAG.retrieve(query, top_k=3)
        assert len(retrieved) <= 3
        # Debe recuperar el criterio de sospecha de SCA (Nivel 2)
        assert any(item["level"] == 2 and "torácico" in item["criterion"] for item in retrieved)

    def test_retrieve_minor_symptom_criteria(self):
        query = "Tengo gripa, tos y congestion nasal sin fiebre desde ayer"
        retrieved = ClinicalKnowledgeRAG.retrieve(query, top_k=3)
        assert any(item["level"] == 4 for item in retrieved)

    def test_format_context_for_prompt(self):
        criteria = [
            {
                "id": "c2_chest_pain_sca",
                "level": 2,
                "name": "Emergencia",
                "category": "cardiovascular",
                "criterion": "Dolor torácico opresivo con signos de alarma",
                "keywords": ["dolor toracico"]
            }
        ]
        formatted = ClinicalKnowledgeRAG.format_context_for_prompt(criteria)
        assert "[2 - EMERGENCIA]" in formatted
        assert "Dolor torácico opresivo" in formatted
        assert "Dentro de los siguientes 30 minutos" in formatted


class TestClinicalQueryCache:
    """Pruebas del cache canonico de consultas clinicas."""

    def setup_method(self):
        ClinicalQueryCache.clear()

    def test_fingerprint_generation_consistent(self):
        fp1 = ClinicalQueryCache.generate_fingerprint("dolor de cabeza fuerte", {"bp_sys": 120, "spo2": 98})
        fp2 = ClinicalQueryCache.generate_fingerprint("dolor de cabeza fuerte", {"bp_sys": 120, "spo2": 98})
        assert fp1 == fp2

    def test_fingerprint_preserves_negation(self):
        fp_pos = ClinicalQueryCache.generate_fingerprint("tiene dolor de pecho", {})
        fp_neg = ClinicalQueryCache.generate_fingerprint("no tiene dolor de pecho", {})
        fp_sin = ClinicalQueryCache.generate_fingerprint("tiene dolor sin fiebre", {})
        fp_con = ClinicalQueryCache.generate_fingerprint("tiene dolor con fiebre", {})
        assert fp_pos != fp_neg
        assert fp_sin != fp_con

    def test_fingerprint_preserves_word_order(self):
        fp_a = ClinicalQueryCache.generate_fingerprint("no tiene dolor tiene fiebre", {})
        fp_b = ClinicalQueryCache.generate_fingerprint("tiene dolor no tiene fiebre", {})
        assert fp_a != fp_b

    def test_fingerprint_missing_vitals_not_assumed_normal(self):
        fp_missing = ClinicalQueryCache.generate_fingerprint("disnea", {})
        fp_normal = ClinicalQueryCache.generate_fingerprint("disnea", {"bp_sys": 120, "spo2": 98})
        fp_hypox = ClinicalQueryCache.generate_fingerprint("disnea", {"bp_sys": 120, "spo2": 85})
        assert fp_missing != fp_normal
        assert fp_normal != fp_hypox

    def test_cache_never_stores_patient_info(self):
        fp = ClinicalQueryCache.generate_fingerprint("ardor al orinar", {})
        payload = {
            "patientInfo": {"name": "Paciente A", "documentId": "1111111111"},
            "triage": {"level": 4},
            "entities": {"symptoms": ["disuria"]},
        }
        ClinicalQueryCache.set(fp, payload)
        payload["entities"]["symptoms"].append("mutado")

        cached = ClinicalQueryCache.get(fp)
        assert "patientInfo" not in cached
        assert cached["entities"]["symptoms"] == ["disuria"]

    def test_cache_miss_then_hit(self):
        fp = ClinicalQueryCache.generate_fingerprint("ardor al orinar", {})
        assert ClinicalQueryCache.get(fp) is None

        payload = {
            "triage": {"level": 4, "name": "Consulta Prioritaria", "attention_time": "Direccionamiento a su EPS", "justification": "Infeccion urinaria baja"},
            "entities": {"symptoms": ["disuria"], "medications": [], "vitals": [], "history": []},
            "confidence": 0.90
        }
        ClinicalQueryCache.set(fp, payload, ttl_seconds=3600, estimated_tokens=450)

        cached = ClinicalQueryCache.get(fp)
        assert cached is not None
        assert cached["cached"] is True
        assert cached["tokens_used"] == 0
        assert cached["triage"]["level"] == 4

        stats = ClinicalQueryCache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["estimated_tokens_saved"] == 450


class TestPydanticTriageSchemas:
    """Pruebas de validacion estricta con Pydantic v2."""

    def test_valid_triage_schema(self):
        data = {
            "patientInfo": {
                "name": "Carlos Gomez",
                "documentId": "1144123456",
                "birthDate": "1980-05-12",
                "gender": "male",
                "phone": "3001234567",
                "insurance": "SURA"
            },
            "entities": {
                "symptoms": ["dolor toracico", "diaforesis"],
                "medications": ["aspirina"],
                "vitals": ["PA: 140/90 mmHg"],
                "history": ["hipertension"]
            },
            "triage": {
                "level": 2,
                "name": "Emergencia",
                "attention_time": "Dentro de los siguientes 30 minutos",
                "justification": "Dolor toracico con signos de alarma compatibles con SCA."
            },
            "confidence": 0.96,
            "protocol": "Christus Sinergia Salud"
        }
        schema = TriageOutputSchema.model_validate(data)
        assert schema.triage.level == 2
        assert schema.patientInfo.name == "Carlos Gomez"

    def test_invalid_level_rejected(self):
        data = {
            "patientInfo": {},
            "entities": {},
            "triage": {
                "level": 6,  # Invalido (debe ser 1-5)
                "name": "Emergencia",
                "attention_time": "Inmediata",
                "justification": "Test"
            },
            "confidence": 0.5
        }
        with pytest.raises(ValidationError):
            TriageOutputSchema.model_validate(data)


@pytest.mark.django_db
class TestAIAnalyzerEndToEnd:
    """Pruebas de integracion del analizador optimizado."""

    def setup_method(self):
        ClinicalQueryCache.clear()

    def test_analyze_empty_transcript(self):
        res = analyze_triage_transcript("")
        assert "error" in res

    def test_analyze_fallback_path_without_api_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        # Forzar falla de DB credential
        from system_settings.models import APIKeyCredential
        APIKeyCredential.objects.filter(provider='gemini').delete()

        transcript = "Tengo dolor en el pecho muy fuerte que se me va al brazo izquierdo desde hace 20 minutos"
        res = analyze_triage_transcript(transcript, use_cache=False)
        assert "triage" in res
        assert res["triage"]["level"] in [1, 2]
        assert "Christus Sinergia" in res["protocol"]
        assert res["compression_ratio"] >= 0
        assert "rag_context" in res

    def test_cache_integration_in_analyzer(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        from system_settings.models import APIKeyCredential
        APIKeyCredential.objects.filter(provider='gemini').delete()

        query = "Paciente con tos y congestion nasal de tres dias sin dolor"
        first_call = analyze_triage_transcript(query, use_cache=True)
        assert first_call["cached"] is False

        # Segunda llamada identica debe ser servida de cache
        second_call = analyze_triage_transcript(query, use_cache=True)
        assert second_call["cached"] is True
        assert second_call["tokens_used"] == 0
        assert second_call["triage"]["level"] == first_call["triage"]["level"]

    def test_cache_hit_does_not_leak_previous_patient(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        from system_settings.models import APIKeyCredential
        APIKeyCredential.objects.filter(provider='gemini').delete()

        # Si un resultado previo trae datos de paciente, el acierto de cache no debe reutilizarlos.
        query ="Paciente con tos y congestion nasal de tres dias"
        first = analyze_triage_transcript(query, use_cache=True)
        first["patientInfo"]["documentId"] = "9999999999"  # mutar el resultado devuelto
        second = analyze_triage_transcript(query, use_cache=True)
        assert second["cached"] is True
        assert second["patientInfo"]["documentId"] is None
