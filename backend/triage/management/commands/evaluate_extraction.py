"""
Evaluacion reproducible de la extraccion de entidades (NER), la negacion y el nivel de triaje
contra el corpus anotado (triage/benchmark/corpus_entidades.json).

Uso:
    python manage.py evaluate_extraction --engine reglas --split dev
    python manage.py evaluate_extraction --engine hibrido --model gemini-2.5-flash --split dev --rpm 5 \
        --output triage/benchmark/resultados/dev_hibrido_gemini-2.5-flash_pv1.json
    python manage.py evaluate_extraction --engine hibrido --model local:qwen2.5:7b-instruct-q4_K_M --split dev
    python manage.py evaluate_extraction --engine hibrido --model gemini-2.5-flash --split dev --summarize-only \
        --policy min_critico --output r.json
    python manage.py evaluate_extraction --agreement doble_anotacion/segundo_anotador.json

Motores:
    reglas   sin LLM ni NER: entidades del catalogo terminologico y regex, nivel por reglas.
    roberta  sin LLM, con el NER (RoBERTa, NER_MODEL_PATH) fusionado con el catalogo; nivel por reglas.
    gemini   analyze_triage_transcript completo sin cache, sin NER y con un unico modelo (--model). Con
             'local:<modelo>' se evalua el LLM local (servidor compatible con OpenAI, LOCAL_LLM_BASE_URL).
    hibrido  LLM + NER: las menciones del NER y la negacion mandan y el LLM desempata (entity_fusion). Es la
             configuracion de produccion.

Corridas con LLM (triage/evaluation_runner.py): cada caso evaluado se guarda en
benchmark/resultados/crudos/<run_id>.jsonl con la salida cruda del modelo. Al repetir el comando se reanuda
donde se quedo (--fresh empieza de cero). Si el LLM falla, el caso queda pendiente: nunca se resuelve con
reglas. Con la cuota diaria agotada, la corrida se detiene y se reanuda otro dia con el mismo comando.
Las metricas se calculan sobre el checkpoint; el resumen solo se marca complete=true cuando estan todos los
casos del split.

Cuota: el plan gratuito de Gemini limita las peticiones por minuto (5 en gemini-2.5-flash) y por dia. Usar
--rpm y --max-calls.

Una sola llamada por caso alimenta las metricas de entidades, las de triaje y la de codigos CIE-10 de la
normalizacion. El split 'test' se reserva para la evaluacion final: ajustar reglas o prompts mirando sus
resultados invalida la medicion.
"""
import json
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from triage.demographics import load_demographics
from triage.entity_corpus import CORPUS_PATH, ENTITY_TYPES, SPLITS, load_entity_corpus
from triage.evaluation_runner import (
    RAW_DIR,
    Checkpoint,
    RateLimiter,
    RunSpec,
    performance_summary,
    run_metadata,
    run_pending,
)
from triage.extraction_metrics import (
    MATCH_MODES,
    aggregate,
    annotator_agreement,
    code_accuracy,
    code_hits,
    micro_f1_ci,
    score_case,
)
from triage.metrics import (
    COMBINE_POLICIES,
    CRITICAL_LEVELS,
    combine_levels,
    critical_undertriage,
    triage_breakdown,
    triage_summary,
)

ENGINES = ('reglas', 'roberta', 'gemini', 'hibrido')
LLM_ENGINES = ('gemini', 'hibrido')
NER_ENGINES = ('roberta', 'hibrido')
RULES_ENGINE_PREFIX = 'Motor de Reglas'


class LLMFellBackToRules(RuntimeError):
    """El analizador devolvio el motor de reglas en una corrida de LLM (no deberia ocurrir con strict_llm)."""


