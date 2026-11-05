"""
Genera la planilla de revision de las etiquetas del corpus (sin ninguna prediccion del sistema).

Uso:
    python manage.py export_corpus_review --split test
    python manage.py export_corpus_review --split test --output triage/benchmark/revision/revision_test.csv

La planilla (CSV con ';', se abre en Excel o Google Sheets) trae por caso el transcript, el nivel y el criterio
actuales y las entidades anotadas, y columnas vacias para el revisor. Instrucciones en
benchmark/revision/GUIA_REVISION_ETIQUETAS.md. Se devuelve al corpus con apply_corpus_review.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from triage.corpus_review import export_rows, to_csv
from triage.entity_corpus import CORPUS_PATH, SPLITS, load_entity_corpus

REVIEW_DIR = Path(__file__).resolve().parents[2] / 'benchmark' / 'revision'


class Command(BaseCommand):
    help = "Genera la planilla de revision de las etiquetas de un split del corpus."

    def add_arguments(self, parser):
        parser.add_argument('--corpus', type=Path, default=CORPUS_PATH)
        parser.add_argument('--split', choices=SPLITS, required=True)
        parser.add_argument('--only-draft', action='store_true', help="Solo los casos en estado borrador")
        parser.add_argument('--output', type=Path, help="Por defecto benchmark/revision/revision_<split>.csv")

    def handle(self, *args, **options):
        try:
            cases = load_entity_corpus(options['corpus'], split=options['split'])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        if options['only_draft']:
            cases = [c for c in cases if c['estado'] == 'borrador']
        output = options.get('output') or REVIEW_DIR / f"revision_{options['split']}.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(to_csv(export_rows(cases)), encoding='utf-8', newline='')
        by_level = {}
        for case in cases:
            by_level[case['reference_level']] = by_level.get(case['reference_level'], 0) + 1
        self.stdout.write(f"Planilla con {len(cases)} casos del split {options['split']} "
                          f"(por nivel: {dict(sorted(by_level.items()))}) en {output}")
