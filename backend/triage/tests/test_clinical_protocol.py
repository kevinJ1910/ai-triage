import pytest
from unittest.mock import patch, MagicMock
from triage.clinical_protocol import evaluate_christus_sinergia_triage, CHRISTUS_SINERGIA_LEVELS
from triage.ai_analyzer import analyze_triage_transcript


class TestChristusSinergiaProtocol:
    def test_protocol_levels_structure(self):
        assert len(CHRISTUS_SINERGIA_LEVELS) == 5
        assert CHRISTUS_SINERGIA_LEVELS[1]["name"] == "Reanimación"
        assert CHRISTUS_SINERGIA_LEVELS[2]["name"] == "Emergencia"
        assert CHRISTUS_SINERGIA_LEVELS[3]["name"] == "Urgencia"
        assert CHRISTUS_SINERGIA_LEVELS[4]["name"] == "Consulta Prioritaria"
        assert CHRISTUS_SINERGIA_LEVELS[5]["name"] == "Consulta Externa"

    def test_level_1_reanimation(self):
        transcript = "El paciente ingresa sin signos vitales, en paro respiratorio e inconsciente"
        res = evaluate_christus_sinergia_triage(transcript)
        assert res["level"] == 1
        assert res["name"] == "Reanimación"
        assert "Inmediata" in res["attention_time"]

    def test_level_2_emergency_chest_pain(self):
        transcript = "Hombre de 55 años con dolor en el pecho opresivo irradiado al brazo izquierdo y sudoracion fria"
        res = evaluate_christus_sinergia_triage(transcript)
        assert res["level"] == 2
        assert res["name"] == "Emergencia"
        assert "30 minutos" in res["attention_time"]

    def test_level_2_emergency_convulsion(self):
        transcript = "Paciente que entra convulsionando activamente, estado convulsivo prolongado"
        res = evaluate_christus_sinergia_triage(transcript)
        assert res["level"] == 2
        assert res["name"] == "Emergencia"

    def test_level_3_urgency(self):
        transcript = "Vengo por vértigo severo e incapacitante desde la mañana, no me puedo parar por el mareo"
        res = evaluate_christus_sinergia_triage(transcript)
        assert res["level"] == 3
        assert res["name"] == "Urgencia"
        assert "120 minutos" in res["attention_time"]

    def test_level_4_priority_consult(self):
        transcript = "Tengo tos y congestion nasal, faringitis y dolor de garganta hace dos dias"
        res = evaluate_christus_sinergia_triage(transcript)
        assert res["level"] == 4
        assert res["name"] == "Consulta Prioritaria"
        assert "EPS" in res["attention_time"]

    def test_level_5_external_consult(self):
        transcript = "Vengo para lectura de examenes de laboratorio y formulacion de medicamentos de control"
        res = evaluate_christus_sinergia_triage(transcript)
        assert res["level"] == 5
        assert res["name"] == "Consulta Externa"
        assert "EPS" in res["attention_time"]

    def test_ai_analyzer_fallback_on_llm_failure(self):
        # Simular fallo de LLM (e.g. 503 UNAVAILABLE)
        with patch("google.genai.Client") as mock_client:
            mock_inst = MagicMock()
            mock_inst.models.generate_content.side_effect = Exception("503 UNAVAILABLE: Model is overloaded")
            mock_client.return_value = mock_inst

            transcript = "Paciente Carlos Perez CC 1020304050 con dolor toracico opresivo de inicio subito"
            result = analyze_triage_transcript(transcript)

            assert "triage" in result
            assert result["triage"]["level"] == 2
            assert result["triage"]["name"] == "Emergencia"
            assert result["protocol"] == "Christus Sinergia Salud"
            assert "warning" in result
            assert "alta demanda temporal" in result["warning"]
            assert result["patientInfo"]["documentId"] == "1020304050"


