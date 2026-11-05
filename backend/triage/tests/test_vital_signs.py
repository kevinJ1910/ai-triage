import pytest

from triage.clinical_protocol import evaluate_christus_sinergia_triage, evaluate_vital_signs


class TestVitalSignRules:
    @pytest.mark.parametrize("vitals, level", [
        ({'gcs': 7}, 1),
        ({'spo2': 82}, 1),
        ({'bp_sys': 65, 'bp_dia': 40}, 1),
        ({'bp_sys': 85, 'bp_dia': 50, 'heart_rate': 130}, 1),
        ({'heart_rate': 160}, 1),
        ({'respiratory_rate': 38}, 1),
        ({'temperature': 27.0}, 1),
        ({'gcs': 13}, 2),
        ({'spo2': 90}, 2),
        ({'bp_sys': 85, 'bp_dia': 50}, 2),
        ({'bp_sys': 190, 'bp_dia': 100}, 2),
        ({'bp_sys': 170, 'bp_dia': 120}, 2),
        ({'heart_rate': 135}, 2),
        ({'respiratory_rate': 26}, 2),
        ({'temperature': 34.5}, 2),
        ({'glucose': 45}, 2),
        ({'glucose': 480}, 2),
        ({'eva': 9}, 2),
        ({'eva': 6}, 3),
    ])
    def test_thresholds(self, vitals, level):
        assert evaluate_vital_signs(vitals)["level"] == level

    @pytest.mark.parametrize("vitals", [
        {}, None,
        {'spo2': 96, 'heart_rate': 88, 'bp_sys': 125, 'bp_dia': 80, 'respiratory_rate': 16, 'temperature': 37.0},
        {'gcs': 15, 'glucose': 110, 'eva': 3},
        {'temperature': 39.5},
    ])
    def test_normal_or_missing_vitals_do_not_escalate(self, vitals):
        assert evaluate_vital_signs(vitals) is None

    def test_justification_lists_every_criterion_of_the_level(self):
        result = evaluate_vital_signs({'spo2': 80, 'respiratory_rate': 40})
        assert "SpO2 < 85 %" in result["justification"]
        assert "FR < 8 o > 35 rpm" in result["justification"]


class TestVitalSignsInRulesEngine:
    def test_vitals_only_raise_urgency(self):
        # Patron de nivel 1 (no respira) con signos vitales normales: se mantiene en 1.
        assert evaluate_christus_sinergia_triage("no respira, saturacion de 97")["level"] == 1

    def test_vitals_escalate_a_mild_complaint(self):
        result = evaluate_christus_sinergia_triage("tengo gripa y moqueo, saturando al 88 por ciento")
        assert result["level"] == 2
        assert "signos vitales" in result["justification"]

    def test_structured_vitals_can_be_passed_explicitly(self):
        assert evaluate_christus_sinergia_triage("me siento raro", vitals={'gcs': 6})["level"] == 1

    def test_accented_transcript_is_parsed(self):
        assert evaluate_christus_sinergia_triage("Tensión arterial de 85 sobre 50, pulso de 128")["level"] == 1

    def test_colloquial_glucometry_phrases_escalate_to_level_2(self):
        res = evaluate_christus_sinergia_triage("La glucometría salió en 480, tiene mucha sed y dolor de barriga")
        assert res["level"] == 2
        assert "Glucemia" in res["justification"]
