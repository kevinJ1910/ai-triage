"""
Tabla comparativa de motores de triaje a partir de los JSON de evaluate_extraction/evaluate_benchmark.

Filas: cada corrida completa de un split (reglas, LLM local, Gemini sin pauta, hibrido...). Columnas: exactitud,
Kappa ponderado y sensibilidad en niveles 1-2 con IC95, infratriaje, latencia, costo por 1.000 triajes y
privacidad. Las diferencias frente al motor de referencia se calculan pareadas sobre los mismos casos
(bootstrap pareado). Funciones puras: el comando compare_engines solo lee y escribe archivos.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .evaluation_runner import is_local_model, privacy_label
from .metrics import paired_bootstrap_diff, reference_agreement

PAIRED_METRICS = ('exact_agreement', 'cohen_kappa', 'critical_sensitivity', 'undertriage_rate')
MARKER_START = '<!-- comparativa:{split}:inicio -->'
MARKER_END = '<!-- comparativa:{split}:fin -->'


def _model_name(model: Optional[str]) -> str:
    if not model:
        return ''
    if is_local_model(model):
        return model.partition(':')[2] or 'local'
    return model.replace('gemini-', 'Gemini ').replace('-flash-lite', ' Flash-Lite').replace('-flash', ' Flash')


def engine_label(data: Dict[str, Any]) -> str:
    """Nombre legible del motor de una corrida."""
    engine = data.get('engine')
    model = data.get('model')
    run = data.get('run') or {}
    if engine == 'reglas':
        return 'Reglas (Christus Sinergia / Res. 5596)'
    if engine == 'roberta':
        return 'Reglas + NER RoBERTa'
    if is_local_model(model):
        label = f"LLM local ({_model_name(model)}) + reglas"
    elif run.get('rule_hint') is False:
        label = f"{_model_name(model)} sin pauta de reglas" + (' ni RAG' if run.get('rag') is False else '')
    else:
        label = f"Híbrido: reglas + RAG + {_model_name(model) or 'LLM'}"
    extras = []
    if run.get('prompt_version'):
        extras.append(f"prompt {run['prompt_version']}")
    if run.get('policy') and run['policy'] != 'llm':
        extras.append(f"política {run['policy']}")
    if engine == 'hibrido':
        extras.append('NER')
    return f"{label} ({', '.join(extras)})" if extras else label


def is_comparable(data: Dict[str, Any], split: str) -> bool:
    return (data.get('split') == split and data.get('complete') is not False
            and isinstance(data.get('triage'), dict) and bool(data.get('cases')))


def _levels(data: Dict[str, Any]) -> Dict[str, Tuple[int, int]]:
    return {str(c['id']): (int(c['predicted_level']), int(c['reference_level'])) for c in data.get('cases') or []}


def build_row(name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    triage = data['triage']
    performance = data.get('performance') or {}
    run = data.get('run') or {}
    model = data.get('model')
    cost = performance.get('cost_usd_per_1000')
    if cost is None and (not model or is_local_model(model)):
        cost = 0.0
    return {
        'name': name,
        'label': engine_label(data),
        'engine': data.get('engine'),
        'model': model,
        'model_versions': run.get('model_versions'),
        'prompt_version': run.get('prompt_version'),
        'policy': run.get('policy'),
        'n': triage.get('n'),
        **{key: triage.get(key) for key in (
            'exact_agreement', 'exact_agreement_ci95', 'cohen_kappa', 'cohen_kappa_ci95', 'critical_sensitivity',
            'critical_sensitivity_ci95', 'undertriage_rate', 'undertriage_rate_ci95', 'overtriage_rate',
            'critical_undertriage_count')},
        'latency_ms_p50': performance.get('latency_ms_p50', performance.get('latency_ms_mean')),
        'latency_ms_p95': performance.get('latency_ms_p95'),
        'hardware': run.get('hardware') or run.get('processor'),
        'cost_usd_per_1000': cost,
        'privacy': run.get('privacy') or privacy_label(data.get('engine') or '', model),
    }


def paired_differences(runs: Sequence[Tuple[str, Dict[str, Any]]], baseline: str) -> List[Dict[str, Any]]:
    """Diferencias pareadas de cada motor frente al de referencia, sobre los casos que comparten."""
    by_name = dict(runs)
    base_levels = _levels(by_name[baseline])
    out = []
    for name, data in runs:
        if name == baseline:
            continue
        levels = _levels(data)
        common = sorted(set(levels) & set(base_levels))
        triples = [(levels[i][0], base_levels[i][0], levels[i][1]) for i in common]
        out.append({'name': name, 'baseline': baseline, 'n': len(triples),
                    'metrics': {m: paired_bootstrap_diff(triples, m) for m in PAIRED_METRICS}})
    return out


def compare(runs: Sequence[Tuple[str, Dict[str, Any]]], split: str, baseline: Optional[str] = None
            ) -> Dict[str, Any]:
    runs = [(name, data) for name, data in runs if is_comparable(data, split)]
    if baseline is None:
        baseline = next((name for name, data in runs if data.get('engine') == 'reglas'), None)
    elif baseline not in dict(runs):
        raise ValueError(f"La corrida de referencia {baseline} no esta entre las comparables del split {split}")
    return {
        'split': split,
        'baseline': baseline,
        'rows': [build_row(name, data) for name, data in runs],
        'paired': paired_differences(runs, baseline) if baseline else [],
        'critical_misses': {name: critical_misses(data) for name, data in runs},
    }


def critical_misses(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Infratriajes criticos (referencia 1-2, prediccion 3-5) de una corrida, sin la justificacion."""
    misses = (data.get('triage') or {}).get('critical_undertriage')
    if misses is None:
        misses = [{'id': c['id'], 'tipo': c.get('tipo'), 'reference_level': c['reference_level'],
                   'predicted_level': c['predicted_level'], 'rule_level': c.get('rule_level'),
                   'distance': c['predicted_level'] - c['reference_level']}
                  for c in data.get('cases') or []
                  if c['reference_level'] in (1, 2) and c['predicted_level'] not in (1, 2)]
    return [{k: m.get(k) for k in ('id', 'tipo', 'reference_level', 'predicted_level', 'rule_level', 'distance')}
            for m in misses]


