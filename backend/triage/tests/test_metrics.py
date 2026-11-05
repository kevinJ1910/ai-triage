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


class TestEvaluationSummaries:
    PAIRS = [(1, 1), (2, 1), (2, 2), (3, 3), (4, 3), (4, 4), (5, 5), (5, 4), (3, 2), (1, 1)] * 3

    def test_triage_summary_has_cis_that_contain_the_point_estimate(self):
        from triage.metrics import CI_METRICS, triage_summary
        summary = triage_summary(self.PAIRS)
        for key in CI_METRICS:
            low, high = summary[f'{key}_ci95']
            assert low <= summary[key] <= high

    def test_triage_summary_matches_legacy_kappa_ci(self):
        from triage.metrics import bootstrap_ci, triage_summary
        legacy = bootstrap_ci(self.PAIRS, lambda sample: reference_agreement(list(sample))['cohen_kappa'])
        assert triage_summary(self.PAIRS)['cohen_kappa_ci95'] == legacy

    def test_empty_inputs(self):
        from triage.metrics import mean_ci, triage_summary
        assert triage_summary([])['cohen_kappa_ci95'] is None
        assert mean_ci([]) == {'n': 0, 'mean': None, 'ci95': None}

    def test_combine_levels(self):
        import pytest
        from triage.metrics import combine_levels
        assert combine_levels(4, 1, 'min_critico') == 1
        assert combine_levels(1, 2, 'min_critico') == 1
        assert combine_levels(4, 3, 'min_critico') == 4   # reglas no criticas: manda el LLM
        assert combine_levels(4, None, 'min_critico') == 4
        assert combine_levels(4, 1, 'llm') == 4
        with pytest.raises(ValueError):
            combine_levels(4, 1, 'otra')

    def test_breakdown_omits_cis_for_small_groups(self):
        from triage.metrics import triage_breakdown
        results = [{'predicted_level': p, 'reference_level': r, 'tipo': 'coloquial' if i < 25 else 'tipico'}
                   for i, (p, r) in enumerate(self.PAIRS)]
        out = triage_breakdown(results, 'tipo')
        assert out['coloquial']['n'] == 25 and 'cohen_kappa_ci95' in out['coloquial']
        assert out['tipico']['n'] == 5 and 'cohen_kappa_ci95' not in out['tipico']

    def test_critical_undertriage_sorted_by_distance(self):
        from triage.metrics import critical_undertriage
        results = [{'id': 'a', 'reference_level': 1, 'predicted_level': 3},
                   {'id': 'b', 'reference_level': 2, 'predicted_level': 5},
                   {'id': 'c', 'reference_level': 2, 'predicted_level': 2},
                   {'id': 'd', 'reference_level': 4, 'predicted_level': 5}]
        assert [m['id'] for m in critical_undertriage(results)] == ['b', 'a']

    def test_paired_bootstrap_diff(self):
        from triage.metrics import paired_bootstrap_diff
        triples = [(r, 5, r) for _, r in self.PAIRS]  # a acierta siempre, b siempre dice 5
        out = paired_bootstrap_diff(triples, 'exact_agreement')
        assert out['diff'] > 0 and out['ci95'][0] > 0
        same = paired_bootstrap_diff([(p, p, r) for p, r in self.PAIRS], 'cohen_kappa')
        assert same['diff'] == 0 and same['ci95'] == (0, 0)

    def test_mean_ci(self):
        from triage.metrics import mean_ci
        out = mean_ci([4, 5, 3, 4, 4])
        assert out['n'] == 5 and out['mean'] == 4.0
        assert out['ci95'][0] <= 4.0 <= out['ci95'][1]
