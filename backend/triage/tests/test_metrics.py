from collections import Counter

from triage.metrics import (
    confusion_matrix, confusion_matrix_from_counts, cohen_kappa, interpret_kappa,
    triage_safety_metrics, triage_safety_metrics_from_matrix,
    reference_agreement, reference_agreement_from_matrix,
)


class TestConcordanceMetrics:
    def test_confusion_matrix_rows_are_ai_columns_are_physician(self):
        matrix = confusion_matrix([(2, 1), (2, 1), (3, 3)])
        assert matrix[1][0] == 2
        assert matrix[2][2] == 1
        assert sum(sum(r) for r in matrix) == 3

    def test_kappa_none_without_data(self):
        assert cohen_kappa(confusion_matrix([])) is None
        assert interpret_kappa(None) == "Sin datos suficientes"

    def test_perfect_agreement(self):
        matrix = confusion_matrix([(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])
        assert cohen_kappa(matrix, 'quadratic') == 1.0
        assert cohen_kappa(matrix, 'none') == 1.0

    def test_weighted_kappa_penalizes_distant_disagreement_more(self):
        base = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)] * 4
        near = confusion_matrix(base + [(2, 3), (3, 4)])
        far = confusion_matrix(base + [(1, 5), (5, 1)])
        # Sin ponderar ambos casos tienen el mismo numero de desacuerdos
        assert cohen_kappa(near, 'none') == cohen_kappa(far, 'none')
        # Ponderado cuadratico: el desacuerdo 1 vs 5 es mucho mas grave
        assert cohen_kappa(near, 'quadratic') > cohen_kappa(far, 'quadratic')

    def test_known_quadratic_kappa_value(self):
        # Referencia calculada a mano: O=[[1,1],[0,2]] en escala de 5 niveles (solo niveles 1 y 2)
        matrix = confusion_matrix([(1, 1), (1, 2), (2, 2), (2, 2)])
        # w(0,1) = (1/4)^2 = 0.0625; observado = 0.0625*1/4; esperado = 0.0625*(2*1 + 2*3)/16
        expected = round(1 - (0.0625 / 4) / (0.0625 * 8 / 16), 3)
        assert cohen_kappa(matrix, 'quadratic') == expected


class TestTriageSafetyMetrics:
    def test_empty(self):
        res = triage_safety_metrics([])
        assert res["undertriage_rate"] is None
        assert res["critical_sensitivity"] is None

    def test_undertriage_and_critical_sensitivity(self):
        pairs = [
            (1, 1),  # critico detectado
            (3, 2),  # critico infratriado por la IA
            (2, 3),  # sobretriaje
            (4, 4),
        ]
        res = triage_safety_metrics(pairs)
        assert res["undertriage_rate"] == 25.0
        assert res["overtriage_rate"] == 25.0
        assert res["critical_cases"] == 2
        assert res["critical_sensitivity"] == 50.0
        assert res["critical_undertriage_count"] == 1

    def test_reference_agreement_null_without_pairs(self):
        result = reference_agreement([])
        assert result["n"] == 0
        assert result["exact_agreement"] is None
        assert result["cohen_kappa"] is None

    def test_reference_agreement_counts_undertriage_against_reference(self):
        # (evaluado, referencia): un caso critico enviado a nivel 3 es infratriaje
        result = reference_agreement([(1, 1), (3, 2), (4, 4), (4, 5)])
        assert result["n"] == 4
        assert result["exact_agreement"] == 50.0
        assert result["undertriage_rate"] == 25.0
        assert result["overtriage_rate"] == 25.0
        assert result["critical_cases"] == 2
        assert result["critical_sensitivity"] == 50.0


class TestMatrixBasedMetrics:
    """Las variantes sobre la matriz (usadas con GROUP BY en la vista) equivalen a las de pares."""
    PAIRS = [(1, 1), (2, 1), (3, 2), (2, 2), (4, 4), (5, 3), (3, 3), (1, 2), (4, 5)]

    def test_matrix_from_counts_equals_matrix_from_pairs(self):
        counts = [(ai, final, n) for (ai, final), n in Counter(self.PAIRS).items()]
        assert confusion_matrix_from_counts(counts) == confusion_matrix(self.PAIRS)

    def test_counts_outside_scale_are_ignored(self):
        matrix = confusion_matrix_from_counts([(0, 3, 4), (3, 6, 2), (2, 2, 5)])
        assert sum(map(sum, matrix)) == 5

    def test_safety_metrics_match(self):
        matrix = confusion_matrix(self.PAIRS)
        assert triage_safety_metrics_from_matrix(matrix) == triage_safety_metrics(self.PAIRS)

    def test_reference_agreement_matches(self):
        matrix = confusion_matrix(self.PAIRS)
        assert reference_agreement_from_matrix(matrix) == reference_agreement(self.PAIRS)

    def test_empty_matrix(self):
        empty = confusion_matrix([])
        assert triage_safety_metrics_from_matrix(empty)["undertriage_rate"] is None
        assert reference_agreement_from_matrix(empty)["exact_agreement"] is None