def run_agreement(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    """Repetibilidad: concordancia entre dos corridas del mismo motor sobre los mismos casos."""
    a, b = _levels(first), _levels(second)
    common = sorted(set(a) & set(b))
    summary = reference_agreement([(a[i][0], b[i][0]) for i in common])
    return {'n': len(common), 'exact_agreement': summary['exact_agreement'], 'cohen_kappa': summary['cohen_kappa'],
            'kappa_interpretation': summary['kappa_interpretation'],
            'changed_cases': [i for i in common if a[i][0] != b[i][0]]}


def _num(value, digits=1, suffix=''):
    if value is None:
        return '—'
    return f"{value:.{digits}f}".replace('.', ',') + suffix


def _with_ci(value, interval, digits=1, suffix=''):
    text = _num(value, digits, suffix)
    if interval:
        text += f" [{_num(interval[0], digits)}–{_num(interval[1], digits)}]"
    return text


def markdown_table(comparison: Dict[str, Any]) -> str:
    lines = [
        f"Split **{comparison['split']}**. Intervalos de confianza al 95 % por bootstrap (1.000 remuestreos).",
        '',
        '| Motor | n | Exactitud | Kappa ponderado | Sensibilidad I–II | Infratriaje | Sobretriaje '
        '| Latencia p50 / p95 | Costo por 1.000 | Privacidad |',
        '| :--- | ---: | :--- | :--- | :--- | :--- | ---: | :--- | ---: | :--- |',
    ]
    for row in comparison['rows']:
        latency = f"{_num(row['latency_ms_p50'], 0)} / {_num(row['latency_ms_p95'], 0)} ms"
        if row.get('hardware'):
            latency += f" ({row['hardware']})"
        cost = '—' if row['cost_usd_per_1000'] is None else f"{_num(row['cost_usd_per_1000'], 2)} USD"
        lines.append(
            f"| {row['label']} | {row['n']} | {_with_ci(row['exact_agreement'], row.get('exact_agreement_ci95'), suffix=' %')} "
            f"| {_with_ci(row['cohen_kappa'], row.get('cohen_kappa_ci95'), 3)} "
            f"| {_with_ci(row['critical_sensitivity'], row.get('critical_sensitivity_ci95'), suffix=' %')} "
            f"| {_with_ci(row['undertriage_rate'], row.get('undertriage_rate_ci95'), suffix=' %')} "
            f"| {_num(row['overtriage_rate'], suffix=' %')} | {latency} | {cost} | {row['privacy']} |"
        )
    if comparison.get('paired'):
        base = next((r['label'] for r in comparison['rows'] if r['name'] == comparison['baseline']), comparison['baseline'])
        lines += ['', f"Diferencias pareadas frente a «{base}» (motor − referencia, IC95):", '',
                  '| Motor | n | Exactitud (pp) | Kappa | Sensibilidad I–II (pp) | Infratriaje (pp) |',
                  '| :--- | ---: | :--- | :--- | :--- | :--- |']
        labels = {r['name']: r['label'] for r in comparison['rows']}
        for diff in comparison['paired']:
            m = diff['metrics']
            lines.append(
                f"| {labels.get(diff['name'], diff['name'])} | {diff['n']} "
                f"| {_with_ci(m['exact_agreement']['diff'], m['exact_agreement']['ci95'])} "
                f"| {_with_ci(m['cohen_kappa']['diff'], m['cohen_kappa']['ci95'], 3)} "
                f"| {_with_ci(m['critical_sensitivity']['diff'], m['critical_sensitivity']['ci95'])} "
                f"| {_with_ci(m['undertriage_rate']['diff'], m['undertriage_rate']['ci95'])} |"
            )
    if comparison.get('critical_misses'):
        labels = {r['name']: r['label'] for r in comparison['rows']}
        lines += ['', 'Infratriaje crítico (referencia I–II clasificada como III–V), por motor:', '']
        for name, misses in comparison['critical_misses'].items():
            detail = ', '.join(f"{m['id']} ({m.get('tipo') or '?'}; ref. {m['reference_level']}, pred. {m['predicted_level']})"
                               for m in misses[:15])
            more = f" y {len(misses) - 15} más" if len(misses) > 15 else ''
            lines.append(f"- {labels.get(name, name)}: {len(misses)} casos" + (f": {detail}{more}" if misses else ''))
    if comparison.get('repeatability'):
        rep = comparison['repeatability']
        lines += ['', f"Repetibilidad ({rep['n']} casos repetidos): concordancia {_num(rep['exact_agreement'], suffix=' %')}, "
                      f"Kappa {_num(rep['cohen_kappa'], 3)} ({rep['kappa_interpretation']})."]
    return '\n'.join(lines)


def write_markdown_section(path: Path, split: str, table: str) -> None:
    """Sustituye la tabla del split entre sus marcadores; si no estan, la anade al final."""
    start, end = MARKER_START.format(split=split), MARKER_END.format(split=split)
    block = f"{start}\n{table}\n{end}"
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    pattern = re.compile(re.escape(start) + r'.*?' + re.escape(end), re.S)
    if pattern.search(text):
        text = pattern.sub(lambda _: block, text)
    else:
        text = text.rstrip('\n') + ('\n\n' if text else '') + block + '\n'
    path.write_text(text, encoding='utf-8', newline='\n')
