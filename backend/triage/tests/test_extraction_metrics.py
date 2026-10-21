import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from triage.entity_corpus import ENTITY_TYPES, load_entity_corpus
from triage.extraction_metrics import (
    aggregate,
    annotator_agreement,
    bootstrap_ci,
    canonical_vital,
    code_accuracy,
    code_hits,
    score_case,
    terms_match,
)


def _ent(text, normalized, negated=False):
    return {'text': text, 'normalized': normalized, 'negated': negated, 'cie10': None}


def _gold(**kwargs):
    return {etype: kwargs.get(etype, []) for etype in ENTITY_TYPES}


class TestTermMatching:
    def test_strict_accepts_span_or_normalized_ignoring_accents(self):
        gold = _ent('dolor en el pecho', 'dolor torácico')
        assert terms_match('Dolor toracico', gold, 'symptoms', 'strict')
        assert terms_match('dolor en el pecho', gold, 'symptoms', 'strict')
        assert not terms_match('dolor torácico opresivo', gold, 'symptoms', 'strict')

    def test_relaxed_accepts_containment_and_token_overlap(self):
        gold = _ent('dolor en el pecho tipo opresión', 'dolor torácico opresivo')
        assert terms_match('dolor torácico', gold, 'symptoms', 'relaxed')
        assert not terms_match('cefalea', gold, 'symptoms', 'relaxed')

    def test_vitals_compare_type_and_values(self):
        gold = _ent('Presión 70 sobre 40', 'PA: 70/40 mmHg')
        assert canonical_vital('presion 70 sobre 40') == ('PA', ('70', '40'))
        assert terms_match('PA: 70/40 mmHg', gold, 'vitals')
        assert terms_match('Tensión arterial 70/40', gold, 'vitals')
        assert not terms_match('PA: 80/40 mmHg', gold, 'vitals')
        assert not terms_match('FC: 70/40', gold, 'vitals')


class TestScoring:
    def test_counts_true_false_positives_and_misses(self):
        gold = _gold(symptoms=[_ent('fiebre', 'fiebre'), _ent('tos', 'tos')])
        counts = score_case(gold, {'symptoms': ['fiebre', 'mareo']})
        assert counts['symptoms'] == {'tp': 1, 'fp': 1, 'fn': 1, 'negated_gold': 0,
                                      'negation_errors': 0, 'negated_detected': 0}

    def test_negated_finding_reported_as_present_is_a_negation_error(self):
        gold = _gold(symptoms=[_ent('fiebre', 'fiebre', negated=True), _ent('moqueo', 'rinorrea')])
        counts = score_case(gold, {'symptoms': ['fiebre', 'rinorrea']})['symptoms']
        assert counts['tp'] == 1 and counts['fp'] == 1
        assert counts['negation_errors'] == 1

    def test_explicit_negated_findings_are_credited(self):
        gold = _gold(symptoms=[_ent('dolor en el pecho', 'dolor torácico', negated=True)])
        counts = score_case(gold, {'symptoms': [], 'negated_findings': ['dolor torácico']})['symptoms']
        assert counts['negated_detected'] == 1 and counts['negation_errors'] == 0

    def test_aggregate_micro_and_negation(self):
        gold = _gold(symptoms=[_ent('fiebre', 'fiebre', negated=True), _ent('tos', 'tos')],
                     medications=[_ent('losartán', 'losartán')])
        summary = aggregate([score_case(gold, {'symptoms': ['tos', 'fiebre'], 'medications': ['losartan']})])
        assert summary['micro'] == {'tp': 2, 'fp': 1, 'fn': 0, 'precision': 0.667, 'recall': 1.0, 'f1': 0.8}
        assert summary['negation']['negation_accuracy'] == 0.0
        assert summary['by_type']['allergies']['f1'] is None

    def test_missing_type_counts_as_zero_in_macro_f1(self):
        gold = _gold(symptoms=[_ent('tos', 'tos')], allergies=[_ent('penicilina', 'penicilina')])
        summary = aggregate([score_case(gold, {'symptoms': ['tos']})])
        assert summary['by_type']['allergies']['f1'] == 0.0
        assert summary['macro_f1'] == 0.5

    def test_bootstrap_is_reproducible_and_bounded(self):
        values = [0, 1, 1, 1, 0, 1, 1, 0, 1, 1]
        mean = lambda sample: sum(sample) / len(sample)  # noqa: E731
        first = bootstrap_ci(values, mean, n_resamples=200)
        assert first == bootstrap_ci(values, mean, n_resamples=200)
        assert 0.0 <= first[0] <= 0.7 <= first[1] <= 1.0
        assert bootstrap_ci([], mean) is None

    def test_annotator_agreement_compares_negation_on_matched_entities(self):
        first = _gold(symptoms=[_ent('fiebre', 'fiebre', negated=True), _ent('tos', 'tos')])
        second = _gold(symptoms=[_ent('fiebre', 'fiebre', negated=False)])
        counts = annotator_agreement(first, second)['symptoms']
        assert (counts['tp'], counts['fn'], counts['negation_agree']) == (1, 1, 0)


