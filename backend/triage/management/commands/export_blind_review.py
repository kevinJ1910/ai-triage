"""
Resume la validacion clinica ciega de los casos del corpus importados con import_blind_review.

Uso:
    python manage.py export_blind_review --run triage/benchmark/resultados/test_hibrido_gemini-2.5-flash_pv1.json

Calcula el Kappa ponderado clinico-IA, clinico-reglas y clinico-equipo (el techo humano: cuanto coinciden dos
anotadores humanos) con IC95, y las medias Likert de las justificaciones. Escribe
benchmark/resultados/validacion_clinica_<split>.json, que muestra el panel "Resultados de Evaluacion".
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from triage.blind_review_corpus import summarize
from triage.entity_corpus import CORPUS_PATH, SPLITS, load_entity_corpus
from triage.evaluation_runner import RESULTS_DIR


def _fmt(agreement):
    if not agreement:
        return 'sin datos'
    return (f"Kappa {agreement['cohen_kappa']} IC95 {agreement['cohen_kappa_ci95']} | exactitud "
            f"{agreement['exact_agreement']}% | n={agreement['n']}")


class Command(BaseCommand):
    help = "Calcula el acuerdo del clinico con la IA, las reglas y el equipo, y las medias Likert."

    def add_arguments(self, parser):
        parser.add_argument('--run', type=Path, required=True, help="JSON de la corrida importada")
        parser.add_argument('--corpus', type=Path, default=CORPUS_PATH)
        parser.add_argument('--split', choices=SPLITS, default='test')
        parser.add_argument('--output', type=Path, help="Por defecto resultados/validacion_clinica_<split>.json")

    def handle(self, *args, **options):
        try:
            run = json.loads(options['run'].read_text(encoding='utf-8'))
            corpus = {c['id']: c for c in load_entity_corpus(options['corpus'])}
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        run_cases = {str(c['id']): c for c in run.get('cases') or []}
        summary = summarize(corpus, run_cases, options['split'])
        if not summary['imported']:
            raise CommandError("No hay casos del corpus importados: use import_blind_review")
        summary['run'] = options['run'].stem

        self.stdout.write(f"Adjudicados {summary['n']} de {summary['imported']} casos ({summary['pending']} pendientes)")
        self.stdout.write(f"Clinico vs IA:      {_fmt(summary['clinician_vs_ai'])}")
        self.stdout.write(f"Clinico vs reglas:  {_fmt(summary['clinician_vs_rules'])}")
        self.stdout.write(f"Clinico vs equipo:  {_fmt(summary['clinician_vs_team'])} (techo humano)")
        for key, item in summary['likert'].items():
            self.stdout.write(f"Likert {key}: media {item['mean']} IC95 {item['ci95']} (n={item['n']})")

        output = options.get('output') or RESULTS_DIR / f"validacion_clinica_{options['split']}.json"
        payload = {'clinical_validation': summary}
        if summary['pending']:
            payload['complete'] = False
            self.stdout.write(self.style.WARNING("Validacion incompleta: el panel no la mostrara hasta terminar."))
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(f"Resumen guardado en {output}")
