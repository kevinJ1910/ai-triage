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
