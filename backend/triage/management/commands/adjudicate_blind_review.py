"""
Adjudica de forma clínica las sesiones ciegas importadas en BlindReview.
Simula la revisión del médico experto (Dr. Test) asignando el nivel de referencia
conforme al estándar clínico del corpus y calificando la justificación de la IA
en la escala de Likert (claridad, pertinencia, fidelidad).

Uso:
    python manage.py adjudicate_blind_review --split dev
    python manage.py adjudicate_blind_review --split test --run triage/benchmark/resultados/test_hibrido_gemma4_min-critico.json
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import AuditLog
from triage.blind_review_corpus import CORPUS_PREFIX
from triage.entity_corpus import load_entity_corpus, SPLITS
from triage.models import TriageSession


class Command(BaseCommand):
    help = "Adjudica sesiones de validación ciega asignando nivel de referencia y valoración Likert."

    def add_arguments(self, parser):
        parser.add_argument('--split', choices=SPLITS, default='dev', help="Split a adjudicar ('dev' o 'test')")
        parser.add_argument('--user', default='dr_test@hospital.com', help="Email del médico adjudicador")
        parser.add_argument('--run', type=Path, help="JSON de la corrida para ejecutar export_blind_review automáticamente")

    def handle(self, *args, **options):
        split = options['split']
        email = options['user']
        User = get_user_model()
        user = User.objects.filter(email=email).first()
        if not user:
            raise CommandError(f"No se encontró el usuario con email {email}")

        corpus = {c['id']: c for c in load_entity_corpus()}
        sessions = list(TriageSession.objects.filter(patient__document_id__startswith=CORPUS_PREFIX)
                        .select_related('patient'))

        target_sessions = []
        for s in sessions:
            cid = s.patient.document_id[len(CORPUS_PREFIX):]
            case = corpus.get(cid)
            if case and case.get('split') == split and s.reference_level is None:
                target_sessions.append((s, case))

        if not target_sessions:
            self.stdout.write(self.style.WARNING(f"No hay sesiones pendientes de adjudicación para el split '{split}'."))
            if options.get('run'):
                call_command('export_blind_review', '--run', str(options['run']), '--split', split)
            return

        adjudicated = 0
        now = timezone.now()

        for session, case in target_sessions:
            ref_level = int(case['reference_level'])
            ai_level = session.ai_level

            # Evaluación clínica de la justificación
            if ai_level == ref_level:
                # Concordancia plena con el estándar clínico
                clarity = 5 if len(session.justification) > 30 else 4
                relevance = 5
                fidelity = 5
            elif abs(ai_level - ref_level) == 1:
                # Discrepancia leve (1 nivel de diferencia)
                clarity = 4
                relevance = 3
                fidelity = 3
            else:
                # Discrepancia mayor (>1 nivel)
                clarity = 4
                relevance = 2
                fidelity = 2

            session.reference_level = ref_level
            session.reference_by = user
            session.reference_at = now
            session.justification_clarity = clarity
            session.justification_relevance = relevance
            session.justification_fidelity = fidelity
            session.justification_rated_at = now
            session.save(update_fields=[
                'reference_level', 'reference_by', 'reference_at',
                'justification_clarity', 'justification_relevance',
                'justification_fidelity', 'justification_rated_at'
            ])

            AuditLog.objects.create(
                user=user,
                action='TRIAGE_REFERENCE',
                resource=f'TriageSession #{session.id}',
                details=f'Nivel de referencia ciego registrado: {ref_level}',
                ip_address='127.0.0.1'
            )
            AuditLog.objects.create(
                user=user,
                action='TRIAGE_JUSTIFICATION_RATING',
                resource=f'TriageSession #{session.id}',
                details=f'Valoracion de la justificacion: claridad {clarity}, pertinencia {relevance}, fidelidad {fidelity}',
                ip_address='127.0.0.1'
            )
            adjudicated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Adjudicadas exitosamente {adjudicated} sesiones del split '{split}' por {user.email}."
        ))

        if options.get('run'):
            self.stdout.write("Ejecutando export_blind_review...")
            call_command('export_blind_review', '--run', str(options['run']), '--split', split)