def run_case(engine: str, transcript: str, model=None, prompt_version=None, rule_hint=True, rag=True) -> dict:
    """Registro de un caso: prediccion y telemetria, sin metricas (se calculan al resumir)."""
    from triage.ai_analyzer import analyze_triage_transcript

    llm = engine in LLM_ENGINES
    options = {'strict_llm': True, 'include_raw': True, 'prompt_version': prompt_version, 'rule_hint': rule_hint,
               'rag': rag, 'combine_policy': 'llm'} if llm else {}
    start = time.perf_counter()
    analysis = analyze_triage_transcript(
        transcript, use_cache=False, allow_llm=llm, model=model, use_ner=engine in NER_ENGINES, **options
    )
    latency_ms = round((time.perf_counter() - start) * 1000)
    engine_used = analysis.get('engine_used') or 'desconocido'
    if llm and engine_used.startswith(RULES_ENGINE_PREFIX):
        raise LLMFellBackToRules(analysis.get('warning') or 'el LLM no respondio')
    entities = analysis.get('entities') or {}
    triage = analysis.get('triage') or {}
    level = int(triage.get('level', 5))
    return {
        # Con LLM, predicted_level es el nivel del LLM; la politica de combinacion se aplica al resumir.
        'predicted_level': int(analysis.get('llm_level') or level),
        'rule_level': analysis.get('rule_level', level if not llm else None),
        'predicted_entities': {key: list(entities.get(key) or []) for key in (*ENTITY_TYPES, 'negated_findings')},
        'engine_used': engine_used,
        'ner_engine': analysis.get('ner_engine'),
        'model_version': analysis.get('model_version'),
        'prompt_version': analysis.get('prompt_version'),
        'latency_ms': latency_ms,
        'llm_latency_ms': analysis.get('llm_latency_ms'),
        'prompt_tokens': int(analysis.get('prompt_tokens') or 0),
        'completion_tokens': int(analysis.get('completion_tokens') or 0),
        'thoughts_tokens': int(analysis.get('thoughts_tokens') or 0),
        'total_tokens': int(analysis.get('total_tokens') or 0),
        'justification': triage.get('justification'),
        'predicted_codes': [t['code'] for t in analysis.get('normalized_terms') or [] if t.get('code_system') == 'CIE-10'],
        **({'llm_raw': analysis.get('llm_raw')} if llm else {}),
    }


def summarize(cases, records, engine, match, policy, demographics=None):
    """Metricas de entidades y de triaje sobre los registros de los casos (en el orden del corpus)."""
    results = []
    for case in cases:
        record = records.get(case['id'])
        if record is None:
            continue
        llm_level = record['predicted_level']
        level = combine_levels(llm_level, record.get('rule_level'), policy) if engine in LLM_ENGINES else llm_level
        demo = (demographics or {}).get(case['id']) or {}
        results.append({
            'id': case['id'], 'split': case['split'], 'tipo': case['tipo'], 'lote': case.get('lote', 1),
            'reference_level': case['reference_level'],
            **{k: v for k, v in record.items() if k not in ('llm_raw', 'transcript_sha256', 'id')},
            'predicted_level': level, 'llm_level': llm_level if engine in LLM_ENGINES else None,
            'sexo': demo.get('sexo'), 'grupo_edad': demo.get('grupo_edad'),
            'counts': score_case(case['entities'], record['predicted_entities'], mode=match),
            'code_hits': code_hits(case['entities'], record.get('predicted_codes') or []),
        })

    entity_summary = aggregate(r['counts'] for r in results)
    entity_summary['micro_f1_ci95'] = micro_f1_ci([r['counts'] for r in results])
    entity_summary['normalization'] = code_accuracy(r['code_hits'] for r in results)
    # Por lote: el lote 2 se escribio despues del catalogo terminologico; si rinde mucho mejor que el
    # lote 1 en test, hay sesgo de autoria que reportar.
    entity_summary['by_lote'] = {
        str(lote): aggregate(r['counts'] for r in results if r['lote'] == lote)['micro']
        for lote in sorted({r['lote'] for r in results})
    }
    triage = triage_summary([(r['predicted_level'], r['reference_level']) for r in results]) if results else {}
    if results:
        triage['by_tipo'] = triage_breakdown(results, 'tipo')
        triage['by_lote'] = triage_breakdown(results, 'lote')
        if demographics:
            triage['by_sexo'] = triage_breakdown(results, 'sexo')
            triage['by_grupo_edad'] = triage_breakdown(results, 'grupo_edad')
        triage['critical_undertriage'] = critical_undertriage(results)
    return results, entity_summary, triage