# Una frase por criterio del motor: si se rompe un patron, el test indica cual.
CRITERIA_CASES = [
    # Nivel 1 - Reanimacion
    ("paciente sin signos vitales", 1),
    ("llega inconsciente a la sala", 1),
    ("le dio un paro cardiaco en la casa", 1),
    ("lo trajeron en coma", 1),
    ("presenta cianosis severa y asfixia", 1),
    ("se esta desangrando por la herida", 1),
    ("amputacion traumatica de la mano", 1),
    ("parto expulsivo, el bebe esta coronando", 1),
    ("gran quemado por explosion", 1),
    ("hipotermia severa tras inmersion", 1),
    ("politraumatismo severo por accidente de transito", 1),
    # Nivel 2 - Emergencia
    ("dolor toracico opresivo", 2),
    ("dolor de pecho irradiado a la mandibula", 2),
    ("tuvo una crisis epileptica", 2),
    ("presion 200 con cefalea", 2),
    ("paciente con cetoacidosis diabetica", 2),
    ("tiene tirajes intercostales", 2),
    ("fractura expuesta de tibia", 2),
    ("sobredosis de medicamentos", 2),
    ("intento de suicidio con arma corto punzante", 2),
    ("quemadura de tercer grado en el brazo", 2),
    # Nivel 3 - Urgencia
    ("vertigo severo desde la mañana", 3),
    ("disnea leve al caminar", 3),
    ("no tolera via oral desde ayer", 3),
    ("dolor en la fistula arteriovenosa", 3),
    ("urticaria generalizada tras comer mariscos", 3),
    ("quemadura de segundo grado en la mano", 3),
    ("luxacion de hombro", 3),
    # Nivel 4 - Consulta prioritaria
    ("resfriado comun con rinorrea", 4),
    ("amigdalitis con placas en la garganta", 4),
    ("disuria desde hace dos dias", 4),
    ("herida superficial en la rodilla", 4),
    ("crisis de angustia leve", 4),
    # Nivel 5 - Consulta externa
    ("migraña de años sin cambios", 5),
    ("tos cronica de fumador", 5),
    ("estreñimiento hace semanas", 5),
    ("dermatitis en las manos", 5),
    ("vengo por resultados de laboratorio", 5),
    ("renovacion de formula de la tension", 5),
]


class TestRuleCriteria:
    @pytest.mark.parametrize("transcript,expected", CRITERIA_CASES)
    def test_each_criterion_maps_to_its_level(self, transcript, expected):
        assert evaluate_christus_sinergia_triage(transcript)["level"] == expected

    @pytest.mark.parametrize("transcript", [
        "DOLOR TORÁCICO OPRESIVO",
        "Dolor Torácico opresivo",
        "dolor toracico opresivo",
    ])
    def test_ignores_case_and_accents(self, transcript):
        assert evaluate_christus_sinergia_triage(transcript)["level"] == 2

    def test_most_severe_level_wins(self):
        # Una sola consulta con criterios de varios niveles se clasifica por el mas grave.
        transcript = "tiene gripa y dolor de garganta, pero ahora llega inconsciente y con dolor toracico"
        assert evaluate_christus_sinergia_triage(transcript)["level"] == 1
        assert evaluate_christus_sinergia_triage("tos y congestion con dolor toracico")["level"] == 2

    def test_symptoms_list_is_evaluated(self):
        res = evaluate_christus_sinergia_triage("consulta por malestar", symptoms=["Estado convulsivo"])
        assert res["level"] == 2

    def test_justification_names_the_matched_criterion(self):
        res = evaluate_christus_sinergia_triage("fractura expuesta de femur")
        assert res["justification"].startswith("Protocolo Christus Sinergia Salud - Triage 2")
        assert "Fractura expuesta" in res["justification"]


class TestRuleFallbacks:
    def test_unmatched_pain_defaults_to_level_4(self):
        res = evaluate_christus_sinergia_triage("me duele la espalda, tengo dolor desde ayer")
        assert res["level"] == 4
        assert res["confidence"] == 0.80

    def test_unmatched_fever_defaults_to_level_4(self):
        assert evaluate_christus_sinergia_triage("tiene fiebre")["level"] == 4

    @pytest.mark.parametrize("transcript", ["", "   ", "vengo a una consulta general"])
    def test_without_findings_defaults_to_level_5(self, transcript):
        res = evaluate_christus_sinergia_triage(transcript)
        assert res["level"] == 5
        assert res["confidence"] == 0.78


