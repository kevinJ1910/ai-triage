import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from triage.benchmark_results import load_results
from triage.engine_comparison import compare, engine_label, markdown_table, run_agreement, write_markdown_section
from triage.metrics import triage_summary

REFERENCE = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5] * 3


def _run(engine, predicted, split='test', model=None, complete=True, **run):
    cases = [{'id': f'c{i}', 'predicted_level': p, 'reference_level': r, 'transcript': 'texto privado'}
             for i, (p, r) in enumerate(zip(predicted, REFERENCE))]
    data = {'engine': engine, 'model': model, 'split': split, 'complete': complete, 'cases': cases,
            'triage': triage_summary([(c['predicted_level'], c['reference_level']) for c in cases]),
            'performance': {'latency_ms_p50': 900, 'latency_ms_p95': 1500, 'cost_usd_per_1000': 4.2 if model else None},
            'entities': {'micro': {'f1': 0.5}}}
    if run:
        data['run'] = run
    return data


RULES = [5 if r <= 2 else r for r in REFERENCE]       # infratriaje de todos los criticos
HYBRID = list(REFERENCE)                               # acierta todo
LOCAL = [r if i % 3 else min(5, r + 1) for i, r in enumerate(REFERENCE)]


class TestEngineComparison:
    def test_labels(self):
        assert engine_label({'engine': 'reglas'}).startswith('Reglas')
        assert engine_label({'engine': 'hibrido', 'model': 'gemini-2.5-flash', 'run': {'prompt_version': 'v2',
                                                                                        'policy': 'min_critico'}}) \
            == 'Híbrido: reglas + RAG + Gemini 2.5 Flash (prompt v2, política min_critico, NER)'
        assert engine_label({'engine': 'gemini', 'model': 'gemini-2.5-flash',
                             'run': {'rule_hint': False, 'rag': False}}) == 'Gemini 2.5 Flash sin pauta de reglas ni RAG'
        assert engine_label({'engine': 'hibrido', 'model': 'local:qwen2.5:7b'}).startswith('LLM local (qwen2.5:7b)')

    def test_compare_builds_rows_and_paired_differences(self):
        runs = [('test_reglas', _run('reglas', RULES)),
                ('test_hibrido', _run('hibrido', HYBRID, model='gemini-2.5-flash')),
                ('test_local', _run('hibrido', LOCAL, model='local:qwen')),
                ('test_parcial', _run('hibrido', HYBRID, model='x', complete=False)),
                ('dev_reglas', _run('reglas', RULES, split='dev'))]
        comparison = compare(runs, 'test')
        assert [r['name'] for r in comparison['rows']] == ['test_reglas', 'test_hibrido', 'test_local']
        assert comparison['baseline'] == 'test_reglas'
        rows = {r['name']: r for r in comparison['rows']}
        assert rows['test_reglas']['cost_usd_per_1000'] == 0.0
        assert rows['test_local']['privacy'].startswith('local')
        assert rows['test_hibrido']['privacy'].startswith('nube')
        diff = next(d for d in comparison['paired'] if d['name'] == 'test_hibrido')['metrics']
        assert diff['critical_sensitivity']['diff'] == 100.0
        assert diff['cohen_kappa']['ci95'][0] > 0
        assert len(comparison['critical_misses']['test_reglas']) == 12
        assert comparison['critical_misses']['test_hibrido'] == []
        assert 'justification' not in comparison['critical_misses']['test_reglas'][0]
        assert 'Infratriaje crítico' in markdown_table(comparison)

    def test_unknown_baseline_is_rejected(self):
        with pytest.raises(ValueError):
            compare([('a', _run('reglas', RULES))], 'test', baseline='no-existe')

    def test_markdown_and_section_replacement(self, tmp_path):
        comparison = compare([('r', _run('reglas', RULES)), ('h', _run('hibrido', HYBRID, model='gemini-2.5-flash'))],
                             'test')
        table = markdown_table(comparison)
        assert '| Reglas (Christus Sinergia / Res. 5596) | 30 |' in table
        assert 'Diferencias pareadas' in table
        doc = tmp_path / 'EVALUACION.md'
        doc.write_text('# Evaluación\n\nTexto previo.\n', encoding='utf-8')
        write_markdown_section(doc, 'test', 'tabla v1')
        write_markdown_section(doc, 'test', 'tabla v2')
        text = doc.read_text(encoding='utf-8')
        assert 'Texto previo.' in text and 'tabla v2' in text and 'tabla v1' not in text
        assert text.count('comparativa:test:inicio') == 1

    def test_run_agreement(self):
        result = run_agreement(_run('hibrido', HYBRID), _run('hibrido', LOCAL))
        assert result['n'] == 30
        assert len(result['changed_cases']) == sum(1 for a, b in zip(HYBRID, LOCAL) if a != b)


