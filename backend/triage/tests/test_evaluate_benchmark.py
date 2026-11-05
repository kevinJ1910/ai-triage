import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return path


class TestEvaluateBenchmark:
    def test_rules_engine_reports_metrics_and_critical_misses(self, tmp_path):
        dataset = _write(tmp_path, 'casos.json', json.dumps([
            {"id": "c1", "transcript": "paciente inconsciente, no respira", "reference_level": 1},
            {"id": "c2", "transcript": "vengo por renovacion de formula", "reference_level": 5},
            # Caso critico que el motor de reglas no reconoce: debe reportarse como infratriaje
            {"id": "c3", "transcript": "me siento raro desde hace un rato", "reference_level": 2},
        ]))
        output = tmp_path / 'resultados.json'
        out = StringIO()
        call_command('evaluate_benchmark', str(dataset), '--engine', 'reglas', '--output', str(output), stdout=out)

        text = out.getvalue()
        assert "Casos evaluados: 3" in text
        assert "Casos criticos infratriados: c3" in text

        detail = json.loads(output.read_text(encoding='utf-8'))
        assert [c['predicted_level'] for c in detail['cases']][:2] == [1, 5]
        assert detail['summary']['critical_cases'] == 2
        assert detail['summary']['critical_sensitivity'] == 50.0

    def test_accepts_csv(self, tmp_path):
        dataset = _write(tmp_path, 'casos.csv', "id,transcript,reference_level\na,paciente inconsciente,1\n")
        out = StringIO()
        call_command('evaluate_benchmark', str(dataset), stdout=out)
        assert "Concordancia exacta: 100.0%" in out.getvalue()

    def test_pipeline_engine_requires_split(self, tmp_path, mocker):
        analyzer = mocker.patch('triage.ai_analyzer.analyze_triage_transcript')
        dataset = _write(tmp_path, 'casos.json', json.dumps([{"id": 1, "transcript": "dolor", "reference_level": 3}]))
        with pytest.raises(CommandError, match='--split'):
            call_command('evaluate_benchmark', str(dataset), '--engine', 'pipeline', stdout=StringIO())
        analyzer.assert_not_called()

    def test_pipeline_engine_uses_analyzer_without_cache(self, tmp_path, mocker, _raw_dir_in_tmp):
        analyzer = mocker.patch(
            'triage.ai_analyzer.analyze_triage_transcript',
            return_value={"triage": {"level": 3}, "engine_used": "gemini-2.5-flash", "rule_level": 4,
                          "llm_raw": "{}"},
        )
        dataset = _write(tmp_path, 'casos.json', json.dumps([
            {"id": 1, "transcript": "dolor", "reference_level": 3, "split": "dev"}]))
        out = StringIO()
        call_command('evaluate_benchmark', str(dataset), '--engine', 'pipeline', '--split', 'dev', stdout=out,
                     stderr=StringIO())
        from triage.ai_analyzer import PROMPT_VERSION
        analyzer.assert_called_once_with("dolor", use_cache=False, strict_llm=True, include_raw=True,
                                         combine_policy='llm', prompt_version=PROMPT_VERSION)
        assert "gemini-2.5-flash" in out.getvalue()
        assert list(_raw_dir_in_tmp.glob('*.jsonl'))

        # Reanudar no repite el caso ya evaluado.
        call_command('evaluate_benchmark', str(dataset), '--engine', 'pipeline', '--split', 'dev', stdout=StringIO(),
                     stderr=StringIO())
        assert analyzer.call_count == 1

    def test_pipeline_failed_case_stays_pending(self, tmp_path, mocker):
        mocker.patch('triage.ai_analyzer.analyze_triage_transcript', side_effect=RuntimeError("500 INTERNAL"))
        dataset = _write(tmp_path, 'casos.json', json.dumps([
            {"id": 1, "transcript": "dolor", "reference_level": 3, "split": "dev"}]))
        with pytest.raises(CommandError, match='Ningun caso'):
            call_command('evaluate_benchmark', str(dataset), '--engine', 'pipeline', '--split', 'dev',
                         '--retries', '0', stdout=StringIO(), stderr=StringIO())

    @pytest.mark.parametrize("content", [
        "[]",
        json.dumps([{"id": 1, "transcript": "tos", "reference_level": 9}]),
        json.dumps([{"id": 1, "transcript": "", "reference_level": 3}]),
        "{no es json",
    ])
    def test_rejects_invalid_datasets(self, tmp_path, content):
        dataset = _write(tmp_path, 'casos.json', content)
        with pytest.raises(CommandError):
            call_command('evaluate_benchmark', str(dataset), stdout=StringIO())