class TestRuleOutputContract:
    @pytest.mark.parametrize("transcript,expected", [
        ("paciente sin signos vitales", 1),
        ("fractura expuesta", 2),
        ("luxacion de codo", 3),
        ("dolor de garganta", 4),
        ("dermatitis", 5),
    ])
    def test_output_matches_protocol_table(self, transcript, expected):
        res = evaluate_christus_sinergia_triage(transcript)
        assert set(res) == {"level", "name", "attention_time", "justification", "confidence", "protocol"}
        assert res["level"] == expected
        assert res["name"] == CHRISTUS_SINERGIA_LEVELS[expected]["name"]
        assert res["attention_time"] == CHRISTUS_SINERGIA_LEVELS[expected]["attention_time"]
        assert res["protocol"] == "Christus Sinergia Salud"
        assert 0 < res["confidence"] <= 1

    def test_confidence_decreases_with_severity_level(self):
        confidences = [
            evaluate_christus_sinergia_triage(text)["confidence"]
            for text in ["sin signos vitales", "fractura expuesta", "luxacion", "faringitis", "dermatitis"]
        ]
        assert confidences == sorted(confidences, reverse=True)


class TestRuleRegressions:
    """Fallos de patrones detectados al construir el benchmark sintetico."""

    @pytest.mark.parametrize("transcript", [
        "embarazada de 20 semanas con sangrado vaginal abundante",
        "sangrado vaginal en paciente embarazada",
        "sangrado vaginal y esta en embarazo",
    ])
    def test_vaginal_bleeding_in_pregnancy_is_level_2(self, transcript):
        assert evaluate_christus_sinergia_triage(transcript)["level"] == 2

    @pytest.mark.parametrize("transcript", [
        "vomito dos veces hoy, sin deshidratacion",
        "diarrea desde ayer sin deshidratacion",
        "vomito y diarrea sin deshidratacion, tolera liquidos",
    ])
    def test_without_dehydration_is_level_4(self, transcript):
        assert evaluate_christus_sinergia_triage(transcript)["level"] == 4

    def test_dehydration_is_still_level_3(self):
        assert evaluate_christus_sinergia_triage("vomito y diarrea con deshidratacion")["level"] == 3

    @pytest.mark.parametrize("transcript,expected", [
        ("tuvo dos convulsiones seguidas", 2),
        ("crisis epilepticas repetidas", 2),
        ("tiene sibilancias", 3),
        ("tengo silbidos en el pecho", 3),
    ])
    def test_plural_forms_are_recognized(self, transcript, expected):
        assert evaluate_christus_sinergia_triage(transcript)["level"] == expected

    @pytest.mark.parametrize("transcript", ["glucosa > 400 en la casa", "glucosa >450"])
    def test_high_glucose_is_level_2(self, transcript):
        assert evaluate_christus_sinergia_triage(transcript)["level"] == 2

    @pytest.mark.parametrize("transcript", [
        "cuando me paro rapido me mareo un poquito",
        "la mama dice que no quiere que coma",
        "vino con la comadre a consulta general",
    ])
    def test_everyday_words_do_not_trigger_reanimation(self, transcript):
        assert evaluate_christus_sinergia_triage(transcript)["level"] != 1

    def test_colombian_flu_term_is_level_4(self):
        assert evaluate_christus_sinergia_triage("tengo gripa desde el lunes")["level"] == 4

    def test_negated_finding_is_ignored(self):
        # Antes era una limitacion conocida (xfail); se resolvio con triage/negation.py.
        assert evaluate_christus_sinergia_triage("niega dolor toracico, consulta por resfriado comun")["level"] == 4

    # Antes eran limitaciones conocidas (xfail); se resolvieron con el escalado por signos vitales.
    def test_low_oxygen_saturation_escalates(self):
        assert evaluate_christus_sinergia_triage("saturacion de 84 por ciento al aire ambiente")["level"] <= 2

    def test_hypotension_escalates(self):
        assert evaluate_christus_sinergia_triage("presion 70 sobre 40 y frecuencia cardiaca de 140")["level"] == 1


class TestRuleKnownLimitations:
    """
    Limitaciones conocidas del motor lexico (documentadas en docs/INFORME_IMPLEMENTACION_Y_BRECHAS.md).
    strict=True: si un cambio las resuelve, el test pasa a fallar y obliga a actualizar la documentacion.
    """

    @pytest.mark.xfail(strict=True, reason="Solo reconoce las expresiones literales del catalogo, no parafrasis")
    def test_paraphrased_stroke_is_level_2(self):
        assert evaluate_christus_sinergia_triage("de repente no puede mover el brazo y habla enredado")["level"] <= 2
