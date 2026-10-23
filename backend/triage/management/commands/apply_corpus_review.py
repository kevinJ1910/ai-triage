"""
Aplica al corpus la planilla de revision de etiquetas (export_corpus_review).

Uso:
    python manage.py apply_corpus_review triage/benchmark/revision/revision_test.csv --dry-run
    python manage.py apply_corpus_review triage/benchmark/revision/revision_test.csv

Solo se aplican las filas con revisado_por. Si cambia un nivel, el nivel original se guarda en nivel_particion
para que ningun caso cambie de particion. Con entidades_ok = si el caso pasa a 'revisado'; con 'no' queda en
'borrador' y se lista para corregir las entidades a mano. El corpus resultante se valida antes de escribirse y los
cambios quedan en el historial de git.
"""
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from triage.corpus_review import apply_review, read_csv
from triage.entity_corpus import CORPUS_PATH, validate_entity_corpus


class Command(BaseCommand):
    help = "Aplica la planilla de revision de etiquetas al corpus anotado."

    def add_arguments(self, parser):
        parser.add_argument('sheet', type=Path, help="Planilla CSV revisada")
        parser.add_argument('--corpus', type=Path, default=CORPUS_PATH)
        parser.add_argument('--dry-run', action='store_true', help="Muestra los cambios sin escribir el corpus")

    def handle(self, *args, **options):
        try:
            cases = json.loads(options['corpus'].read_text(encoding='utf-8'))
            rows = read_csv(options['sheet'].read_text(encoding='utf-8'))
            updated, report = apply_review(cases, rows)
        except (OSError, ValueError) as exc:
            raise CommandError(f"No se aplico la revision:\n{exc}") from exc
        errors = validate_entity_corpus(updated)
        if errors:
            raise CommandError("El corpus revisado no es valido:\n" + '\n'.join(errors))

        transitions = Counter(f"{old}->{new}" for _, old, new in report['level_changes'])
        self.stdout.write(f"Filas revisadas: {len(report['reviewed']) + len(report['entity_fixes'])} "
                          f"| sin revisar (sin revisado_por): {len(report['skipped'])}")
        self.stdout.write(f"Pasan a 'revisado': {len(report['reviewed'])}")
        self.stdout.write(f"Niveles cambiados: {len(report['level_changes'])} {dict(transitions)}")
        for cid, old, new in report['level_changes']:
            self.stdout.write(f"  {cid}: {old} -> {new}")
        self.stdout.write(f"Criterios cambiados: {len(report['criterio_changes'])}")
        if report['entity_fixes']:
            self.stdout.write(self.style.WARNING(
                f"Quedan en borrador por entidades a corregir a mano ({len(report['entity_fixes'])}):"))
            for cid, comment in report['entity_fixes']:
                self.stdout.write(f"  {cid}: {comment or '(sin comentario)'}")
        if options['dry_run']:
            self.stdout.write("Simulacion: no se escribio el corpus.")
            return
        options['corpus'].write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                     newline='\n')
        self.stdout.write(f"Corpus actualizado en {options['corpus']}. Revise el diff con git antes del commit.")
