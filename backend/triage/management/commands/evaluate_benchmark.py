"""
Evaluacion reproducible del triaje contra un conjunto de casos con nivel de referencia.

Uso:
    python manage.py evaluate_benchmark casos.json --engine reglas
    python manage.py evaluate_benchmark casos.csv --engine pipeline --output resultados.json

Formato de entrada (JSON: lista de objetos; CSV: columnas con el mismo nombre):
    id               identificador del caso
    transcript       texto de la consulta
    reference_level  nivel 1-5 asignado por expertos (idealmente por consenso y a ciegas)

Motores:
    reglas    motor determinista Christus Sinergia (sin red, sin coste).
    pipeline  analyze_triage_transcript completo sin cache (llama a Gemini si hay clave
              y cae al motor de reglas si falla; el motor usado se informa por caso).
"""
import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from triage.clinical_protocol import evaluate_christus_sinergia_triage
from triage.metrics import reference_agreement, CRITICAL_LEVELS


def load_cases(path: Path) -> list:
    if not path.exists():
        raise CommandError(f"No existe el archivo {path}")
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as fh:
            rows = list(csv.DictReader(fh))
    else:
        try:
            rows = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise CommandError(f"JSON invalido: {exc}") from exc
    if not isinstance(rows, list) or not rows:
        raise CommandError("El archivo debe contener una lista no vacia de casos")

    cases = []
    for index, row in enumerate(rows, start=1):
        case_id = str(row.get('id') or index)
        transcript = (row.get('transcript') or '').strip()
        try:
            reference = int(row.get('reference_level'))
        except (TypeError, ValueError):
            reference = None
        if not transcript or reference not in range(1, 6):
            raise CommandError(f"Caso {case_id}: requiere 'transcript' y 'reference_level' entre 1 y 5")
        cases.append({'id': case_id, 'transcript': transcript, 'reference_level': reference})
    return cases


def run_engine(engine: str, transcript: str) -> dict:
    if engine == 'reglas':
        result = evaluate_christus_sinergia_triage(transcript)
        return {'level': int(result['level']), 'engine_used': 'Motor de Reglas Clínico (Christus Sinergia)'}

    from triage.ai_analyzer import analyze_triage_transcript
    analysis = analyze_triage_transcript(transcript, use_cache=False)
    return {
        'level': int(analysis.get('triage', {}).get('level', 5)),
        'engine_used': analysis.get('engine_used') or 'desconocido',
    }


class Command(BaseCommand):
    help = "Evalua el motor de triaje contra un conjunto de casos con nivel de referencia."

    def add_arguments(self, parser):
        parser.add_argument('dataset', type=Path, help="Archivo .json o .csv con los casos")
        parser.add_argument('--engine', choices=['reglas', 'pipeline'], default='reglas')
        parser.add_argument('--output', type=Path, help="Ruta opcional para guardar el detalle en JSON")

    def handle(self, *args, **options):
        cases = load_cases(options['dataset'])
        engine = options['engine']

        results = []
        for case in cases:
            prediction = run_engine(engine, case['transcript'])
            results.append({**case, 'predicted_level': prediction['level'], 'engine_used': prediction['engine_used']})

        summary = reference_agreement([(r['predicted_level'], r['reference_level']) for r in results])
        critical_misses = [
            r['id'] for r in results
            if r['reference_level'] in CRITICAL_LEVELS and r['predicted_level'] not in CRITICAL_LEVELS
        ]
        engines = sorted({r['engine_used'] for r in results})

        self.stdout.write(f"Casos evaluados: {summary['n']} | Motor: {engine} ({', '.join(engines)})")
        self.stdout.write(f"Concordancia exacta: {summary['exact_agreement']}%")
        self.stdout.write(f"Kappa ponderado cuadratico: {summary['cohen_kappa']} ({summary['kappa_interpretation']})")
        self.stdout.write(f"Infratriaje: {summary['undertriage_rate']}% | Sobretriaje: {summary['overtriage_rate']}%")
        self.stdout.write(
            f"Sensibilidad niveles 1-2: {summary['critical_sensitivity']}% "
            f"({summary['critical_cases']} casos criticos)"
        )
        if critical_misses:
            self.stdout.write(self.style.WARNING(f"Casos criticos infratriados: {', '.join(critical_misses)}"))

        if options.get('output'):
            options['output'].write_text(
                json.dumps({'engine': engine, 'summary': summary, 'cases': results}, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            self.stdout.write(f"Detalle guardado en {options['output']}")
