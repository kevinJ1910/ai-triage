"""
Evaluacion reproducible de la extraccion de entidades (NER), la negacion y el nivel de triaje
contra el corpus anotado (triage/benchmark/corpus_entidades.json).

Uso:
    python manage.py evaluate_extraction --engine reglas --split dev
    python manage.py evaluate_extraction --engine gemini --model gemini-2.5-flash --split dev --output r.json
    python manage.py evaluate_extraction --agreement doble_anotacion/segundo_anotador.json

Motores:
    reglas   sin LLM ni NER: entidades del catalogo terminologico y regex, nivel por reglas.
    roberta  sin LLM, con el NER (RoBERTa, NER_MODEL_PATH) fusionado con el catalogo; nivel por reglas.
    gemini   analyze_triage_transcript completo sin cache, sin NER y con un unico modelo (--model). Si la
             llamada falla (p. ej. 429 por cuota), se reintenta --retries veces esperando --retry-wait
             segundos; si sigue fallando, el caso se resuelve con reglas y se cuenta en 'llm_failures'.
    hibrido  gemini + NER: las menciones del NER y la negacion mandan y Gemini desempata (entity_fusion).

Cuota: el plan gratuito de Gemini limita las peticiones por minuto (5 en gemini-2.5-flash). Usar
--pause para no superarla; un caso resuelto por reglas no mide al modelo.

Una sola llamada por caso alimenta las metricas de entidades, las de triaje y la de codigos CIE-10 de la
normalizacion (normalized_terms; es la misma capa determinista con cualquier motor). El split 'test' se
reserva para la evaluacion final: ajustar reglas o prompts mirando sus resultados invalida la medicion.
"""
import json
import statistics
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from triage.entity_corpus import CORPUS_PATH, ENTITY_TYPES, SPLITS, load_entity_corpus
from triage.extraction_metrics import (
    MATCH_MODES,
    aggregate,
    annotator_agreement,
    bootstrap_ci,
    code_accuracy,
    code_hits,
    micro_f1_ci,
    score_case,
)
from triage.metrics import CRITICAL_LEVELS, reference_agreement

ENGINES = ('reglas', 'roberta', 'gemini', 'hibrido')
LLM_ENGINES = ('gemini', 'hibrido')
NER_ENGINES = ('roberta', 'hibrido')
RULES_ENGINE_PREFIX = 'Motor de Reglas'


def run_case(engine: str, transcript: str, model=None) -> dict:
    from triage.ai_analyzer import analyze_triage_transcript

    start = time.perf_counter()
    analysis = analyze_triage_transcript(
        transcript, use_cache=False, allow_llm=engine in LLM_ENGINES, model=model, use_ner=engine in NER_ENGINES
    )
    latency_ms = round((time.perf_counter() - start) * 1000)
    entities = analysis.get('entities') or {}
    engine_used = analysis.get('engine_used') or 'desconocido'
    return {
        'predicted_level': int((analysis.get('triage') or {}).get('level', 5)),
        'predicted_entities': {key: list(entities.get(key) or []) for key in (*ENTITY_TYPES, 'negated_findings')},
        'engine_used': engine_used,
        'llm_failed': engine in LLM_ENGINES and engine_used.startswith(RULES_ENGINE_PREFIX),
        'ner_engine': analysis.get('ner_engine'),
        'latency_ms': latency_ms,
        'total_tokens': int(analysis.get('total_tokens') or 0),
        'predicted_codes': [t['code'] for t in analysis.get('normalized_terms') or [] if t.get('code_system') == 'CIE-10'],
    }


def _percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))]


def triage_summary(results):
    pairs = [(r['predicted_level'], r['reference_level']) for r in results]
    summary = reference_agreement(pairs)
    summary['cohen_kappa_ci95'] = bootstrap_ci(
        pairs, lambda sample: reference_agreement(list(sample))['cohen_kappa']
    )
    summary['critical_sensitivity_ci95'] = bootstrap_ci(
        pairs, lambda sample: reference_agreement(list(sample))['critical_sensitivity']
    )
    return summary


