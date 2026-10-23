"""
Metricas de concordancia IA vs medico para la escala ordinal de triaje (1 = mas urgente, 5 = menos urgente).
Funciones puras sobre pares (ai_level, final_level) para poder probarlas sin base de datos.
"""
import random
import statistics
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

LEVELS = (1, 2, 3, 4, 5)
CRITICAL_LEVELS = (1, 2)
# Politicas para combinar el nivel del LLM con el del motor de reglas:
#   llm          el nivel del LLM tal cual.
#   min_critico  si las reglas detectan un nivel 1-2, prevalece el mas urgente de los dos (red de seguridad).
COMBINE_POLICIES = ('llm', 'min_critico')


def combine_levels(llm_level: int, rule_level: Optional[int], policy: str = 'llm') -> int:
    """Nivel final segun la politica de combinacion (1 = mas urgente)."""
    if policy not in COMBINE_POLICIES:
        raise ValueError(f"politica desconocida: {policy}")
    if policy == 'min_critico' and rule_level in CRITICAL_LEVELS:
        return min(llm_level, rule_level)
    return llm_level


def confusion_matrix(pairs: Iterable[Tuple[int, int]]) -> List[List[int]]:
    """Matriz 5x5: filas = nivel IA, columnas = nivel final del medico."""
    matrix = [[0] * len(LEVELS) for _ in LEVELS]
    for ai, final in pairs:
        if ai in LEVELS and final in LEVELS:
            matrix[ai - 1][final - 1] += 1
    return matrix


def confusion_matrix_from_counts(rows: Iterable[Tuple[int, int, int]]) -> List[List[int]]:
    """Matriz 5x5 a partir de conteos agregados (nivel evaluado, nivel referencia, n), p. ej. un GROUP BY."""
    matrix = [[0] * len(LEVELS) for _ in LEVELS]
    for ai, final, count in rows:
        if ai in LEVELS and final in LEVELS:
            matrix[ai - 1][final - 1] += count
    return matrix


def cohen_kappa(matrix: List[List[int]], weights: str = 'quadratic') -> Optional[float]:
    """
    Kappa de Cohen sobre la matriz de confusion.
    weights: 'quadratic' (recomendado para escalas ordinales), 'linear' o 'none'.
    Devuelve None si no hay datos.
    """
    n = len(matrix)
    total = sum(sum(row) for row in matrix)
    if total == 0:
        return None

    def w(i: int, j: int) -> float:
        if weights == 'none':
            return 0.0 if i == j else 1.0
        dist = abs(i - j) / (n - 1)
        return dist ** 2 if weights == 'quadratic' else dist

    row_tot = [sum(matrix[i]) for i in range(n)]
    col_tot = [sum(matrix[i][j] for i in range(n)) for j in range(n)]

    observed = sum(w(i, j) * matrix[i][j] for i in range(n) for j in range(n)) / total
    expected = sum(w(i, j) * row_tot[i] * col_tot[j] for i in range(n) for j in range(n)) / (total * total)

    if expected == 0:
        # Todas las observaciones en una sola categoria en ambos evaluadores.
        return 1.0 if observed == 0 else 0.0
    return round(max(-1.0, min(1.0, 1.0 - observed / expected)), 3)


def interpret_kappa(kappa: Optional[float]) -> str:
    """Escala de Landis y Koch."""
    if kappa is None:
        return "Sin datos suficientes"
    if kappa >= 0.81:
        return "Concordancia casi perfecta"
    if kappa >= 0.61:
        return "Concordancia sustancial"
    if kappa >= 0.41:
        return "Concordancia moderada"
    if kappa >= 0.21:
        return "Concordancia aceptable"
    return "Concordancia debil"


def reference_agreement(pairs: List[Tuple[int, int]]) -> Dict[str, Optional[float]]:
    """
    Concordancia de un evaluador (IA o medico tratante) contra el nivel de referencia ciego.
    pairs: (nivel_evaluado, nivel_referencia). Sin pares devuelve metricas null.
    """
    return reference_agreement_from_matrix(confusion_matrix(pairs))