class TestCompareEnginesCommand:
    def test_writes_json_and_markdown_without_cases(self, tmp_path):
        results = tmp_path / 'resultados'
        results.mkdir()
        (results / 'test_reglas.json').write_text(json.dumps(_run('reglas', RULES)), encoding='utf-8')
        (results / 'test_hibrido.json').write_text(json.dumps(_run('hibrido', HYBRID, model='gemini-2.5-flash',
                                                                   prompt_version='v1')), encoding='utf-8')
        doc = tmp_path / 'EVALUACION_TRIAJE.md'
        out = StringIO()
        call_command('compare_engines', '--split', 'test', '--results-dir', str(results), '--markdown', str(doc),
                     '--repeatability', str(results / 'test_hibrido.json'), str(results / 'test_hibrido.json'),
                     stdout=out)
        saved = json.loads((results / 'comparativa_test.json').read_text(encoding='utf-8'))
        assert len(saved['comparison']['rows']) == 2
        assert saved['comparison']['repeatability']['cohen_kappa'] == 1.0
        assert 'texto privado' not in json.dumps(saved)
        assert 'comparativa:test:inicio' in doc.read_text(encoding='utf-8')

        data = load_results(results_dir=results, asr_dir=tmp_path / 'sin_asr')
        assert [c['name'] for c in data['comparison']] == ['comparativa_test']
        assert {r['name'] for r in data['extraction']} == {'test_reglas', 'test_hibrido'}

    def test_fails_without_runs(self, tmp_path):
        with pytest.raises(CommandError, match='No hay corridas'):
            call_command('compare_engines', '--split', 'test', '--results-dir', str(tmp_path), '--no-markdown',
                         stdout=StringIO())


class TestLoadResults:
    def test_skips_partial_runs_and_exposes_run_metadata(self, tmp_path):
        (tmp_path / 'parcial.json').write_text(json.dumps(_run('hibrido', HYBRID, model='m', complete=False)),
                                               encoding='utf-8')
        (tmp_path / 'completa.json').write_text(json.dumps(_run(
            'hibrido', HYBRID, model='gemini-2.5-flash', model_versions=['gemini-2.5-flash-001'], prompt_version='v1',
            git_commit='abc', corpus_sha256='x', processor='CPU privado')), encoding='utf-8')
        (tmp_path / 'validacion_clinica_test.json').write_text(json.dumps(
            {'clinical_validation': {'n': 50, 'clinician_vs_ai': {'cohen_kappa': 0.6}}}), encoding='utf-8')
        data = load_results(results_dir=tmp_path, asr_dir=tmp_path / 'sin_asr')
        [run] = data['extraction']
        assert run['name'] == 'completa'
        assert run['run']['model_versions'] == ['gemini-2.5-flash-001']
        assert 'git_commit' not in run['run'] and 'processor' not in run['run']
        assert run['triage']['exact_agreement_ci95'] is not None
        assert data['clinical_validation'][0]['n'] == 50