class Command(BaseCommand):
    help = "Evalua la extraccion de entidades, la negacion y el triaje contra el corpus anotado."

    def add_arguments(self, parser):
        parser.add_argument('--corpus', type=Path, default=CORPUS_PATH, help="Corpus anotado (JSON)")
        parser.add_argument('--engine', choices=ENGINES, default='reglas')
        parser.add_argument('--model', help="Modelo Gemini a evaluar (obligatorio con gemini e hibrido)")
        parser.add_argument('--split', choices=SPLITS, help="Particion a evaluar (por defecto, todo el corpus)")
        parser.add_argument('--match', choices=MATCH_MODES, default='relaxed', help="Criterio de emparejamiento")
        parser.add_argument('--limit', type=int, help="Evaluar solo los primeros N casos (pruebas rapidas)")
        parser.add_argument('--pause', type=float, default=0.0, help="Segundos de espera entre llamadas al LLM")
        parser.add_argument('--retries', type=int, default=2, help="Reintentos de un caso cuando falla el LLM")
        parser.add_argument('--retry-wait', type=float, default=60.0, help="Segundos de espera antes de reintentar")
        parser.add_argument('--output', type=Path, help="Ruta opcional para guardar el detalle en JSON")
        parser.add_argument('--agreement', type=Path,
                            help="Anotacion de un segundo anotador: calcula el acuerdo y no ejecuta ningun motor")

    def handle(self, *args, **options):
        try:
            cases = load_entity_corpus(options['corpus'], split=options.get('split'))
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        if options.get('agreement'):
            return self._agreement(cases, options)

        engine = options['engine']
        model = options.get('model')
        if engine in LLM_ENGINES and not model:
            raise CommandError(f"--engine {engine} requiere --model (p. ej. gemini-2.5-flash)")
        ner_engine = None
        if engine in NER_ENGINES:
            from triage.ner_model import engine_label
            ner_engine = engine_label()
            if not ner_engine:
                raise CommandError(f"--engine {engine} requiere el modelo NER: defina NER_MODEL_PATH "
                                   "(ver ml/ner/README.md) y compruebe que carga.")
        if options.get('limit'):
            cases = cases[:options['limit']]

        results = []
        for index, case in enumerate(cases, start=1):
            if index > 1 and engine in LLM_ENGINES and options['pause']:
                time.sleep(options['pause'])
            prediction = run_case(engine, case['transcript'], model=model)
            attempts = 1
            while prediction['llm_failed'] and attempts <= options['retries']:
                time.sleep(options['retry_wait'])
                prediction = run_case(engine, case['transcript'], model=model)
                attempts += 1
            prediction['attempts'] = attempts
            counts = score_case(case['entities'], prediction['predicted_entities'], mode=options['match'])
            results.append({
                'id': case['id'], 'split': case['split'], 'tipo': case['tipo'],
                'reference_level': case['reference_level'], **prediction, 'counts': counts,
                'code_hits': code_hits(case['entities'], prediction['predicted_codes']),
            })
            self.stderr.write(f"[{index}/{len(cases)}] {case['id']} -> nivel {prediction['predicted_level']} "
                              f"({prediction['latency_ms']} ms)")

        entity_summary = aggregate(r['counts'] for r in results)
        entity_summary['micro_f1_ci95'] = micro_f1_ci([r['counts'] for r in results])
        entity_summary['normalization'] = code_accuracy(r['code_hits'] for r in results)
        triage = triage_summary(results)
        latencies = [r['latency_ms'] for r in results]
        tokens = [r['total_tokens'] for r in results]
        performance = {
            'latency_ms_mean': round(statistics.mean(latencies)) if latencies else None,
            'latency_ms_p95': _percentile(latencies, 0.95) if latencies else None,
            'tokens_mean': round(statistics.mean(tokens), 1) if tokens else None,
            'tokens_total': sum(tokens),
            'llm_failures': sum(r['llm_failed'] for r in results),
            'retried_cases': sum(r['attempts'] > 1 for r in results),
        }
        self._report(engine, model, options, results, entity_summary, triage, performance)

        if options.get('output'):
            payload = {
                'engine': engine, 'model': model, 'ner_engine': ner_engine, 'split': options.get('split') or 'todo',
                'match': options['match'], 'corpus': str(options['corpus']),
                'entities': entity_summary, 'triage': triage, 'performance': performance, 'cases': results,
            }
            options['output'].parent.mkdir(parents=True, exist_ok=True)
            options['output'].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            self.stdout.write(f"Detalle guardado en {options['output']}")

    def _report(self, engine, model, options, results, entities, triage, performance):
        label = f"{engine} ({model})" if model else engine
        self.stdout.write(f"Casos: {len(results)} | Motor: {label} | Split: {options.get('split') or 'todo'} "
                          f"| Emparejamiento: {options['match']}")
        self.stdout.write("Entidades (P / R / F1):")
        for etype in ENTITY_TYPES:
            values = entities['by_type'][etype]
            self.stdout.write(f"  {etype:<12} {values['precision']} / {values['recall']} / {values['f1']} "
                              f"(tp={values['tp']} fp={values['fp']} fn={values['fn']})")
        micro = entities['micro']
        self.stdout.write(f"  micro        {micro['precision']} / {micro['recall']} / {micro['f1']} "
                          f"IC95 {entities['micro_f1_ci95']} | macro-F1 {entities['macro_f1']}")
        negation = entities['negation']
        self.stdout.write(f"Negacion: exactitud {negation['negation_accuracy']} ({negation['negation_errors']} de "
                          f"{negation['negated_gold']} negados reportados como presentes) | deteccion explicita "
                          f"{negation['negated_detection_recall']}")
        normalization = entities['normalization']
        self.stdout.write(f"Normalizacion: codigo CIE-10 correcto en {normalization['code_hits']} de "
                          f"{normalization['coded_gold']} entidades codificadas ({normalization['cie10_accuracy']})")
        self.stdout.write(f"Triaje: concordancia {triage['exact_agreement']}% | Kappa {triage['cohen_kappa']} "
                          f"IC95 {triage['cohen_kappa_ci95']} | sensibilidad 1-2 {triage['critical_sensitivity']}% "
                          f"IC95 {triage['critical_sensitivity_ci95']} | infratriaje {triage['undertriage_rate']}%")
        self.stdout.write(f"Rendimiento: latencia media {performance['latency_ms_mean']} ms, p95 "
                          f"{performance['latency_ms_p95']} ms | tokens medios {performance['tokens_mean']} | "
                          f"fallos del LLM {performance['llm_failures']} (casos reintentados "
                          f"{performance['retried_cases']})")
        if performance['llm_failures']:
            self.stdout.write(self.style.WARNING(
                f"{performance['llm_failures']} casos se resolvieron con reglas: no miden al modelo."))
        critical_misses = [r['id'] for r in results
                           if r['reference_level'] in CRITICAL_LEVELS and r['predicted_level'] not in CRITICAL_LEVELS]
        if critical_misses:
            self.stdout.write(self.style.WARNING(f"Casos criticos infratriados: {', '.join(critical_misses)}"))

    def _agreement(self, cases, options):
        try:
            second = json.loads(options['agreement'].read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"No se pudo leer la segunda anotacion: {exc}") from exc
        by_id = {c['id']: c for c in cases}
        counts = []
        missing = []
        for item in second:
            case = by_id.get(item.get('id'))
            if case is None:
                missing.append(str(item.get('id')))
                continue
            counts.append(annotator_agreement(case['entities'], item.get('entities') or {}, mode=options['match']))
        if not counts:
            raise CommandError("Ningun caso de la segunda anotacion coincide con el corpus")

        summary = aggregate(counts)
        matched = sum(c[e]['matched'] for c in counts for e in ENTITY_TYPES)
        negation_agree = sum(c[e]['negation_agree'] for c in counts for e in ENTITY_TYPES)
        self.stdout.write(f"Acuerdo entre anotadores en {len(counts)} casos (F1 por pares, {options['match']}):")
        for etype in ENTITY_TYPES:
            self.stdout.write(f"  {etype:<12} F1 {summary['by_type'][etype]['f1']}")
        self.stdout.write(f"  micro        F1 {summary['micro']['f1']} IC95 {micro_f1_ci(counts)}")
        if matched:
            self.stdout.write(f"Acuerdo en la negacion de las entidades emparejadas: {round(negation_agree / matched, 3)}")
        if missing:
            self.stdout.write(self.style.WARNING(f"Casos fuera del corpus o del split: {', '.join(missing)}"))