def reference_agreement_from_matrix(matrix: List[List[int]]) -> Dict[str, Optional[float]]:
    """Igual que reference_agreement, sobre la matriz (filas = evaluado, columnas = referencia)."""
    total = sum(sum(row) for row in matrix)
    exact = sum(matrix[i][i] for i in range(len(matrix)))
    kappa = cohen_kappa(matrix, weights='quadratic')
    return {
        "n": total,
        "exact_agreement": round(exact / total * 100, 1) if total else None,
        "cohen_kappa": kappa,
        "kappa_interpretation": interpret_kappa(kappa),
        **triage_safety_metrics_from_matrix(matrix),
        "confusion_matrix": matrix,
    }


def triage_safety_metrics(pairs: List[Tuple[int, int]]) -> Dict[str, Optional[float]]:
    """
    Tasas de error de triaje tomando el nivel final del medico como referencia:
    - undertriage_rate: la IA asigno MENOR urgencia que el medico (ai > final). Es el error peligroso.
    - overtriage_rate: la IA asigno MAYOR urgencia que el medico (ai < final).
    - critical_sensitivity: de los casos que el medico clasifico como nivel 1-2,
      porcentaje que la IA tambien clasifico como 1-2.
    - critical_undertriage_count: casos criticos (final 1-2) que la IA envio a nivel 3-5.
    """
    return triage_safety_metrics_from_matrix(confusion_matrix(pairs))


def triage_safety_metrics_from_matrix(matrix: List[List[int]]) -> Dict[str, Optional[float]]:
    """Igual que triage_safety_metrics, sobre la matriz (filas = IA, columnas = referencia)."""
    total = sum(sum(row) for row in matrix)
    if total == 0:
        return {
            "undertriage_rate": None,
            "overtriage_rate": None,
            "critical_cases": 0,
            "critical_sensitivity": None,
            "critical_undertriage_count": 0,
        }

    n = len(matrix)
    critical_idx = [lvl - 1 for lvl in CRITICAL_LEVELS]
    under = sum(matrix[i][j] for i in range(n) for j in range(n) if i > j)
    over = sum(matrix[i][j] for i in range(n) for j in range(n) if i < j)
    critical = sum(matrix[i][j] for i in range(n) for j in critical_idx)
    detected = sum(matrix[i][j] for i in critical_idx for j in critical_idx)

    return {
        "undertriage_rate": round(under / total * 100, 1),
        "overtriage_rate": round(over / total * 100, 1),
        "critical_cases": critical,
        "critical_sensitivity": round(detected / critical * 100, 1) if critical else None,
        "critical_undertriage_count": critical - detected,
    }


# --- Intervalos de confianza por bootstrap y resumenes de evaluacion ---

CI_METRICS = ('exact_agreement', 'cohen_kappa', 'critical_sensitivity', 'undertriage_rate', 'overtriage_rate')


def _percentile_ci(values: List[float], alpha: float) -> Optional[Tuple[float, float]]:
    if not values:
        return None
    values = sorted(values)
    low = values[int((alpha / 2) * (len(values) - 1))]
    high = values[int((1 - alpha / 2) * (len(values) - 1))]
    return round(low, 3), round(high, 3)


def bootstrap_many(items: Sequence[Any], statistic: Callable[[Sequence[Any]], Dict[str, Optional[float]]],
                   keys: Sequence[str], n_resamples: int = 1000, alpha: float = 0.05,
                   seed: int = 0) -> Dict[str, Optional[Tuple[float, float]]]:
    """
    IC percentil (1 - alpha) de varias estadisticas a la vez, remuestreando los casos con reemplazo.
    Con la misma semilla usa los mismos remuestreos que bootstrap_ci, asi que sus IC coinciden.
    """
    if not items:
        return {key: None for key in keys}
    rng = random.Random(seed)
    collected: Dict[str, List[float]] = {key: [] for key in keys}
    for _ in range(n_resamples):
        sample = [items[rng.randrange(len(items))] for _ in items]
        values = statistic(sample)
        for key in keys:
            if values.get(key) is not None:
                collected[key].append(values[key])
    return {key: _percentile_ci(collected[key], alpha) for key in keys}


