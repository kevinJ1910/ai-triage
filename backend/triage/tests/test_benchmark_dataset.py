import json
from collections import Counter
from pathlib import Path

from triage.clinical_protocol import evaluate_christus_sinergia_triage
from triage.management.commands.evaluate_benchmark import load_cases
from triage.metrics import reference_agreement

DATASET = Path(__file__).resolve().parents[1] / 'benchmark' / 'casos_sinteticos.json'
TIPOS = {'tipico', 'coloquial', 'negacion', 'signos_vitales'}

# Linea base del motor de reglas sobre el conjunto sintetico. Si una mejora la supera,
# actualizar estos valores (y la documentacion); si un cambio la empeora, el test falla.
MIN_EXACT_AGREEMENT = 46.2
MIN_CRITICAL_SENSITIVITY = 28.6


class TestBenchmarkDataset:
    def test_dataset_is_valid_for_the_benchmark_command(self):
        cases = load_cases(DATASET)
        assert len(cases) == 65
        assert len({c['id'] for c in cases}) == len(cases)

    def test_every_level_is_represented(self):
        levels = Counter(c['reference_level'] for c in load_cases(DATASET))
        assert set(levels) == {1, 2, 3, 4, 5}
        assert min(levels.values()) >= 10

    def test_cases_document_type_and_protocol_criterion(self):
        raw = json.loads(DATASET.read_text(encoding='utf-8'))
        for case in raw:
            assert case['tipo'] in TIPOS, case['id']
            assert case['criterio'].strip(), case['id']


class TestRulesEngineBaseline:
    def _summary(self):
        cases = load_cases(DATASET)
        pairs = [(evaluate_christus_sinergia_triage(c['transcript'])['level'], c['reference_level']) for c in cases]
        return reference_agreement(pairs)

    def test_rules_engine_does_not_regress_on_benchmark(self):
        summary = self._summary()
        assert summary['exact_agreement'] >= MIN_EXACT_AGREEMENT
        assert summary['critical_sensitivity'] >= MIN_CRITICAL_SENSITIVITY

    def test_no_non_urgent_case_is_escalated_to_reanimation(self):
        for case in load_cases(DATASET):
            if case['reference_level'] >= 4:
                assert evaluate_christus_sinergia_triage(case['transcript'])['level'] != 1, case['id']
