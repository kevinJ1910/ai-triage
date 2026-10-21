"""
Analisis de errores del NER y auditoria de coherencia del corpus propio. Solo biblioteca estandar.

Errores de prediccion (tipologia habitual en NER: exacto, limites, etiqueta, ambos, omitido, espurio):

    python ml/ner/error_analysis.py errores ml/ner/output/cv_predicciones.json

cv_predicciones.json lo escribe el notebook (celda 8): por documento, el texto, los spans gold y los
predichos en la validacion cruzada. Cada documento se predice con el modelo que no lo vio al entrenar.

Auditoria del corpus (sin modelo; detecta anotaciones incoherentes que el span exacto castiga dos veces):

    python ml/ner/error_analysis.py auditoria --split dev
"""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ner_data import CORPUS_TYPE_MAP, ENTITY_LABELS, Span, span_prf, span_prf_partial  # noqa: E402

DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / 'backend/triage/benchmark/corpus_entidades.json'
ERROR_TYPES = ('exacto', 'limites', 'etiqueta', 'limites_y_etiqueta', 'omitido', 'espurio')
# Bordes que casi nunca forman parte de una mencion. Los cliticos («me duele») y los articulos iniciales
# («la piel se ve blanca») si entran segun la guia del corpus, que anota la expresion coloquial completa.
LEADING_EDGE = {'y', 'o', 'de', 'del', 'con', 'en', 'a', 'al', 'que', 'pero'}
TRAILING_EDGE = {'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'y', 'o', 'con', 'en', 'a', 'al', 'que',
                 'se', 'le', 'me', 'muy', 'pero'}


def _overlap(a: Span, b: Span) -> int:
    return max(0, min(a.end, b.end) - max(a.start, b.start))


def _as_span(item) -> Span:
    if isinstance(item, Span):
        return item
    if isinstance(item, dict):
        return Span(int(item['start']), int(item['end']), item['label'])
    return Span(int(item[0]), int(item[1]), item[2])


# --------------------------------------------------------------------------- tipologia de errores

def classify_errors(text: str, gold: Sequence, predicted: Sequence) -> List[Dict]:
    """
    Una fila por error (y por acierto exacto). Cada gold y cada predicho aparecen una sola vez:
    los pares se toman por mayor solape.
    """
    g = sorted({_as_span(s) for s in gold}, key=lambda s: (s.start, s.end))
    p = sorted({_as_span(s) for s in predicted}, key=lambda s: (s.start, s.end))
    pairs = sorted(((_overlap(a, b), a.label == b.label, i, j) for i, a in enumerate(g) for j, b in enumerate(p)
                    if _overlap(a, b) > 0), reverse=True)
    used_g, used_p, rows = set(), set(), []
    for _, _, i, j in pairs:
        if i in used_g or j in used_p:
            continue
        used_g.add(i)
        used_p.add(j)
        a, b = g[i], p[j]
        same_bounds = (a.start, a.end) == (b.start, b.end)
        kind = ('exacto' if a.label == b.label else 'etiqueta') if same_bounds else \
               ('limites' if a.label == b.label else 'limites_y_etiqueta')
        rows.append({'tipo': kind, 'gold': text[a.start:a.end], 'gold_label': a.label,
                     'pred': text[b.start:b.end], 'pred_label': b.label, 'pos': a.start})
    for i, a in enumerate(g):
        if i not in used_g:
            rows.append({'tipo': 'omitido', 'gold': text[a.start:a.end], 'gold_label': a.label,
                         'pred': None, 'pred_label': None, 'pos': a.start})
    for j, b in enumerate(p):
        if j not in used_p:
            rows.append({'tipo': 'espurio', 'gold': None, 'gold_label': None,
                         'pred': text[b.start:b.end], 'pred_label': b.label, 'pos': b.start})
    return sorted(rows, key=lambda r: r['pos'])


def _boundary_pattern(row: Dict) -> str:
    """Describe un error de limites: el predicho es mas largo, mas corto o esta desplazado."""
    gold, pred = row['gold'], row['pred']
    if gold in pred:
        return 'predicho_mas_largo'
    if pred in gold:
        return 'predicho_mas_corto'
    return 'desplazado'


