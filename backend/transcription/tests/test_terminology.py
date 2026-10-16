import json
import shutil
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command

from transcription import normalizer
from django.core.management.base import CommandError

from transcription.terminology import (
    ATC, CATALOG_DIR, CIE10, _lexicon, canonical_cie10, clear_caches, find_concepts, is_snomed_concept_id,
    lookup_term, snomed_catalog, validate_catalogs, validate_code, validate_snomed,
)


def _terms(text):
    return [(m.raw, m.concept.term, m.source) for m in find_concepts(text)]


class TestCatalogs:
    def test_catalogs_are_consistent(self):
        # Sin formas duplicadas entre conceptos, categorias validas y todos los codigos en el catalogo local.
        assert validate_catalogs() == []

    def test_dictionary_covers_at_least_300_surface_forms(self):
        assert len(_lexicon()) >= 300


class TestConceptMatching:
    def test_longest_match_wins(self):
        assert _terms("me aprieta el pecho") == [("me aprieta el pecho", "dolor torácico opresivo", "diccionario")]

    def test_spans_refer_to_the_original_text(self):
        text = "Tengo dolor torácico y vómito"
        matches = find_concepts(text)
        assert [text[m.start:m.end] for m in matches] == ["dolor torácico", "vómito"]

    def test_accents_and_case_do_not_matter(self):
        assert _terms("DOLOR TORACICO")[0][1] == "dolor torácico"

    def test_abbreviations(self):
        assert _terms("antecedente de HTA y DM2") == [
            ("HTA", "hipertensión arterial", "abreviatura"),
            ("DM2", "diabetes mellitus tipo 2", "abreviatura"),
        ]

    def test_asr_corrections_resolve_to_the_catalog_concept(self):
        match = find_concepts("tomo posartan en la mañana")[0]
        assert (match.concept.term, match.concept.code, match.source) == ("losartán", "C09CA01", "correccion_asr")

    def test_word_boundaries(self):
        assert _terms("hipoglicemia") == [("hipoglicemia", "hipoglucemia", "diccionario")]

    def test_lookup_term(self):
        assert lookup_term("Disnea").code == "R06.0"
        assert lookup_term("algo que no existe") is None


class TestCodeValidation:
    @pytest.mark.parametrize("raw, expected", [
        ("R06.0", "R06.0"), ("r060", "R06.0"), ("R51X", "R51"), ("I10", "I10"), ("123", None), ("R0", None),
    ])
    def test_canonical_cie10(self, raw, expected):
        assert canonical_cie10(raw) == expected

    def test_cie10_in_catalog_is_valid(self):
        assert validate_code("R060", CIE10) == ("R06.0", True)

    def test_well_formed_cie10_outside_partial_catalog_is_unverifiable(self):
        assert validate_code("Q99.9", CIE10) == ("Q99.9", None)

    def test_malformed_codes_are_flagged_not_fixed(self):
        assert validate_code("267036007", CIE10) == ("267036007", False)
        assert validate_code("99XX", ATC) == ("99XX", False)

    def test_atc(self):
        assert validate_code("C09CA01", ATC) == ("C09CA01", True)
        assert validate_code("C09CA99", ATC) == ("C09CA99", None)

    def test_missing_code(self):
        assert validate_code(None, CIE10) == (None, None)


class TestSnomedValidation:
    def test_verhoeff_check_digit_and_partition(self):
        assert is_snomed_concept_id("267036007")
        assert not is_snomed_concept_id("267036008")  # digito de control alterado
        assert is_snomed_concept_id("450671000124109")  # concepto de una extension (particion 10)
        assert not is_snomed_concept_id("12345")

    def test_catalog_code_is_valid_and_unknown_well_formed_is_unverifiable(self):
        assert validate_snomed("25064002") == ("25064002", True)
        assert validate_snomed("450671000124109") == ("450671000124109", None)
        assert validate_snomed("267036008") == ("267036008", False)
        assert validate_snomed(None) == (None, None)

    def test_catalog_records_the_verified_edition(self):
        catalog = snomed_catalog()
        assert catalog["edicion"].startswith("SNOMED CT International Edition")
        assert catalog["codigos"]["267036007"] == "Dyspnea (finding)"


class TestConceptMappings:
    def test_negation_and_allergy_context(self):
        mappings = normalizer.concept_mappings(
            "Hipertenso, toma losartán, alérgico a la penicilina y a las sulfas, niega fiebre"
        )
        by_term = {m["medical_term"]: m for m in mappings}
        assert by_term["losartán"]["allergy"] is False
        assert by_term["penicilina"]["allergy"] is True
        assert by_term["sulfonamidas"]["allergy"] is True
        assert by_term["fiebre"]["negated"] is True
        assert by_term["hipertensión arterial"]["negated"] is False

    def test_allergen_outside_allergy_context_is_ignored(self):
        assert normalizer.concept_mappings("se cayó al polvo del camino") == []

    def test_rules_output(self):
        result = normalizer.normalize_with_rules("tengo calentura y HTA, tomo posartan")
        assert result["normalized_text"] == "tengo fiebre y hipertensión arterial, tomo losartán"
        assert result["layers"] == {"correccion_asr": 1, "abreviatura": 1, "diccionario": 1, "llm": 0}
        assert all(m["valid"] is True for m in result["mappings"])
        assert set(result["catalog_version"]) == {"coloquialismos", "abreviaturas", "correcciones_asr", "cie10", "snomed"}

    def test_mappings_carry_verified_snomed_codes(self):
        mapping = normalizer.concept_mappings("me falta el aire")[0]
        assert (mapping["code"], mapping["code_snomed"], mapping["snomed_valid"]) == ("R06.0", "267036007", True)


