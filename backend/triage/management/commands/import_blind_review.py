"""
Carga una muestra estratificada del corpus en la Validacion ciega (BlindReview) para que el clinico la adjudique.

Uso:
    python manage.py import_blind_review --run triage/benchmark/resultados/test_hibrido_gemini-2.5-flash_pv1.json
    python manage.py import_blind_review --run ... --split test --per-level 10
    python manage.py import_blind_review --purge

--run es el JSON completo de evaluate_extraction del motor congelado: su nivel y su justificacion son los que
el clinico valora despues de fijar su referencia (no se llama al LLM). La muestra se elige por hash, de forma
determinista, y repetir el comando no duplica casos. El clinico no debe ver el corpus ni los resultados antes
de terminar. --purge borra los pacientes CORPUS- (y sus sesiones) de la base de datos.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from triage.blind_review_corpus import import_cases, purge, select_sample
from triage.engine_comparison import engine_label
from triage.entity_corpus import CORPUS_PATH, SPLITS, load_entity_corpus


class Command(BaseCommand):
    help = "Importa casos del corpus a la Validacion ciega con el nivel y la justificacion del motor congelado."

    def add_arguments(self, parser):
        parser.add_argument('--run', type=Path, help="JSON de evaluate_extraction del motor a validar")
        parser.add_argument('--corpus', type=Path, default=CORPUS_PATH)
        parser.add_argument('--split', choices=SPLITS, default='test')
        parser.add_argument('--per-level', type=int, default=10, help="Casos por nivel de referencia (5 niveles)")
        parser.add_argument('--purge', action='store_true', help="Borra los casos CORPUS- importados")

    def handle(self, *args, **options):
        if options['purge']:
            deleted = purge()
            self.stdout.write(f"Borrados {deleted} registros de casos del corpus.")
            return
        if not options.get('run'):
            raise CommandError("Indique --run con el JSON de la corrida congelada (o --purge)")
        try:
            run = json.loads(options['run'].read_text(encoding='utf-8'))
            cases = load_entity_corpus(options['corpus'], split=options['split'])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        if run.get('split') != options['split']:
            raise CommandError(f"La corrida es del split {run.get('split')}, no de {options['split']}")
        if run.get('complete') is False:
            raise CommandError("La corrida esta incompleta: termine la evaluacion antes de validar")
        run_cases = {str(c['id']): c for c in run.get('cases') or []}
        sample = [c for c in select_sample(cases, options['per_level']) if c['id'] in run_cases]
        if not sample:
            raise CommandError("Ningun caso de la muestra esta en la corrida")
        counts = import_cases(sample, run_cases, engine_label(run))
        self.stdout.write(f"Muestra de {len(sample)} casos ({options['per_level']} por nivel) del split "
                          f"{options['split']}: {counts['created']} creados, {counts['skipped']} ya existian.")
        self.stdout.write("El clinico los adjudica en Validacion ciega; despues: python manage.py export_blind_review "
                          f"--run {options['run'].name}")