def error_report(predictions: Dict[str, Dict], examples: int = 12) -> Dict:
    """predictions: {doc_id: {'text', 'gold': [...], 'pred': [...]}} (formato de cv_predicciones.json)."""
    by_label = {label: Counter() for label in ENTITY_LABELS}
    patterns, confusions = Counter(), Counter()
    samples = defaultdict(list)
    for doc_id, item in sorted(predictions.items()):
        for row in classify_errors(item['text'], item['gold'], item['pred']):
            label = row['gold_label'] or row['pred_label']
            by_label[label][row['tipo']] += 1
            if row['tipo'] == 'limites':
                patterns[_boundary_pattern(row)] += 1
            if row['tipo'] in ('etiqueta', 'limites_y_etiqueta'):
                confusions[f"{row['gold_label']} -> {row['pred_label']}"] += 1
            if row['tipo'] != 'exacto' and len(samples[row['tipo']]) < examples:
                samples[row['tipo']].append({'doc': doc_id, **{k: row[k] for k in
                                                               ('gold', 'gold_label', 'pred', 'pred_label')}})
    gold = {d: [_as_span(s) for s in item['gold']] for d, item in predictions.items()}
    pred = {d: [_as_span(s) for s in item['pred']] for d, item in predictions.items()}
    totals = sum(by_label.values(), Counter())
    errors = sum(v for k, v in totals.items() if k != 'exacto')
    return {
        'documentos': len(predictions),
        'exacto': span_prf(gold, pred),
        'parcial': span_prf_partial(gold, pred),
        'errores_por_tipo': {label: {t: c[t] for t in ERROR_TYPES} for label, c in by_label.items()},
        'reparto_de_errores': {t: {'n': totals[t], 'porcentaje': round(100 * totals[t] / errors, 1) if errors else None}
                               for t in ERROR_TYPES if t != 'exacto'},
        'patrones_de_limites': dict(patterns),
        'confusiones_de_etiqueta': dict(confusions.most_common()),
        'ejemplos': dict(samples),
    }


# --------------------------------------------------------------------------- auditoria del corpus

def _fold(text: str) -> str:
    # Sin tildes ni mayusculas, pero la ñ se conserva («uña» no es «una»).
    text = unicodedata.normalize('NFKD', text.lower().replace('ñ', ''))
    return ''.join(ch for ch in text if not unicodedata.combining(ch)).replace('', 'ñ')


def _occurrences(haystack: str, needle: str) -> List[int]:
    """Posiciones de needle como palabra completa, sin distinguir mayusculas ni tildes."""
    folded_h, folded_n = _fold(haystack), _fold(needle)
    return [m.start() for m in re.finditer(rf'(?<!\w){re.escape(folded_n)}(?!\w)', folded_h)]


