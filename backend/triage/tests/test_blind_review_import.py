import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from patients.models import Patient
from triage.blind_review_corpus import CORPUS_PREFIX, select_sample
from triage.entity_corpus import load_entity_corpus
from triage.models import TriageSession

User = get_user_model()


@pytest.fixture
def frozen_run(tmp_path):
    """Corrida congelada de test: la IA acierta salvo en los niveles 1, que deja en 3; las reglas dicen 5."""
    cases = load_entity_corpus(split='test')
    run = {
        'engine': 'hibrido', 'model': 'gemini-2.5-flash', 'split': 'test', 'complete': True,
        'run': {'prompt_version': 'v1'},
        'cases': [{'id': c['id'], 'reference_level': c['reference_level'],
                   'predicted_level': 3 if c['reference_level'] == 1 else c['reference_level'],
                   'rule_level': 5, 'justification': f"Justificación IA {c['id']}",
                   'predicted_entities': {'symptoms': ['x']}} for c in cases],
    }
    path = tmp_path / 'test_hibrido.json'
    path.write_text(json.dumps(run), encoding='utf-8')
    return path


def _clinician():
    user = User.objects.create_user(email='clinico@hospital.com', password='Password123!', role='medico',
                                    is_verified=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestBlindReviewCorpus:
    def test_sample_is_stratified_and_deterministic(self):
        cases = load_entity_corpus(split='test')
        sample = select_sample(cases, 3)
        assert len(sample) == 15
        assert sorted(c['reference_level'] for c in sample) == [1] * 3 + [2] * 3 + [3] * 3 + [4] * 3 + [5] * 3
        assert [c['id'] for c in select_sample(cases, 3)] == [c['id'] for c in sample]

    def test_import_is_idempotent_and_queue_hides_levels(self, frozen_run):
        out = StringIO()
        call_command('import_blind_review', '--run', str(frozen_run), '--per-level', '2', stdout=out)
        assert '10 creados' in out.getvalue()
        call_command('import_blind_review', '--run', str(frozen_run), '--per-level', '2', stdout=out)
        assert TriageSession.objects.filter(patient__document_id__startswith=CORPUS_PREFIX).count() == 10

        queue = _clinician().get('/api/triage/sessions/blind_review_queue/').data
        assert queue['pending_total'] == 10
        case = queue['results'][0]
        assert case['transcript']
        for hidden in ('ai_level', 'final_level', 'level', 'justification'):
            assert hidden not in case

    def test_export_computes_agreements_and_likert(self, frozen_run, tmp_path):
        call_command('import_blind_review', '--run', str(frozen_run), '--per-level', '2', stdout=StringIO())
        client = _clinician()
        corpus = {c['id']: c for c in load_entity_corpus()}
        for session in TriageSession.objects.filter(patient__document_id__startswith=CORPUS_PREFIX):
            team = corpus[session.patient.document_id[len(CORPUS_PREFIX):]]['reference_level']
            assert client.post(f'/api/triage/sessions/{session.id}/reference_level/', {'reference_level': team},
                               format='json').status_code == 200
            assert client.post(f'/api/triage/sessions/{session.id}/justification_rating/',
                               {'clarity': 4, 'relevance': 5, 'fidelity': 3}, format='json').status_code == 200

        output = tmp_path / 'validacion.json'
        out = StringIO()
        call_command('export_blind_review', '--run', str(frozen_run), '--output', str(output), stdout=out)
        summary = json.loads(output.read_text(encoding='utf-8'))['clinical_validation']
        assert summary['n'] == 10 and summary['pending'] == 0
        assert summary['clinician_vs_team']['cohen_kappa'] == 1.0
        assert summary['clinician_vs_ai']['exact_agreement'] == 80.0
        assert summary['clinician_vs_ai']['critical_sensitivity'] == 50.0
        assert summary['clinician_vs_rules']['exact_agreement'] == 20.0
        assert summary['likert']['clarity']['mean'] == 4.0
        assert {d['id'] for d in summary['disagreements']} and 'transcript' not in json.dumps(summary)

    def test_corpus_sessions_are_excluded_from_clinical_metrics(self, frozen_run):
        call_command('import_blind_review', '--run', str(frozen_run), '--per-level', '1', stdout=StringIO())
        real = Patient.objects.create(document_id='CC-REAL-1')
        TriageSession.objects.create(patient=real, level=3, ai_level=3, final_level=3, justification='J')
        data = _clinician().get('/api/triage/sessions/evaluation_metrics/').data
        assert data['total_triages'] == 1
        assert all(not str(r['patient']).startswith(CORPUS_PREFIX) for r in data['recent_evaluations'])

    def test_purge_and_guards(self, frozen_run, tmp_path):
        call_command('import_blind_review', '--run', str(frozen_run), '--per-level', '1', stdout=StringIO())
        call_command('import_blind_review', '--purge', stdout=StringIO())
        assert not Patient.objects.filter(document_id__startswith=CORPUS_PREFIX).exists()

        partial = json.loads(frozen_run.read_text(encoding='utf-8'))
        partial['complete'] = False
        bad = tmp_path / 'parcial.json'
        bad.write_text(json.dumps(partial), encoding='utf-8')
        with pytest.raises(CommandError, match='incompleta'):
            call_command('import_blind_review', '--run', str(bad), stdout=StringIO())
        with pytest.raises(CommandError, match='split'):
            call_command('import_blind_review', '--run', str(frozen_run), '--split', 'dev', stdout=StringIO())
        with pytest.raises(CommandError, match='import_blind_review'):
            call_command('export_blind_review', '--run', str(frozen_run), '--output', str(tmp_path / 'x.json'),
                         stdout=StringIO())
