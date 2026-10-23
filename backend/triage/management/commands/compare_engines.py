"""
Tabla comparativa de los motores de triaje evaluados sobre un split.

Uso:
    python manage.py compare_engines --split test
    python manage.py compare_engines --split dev --baseline dev_reglas_lotes
    python manage.py compare_engines --split dev --only dev_reglas_lotes dev_hibrido_gemini-2.5-flash_pv1
    python manage.py compare_engines --split dev --repeatability resultados/dev_a.json resultados/dev_a_r2.json

Lee las corridas completas de benchmark/resultados/*.json (evaluate_extraction o evaluate_benchmark con
--output), escribe benchmark/resultados/comparativa_<split>.json (lo muestra el panel "Resultados de
Evaluacion") y actualiza la tabla de docs/EVALUACION_TRIAJE.md entre sus marcadores. No llama a ningun modelo.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from triage.engine_comparison import compare, markdown_table, run_agreement, write_markdown_section
from triage.evaluation_runner import RESULTS_DIR


def _read(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise CommandError(f"No se pudo leer {path}: {exc}") from exc


class Command(BaseCommand):
    help = "Compara los motores de triaje evaluados (reglas, LLM local, Gemini, hibrido) sobre un split."

    def add_arguments(self, parser):
        parser.add_argument('--split', choices=('dev', 'test'), required=True)
        parser.add_argument('--results-dir', type=Path, default=None, help="Carpeta de los JSON de resultados")
        parser.add_argument('--baseline', help="Corrida de referencia para las diferencias pareadas "
                                               "(nombre del archivo sin .json; por defecto, la de reglas)")
        parser.add_argument('--only', nargs='+', metavar='CORRIDA',
                            help="Comparar solo estas corridas (nombres de archivo sin .json)")
        parser.add_argument('--repeatability', nargs=2, type=Path, metavar=('CORRIDA_A', 'CORRIDA_B'),
                            help="Dos corridas del mismo motor para medir la repetibilidad")
        parser.add_argument('--output', type=Path, help="JSON de salida (por defecto comparativa_<split>.json)")
        parser.add_argument('--markdown', type=Path, help="Documento donde se actualiza la tabla "
                                                          "(por defecto docs/EVALUACION_TRIAJE.md)")
        parser.add_argument('--no-markdown', action='store_true', help="No actualizar el documento")

    def handle(self, *args, **options):
        results_dir = options['results_dir'] or RESULTS_DIR
        split = options['split']
        runs = []
        for path in sorted(Path(results_dir).glob('*.json')):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and (not options.get('only') or path.stem in options['only']):
                runs.append((path.stem, data))
        try:
            comparison = compare(runs, split, baseline=options.get('baseline'))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if not comparison['rows']:
            raise CommandError(f"No hay corridas completas del split {split} en {Path(results_dir).name}/")
        if options.get('repeatability'):
            first, second = (_read(p) for p in options['repeatability'])
            comparison['repeatability'] = {**run_agreement(first, second),
                                           'runs': [p.stem for p in options['repeatability']]}
        comparison['generated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')

        table = markdown_table(comparison)
        self.stdout.write(table)
        output = options.get('output') or Path(results_dir) / f'comparativa_{split}.json'
        output.write_text(json.dumps({'comparison': comparison}, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(f"Comparativa guardada en {output}")
        if not options['no_markdown']:
            doc = options.get('markdown') or Path(settings.BASE_DIR).parent / 'docs' / 'EVALUACION_TRIAJE.md'
            if not doc.parent.is_dir():
                # En Docker solo se monta backend/: la tabla se actualiza ejecutando el comando en el host.
                self.stdout.write(self.style.WARNING(f"No existe {doc.parent}: no se actualiza el documento"))
                return
            write_markdown_section(doc, split, table)
            self.stdout.write(f"Tabla actualizada en {doc}")