def audit_corpus(cases: Sequence[Dict], min_docs: int = 1) -> Dict:
    """
    Problemas de anotacion que penalizan al modelo aunque acierte:
      no_encontrado         el texto del span no esta literal en el transcript (el span se pierde).
      repetido_sin_anotar   el texto aparece mas veces en el transcript que las veces anotado: la otra
                            aparicion queda como 'O' aunque el modelo la marque bien.
      solape                spans del mismo caso que se pisan (BIO solo conserva uno).
      etiqueta_inconsistente el mismo texto se anota con etiquetas distintas en distintos casos.
      anotado_aqui_no_alla  un texto anotado en varios casos aparece sin anotar en otro.
      borde_sospechoso      el span empieza en conjuncion o preposicion, o termina en una palabra funcional.
    """
    issues = defaultdict(list)
    labels_by_text: Dict[str, Counter] = defaultdict(Counter)
    docs_by_text: Dict[str, set] = defaultdict(set)
    annotated_spans: Dict[str, List[Tuple[int, int]]] = {}
    for case in cases:
        text, spans = case['transcript'], []
        counted = Counter()
        for etype, label in CORPUS_TYPE_MAP.items():
            for item in case['entities'].get(etype, []):
                surface = item['text']
                start = text.find(surface)
                if start < 0:
                    issues['no_encontrado'].append({'caso': case['id'], 'texto': surface, 'tipo': etype})
                    continue
                counted[surface] += 1
                key = _fold(surface).strip()
                labels_by_text[key][label] += 1
                docs_by_text[key].add(case['id'])
                words = _fold(surface).split()
                if words and (words[0] in LEADING_EDGE or words[-1] in TRAILING_EDGE):
                    issues['borde_sospechoso'].append({'caso': case['id'], 'texto': surface, 'tipo': etype})
                spans.append((start, start + len(surface), surface))
        for surface, n in counted.items():
            found = len(_occurrences(text, surface))
            if found > n:
                issues['repetido_sin_anotar'].append({'caso': case['id'], 'texto': surface,
                                                     'anotado': n, 'aparece': found})
        for i, a in enumerate(spans):
            for b in spans[i + 1:]:
                if a[0] < b[1] and b[0] < a[1] and (a[0], a[1]) != (b[0], b[1]):
                    issues['solape'].append({'caso': case['id'], 'a': a[2], 'b': b[2]})
        annotated_spans[case['id']] = [(s, e) for s, e, _ in spans]

    for key, counter in labels_by_text.items():
        if len(counter) > 1:
            issues['etiqueta_inconsistente'].append({'texto': key, 'etiquetas': dict(counter)})

    # Textos anotados en al menos min_docs casos que aparecen sin anotar (como palabra completa) en otro sitio.
    frequent = {k for k, docs in docs_by_text.items() if len(docs) >= min_docs and len(k) >= 4}
    for case in cases:
        covered = annotated_spans.get(case['id'], [])
        for key in sorted(frequent):
            for pos in _occurrences(case['transcript'], key):
                end = pos + len(key)
                if not any(s <= pos and end <= e for s, e in covered):
                    issues['anotado_aqui_no_alla'].append({
                        'caso': case['id'], 'texto': case['transcript'][pos:end],
                        'anotado_en': len(docs_by_text[key]),
                        'contexto': case['transcript'][max(0, pos - 30):end + 30]})
    summary = {kind: len(rows) for kind, rows in issues.items()}
    return {'casos': len(cases), 'resumen': summary, 'detalle': dict(issues)}


# --------------------------------------------------------------------------- CLI

def _print_errors(report: Dict) -> None:
    print(f"Documentos: {report['documentos']}")
    print(f"{'':<12}{'exacto':>8}{'parcial':>9}")
    for label in (*ENTITY_LABELS, 'micro'):
        print(f"{label:<12}{report['exacto'][label]['f1'] or 0:>8.3f}{report['parcial'][label]['f1'] or 0:>9.3f}")
    print('\nReparto de errores:')
    for kind, values in report['reparto_de_errores'].items():
        print(f"  {kind:<20}{values['n']:>5}  {values['porcentaje'] or 0:>5.1f} %")
    print('\nPor etiqueta:', json.dumps(report['errores_por_tipo'], ensure_ascii=False))
    print('Patrones de limites:', report['patrones_de_limites'])
    print('Confusiones de etiqueta:', report['confusiones_de_etiqueta'])
    for kind, rows in report['ejemplos'].items():
        print(f'\n[{kind}]')
        for row in rows:
            print(f"  {row['doc']}: gold={row['gold']!r} ({row['gold_label']})  pred={row['pred']!r} ({row['pred_label']})")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    errors = sub.add_parser('errores', help='Tipologia de errores y metrica parcial de unas predicciones.')
    errors.add_argument('predicciones', type=Path)
    errors.add_argument('--json', type=Path, help='Guarda el informe completo en este fichero.')
    errors.add_argument('--ejemplos', type=int, default=12)
    audit = sub.add_parser('auditoria', help='Coherencia de las anotaciones del corpus propio.')
    audit.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS)
    audit.add_argument('--split', default='dev', help="dev, test o 'todos'.")
    audit.add_argument('--json', type=Path)
    options = parser.parse_args(argv)

    if options.command == 'errores':
        report = error_report(json.loads(options.predicciones.read_text(encoding='utf-8')), options.ejemplos)
        _print_errors(report)
    else:
        cases = json.loads(options.corpus.read_text(encoding='utf-8'))
        if options.split != 'todos':
            cases = [c for c in cases if c['split'] == options.split]
        report = audit_corpus(cases)
        print(json.dumps(report['resumen'], ensure_ascii=False, indent=2))
        for kind, rows in report['detalle'].items():
            print(f'\n[{kind}] {len(rows)}')
            for row in rows[:25]:
                print('  ', json.dumps(row, ensure_ascii=False))
    if options.json:
        options.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