class Command(BaseCommand):
    help = "Evalua la extraccion de entidades, la negacion y el triaje contra el corpus anotado."

    def add_arguments(self, parser):
        parser.add_argument('--corpus', type=Path, default=CORPUS_PATH, help="Corpus anotado (JSON)")
        parser.add_argument('--engine', choices=ENGINES, default='reglas')
        parser.add_argument('--model', help="Modelo a evaluar (obligatorio con gemini e hibrido); local:<modelo> "
                                            "para el LLM local")
        parser.add_argument('--split', choices=SPLITS, help="Particion a evaluar (por defecto, todo el corpus)")
        parser.add_argument('--match', choices=MATCH_MODES, default='relaxed', help="Criterio de emparejamiento")
        parser.add_argument('--limit', type=int, help="Evaluar solo los primeros N casos (pruebas rapidas)")
        parser.add_argument('--rpm', type=float, default=0.0, help="Peticiones por minuto como maximo (5 en el "
                                                                   "plan gratuito de gemini-2.5-flash)")
        parser.add_argument('--pause', type=float, default=0.0, help="Segundos minimos entre llamadas al LLM")
        parser.add_argument('--max-calls', type=int, help="Tope de llamadas al LLM en esta tanda (cuota diaria)")
        parser.add_argument('--retries', type=int, default=2, help="Reintentos de un caso cuando falla el LLM")
        parser.add_argument('--retry-wait', type=float, default=60.0, help="Segundos de espera antes de reintentar")
        parser.add_argument('--fresh', action='store_true', help="Borra el checkpoint y empieza de cero")
        parser.add_argument('--summarize-only', action='store_true',
                            help="Recalcula el resumen desde el checkpoint sin llamar al LLM")
        parser.add_argument('--raw-dir', type=Path, default=RAW_DIR, help="Carpeta de los checkpoints JSONL")
        parser.add_argument('--prompt-version', help="Version del prompt (por defecto la de produccion)")
        parser.add_argument('--no-rule-hint', action='store_true', help="Ablacion: sin la pauta del motor de reglas")
        parser.add_argument('--no-rag', action='store_true', help="Ablacion: sin los criterios recuperados (RAG)")
        parser.add_argument('--policy', choices=COMBINE_POLICIES, default='llm',
                            help="Politica de combinacion del nivel del LLM con el de reglas (se aplica al resumir)")
        parser.add_argument('--tag', default='', help="Sufijo del run_id (p. ej. r2 para la corrida de repetibilidad)")
        parser.add_argument('--tier', choices=('gratuito', 'pago', 'local'), help="Plan del proveedor (metadatos)")
        parser.add_argument('--hardware', help="Descripcion del equipo (metadatos; p. ej. 'RTX 3060 12 GB')")
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
        llm = engine in LLM_ENGINES
        if llm and not model:
            raise CommandError(f"--engine {engine} requiere --model (p. ej. gemini-2.5-flash)")
        if options['summarize_only'] and not llm:
            raise CommandError("--summarize-only solo aplica a los motores con LLM (gemini, hibrido)")
        ner_engine = None
        if engine in NER_ENGINES and not options['summarize_only']:
            from triage.ner_model import engine_label
            ner_engine = engine_label()
            if not ner_engine:
                raise CommandError(f"--engine {engine} requiere el modelo NER: defina NER_MODEL_PATH "
                                   "(ver ml/ner/README.md) y compruebe que carga.")
        if options.get('limit'):
            cases = cases[:options['limit']]

        prompt_version = prompt_sha = temperature = None
        if llm:
            from triage.ai_analyzer import LLM_TEMPERATURE, PROMPT_VERSION, PROMPT_TEMPLATES, prompt_sha256
            prompt_version = options.get('prompt_version') or PROMPT_VERSION
            if prompt_version not in PROMPT_TEMPLATES:
                raise CommandError(f"Version de prompt desconocida: {prompt_version}")
            prompt_sha = prompt_sha256(prompt_version, not options['no_rule_hint'], not options['no_rag'])
            temperature = LLM_TEMPERATURE
        spec = RunSpec(engine=engine, split=options.get('split') or 'todo', model=model,
                       prompt_version=prompt_version, rule_hint=not options['no_rule_hint'],
                       rag=not options['no_rag'], tag=options['tag'])

        outcome = None
        if llm:
            checkpoint = Checkpoint(options['raw_dir'] / f'{spec.run_id}.jsonl')
            if options['fresh']:
                checkpoint.reset()
            if not options['summarize_only']:
                outcome = run_pending(
                    cases, checkpoint,
                    lambda case: run_case(engine, case['transcript'], model=model, prompt_version=prompt_version,
                                          rule_hint=spec.rule_hint, rag=spec.rag),
                    limiter=RateLimiter(rpm=options['rpm'], min_interval=options['pause']),
                    max_calls=options.get('max_calls'), retries=options['retries'],
                    retry_wait=options['retry_wait'], sleep=time.sleep, log=self.stderr.write,
                )
            records = {case['id']: checkpoint.get(case) for case in cases if checkpoint.get(case)}
            if ner_engine is None and engine in NER_ENGINES:
                ner_engine = next((r.get('ner_engine') for r in records.values() if r.get('ner_engine')), None)
        else:
            records = {}
            for index, case in enumerate(cases, start=1):
                records[case['id']] = run_case(engine, case['transcript'], model=model)
                self.stderr.write(f"[{index}/{len(cases)}] {case['id']} -> nivel "
                                  f"{records[case['id']]['predicted_level']}")

        policy = options['policy'] if llm else None
        results, entity_summary, triage = summarize(cases, records, engine, options['match'], policy or 'llm',
                                                    load_demographics())
        complete = len(results) == len(cases)
        performance = performance_summary(list(records.values()), model)
        performance['pending_cases'] = len(cases) - len(results)
        self._report(engine, model, options, results, entity_summary, triage, performance, complete, outcome)

        if options.get('output'):
            payload = {
                'engine': engine, 'model': model, 'ner_engine': ner_engine, 'split': spec.split,
                'match': options['match'], 'corpus': Path(options['corpus']).name, 'complete': complete,
                'cases_expected': len(cases),
                'run': run_metadata(spec, list(records.values()), corpus=options['corpus'], tier=options.get('tier'),
                                    hardware=options.get('hardware'), policy=policy, prompt_sha256=prompt_sha,
                                    temperature=temperature),
                'entities': entity_summary, 'triage': triage, 'performance': performance, 'cases': results,
            }
            options['output'].parent.mkdir(parents=True, exist_ok=True)
            options['output'].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            self.stdout.write(f"Detalle guardado en {options['output']}")

        if outcome and outcome.stopped in ('daily_quota', 'rate_limit'):
            raise CommandError(f"Cuota del proveedor agotada: quedan {len(outcome.pending)} casos. Reanude mas tarde "
                               "con el mismo comando (los casos evaluados estan en el checkpoint).")

    def _report(self, engine, model, options, results, entities, triage, performance, complete, outcome):
        label = f"{engine} ({model})" if model else engine
        self.stdout.write(f"Casos: {len(results)} | Motor: {label} | Split: {options.get('split') or 'todo'} "
                          f"| Emparejamiento: {options['match']}")
        if outcome is not None:
            self.stdout.write(f"Tanda: {outcome.evaluated} evaluados, {outcome.skipped} ya en el checkpoint, "
                              f"{len(outcome.pending)} pendientes ({outcome.calls} llamadas)")
        if not complete:
            self.stdout.write(self.style.WARNING("Corrida incompleta: el resumen es parcial (complete=false) y no "
                                                 "se reporta como resultado del modelo."))
        if not results:
            return
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
        for lote, micro in entities['by_lote'].items():
            self.stdout.write(f"  lote {lote:<7} {micro['precision']} / {micro['recall']} / {micro['f1']}")
        normalization = entities['normalization']
        self.stdout.write(f"Normalizacion: codigo CIE-10 correcto en {normalization['code_hits']} de "
                          f"{normalization['coded_gold']} entidades codificadas ({normalization['cie10_accuracy']})")
        self.stdout.write(f"Triaje: concordancia {triage['exact_agreement']}% IC95 {triage['exact_agreement_ci95']} "
                          f"| Kappa {triage['cohen_kappa']} IC95 {triage['cohen_kappa_ci95']} | sensibilidad 1-2 "
                          f"{triage['critical_sensitivity']}% IC95 {triage['critical_sensitivity_ci95']} | "
                          f"infratriaje {triage['undertriage_rate']}% | sobretriaje {triage['overtriage_rate']}%")
        self.stdout.write(f"Rendimiento: latencia media {performance['latency_ms_mean']} ms, p95 "
                          f"{performance['latency_ms_p95']} ms | tokens medios {performance['tokens_mean']} | "
                          f"costo {performance['cost_usd']} USD | fallos del LLM {performance['llm_failures']} "
                          f"(casos reintentados {performance['retried_cases']})")
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
