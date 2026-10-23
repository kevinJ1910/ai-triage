"""
Evaluacion reproducible del triaje contra un conjunto de casos con nivel de referencia.

Uso:
    python manage.py evaluate_benchmark casos.json --engine reglas
    python manage.py evaluate_benchmark corpus_entidades.json --engine pipeline --model gemini-2.5-flash --split dev
    python manage.py evaluate_benchmark corpus_entidades.json --engine pipeline --split dev --output resultados.json

Formato de entrada (JSON: lista de objetos; CSV: columnas con el mismo nombre):
    id               identificador del caso
    transcript       texto de la consulta
    reference_level  nivel 1-5 asignado por expertos (idealmente por consenso y a ciegas)
    split            opcional: dev o test, para filtrar con --split

Motores:
    reglas    motor determinista Christus Sinergia (sin red, sin coste).
    pipeline  analyze_triage_transcript completo sin cache, con el LLM activo o el fijado con --model
              ('local:<modelo>' para el LLM local). Exige --split: casos_sinteticos.json no tiene particion y
              parte de sus casos estan en el test del corpus, asi que pasar un LLM por el contaminaria test.
              Es reanudable (checkpoint en benchmark/resultados/crudos/) y un caso cuyo LLM falla queda
              pendiente en vez de resolverse con reglas.
"""
import csv
import json
import statistics
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from triage.clinical_protocol import evaluate_christus_sinergia_triage
from triage.evaluation_runner import (
    RAW_DIR,
    Checkpoint,
    RateLimiter,
    RunSpec,
    performance_summary,
    run_metadata,
    run_pending,
)
from triage.metrics import COMBINE_POLICIES, CRITICAL_LEVELS, combine_levels, reference_agreement, triage_summary


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
        case = {'id': case_id, 'transcript': transcript, 'reference_level': reference}
        if row.get('split'):
            case['split'] = str(row['split']).strip()
        cases.append(case)
    return cases


def run_engine(engine: str, transcript: str, model=None, prompt_version=None) -> dict:
    start = time.perf_counter()
    if engine == 'reglas':
        result = evaluate_christus_sinergia_triage(transcript)
        prediction = {'level': int(result['level']), 'rule_level': int(result['level']),
                      'engine_used': 'Motor de Reglas Clínico (Christus Sinergia)', 'total_tokens': 0}
    else:
        from triage.ai_analyzer import analyze_triage_transcript
        kwargs = {'use_cache': False, 'strict_llm': True, 'include_raw': True, 'combine_policy': 'llm'}
        if model:
            kwargs['model'] = model
        if prompt_version:
            kwargs['prompt_version'] = prompt_version
        analysis = analyze_triage_transcript(transcript, **kwargs)
        level = int((analysis.get('triage') or {}).get('level', 5))
        prediction = {
            'level': int(analysis.get('llm_level') or level),
            'rule_level': analysis.get('rule_level'),
            'engine_used': analysis.get('engine_used') or 'desconocido',
            'model_version': analysis.get('model_version'),
            'prompt_tokens': int(analysis.get('prompt_tokens') or 0),
            'completion_tokens': int(analysis.get('completion_tokens') or 0),
            'thoughts_tokens': int(analysis.get('thoughts_tokens') or 0),
            'total_tokens': int(analysis.get('total_tokens') or 0),
            'llm_raw': analysis.get('llm_raw'),
        }
    prediction['latency_ms'] = round((time.perf_counter() - start) * 1000)
    return prediction


