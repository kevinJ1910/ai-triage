import pytest

from triage.clinical_protocol import _normalize_text, evaluate_christus_sinergia_triage
from triage.clinical_rag import ClinicalKnowledgeRAG
from triage.input_pipeline import ClinicalTranscriptCompressor
from triage.negation import find_affirmed, split_affirmed_negated, strip_negated


def _affirmed(text, phrase):
    match = find_affirmed(rf"\b{phrase}\b", _normalize_text(text))
    return match.group() if match else None


class TestNegationDetector:
    @pytest.mark.parametrize("text, phrase", [
        ("niega dolor torácico, consulta por resfriado", "dolor toracico"),
        ("No tiene dolor en el pecho", "dolor en el pecho"),
        ("sin fiebre ni dificultad para respirar", "fiebre"),
        ("sin fiebre ni dificultad para respirar", "dificultad para respirar"),
        ("no he vomitado y solo tengo un chichón", "vomitado"),
        ("no me falta el aire", "falta el aire"),
        ("no le duele", "duele"),
        ("sin sudoración, sin falta de aire y no se le corre al brazo", "se le corre al brazo"),
        ("tóxicos negativo", "toxicos"),
    ])
    def test_negated_findings(self, text, phrase):
        assert _affirmed(text, phrase) is None

    @pytest.mark.parametrize("text, phrase", [
        # La particula forma parte del hallazgo: apnea, inconsciencia, paresia, oliguria, hiporexia.
        ("no responde, no respira y no le encuentro pulso", "no respira"),
        ("lo encontraron sin respuesta", "sin respuesta"),
        ("no puede mover el brazo derecho", "mover el brazo"),
        ("casi no orino", "orino"),
        ("no he podido comer y tengo náuseas", "comer"),
        ("no me dan ganas de comer", "comer"),
        ("no se le quita el dolor", "dolor"),
        # Terminadores de alcance.
        ("no tengo fiebre, pero vomito mucho", "vomito"),
        ("no tengo fiebre y me duele la cabeza", "duele la cabeza"),
        # Fuera de la ventana de cinco palabras.
        ("no vino ayer porque estaba en el trabajo con dolor", "dolor"),
    ])
    def test_affirmed_findings(self, text, phrase):
        assert _affirmed(text, phrase) is not None

    def test_split_affirmed_negated(self):
        text = _normalize_text("Tengo tos y moqueo desde ayer, sin fiebre")
        assert split_affirmed_negated(text, ["tos", "fiebre", "diarrea"]) == (["tos"], ["fiebre"])

    def test_strip_negated_keeps_only_affirmed_text(self):
        text = _normalize_text("no tengo fiebre ni vómito, pero me duele el pecho")
        assert strip_negated(text) == "pero me duele el pecho"


class TestNegationInPipeline:
    def test_rules_engine_ignores_negated_chest_pain(self):
        assert evaluate_christus_sinergia_triage("No tiene dolor en el pecho, viene por un resfriado con moqueo")["level"] == 4

    def test_rules_engine_keeps_affirmed_finding_with_particle(self):
        assert evaluate_christus_sinergia_triage("no responde y no respira")["level"] == 1

    def test_negated_fever_does_not_trigger_default_level_4(self):
        assert evaluate_christus_sinergia_triage("vengo a control, no tengo fiebre")["level"] == 5

    def test_negated_red_flag_is_not_reported(self):
        flags = ClinicalTranscriptCompressor.detect_red_flags("niega dolor en el pecho y no convulsiona")
        assert "Sospecha Síndrome Coronario Agudo" not in flags

    def test_rag_does_not_retrieve_criteria_for_negated_findings(self):
        negated = ClinicalKnowledgeRAG.retrieve("niega dolor toracico, tiene moqueo y estornudos")
        affirmed = ClinicalKnowledgeRAG.retrieve("dolor toracico opresivo")
        assert "c2_chest_pain_sca" in [c["id"] for c in affirmed]
        assert "c2_chest_pain_sca" not in [c["id"] for c in negated]
