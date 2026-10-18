import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from triage.evaluation_runner import (
    Checkpoint,
    RateLimiter,
    RunSpec,
    classify_llm_error,
    estimate_cost,
    performance_summary,
    privacy_label,
    retry_delay_seconds,
    run_metadata,
    run_pending,
    sha256_text,
)

DAILY = RuntimeError("429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier")
MINUTE = RuntimeError("429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier "
                      "'retryDelay': '37s'")


def _cases(n):
    return [{'id': f'c{i}', 'transcript': f'caso {i}'} for i in range(n)]


def _ok(case):
    return {'predicted_level': 3, 'latency_ms': 5}


class TestRunSpecAndCheckpoint:
    def test_run_id_changes_with_prompt_version_and_ablation(self):
        base = RunSpec(engine='hibrido', split='dev', model='gemini-2.5-flash', prompt_version='v1')
        assert base.run_id == 'dev_hibrido_gemini-2.5-flash_pv1'
        assert RunSpec(engine='hibrido', split='dev', model='gemini-2.5-flash', prompt_version='v2').run_id != base.run_id
        ablation = RunSpec(engine='gemini', split='dev', model='gemini-2.5-flash', prompt_version='v1',
                           rule_hint=False, rag=False)
        assert ablation.run_id.endswith('sin-pauta_sin-rag')
        assert RunSpec(engine='hibrido', split='dev', model='local:qwen2.5:7b').run_id == 'dev_hibrido_local-qwen2.5-7b'

    def test_checkpoint_survives_truncated_last_line(self, tmp_path):
        path = tmp_path / 'r.jsonl'
        checkpoint = Checkpoint(path)
        checkpoint.append({'id': 'a', 'transcript_sha256': sha256_text('x'), 'predicted_level': 2})
        with path.open('a', encoding='utf-8') as fh:
            fh.write('{"id": "b", "transcr')
        reloaded = Checkpoint(path)
        assert reloaded.is_done('a', sha256_text('x'))
        assert 'b' not in reloaded.records


class TestRunPending:
    def test_resume_skips_done_cases_and_reevaluates_changed_transcripts(self, tmp_path):
        checkpoint = Checkpoint(tmp_path / 'r.jsonl')
        calls = []

        def evaluate(case):
            calls.append(case['id'])
            return _ok(case)

        run_pending(_cases(3), checkpoint, evaluate)
        assert calls == ['c0', 'c1', 'c2']
        changed = _cases(3)
        changed[1]['transcript'] = 'texto corregido'
        outcome = run_pending(changed, Checkpoint(tmp_path / 'r.jsonl'), evaluate)
        assert calls[3:] == ['c1']
        assert outcome.skipped == 2 and outcome.evaluated == 1

    def test_daily_quota_stops_without_writing_the_case(self, tmp_path):
        checkpoint = Checkpoint(tmp_path / 'r.jsonl')
        answers = iter([_ok, lambda case: (_ for _ in ()).throw(DAILY)])

        outcome = run_pending(_cases(4), checkpoint, lambda case: next(answers)(case), sleep=lambda s: None)
        assert outcome.stopped == 'daily_quota'
        assert outcome.evaluated == 1
        assert outcome.pending == ['c1', 'c2', 'c3']
        assert set(Checkpoint(tmp_path / 'r.jsonl').records) == {'c0'}

    def test_minute_rate_limit_is_retried_with_suggested_delay(self, tmp_path):
        attempts = []

        def evaluate(case):
            attempts.append(case['id'])
            if len(attempts) == 1:
                raise MINUTE
            return _ok(case)

        slept = []
        outcome = run_pending(_cases(1), Checkpoint(tmp_path / 'r.jsonl'), evaluate, retry_wait=10,
                              sleep=slept.append)
        assert slept == [38.0]
        assert outcome.evaluated == 1
        assert Checkpoint(tmp_path / 'r.jsonl').records['c0']['attempts'] == 2

    def test_persistent_rate_limit_stops_the_run(self, tmp_path):
        def evaluate(case):
            raise MINUTE

        outcome = run_pending(_cases(2), Checkpoint(tmp_path / 'r.jsonl'), evaluate, retries=1, sleep=lambda s: None)
        assert outcome.stopped == 'rate_limit'
        assert outcome.pending == ['c0', 'c1']

    def test_other_errors_leave_the_case_pending_and_continue(self, tmp_path):
        def evaluate(case):
            if case['id'] == 'c0':
                raise ValueError("JSON invalido")
            return _ok(case)

        outcome = run_pending(_cases(2), Checkpoint(tmp_path / 'r.jsonl'), evaluate, retries=0)
        assert outcome.pending == ['c0'] and outcome.evaluated == 1 and outcome.stopped is None

    def test_max_calls_caps_the_batch(self, tmp_path):
        outcome = run_pending(_cases(5), Checkpoint(tmp_path / 'r.jsonl'), _ok, max_calls=2)
        assert outcome.evaluated == 2
        assert outcome.stopped == 'max_calls'
        assert outcome.pending == ['c2', 'c3', 'c4']

    def test_rate_limiter_spaces_calls(self):
        now = [0.0]
        slept = []

        def sleep(seconds):
            slept.append(round(seconds, 2))
            now[0] += seconds

        limiter = RateLimiter(rpm=5, clock=lambda: now[0], sleep=sleep)
        limiter.wait()
        now[0] += 3
        limiter.wait()
        assert slept == [10.2]  # 60 / 5 * 1.1 = 13.2 s entre llamadas; ya pasaron 3