class Command(BaseCommand):
    help = "Evalua el motor de triaje contra un conjunto de casos con nivel de referencia."

    def add_arguments(self, parser):
        parser.add_argument('dataset', type=Path, help="Archivo .json o .csv con los casos")
        parser.add_argument('--engine', choices=['reglas', 'pipeline'], default='reglas')
        parser.add_argument('--model', help="Con --engine pipeline, evalua solo este modelo (sin respaldos)")
        parser.add_argument('--split', choices=['dev', 'test'], help="Evaluar solo los casos de esa particion")
        parser.add_argument('--prompt-version', help="Version del prompt (por defecto la de produccion)")
        parser.add_argument('--policy', choices=COMBINE_POLICIES, default='llm',
                            help="Politica de combinacion LLM + reglas (se aplica al resumir)")
        parser.add_argument('--rpm', type=float, default=0.0, help="Peticiones por minuto como maximo")
        parser.add_argument('--max-calls', type=int, help="Tope de llamadas al LLM en esta tanda")
        parser.add_argument('--retries', type=int, default=2)
        parser.add_argument('--retry-wait', type=float, default=60.0)
        parser.add_argument('--fresh', action='store_true', help="Borra el checkpoint y empieza de cero")
        parser.add_argument('--raw-dir', type=Path, default=RAW_DIR, help="Carpeta de los checkpoints JSONL")
        parser.add_argument('--output', type=Path, help="Ruta opcional para guardar el detalle en JSON")

    def handle(self, *args, **options):
        cases = load_cases(options['dataset'])
        engine = options['engine']
        model = options.get('model')
        if model and engine != 'pipeline':
            raise CommandError("--model solo aplica con --engine pipeline")
        if engine == 'pipeline' and not options.get('split'):
            raise CommandError("--engine pipeline exige --split y un dataset con particion: evaluar un LLM sobre "
                               "casos que estan en test invalida la evaluacion final")
        if options.get('split'):
            if any('split' not in c for c in cases):
                raise CommandError("--split requiere que todos los casos tengan el campo 'split'")
            cases = [c for c in cases if c['split'] == options['split']]
            if not cases:
                raise CommandError(f"No hay casos en el split {options['split']}")

        outcome = None
        spec = None
        if engine == 'pipeline':
            from triage.ai_analyzer import PROMPT_VERSION
            prompt_version = options.get('prompt_version') or PROMPT_VERSION
            spec = RunSpec(engine='pipeline', split=options['split'], model=model or 'activo',
                           prompt_version=prompt_version, tag=options['dataset'].stem)
            checkpoint = Checkpoint(options['raw_dir'] / f'{spec.run_id}.jsonl')
            if options['fresh']:
                checkpoint.reset()

            def evaluate(case):
                prediction = run_engine(engine, case['transcript'], model=model, prompt_version=prompt_version)
                if prediction['engine_used'].startswith('Motor de Reglas'):
                    raise RuntimeError('el analizador aplico el motor de reglas')
                return {'predicted_level': prediction.pop('level'), **prediction}

            outcome = run_pending(cases, checkpoint, evaluate,
                                  limiter=RateLimiter(rpm=options['rpm']), max_calls=options.get('max_calls'),
                                  retries=options['retries'], retry_wait=options['retry_wait'],
                                  log=self.stderr.write)
            records = [checkpoint.get(c) for c in cases]
            results = [{**case, **{k: v for k, v in record.items() if k not in ('llm_raw', 'id', 'transcript_sha256')},
                        'llm_level': record['predicted_level'],
                        'predicted_level': combine_levels(record['predicted_level'], record.get('rule_level'),
                                                          options['policy'])}
                       for case, record in zip(cases, records) if record]
        else:
            results = []
            for case in cases:
                prediction = run_engine(engine, case['transcript'])
                results.append({**case, 'predicted_level': prediction['level'], 'rule_level': prediction['rule_level'],
                                'engine_used': prediction['engine_used'], 'latency_ms': prediction['latency_ms'],
                                'total_tokens': prediction['total_tokens']})

        if not results:
            raise CommandError("Ningun caso evaluado: revise la cuota o la configuracion del LLM")
        pairs = [(r['predicted_level'], r['reference_level']) for r in results]
        summary = reference_agreement(pairs)
        critical_misses = [
            r['id'] for r in results
            if r['reference_level'] in CRITICAL_LEVELS and r['predicted_level'] not in CRITICAL_LEVELS
        ]
        engines = sorted({r['engine_used'] for r in results})
        complete = len(results) == len(cases)

        self.stdout.write(f"Casos evaluados: {summary['n']} | Motor: {engine} ({', '.join(engines)})")
        if not complete:
            self.stdout.write(self.style.WARNING(f"Corrida incompleta: faltan {len(cases) - len(results)} casos"))
        self.stdout.write(f"Concordancia exacta: {summary['exact_agreement']}%")
        self.stdout.write(f"Kappa ponderado cuadratico: {summary['cohen_kappa']} ({summary['kappa_interpretation']})")
        self.stdout.write(f"Infratriaje: {summary['undertriage_rate']}% | Sobretriaje: {summary['overtriage_rate']}%")
        self.stdout.write(
            f"Sensibilidad niveles 1-2: {summary['critical_sensitivity']}% "
            f"({summary['critical_cases']} casos criticos)"
        )
        performance = performance_summary(results, model if engine == 'pipeline' else None)
        performance['latency_ms_mean'] = round(statistics.mean(r['latency_ms'] for r in results))
        self.stdout.write(f"Latencia media: {performance['latency_ms_mean']} ms | Tokens: {performance['tokens_total']}")
        if critical_misses:
            self.stdout.write(self.style.WARNING(f"Casos criticos infratriados: {', '.join(critical_misses)}"))

        if options.get('output'):
            payload = {'engine': engine, 'model': model, 'split': options.get('split'), 'complete': complete,
                       'summary': summary, 'triage': triage_summary(pairs), 'performance': performance,
                       'cases': results}
            if spec:
                payload['run'] = run_metadata(spec, results, corpus=options['dataset'], tier=None, hardware=None,
                                              policy=options['policy'])
            options['output'].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            self.stdout.write(f"Detalle guardado en {options['output']}")

        if outcome and outcome.stopped in ('daily_quota', 'rate_limit'):
            raise CommandError(f"Cuota del proveedor agotada: quedan {len(outcome.pending)} casos. Reanude mas tarde "
                               "con el mismo comando.")