class TestCodeMetrics:
    def test_code_hits_accepts_colombian_format(self):
        gold = _gold(symptoms=[{**_ent('me falta el aire', 'disnea'), 'cie10': 'R06.0'},
                               {**_ent('tos', 'tos'), 'cie10': 'R05'},
                               _ent('rojo', 'eritema')])
        hits = code_hits(gold, ['R060', 'I10'])
        assert hits == {'coded_gold': 2, 'code_hits': 1}
        assert code_accuracy([hits, {'coded_gold': 0, 'code_hits': 0}])['cie10_accuracy'] == 0.5

    def test_accuracy_is_none_without_coded_entities(self):
        assert code_accuracy([])['cie10_accuracy'] is None


class TestEvaluateExtractionCommand:
    def _fake_analysis(self, transcript, use_cache, allow_llm, model, use_ner=None):
        return {'triage': {'level': 1}, 'engine_used': f'LLM ({model})', 'total_tokens': 100,
                'entities': {'symptoms': ['inconsciencia'], 'vitals': []}}

    def test_gemini_engine_requires_model(self):
        with pytest.raises(CommandError, match='--model'):
            call_command('evaluate_extraction', '--engine', 'gemini', stdout=StringIO(), stderr=StringIO())

    def test_reports_entities_triage_and_performance(self, tmp_path, mocker):
        analyzer = mocker.patch('triage.ai_analyzer.analyze_triage_transcript', side_effect=self._fake_analysis)
        output = tmp_path / 'r.json'
        out = StringIO()
        call_command('evaluate_extraction', '--engine', 'gemini', '--model', 'gemini-2.5-flash', '--split', 'dev',
                     '--limit', '3', '--output', str(output), stdout=out, stderr=StringIO())

        assert analyzer.call_count == 3
        assert analyzer.call_args.kwargs == {'use_cache': False, 'allow_llm': True, 'model': 'gemini-2.5-flash',
                                             'use_ner': False}
        text = out.getvalue()
        assert 'Casos: 3 | Motor: gemini (gemini-2.5-flash) | Split: dev' in text
        detail = json.loads(output.read_text(encoding='utf-8'))
        assert detail['performance']['tokens_total'] == 300
        assert detail['performance']['llm_failures'] == 0
        assert {c['split'] for c in detail['cases']} == {'dev'}
        assert set(detail['entities']['by_type']) == set(ENTITY_TYPES)

    def test_ner_engines_require_the_model(self, settings):
        settings.NER_MODEL_PATH = ''
        with pytest.raises(CommandError, match='NER_MODEL_PATH'):
            call_command('evaluate_extraction', '--engine', 'roberta', stdout=StringIO(), stderr=StringIO())

    def test_roberta_engine_uses_ner_without_llm(self, mocker, tmp_path):
        mocker.patch('triage.ner_model.engine_label', return_value='roberta:fake')
        analyzer = mocker.patch('triage.ai_analyzer.analyze_triage_transcript', side_effect=self._fake_analysis)
        output = tmp_path / 'r.json'
        call_command('evaluate_extraction', '--engine', 'roberta', '--split', 'dev', '--limit', '2',
                     '--output', str(output), stdout=StringIO(), stderr=StringIO())
        assert analyzer.call_args.kwargs == {'use_cache': False, 'allow_llm': False, 'model': None, 'use_ner': True}
        assert json.loads(output.read_text(encoding='utf-8'))['ner_engine'] == 'roberta:fake'

    def test_failed_llm_case_is_retried(self, mocker):
        failed = {'triage': {'level': 4}, 'engine_used': 'Motor de Reglas Clínico (Christus Sinergia)',
                  'entities': {}, 'total_tokens': 0}
        ok = {'triage': {'level': 1}, 'engine_used': 'LLM (m)', 'entities': {}, 'total_tokens': 10}
        analyzer = mocker.patch('triage.ai_analyzer.analyze_triage_transcript', side_effect=[failed, ok])
        sleep = mocker.patch('triage.management.commands.evaluate_extraction.time.sleep')
        output = StringIO()
        call_command('evaluate_extraction', '--engine', 'gemini', '--model', 'm', '--limit', '1',
                     '--retry-wait', '7', stdout=output, stderr=StringIO())
        assert analyzer.call_count == 2
        sleep.assert_called_once_with(7.0)
        assert 'fallos del LLM 0 (casos reintentados 1)' in output.getvalue()

    def test_rules_engine_runs_offline(self, mocker):
        mocker.patch('triage.ai_analyzer._resolve_gemini_api_key', side_effect=AssertionError('no debe usar la red'))
        out = StringIO()
        call_command('evaluate_extraction', '--engine', 'reglas', '--limit', '5', stdout=out, stderr=StringIO())
        assert 'Casos: 5 | Motor: reglas' in out.getvalue()

    def test_agreement_mode_does_not_run_engines(self, tmp_path, mocker):
        analyzer = mocker.patch('triage.ai_analyzer.analyze_triage_transcript')
        case = load_entity_corpus()[0]
        second = tmp_path / 'segundo.json'
        second.write_text(json.dumps([{'id': case['id'], 'entities': case['entities']}]), encoding='utf-8')
        out = StringIO()
        call_command('evaluate_extraction', '--agreement', str(second), stdout=out, stderr=StringIO())
        analyzer.assert_not_called()
        assert 'micro        F1 1.0' in out.getvalue()