class TestErrorsCostAndMetadata:
    @pytest.mark.parametrize("err,kind", [
        (DAILY, 'daily_quota'), (MINUTE, 'rate_limit'), (RuntimeError("503 UNAVAILABLE"), 'transient'),
        (RuntimeError("ReadTimeout"), 'transient'), (ValueError("schema"), 'other'),
    ])
    def test_classify(self, err, kind):
        assert classify_llm_error(err) == kind

    def test_retry_delay_defaults_without_hint(self):
        assert retry_delay_seconds(RuntimeError("429"), 60) == 60

    def test_cost(self):
        # 1.500 de entrada, 500 de salida y 1.000 de razonamiento en 2.5 Flash.
        assert estimate_cost('gemini-2.5-flash', 1500, 500, 1000) == pytest.approx(0.00420)
        assert estimate_cost('gemini-2.5-flash-001', 1_000_000, 0) == pytest.approx(0.30)
        assert estimate_cost('local:qwen', 10_000, 10_000) == 0.0
        assert estimate_cost(None, 1, 1) == 0.0
        assert estimate_cost('modelo-sin-precio', 1, 1) is None

    def test_performance_summary(self):
        records = [{'latency_ms': 100, 'prompt_tokens': 1000, 'completion_tokens': 200, 'thoughts_tokens': 300,
                    'total_tokens': 1500, 'attempts': 1},
                   {'latency_ms': 300, 'prompt_tokens': 1000, 'completion_tokens': 200, 'thoughts_tokens': 300,
                    'total_tokens': 1500, 'attempts': 2}]
        perf = performance_summary(records, 'gemini-2.5-flash')
        assert perf['latency_ms_p50'] in (100, 300)
        assert perf['tokens_total'] == 3000
        assert perf['cost_usd'] == pytest.approx(0.0031, abs=1e-4)
        assert perf['cost_usd_per_1000'] == pytest.approx(1.55, abs=0.01)
        assert perf['retried_cases'] == 1

    def test_metadata_has_no_local_paths(self, tmp_path):
        corpus = tmp_path / 'corpus.json'
        corpus.write_text('[]', encoding='utf-8')
        spec = RunSpec(engine='hibrido', split='dev', model='gemini-2.5-flash', prompt_version='v1')
        meta = run_metadata(spec, [{'model_version': 'gemini-2.5-flash-001'}], corpus=corpus, tier='pago',
                            hardware=None, policy='llm', prompt_sha256='abc', temperature=0.1)
        assert meta['model_versions'] == ['gemini-2.5-flash-001']
        assert meta['corpus'] == 'corpus.json'
        assert str(tmp_path) not in json.dumps(meta)
        assert meta['prices']['usd_per_million'] == {'input': 0.30, 'output': 2.50}
        assert privacy_label('hibrido', 'local:qwen').startswith('local')
        assert privacy_label('hibrido', 'gemini-2.5-flash').startswith('nube')


def _fake_analysis(transcript, **kwargs):
    level = 1 if 'respira' in transcript else 4
    return {'triage': {'level': level, 'justification': 'prueba'}, 'engine_used': 'LLM (m)', 'llm_level': level,
            'rule_level': 2, 'model_version': 'm-001', 'prompt_version': kwargs.get('prompt_version'),
            'prompt_tokens': 1000, 'completion_tokens': 100, 'thoughts_tokens': 0, 'total_tokens': 1100,
            'entities': {'symptoms': [], 'vitals': []}, 'llm_raw': '{}'}


