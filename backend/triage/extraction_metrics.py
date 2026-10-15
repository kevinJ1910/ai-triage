"""
Metricas de extraccion de entidades clinicas contra el corpus anotado (triage/entity_corpus.py).
Funciones puras, sin base de datos ni red, para poder probarlas y reutilizarlas en los comandos.

Emparejamiento: cada prediccion se empareja como maximo con una entidad anotada.
  estricto  el termino predicho coincide con el span o con la forma normalizada.
  relajado  ademas, uno contiene al otro o comparten al menos la mitad de sus palabras de contenido.
Las entidades anotadas como negadas no deben aparecer entre las predichas como presentes: si aparecen,
cuentan como falso positivo y como error de negacion.
"""
import random
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .clinical_protocol import _normalize_text
from .entity_corpus import ENTITY_TYPES

MATCH_MODES = ('strict', 'relaxed')

_STOPWORDS = {
    'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'en', 'y', 'a', 'al', 'con', 'por', 'para',
    'que', 'se', 'le', 'me', 'mi', 'su', 'lo', 'muy', 'mas', 'tipo', 'como',
}

# Prefijos de los signos vitales en el formato compacto de input_pipeline y sinonimos libres del LLM.
_VITAL_PREFIXES = (
    ('PA', ('pa', 'ta', 'presion', 'tension')),
    ('FC', ('fc', 'pulso', 'frecuencia cardiaca')),
    ('SpO2', ('spo2', 'sat', 'saturacion')),
    ('FR', ('fr', 'frecuencia respiratoria')),
    ('GLU', ('glu', 'glucosa', 'glucometria', 'glucemia', 'azucar')),
    ('GCS', ('gcs', 'glasgow')),
    ('EVA', ('eva',)),
    ('T', ('t', 'temp', 'temperatura', 'fiebre')),
)


def normalize_term(text: str) -> str:
    """Minusculas, sin tildes ni puntuacion y con espacios simples."""
    norm = _normalize_text(text or '')
    norm = re.sub(r'[^a-z0-9%/.\s]', ' ', norm)
    return ' '.join(norm.split())


def _content_tokens(text: str) -> set:
    return {tok for tok in normalize_term(text).split() if tok not in _STOPWORDS}


def canonical_vital(text: str) -> Tuple[Optional[str], Tuple[str, ...]]:
    """'PA: 70/40 mmHg' y 'presion 70 sobre 40' -> ('PA', ('70', '40'))."""
    norm = normalize_term(text)
    numbers = tuple(n.replace(',', '.').rstrip('.') for n in re.findall(r'\d+(?:[.,]\d+)?', norm))
    prefix = None
    for canonical, aliases in _VITAL_PREFIXES:
        if any(re.match(rf'{re.escape(alias)}\b', norm) for alias in aliases):
            prefix = canonical
            break
    return prefix, numbers


def terms_match(predicted: str, gold: Dict[str, Any], etype: str, mode: str = 'relaxed') -> bool:
    if etype == 'vitals':
        p_prefix, p_numbers = canonical_vital(predicted)
        g_prefix, g_numbers = canonical_vital(gold['normalized'])
        if not p_numbers or p_numbers != g_numbers:
            return False
        return p_prefix is None or g_prefix is None or p_prefix == g_prefix

    pred = normalize_term(predicted)
    candidates = [normalize_term(gold['normalized']), normalize_term(gold['text'])]
    if pred in candidates:
        return True
    if mode == 'strict':
        return False
    pred_tokens = _content_tokens(predicted)
    for candidate in candidates:
        if pred and candidate and (pred in candidate or candidate in pred):
            return True
        cand_tokens = _content_tokens(candidate)
        if pred_tokens and cand_tokens:
            overlap = len(pred_tokens & cand_tokens) / min(len(pred_tokens), len(cand_tokens))
            if overlap >= 0.5:
                return True
    return False


def _greedy_match(predicted: Sequence[str], gold: Sequence[Dict[str, Any]], etype: str, mode: str):
    """Empareja cada prediccion con la primera entidad anotada libre que coincide."""
    used = set()
    pairs = []
    unmatched_pred = []
    for p_idx, term in enumerate(predicted):
        for g_idx, item in enumerate(gold):
            if g_idx not in used and terms_match(term, item, etype, mode):
                used.add(g_idx)
                pairs.append((p_idx, g_idx))
                break
        else:
            unmatched_pred.append(p_idx)
    return pairs, unmatched_pred, [i for i in range(len(gold)) if i not in used]


def score_case(gold_entities: Dict[str, List[Dict[str, Any]]], predicted: Dict[str, List[str]],
               mode: str = 'relaxed') -> Dict[str, Dict[str, int]]:
    """
    Conteos por tipo para un caso: tp, fp, fn sobre las entidades presentes y, para las negadas,
    cuantas se reportaron como presentes (negation_errors) y cuantas detecto el motor como negadas.
    predicted: listas de terminos por tipo; 'negated_findings' (opcional) lista los hallazgos negados.
    """
    negated_reported = list(predicted.get('negated_findings') or [])
    counts = {}
    for etype in ENTITY_TYPES:
        gold = gold_entities.get(etype, [])
        affirmed = [g for g in gold if not g['negated']]
        negated = [g for g in gold if g['negated']]
        preds = [p for p in (predicted.get(etype) or []) if isinstance(p, str) and p.strip()]

        pairs, unmatched, missed = _greedy_match(preds, affirmed, etype, mode)
        # Las predicciones sobrantes que corresponden a un hallazgo negado son errores de negacion.
        leftover = [preds[i] for i in unmatched]
        neg_pairs, _, _ = _greedy_match(leftover, negated, etype, mode)
        detected_neg, _, _ = _greedy_match(negated_reported, negated, etype, mode) if negated else ([], [], [])

        counts[etype] = {
            'tp': len(pairs),
            'fp': len(unmatched),
            'fn': len(missed),
            'negated_gold': len(negated),
            'negation_errors': len(neg_pairs),
            'negated_detected': len(detected_neg),
        }
    return counts


