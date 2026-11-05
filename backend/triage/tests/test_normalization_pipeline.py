import json
from types import SimpleNamespace

import pytest

from triage.ai_analyzer import analyze_triage_transcript
from triage.clinical_cache import ClinicalQueryCache
from triage.clinical_rag import ClinicalKnowledgeRAG

TRANSCRIPT = ("Soy hipertenso, tomo losartán, soy alérgico a la penicilina, "
              "me duele la cabeza desde ayer y no he tenido fiebre")


@pytest.mark.django_db
class TestNormalizationInsideAnalysis:
    def test_rules_fallback_builds_entities_from_the_catalog(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        entities = analyze_triage_transcript(TRANSCRIPT, use_cache=False, allow_llm=False)["entities"]
        assert entities["symptoms"] == ["cefalea"]
        assert entities["history"] == ["hipertensión arterial"]
        assert entities["medications"] == ["losartán"]
        assert entities["allergies"] == ["penicilina"]
        assert entities["negated_findings"] == ["fiebre"]

    def test_result_exposes_normalized_terms_with_codes(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        terms = analyze_triage_transcript(TRANSCRIPT, use_cache=False, allow_llm=False)["normalized_terms"]
        by_term = {t["medical_term"]: t for t in terms}
        assert by_term["cefalea"]["code"] == "R51" and by_term["cefalea"]["valid"] is True
        assert by_term["losartán"]["code_system"] == "ATC"

    def test_llm_prompt_includes_normalized_terms(self, mocker):
        llm_output = {
            "patientInfo": {}, "entities": {"symptoms": ["cefalea"]},
            "triage": {"level": 4, "name": "Consulta Prioritaria", "attention_time": "Hasta 120 minutos",
                       "justification": "Cefalea sin signos de alarma"},
        }
        mocker.patch("triage.ai_analyzer._resolve_gemini_api_key", return_value="test-key")
        client_cls = mocker.patch("triage.ai_analyzer.genai.Client")
        generate = client_cls.return_value.models.generate_content
        generate.return_value = SimpleNamespace(text=json.dumps(llm_output), usage_metadata=None)

        result = analyze_triage_transcript(TRANSCRIPT, use_cache=False)

        prompt = generate.call_args.kwargs["contents"]
        assert '"me duele la cabeza" -> cefalea [R51]' in prompt
        assert 'ALERGIA "penicilina" -> penicilina [J01CE01]' in prompt
        assert 'NEGADO "fiebre" -> fiebre [R50.9]' in prompt
        assert result["normalized_terms"]

    def test_cache_hit_recomputes_normalized_terms_for_the_new_transcript(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "")
        ClinicalQueryCache.clear()
        analyze_triage_transcript("tengo dolor de cabeza fuerte", use_cache=True)
        second = analyze_triage_transcript("tengo cefalea fuerte", use_cache=True)
        assert second["cached"] is True
        assert [t["raw_term"] for t in second["normalized_terms"]] == ["cefalea"]


class TestSingleTerminologySource:
    def test_cache_unifies_synonyms_but_not_distinct_concepts(self):
        same = {ClinicalQueryCache.generate_fingerprint(t, {}) for t in ("me falta el aire", "disnea", "ahogo")}
        assert len(same) == 1
        assert (ClinicalQueryCache.generate_fingerprint("palpitaciones", {})
                != ClinicalQueryCache.generate_fingerprint("pulso acelerado", {}))

    def test_rag_expands_abbreviations_from_the_catalog(self):
        retrieved = ClinicalKnowledgeRAG.retrieve("paciente con ACV hace una hora", top_k=3)
        assert any(c["id"] == "c2_stroke_acv" for c in retrieved)