class TestEvaluateExtractionResume:
    ARGS = ('--engine', 'gemini', '--model', 'gemini-2.5-flash', '--split', 'dev', '--limit', '10')

    def _run(self, *extra, output):
        out = StringIO()
        call_command('evaluate_extraction', *self.ARGS, '--output', str(output), *extra, stdout=out, stderr=StringIO())
        return out.getvalue(), json.loads(output.read_text(encoding='utf-8'))

    def _comparable(self, payload):
        payload = {**payload, 'run': {k: v for k, v in payload['run'].items() if k != 'generated_at'}}
        payload['cases'] = [{k: v for k, v in c.items() if k not in ('timestamp', 'latency_ms')}
                            for c in payload['cases']]
        payload['performance'] = {k: v for k, v in payload['performance'].items() if not k.startswith('latency')}
        return payload

    def test_interrupted_run_resumes_to_the_same_summary(self, tmp_path, mocker):
        mocker.patch('triage.ai_analyzer.analyze_triage_transcript', side_effect=_fake_analysis)
        _, straight = self._run('--raw-dir', str(tmp_path / 'a'), output=tmp_path / 'a.json')

        calls = {'n': 0}

        def flaky(transcript, **kwargs):
            calls['n'] += 1
            if calls['n'] == 5:
                raise DAILY
            return _fake_analysis(transcript, **kwargs)

        mocker.patch('triage.ai_analyzer.analyze_triage_transcript', side_effect=flaky)
        with pytest.raises(CommandError, match='quedan 6 casos'):
            self._run('--raw-dir', str(tmp_path / 'b'), output=tmp_path / 'b.json')
        partial = json.loads((tmp_path / 'b.json').read_text(encoding='utf-8'))
        assert partial['complete'] is False
        assert partial['performance']['pending_cases'] == 6

        text, resumed = self._run('--raw-dir', str(tmp_path / 'b'), output=tmp_path / 'b.json')
        assert 'Tanda: 6 evaluados, 4 ya en el checkpoint' in text
        assert resumed['complete'] is True
        assert self._comparable(resumed) == self._comparable(straight)

    def test_summarize_only_does_not_call_the_llm_and_applies_policy(self, tmp_path, mocker):
        mocker.patch('triage.ai_analyzer.analyze_triage_transcript', side_effect=_fake_analysis)
        _, first = self._run('--raw-dir', str(tmp_path), output=tmp_path / 'r.json')
        analyzer = mocker.patch('triage.ai_analyzer.analyze_triage_transcript')
        _, again = self._run('--raw-dir', str(tmp_path), '--summarize-only', '--policy', 'min_critico',
                             output=tmp_path / 'r2.json')
        analyzer.assert_not_called()
        assert again['run']['policy'] == 'min_critico'
        # Con rule_level 2, min_critico sube a 2 los casos que el LLM dejo en 4.
        assert {c['predicted_level'] for c in again['cases']} <= {1, 2}
        assert {c['llm_level'] for c in again['cases']} == {c['predicted_level'] for c in first['cases']}

    def test_payload_records_reproducibility_metadata(self, tmp_path, mocker):
        mocker.patch('triage.ai_analyzer.analyze_triage_transcript', side_effect=_fake_analysis)
        _, payload = self._run('--raw-dir', str(tmp_path), '--tier', 'pago', output=tmp_path / 'r.json')
        run = payload['run']
        assert run['model_versions'] == ['m-001']
        assert run['prompt_sha256'] and run['prompt_version']
        assert run['tier'] == 'pago'
        assert payload['performance']['cost_usd'] is not None
        assert 'exact_agreement_ci95' in payload['triage']
        assert set(payload['triage']['by_tipo'])
        raw = (tmp_path / f"{run['run_id']}.jsonl").read_text(encoding='utf-8').splitlines()
        assert len(raw) == 10 and json.loads(raw[0])['llm_raw'] == '{}'
        assert 'llm_raw' not in payload['cases'][0]

    def test_summarize_only_requires_llm_engine(self):
        with pytest.raises(CommandError, match='summarize-only'):
            call_command('evaluate_extraction', '--engine', 'reglas', '--summarize-only', stdout=StringIO(),
                         stderr=StringIO())
