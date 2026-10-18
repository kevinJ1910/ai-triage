"""
Validacion clinica ciega sobre casos del corpus, con la Validacion ciega existente (BlindReview).

import_cases crea, por cada caso de la muestra, un paciente (document_id CORPUS-<id>), su transcripcion y una
TriageSession con el nivel y la justificacion del motor congelado (sin nuevas llamadas al LLM). La cola ciega ya
oculta el nivel de la IA y la justificacion hasta que el clinico fija su nivel de referencia.

summarize compara el nivel del clinico con la IA, con el motor de reglas y con las etiquetas del equipo
(el techo humano), y resume las valoraciones Likert de las justificaciones.

Las sesiones CORPUS- no son pacientes reales: evaluation_metrics las excluye.
"""
import hashlib
from typing import Any, Dict, List, Optional

from django.db import transaction

from .clinical_protocol import evaluate_christus_sinergia_triage
from .metrics import LEVELS, mean_ci, triage_summary

CORPUS_PREFIX = 'CORPUS-'
SAMPLE_SALT = 'validacion-ciega'
LIKERT_FIELDS = {'clarity': 'justification_clarity', 'relevance': 'justification_relevance',
                 'fidelity': 'justification_fidelity'}


def select_sample(cases: List[Dict[str, Any]], per_level: int) -> List[Dict[str, Any]]:
    """Muestra estratificada por nivel de referencia, determinista: los primeros por SHA-256 de cada nivel."""
    sample = []
    for level in LEVELS:
        ranked = sorted((c for c in cases if c['reference_level'] == level),
                        key=lambda c: hashlib.sha256(f"{SAMPLE_SALT}:{c['id']}".encode()).hexdigest())
        sample.extend(ranked[:per_level])
    return sample


def import_cases(sample: List[Dict[str, Any]], run_cases: Dict[str, Dict[str, Any]], engine_label: str) -> Dict[str, int]:
    """Crea las sesiones de la muestra. Es idempotente: un caso ya importado no se duplica ni se modifica."""
    from patients.models import Patient
    from .models import TriageSession, Transcription

    created = skipped = 0
    with transaction.atomic():
        for case in sample:
            prediction = run_cases[case['id']]
            patient, _ = Patient.objects.get_or_create(
                document_id=f"{CORPUS_PREFIX}{case['id']}", defaults={'gender': 'unknown'})
            if TriageSession.objects.filter(patient=patient).exists():
                skipped += 1
                continue
            level = int(prediction['predicted_level'])
            session = TriageSession.objects.create(
                patient=patient, level=level, ai_level=level, final_level=level,
                justification=prediction.get('justification') or '',
                clinical_entities=prediction.get('predicted_entities') or {},
            )
            Transcription.objects.create(triage_session=session, session_uuid=f"corpus-{case['id']}",
                                         full_text=case['transcript'], model_used=engine_label)
            created += 1
    return {'created': created, 'skipped': skipped}


def purge() -> int:
    """Borra los pacientes CORPUS- y, en cascada, sus sesiones y transcripciones."""
    from patients.models import Patient
    deleted, _ = Patient.objects.filter(document_id__startswith=CORPUS_PREFIX).delete()
    return deleted


def _agreement(pairs) -> Optional[Dict[str, Any]]:
    if not pairs:
        return None
    full = triage_summary(pairs)
    return {key: full.get(key) for key in (
        'n', 'exact_agreement', 'exact_agreement_ci95', 'cohen_kappa', 'cohen_kappa_ci95', 'kappa_interpretation',
        'critical_sensitivity', 'undertriage_rate', 'overtriage_rate', 'confusion_matrix')}


def summarize(corpus_by_id: Dict[str, Dict[str, Any]], run_cases: Dict[str, Dict[str, Any]], split: str
              ) -> Dict[str, Any]:
    """Kappa clinico-IA, clinico-reglas y clinico-equipo, y medias Likert, sobre las sesiones CORPUS-."""
    from .models import TriageSession

    sessions = list(TriageSession.objects.filter(patient__document_id__startswith=CORPUS_PREFIX)
                    .select_related('patient', 'transcription'))
    rows = []
    for session in sessions:
        case_id = session.patient.document_id[len(CORPUS_PREFIX):]
        case = corpus_by_id.get(case_id)
        if case is None or (split and case.get('split') != split):
            continue
        prediction = run_cases.get(case_id) or {}
        rule_level = prediction.get('rule_level')
        if rule_level is None:
            rule_level = evaluate_christus_sinergia_triage(case['transcript'])['level']
        rows.append({'id': case_id, 'ai': session.ai_level, 'rules': int(rule_level), 'team': case['reference_level'],
                     'clinician': session.reference_level, 'session': session})

    referenced = [r for r in rows if r['clinician'] is not None]
    likert = {}
    for key, field in LIKERT_FIELDS.items():
        likert[key] = mean_ci([getattr(r['session'], field) for r in referenced
                               if r['session'].justification_rated_at is not None])
    return {
        'split': split,
        'n': len(referenced),
        'imported': len(rows),
        'pending': len(rows) - len(referenced),
        # Orientacion (evaluado, referencia = clinico); el Kappa ponderado cuadratico es simetrico.
        'clinician_vs_ai': _agreement([(r['ai'], r['clinician']) for r in referenced]),
        'clinician_vs_rules': _agreement([(r['rules'], r['clinician']) for r in referenced]),
        'clinician_vs_team': _agreement([(r['team'], r['clinician']) for r in referenced]),
        'likert': likert,
        # Solo ids y niveles, nunca el texto: para el analisis de errores.
        'disagreements': [{'id': r['id'], 'clinician': r['clinician'], 'ai': r['ai'], 'team': r['team'],
                           'rules': r['rules']}
                          for r in referenced if r['ai'] != r['clinician'] or r['team'] != r['clinician']],
    }