@pytest.mark.django_db
class TestLLMResidualLayer:
    TEXT = "Me llamo Ana Ruiz, tengo calentura y un dolor punzante en el talón desde hace dos días"

    def _run(self, mocker, mappings, normalized_text="Paciente con fiebre y talalgia."):
        mocker.patch.object(normalizer, "_resolve_gemini_key", return_value="test-key")
        client_cls = mocker.patch("google.genai.Client")
        generate = client_cls.return_value.models.generate_content
        generate.return_value = SimpleNamespace(text=json.dumps(
            {"normalized_text": normalized_text, "summary": "Fiebre y talalgia.", "mappings": mappings}
        ))
        return normalizer.normalize_clinical_text(self.TEXT), generate

    def test_llm_only_adds_validated_residual_terms(self, mocker):
        result, _ = self._run(mocker, [
            {"raw_term": "dolor punzante en el talón", "medical_term": "talalgia", "code": "M79.67",
             "code_snomed": "267036008", "category": "Sintoma"},
            {"raw_term": "calentura", "medical_term": "hipertermia", "code": "R50.9", "category": "Signo"},
            {"raw_term": "dolor de oído", "medical_term": "otalgia", "code": "H92.0", "category": "Sintoma"},
        ])
        sources = {m["raw_term"]: m["source"] for m in result["mappings"]}
        # 'calentura' ya la resolvio el catalogo y 'dolor de oido' no aparece en el relato. El termino del
        # LLM contiene al 'dolor' generico del catalogo: lo precisa y ambos se conservan.
        assert sources == {"calentura": "diccionario", "dolor": "diccionario", "dolor punzante en el talón": "llm"}
        residual = next(m for m in result["mappings"] if m["source"] == "llm")
        assert residual["valid"] is False  # M79.67 no es un codigo CIE-10 de la OMS: se marca, no se corrige.
        assert residual["snomed_valid"] is False  # digito de control invalido
        assert result["layers"]["llm"] == 1

    def test_prompt_is_pseudonymized_and_lists_resolved_terms(self, mocker):
        result, generate = self._run(mocker, [], normalized_text="[NOMBRE] refiere fiebre.")
        prompt = generate.call_args.kwargs["contents"]
        assert "Ana Ruiz" not in prompt
        assert '"calentura" -> fiebre (R50.9)' in prompt
        assert result["normalized_text"] == "Ana Ruiz refiere fiebre."

    def test_uses_flash_lite_first(self, mocker):
        _, generate = self._run(mocker, [])
        assert generate.call_args_list[0].kwargs["model"] == normalizer.NORMALIZER_LLM_MODEL


class TestVerifySnomed:
    def test_reports_inactive_codes(self, monkeypatch):
        def fake_lookup(server, code, timeout=30):
            inactive = code == "267036007"
            return {"fsn": snomed_catalog()["codigos"].get(code), "display": None, "version": None, "inactive": inactive}
        monkeypatch.setattr("transcription.management.commands.verify_snomed.lookup", fake_lookup)
        with pytest.raises(CommandError):
            call_command("verify_snomed", "--pause", "0", stdout=StringIO())

    def test_passes_when_every_code_is_active(self, monkeypatch):
        monkeypatch.setattr("transcription.management.commands.verify_snomed.lookup",
                            lambda server, code, timeout=30: {"fsn": snomed_catalog()["codigos"][code], "display": None,
                                                              "version": None, "inactive": False})
        out = StringIO()
        call_command("verify_snomed", "--pause", "0", stdout=out)
        assert f"{len(snomed_catalog()['codigos'])} de" in out.getvalue()


class TestImportCie10:
    def test_imports_full_table_and_marks_catalog_complete(self, tmp_path, monkeypatch):
        shutil.copy(CATALOG_DIR / "cie10.json", tmp_path / "cie10.json")
        monkeypatch.setattr("transcription.management.commands.import_cie10.CATALOG_DIR", tmp_path)
        csv_path = tmp_path / "tabla.csv"
        csv_path.write_text("Codigo;Nombre\nR060;Disnea\nR51X;Cefalea\nXXXX;fila invalida\n", encoding="utf-8")

        call_command("import_cie10", str(csv_path))

        imported = json.loads((tmp_path / "cie10.json").read_text(encoding="utf-8"))
        assert imported["completo"] is True
        assert imported["codigos"] == {"R06.0": "Disnea", "R51": "Cefalea"}
        clear_caches()
