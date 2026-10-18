"""
Metricas de concordancia IA vs medico para la escala ordinal de triaje (1 = mas urgente, 5 = menos urgente).
Funciones puras sobre pares (ai_level, final_level) para poder probarlas sin base de datos.
"""
from typing import Dict, Iterable, List, Optional, Tuple

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