def _prf(tp: int, fp: int, fn: int) -> Dict[str, Optional[float]]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if recall is None:
        f1 = None  # Sin entidades anotadas de ese tipo: no hay nada que medir.
    elif tp == 0:
        f1 = 0.0  # Habia entidades y no se acerto ninguna (con o sin predicciones).
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        'precision': round(precision, 3) if precision is not None else None,
        'recall': round(recall, 3) if recall is not None else None,
        'f1': round(f1, 3) if f1 is not None else None,
    }


def aggregate(case_counts: Iterable[Dict[str, Dict[str, int]]]) -> Dict[str, Any]:
    """Suma los conteos de varios casos y calcula P/R/F1 por tipo, micro y macro, y la negacion."""
    totals = {etype: {'tp': 0, 'fp': 0, 'fn': 0, 'negated_gold': 0, 'negation_errors': 0, 'negated_detected': 0}
              for etype in ENTITY_TYPES}
    for counts in case_counts:
        for etype, values in counts.items():
            for key, value in values.items():
                totals[etype][key] = totals[etype].get(key, 0) + value

    by_type = {etype: {**values, **_prf(values['tp'], values['fp'], values['fn'])} for etype, values in totals.items()}
    tp = sum(v['tp'] for v in totals.values())
    fp = sum(v['fp'] for v in totals.values())
    fn = sum(v['fn'] for v in totals.values())
    macro_f1 = [v['f1'] for v in by_type.values() if v['f1'] is not None]
    negated_gold = sum(v['negated_gold'] for v in totals.values())
    negation_errors = sum(v['negation_errors'] for v in totals.values())
    negated_detected = sum(v['negated_detected'] for v in totals.values())
    return {
        'by_type': by_type,
        'micro': {'tp': tp, 'fp': fp, 'fn': fn, **_prf(tp, fp, fn)},
        'macro_f1': round(sum(macro_f1) / len(macro_f1), 3) if macro_f1 else None,
        'negation': {
            'negated_gold': negated_gold,
            # Porcentaje de hallazgos negados que el motor NO reporto como presentes.
            'negation_accuracy': round(1 - negation_errors / negated_gold, 3) if negated_gold else None,
            'negation_errors': negation_errors,
            # Porcentaje de hallazgos negados que el motor reporto explicitamente como negados.
            'negated_detection_recall': round(negated_detected / negated_gold, 3) if negated_gold else None,
        },
    }


def bootstrap_ci(items: Sequence[Any], statistic: Callable[[Sequence[Any]], Optional[float]],
                 n_resamples: int = 1000, alpha: float = 0.05, seed: int = 0) -> Optional[Tuple[float, float]]:
    """Intervalo de confianza percentil (1 - alpha) remuestreando los casos con reemplazo."""
    if not items:
        return None
    rng = random.Random(seed)
    values = []
    for _ in range(n_resamples):
        sample = [items[rng.randrange(len(items))] for _ in items]
        value = statistic(sample)
        if value is not None:
            values.append(value)
    if not values:
        return None
    values.sort()
    low = values[int((alpha / 2) * (len(values) - 1))]
    high = values[int((1 - alpha / 2) * (len(values) - 1))]
    return round(low, 3), round(high, 3)


def micro_f1_ci(case_counts: Sequence[Dict[str, Dict[str, int]]], **kwargs) -> Optional[Tuple[float, float]]:
    return bootstrap_ci(case_counts, lambda sample: aggregate(sample)['micro']['f1'], **kwargs)


def annotator_agreement(first: Dict[str, List[Dict[str, Any]]], second: Dict[str, List[Dict[str, Any]]],
                        mode: str = 'relaxed') -> Dict[str, Dict[str, int]]:
    """
    Conteos de acuerdo entre dos anotaciones de un mismo caso. Se usa F1 por pares (Hripcsak y
    Rothschild, 2005): Kappa no esta bien definido para spans porque no hay negativos que contar.
    El segundo anotador hace de prediccion; la negacion se compara en las entidades emparejadas.
    """
    counts = {}
    for etype in ENTITY_TYPES:
        a_items = first.get(etype, [])
        b_items = second.get(etype, [])
        pairs, unmatched, missed = _greedy_match([b['text'] for b in b_items], a_items, etype, mode)
        negation_agree = sum(1 for b_idx, a_idx in pairs if b_items[b_idx]['negated'] == a_items[a_idx]['negated'])
        counts[etype] = {'tp': len(pairs), 'fp': len(unmatched), 'fn': len(missed),
                         'matched': len(pairs), 'negation_agree': negation_agree}
    return counts
