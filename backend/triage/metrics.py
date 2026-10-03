"""
Metricas de concordancia IA vs medico para la escala ordinal de triaje (1 = mas urgente, 5 = menos urgente).
Funciones puras sobre pares (ai_level, final_level) para poder probarlas sin base de datos.
"""
from typing import Dict, Iterable, List, Optional, Tuple

LEVELS = (1, 2, 3, 4, 5)
CRITICAL_LEVELS = (1, 2)


def confusion_matrix(pairs: Iterable[Tuple[int, int]]) -> List[List[int]]:
    """Matriz 5x5: filas = nivel IA, columnas = nivel final del medico."""
    matrix = [[0] * len(LEVELS) for _ in LEVELS]
    for ai, final in pairs:
        if ai in LEVELS and final in LEVELS:
            matrix[ai - 1][final - 1] += 1
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


def triage_safety_metrics(pairs: List[Tuple[int, int]]) -> Dict[str, Optional[float]]:
    """
    Tasas de error de triaje tomando el nivel final del medico como referencia:
    - undertriage_rate: la IA asigno MENOR urgencia que el medico (ai > final). Es el error peligroso.
    - overtriage_rate: la IA asigno MAYOR urgencia que el medico (ai < final).
    - critical_sensitivity: de los casos que el medico clasifico como nivel 1-2,
      porcentaje que la IA tambien clasifico como 1-2.
    - critical_undertriage_count: casos criticos (final 1-2) que la IA envio a nivel 3-5.
    """
    total = len(pairs)
    if total == 0:
        return {
            "undertriage_rate": None,
            "overtriage_rate": None,
            "critical_cases": 0,
            "critical_sensitivity": None,
            "critical_undertriage_count": 0,
        }

    under = sum(1 for ai, final in pairs if ai > final)
    over = sum(1 for ai, final in pairs if ai < final)
    critical = [(ai, final) for ai, final in pairs if final in CRITICAL_LEVELS]
    detected = sum(1 for ai, _ in critical if ai in CRITICAL_LEVELS)

    return {
        "undertriage_rate": round(under / total * 100, 1),
        "overtriage_rate": round(over / total * 100, 1),
        "critical_cases": len(critical),
        "critical_sensitivity": round(detected / len(critical) * 100, 1) if critical else None,
        "critical_undertriage_count": len(critical) - detected,
    }