def bootstrap_ci(items: Sequence[Any], statistic: Callable[[Sequence[Any]], Optional[float]],
                 n_resamples: int = 1000, alpha: float = 0.05, seed: int = 0) -> Optional[Tuple[float, float]]:
    """Intervalo de confianza percentil (1 - alpha) remuestreando los casos con reemplazo."""
    return bootstrap_many(items, lambda sample: {'v': statistic(sample)}, ('v',), n_resamples, alpha, seed)['v']


def triage_summary(pairs: List[Tuple[int, int]], n_resamples: int = 1000) -> Dict[str, Any]:
    """
    Concordancia contra la referencia (reference_agreement) con IC95 bootstrap de la exactitud, el Kappa
    ponderado cuadratico, la sensibilidad en niveles 1-2 y las tasas de infratriaje y sobretriaje.
    """
    summary = reference_agreement(pairs)
    cis = bootstrap_many(pairs, lambda sample: reference_agreement(list(sample)), CI_METRICS, n_resamples)
    for key in CI_METRICS:
        summary[f'{key}_ci95'] = cis[key]
    return summary


def triage_breakdown(results: Sequence[Dict[str, Any]], key: str, min_n_for_ci: int = 20) -> Dict[str, Any]:
    """Metricas de triaje por grupo (tipo, lote, sexo...). Con menos de min_n_for_ci casos no se dan IC."""
    groups: Dict[str, List[Tuple[int, int]]] = {}
    for r in results:
        groups.setdefault(str(r.get(key)), []).append((r['predicted_level'], r['reference_level']))
    out = {}
    for group in sorted(groups):
        pairs = groups[group]
        full = triage_summary(pairs) if len(pairs) >= min_n_for_ci else reference_agreement(pairs)
        out[group] = {k: full.get(k) for k in ('n', 'exact_agreement', 'cohen_kappa', 'critical_cases',
                                               'critical_sensitivity', 'undertriage_rate', 'overtriage_rate')}
        if len(pairs) >= min_n_for_ci:
            out[group].update({f'{k}_ci95': full[f'{k}_ci95'] for k in CI_METRICS})
    return out


def critical_undertriage(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Casos criticos (referencia 1-2) clasificados como 3-5, ordenados por la distancia del error."""
    misses = []
    for r in results:
        if r['reference_level'] in CRITICAL_LEVELS and r['predicted_level'] not in CRITICAL_LEVELS:
            misses.append({
                'id': r['id'], 'tipo': r.get('tipo'), 'lote': r.get('lote'),
                'reference_level': r['reference_level'], 'predicted_level': r['predicted_level'],
                'llm_level': r.get('llm_level'), 'rule_level': r.get('rule_level'),
                'distance': r['predicted_level'] - r['reference_level'],
                'justification': r.get('justification'),
            })
    return sorted(misses, key=lambda m: (-m['distance'], m['id']))


def paired_bootstrap_diff(triples: Sequence[Tuple[int, int, int]], metric: str, n_resamples: int = 1000,
                          seed: int = 0) -> Dict[str, Any]:
    """
    Diferencia de una metrica de reference_agreement entre dos motores evaluados sobre los mismos casos.
    triples: (nivel_motor_a, nivel_motor_b, nivel_referencia). Devuelve a - b con su IC95 pareado.
    """
    def stat(sample):
        a = reference_agreement([(t[0], t[2]) for t in sample])[metric]
        b = reference_agreement([(t[1], t[2]) for t in sample])[metric]
        return {'diff': None if a is None or b is None else a - b}

    point = stat(list(triples))['diff']
    return {
        'metric': metric,
        'n': len(triples),
        'diff': round(point, 3) if point is not None else None,
        'ci95': bootstrap_many(list(triples), stat, ('diff',), n_resamples, seed=seed)['diff'],
    }


def mean_ci(values: Sequence[float], n_resamples: int = 1000, seed: int = 0) -> Dict[str, Any]:
    """Media con IC95 bootstrap (p. ej. valoraciones Likert)."""
    values = [v for v in values if v is not None]
    if not values:
        return {'n': 0, 'mean': None, 'ci95': None}
    return {
        'n': len(values),
        'mean': round(statistics.mean(values), 2),
        'ci95': bootstrap_ci(values, lambda sample: statistics.mean(sample), n_resamples, seed=seed),
    }
