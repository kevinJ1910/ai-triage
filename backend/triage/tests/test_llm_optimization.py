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

    def test_extract_vitals_with_accents(self):
        # Whisper transcribe con tildes ('tensión', 'saturación'); los patrones no las llevan.
        compact, structured = ClinicalTranscriptCompressor.extract_vitals(
            "Tensión arterial de 90 sobre 60 y saturación de 91"
        )
        assert structured["bp_sys"] == 90
        assert structured["spo2"] == 91
        assert "PA: 90/60 mmHg" in compact

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


class TestPseudonymization:
    """Los identificadores del paciente no deben salir hacia el LLM externo."""

    def test_identifiers_are_masked(self):
        from triage.ai_analyzer import _pseudonymize
        text = "Me llamo Carlos Ruiz Gomez, cedula 1144123456, celular 300 123 4567, tengo dolor en el pecho"
        res = _pseudonymize(text)
        assert "Carlos" not in res["text"]
        assert "1144123456" not in res["text"]
        assert "4567" not in res["text"]
        assert "dolor en el pecho" in res["text"]
        assert res["identifiers"]["name"] == "Carlos Ruiz Gomez"
        assert res["identifiers"]["documentId"] == "1144123456"
        assert res["identifiers"]["phone"] == "3001234567"

    def test_vitals_are_not_masked(self):
        from triage.ai_analyzer import _pseudonymize
        text = "tension de 150 sobre 95, saturando al 88 por ciento, temperatura 38.5"
        assert _pseudonymize(text)["text"] == text

    def test_restore_replaces_placeholders(self):
        from triage.ai_analyzer import _restore_identifiers
        info = {"name": "[NOMBRE]", "documentId": "[DOCUMENTO]", "phone": None}
        restored = _restore_identifiers(info, {"name": "Ana", "documentId": "123456789", "phone": None}, "")
        assert restored["name"] == "Ana"
        assert restored["documentId"] == "123456789"

    def test_failure_messages_reflect_real_error(self):
        from triage.ai_analyzer import _describe_llm_failure
        assert "503" in _describe_llm_failure(RuntimeError("503 UNAVAILABLE"))
        assert "429" in _describe_llm_failure(RuntimeError("429 RESOURCE_EXHAUSTED"))
        assert "503" not in _describe_llm_failure(RuntimeError("Read timed out"))
        assert "503" not in _describe_llm_failure(None)


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

    def test_fallback_symptoms_match_accented_transcript(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        from system_settings.models import APIKeyCredential
        APIKeyCredential.objects.filter(provider='gemini').delete()

        # Con o sin tildes, el respaldo devuelve el termino clinico del catalogo.
        for transcript in ("Tengo dolor torácico y vómito desde anoche", "Tengo dolor toracico y vomito desde anoche"):
            res = analyze_triage_transcript(transcript, use_cache=False)
            assert res["entities"]["symptoms"] == ["dolor torácico", "vómito"]

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

    def test_llm_prompt_is_pseudonymized_and_identifiers_restored(self, mocker):
        import json as _json
        from types import SimpleNamespace
        llm_output = {
            "patientInfo": {"name": "[NOMBRE]", "documentId": "[DOCUMENTO]", "gender": "female"},
            "entities": {"symptoms": ["cefalea"], "medications": [], "vitals": [], "history": []},
            "triage": {"level": 4, "name": "Consulta Prioritaria",
                       "attention_time": "Hasta 120 minutos", "justification": "Cefalea sin alarma"},
            "confidence": 0.9,
        }
        mocker.patch("triage.ai_analyzer._resolve_gemini_api_key", return_value="test-key")
        client_cls = mocker.patch("triage.ai_analyzer.genai.Client")
        generate = client_cls.return_value.models.generate_content
        generate.return_value = SimpleNamespace(text=_json.dumps(llm_output), usage_metadata=None)

        res = analyze_triage_transcript(
            "Mi nombre es Laura Martinez, documento 52123456, tengo dolor de cabeza leve", use_cache=False
        )

        sent_prompt = generate.call_args.kwargs["contents"]
        assert "Laura" not in sent_prompt
        assert "52123456" not in sent_prompt
        assert res["patientInfo"]["name"] == "Laura Martinez"
        assert res["patientInfo"]["documentId"] == "52123456"

    def test_without_llm_skips_gemini_and_is_not_cached(self, mocker):
        resolve_key = mocker.patch("triage.ai_analyzer._resolve_gemini_api_key", return_value="test-key")
        client_cls = mocker.patch("triage.ai_analyzer.genai.Client")

        res = analyze_triage_transcript("dolor abdominal leve desde ayer", use_cache=True, allow_llm=False)

        resolve_key.assert_not_called()
        client_cls.assert_not_called()
        assert "no respondió" in res["warning"]
        assert res["triage"]["level"] in range(1, 6)
        assert ClinicalQueryCache.stats()["cached_items_count"] == 0

    def test_llm_failure_fallback_is_not_cached(self, mocker):
        mocker.patch("triage.ai_analyzer._resolve_gemini_api_key", return_value="test-key")
        client_cls = mocker.patch("triage.ai_analyzer.genai.Client")
        client_cls.return_value.models.generate_content.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED")

        res = analyze_triage_transcript("dolor abdominal leve desde ayer", use_cache=True)
        assert "429" in res["warning"]
        assert ClinicalQueryCache.stats()["cached_items_count"] == 0

    def test_explicit_model_skips_fallback_models(self, mocker):
        mocker.patch("triage.ai_analyzer._resolve_gemini_api_key", return_value="test-key")
        client_cls = mocker.patch("triage.ai_analyzer.genai.Client")
        generate = client_cls.return_value.models.generate_content
        generate.side_effect = RuntimeError("500 INTERNAL")

        res = analyze_triage_transcript("dolor abdominal leve desde ayer", use_cache=False, model="gemini-3.8-flash")

        assert [c.kwargs["model"] for c in generate.call_args_list] == ["gemini-3.8-flash"]
        assert res["engine_used"].startswith("Motor de Reglas")

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

    def test_rag_enriched_coverage_and_synonym_expansion(self):
        # 1. Stroke / ACV
        acv_query = "Paciente con boca torcida y se le durmio el brazo de forma repentina"
        acv_res = ClinicalKnowledgeRAG.retrieve(acv_query, top_k=3)
        assert any(c["id"] == "c2_stroke_acv" for c in acv_res)

        # 2. Expresion coloquial 'chistata' -> disuria (Nivel 4)
        chistata_query = "Tengo chistata y me arde mucho al mear"
        chistata_res = ClinicalKnowledgeRAG.retrieve(chistata_query, top_k=3)
        assert any("disuria" in c["id"] or c["level"] == 4 for c in chistata_res)

        # 3. Expresion coloquial 'azucar por las nubes' -> descompensacion diabetica (Nivel 2)
        diab_query = "Paciente diabetico con el azucar por las nubes y respiracion profunda"
        diab_res = ClinicalKnowledgeRAG.retrieve(diab_query, top_k=3)
        assert any(c["id"] == "c2_diabetes_decompensation" for c in diab_res)

    def test_cache_semantic_canonicalization_hits_across_synonyms(self):
        ClinicalQueryCache.clear()
        # Dos consultas con redaccion coloquial distinta pero significado clinico identico
        transcript_a = "tengo dolor de cabeza fuerte desde ayer"
        transcript_b = "tengo cefalea fuerte desde ayer"

        fp_a = ClinicalQueryCache.generate_fingerprint(transcript_a, {})
        fp_b = ClinicalQueryCache.generate_fingerprint(transcript_b, {})

        # La canonicalizacion ontologica unifica los fingerprints ahorrando tokens
        assert fp_a == fp_b

        # Simular cache set con A y acierto inmediato con B
        payload = {
            "triage": {"level": 4, "name": "Consulta Prioritaria", "attention_time": "Direccionamiento a su EPS", "justification": "Cefalea subaguda"},
            "entities": {"symptoms": ["cefalea"]},
            "confidence": 0.95
        }
        ClinicalQueryCache.set(fp_a, payload, estimated_tokens=600)

        hit = ClinicalQueryCache.get(fp_b)
        assert hit is not None
        assert hit["cached"] is True
        assert hit["tokens_used"] == 0
        assert ClinicalQueryCache.stats()["hits"] == 1
        assert ClinicalQueryCache.stats()["estimated_tokens_saved"] == 600

    def test_extended_vitals_extraction_glu_eva_gcs(self):
        text = "Paciente con glucometria de 380 mg/dl, dolor 9 sobre 10 y glasgow de 14 sobre 15"
        compact, structured = ClinicalTranscriptCompressor.extract_vitals(text)
        assert any("GLU: 380 mg/dL" in v for v in compact)
        assert any("EVA: 9/10" in v for v in compact)
        assert any("GCS: 14/15" in v for v in compact)
        assert structured["glucose"] == 380
        assert structured["eva"] == 9
        assert structured["gcs"] == 14