class TestEvaluateBenchmarkOptions:
    def test_split_and_model_options(self, tmp_path, mocker):
        analyzer = mocker.patch(
            'triage.ai_analyzer.analyze_triage_transcript',
            return_value={'triage': {'level': 2}, 'engine_used': 'LLM (gemini-3.8-flash)', 'total_tokens': 50},
        )
        dataset = tmp_path / 'casos.json'
        dataset.write_text(json.dumps([
            {'id': 'a', 'transcript': 'dolor', 'reference_level': 2, 'split': 'dev'},
            {'id': 'b', 'transcript': 'tos', 'reference_level': 4, 'split': 'test'},
        ]), encoding='utf-8')
        out = StringIO()
        call_command('evaluate_benchmark', str(dataset), '--engine', 'pipeline', '--model', 'gemini-3.8-flash',
                     '--split', 'dev', stdout=out)
        analyzer.assert_called_once_with('dolor', use_cache=False, model='gemini-3.8-flash')
        assert 'Casos evaluados: 1' in out.getvalue()
        assert 'Tokens: 50' in out.getvalue()

    def test_model_requires_pipeline_engine(self, tmp_path):
        dataset = tmp_path / 'casos.json'
        dataset.write_text(json.dumps([{'id': 'a', 'transcript': 'dolor', 'reference_level': 2}]), encoding='utf-8')
        with pytest.raises(CommandError, match='pipeline'):
            call_command('evaluate_benchmark', str(dataset), '--model', 'x', stdout=StringIO())

    def test_split_requires_split_field(self, tmp_path):
        dataset = tmp_path / 'casos.json'
        dataset.write_text(json.dumps([{'id': 'a', 'transcript': 'dolor', 'reference_level': 2}]), encoding='utf-8')
        with pytest.raises(CommandError, match='split'):
            call_command('evaluate_benchmark', str(dataset), '--split', 'dev', stdout=StringIO())
