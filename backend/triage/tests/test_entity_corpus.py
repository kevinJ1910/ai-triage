import copy
import json
from collections import Counter

import pytest

from triage.entity_corpus import (
    CORPUS_PATH,
    ENTITY_TYPES,
    double_annotation_sample,
    load_entity_corpus,
    validate_entity_corpus,
)
from triage.management.commands.evaluate_benchmark import load_cases


@pytest.fixture(scope='module')
def corpus():
    return load_entity_corpus()


class TestEntityCorpus:
    def test_corpus_is_valid(self, corpus):
        assert len(corpus) >= 100

    def test_split_is_stratified_by_level(self, corpus):
        per_level = Counter((c['reference_level'], c['split']) for c in corpus)
        for level in range(1, 6):
            assert per_level[(level, 'dev')] > per_level[(level, 'test')] > 0

    def test_split_filter(self, corpus):
        dev = load_entity_corpus(split='dev')
        test = load_entity_corpus(split='test')
        assert len(dev) + len(test) == len(corpus)
        assert {c['split'] for c in dev} == {'dev'}

    def test_every_entity_type_is_annotated(self, corpus):
        totals = Counter()
        for case in corpus:
            for etype, items in case['entities'].items():
                totals[etype] += len(items)
        assert all(totals[etype] > 0 for etype in ENTITY_TYPES)

    def test_corpus_includes_negated_findings(self, corpus):
        negated = sum(item['negated'] for c in corpus for items in c['entities'].values() for item in items)
        assert negated >= 30

    def test_corpus_reuses_benchmark_cases_verbatim(self, corpus):
        by_id = {c['id']: c for c in corpus}
        benchmark = json.loads((CORPUS_PATH.parent / 'casos_sinteticos.json').read_text(encoding='utf-8'))
        for case in benchmark:
            assert by_id[case['id']]['transcript'] == case['transcript']
            assert by_id[case['id']]['reference_level'] == case['reference_level']

    def test_corpus_is_accepted_by_evaluate_benchmark(self):
        assert len(load_cases(CORPUS_PATH)) == len(load_entity_corpus())


class TestDoubleAnnotation:
    TEMPLATE = CORPUS_PATH.parent / 'doble_anotacion' / 'plantilla_segundo_anotador.json'

    def test_sample_has_six_cases_per_level(self, corpus):
        by_id = {c['id']: c for c in corpus}
        levels = Counter(by_id[cid]['reference_level'] for cid in double_annotation_sample(corpus))
        assert levels == {level: 6 for level in range(1, 6)}

    def test_template_matches_sample_and_hides_first_annotation(self, corpus):
        template = json.loads(self.TEMPLATE.read_text(encoding='utf-8'))
        assert [c['id'] for c in template] == double_annotation_sample(corpus)
        for case in template:
            assert set(case) == {'id', 'transcript', 'entities'}
            assert all(items == [] for items in case['entities'].values())


class TestCorpusValidation:
    def _case(self, corpus):
        return copy.deepcopy(corpus[0])

    def test_span_must_appear_in_transcript(self, corpus):
        case = self._case(corpus)
        case['entities']['symptoms'].append({'text': 'no existe', 'normalized': 'x', 'negated': False, 'cie10': None})
        assert any('no aparece' in e for e in validate_entity_corpus([case]))

    def test_negated_must_be_boolean(self, corpus):
        case = self._case(corpus)
        case['entities'] = {k: [] for k in ENTITY_TYPES}
        case['entities']['symptoms'] = [{'text': case['transcript'][:5], 'normalized': 'x', 'negated': 'si', 'cie10': None}]
        assert any('negated' in e for e in validate_entity_corpus([case]))

    def test_split_cannot_be_chosen_by_hand(self, corpus):
        cases = copy.deepcopy(corpus)
        cases[0]['split'] = 'dev' if cases[0]['split'] == 'test' else 'test'
        assert any('no coincide con la regla' in e for e in validate_entity_corpus(cases))

    def test_invalid_corpus_raises_on_load(self, tmp_path, corpus):
        broken = copy.deepcopy(corpus)
        broken[0]['estado'] = 'listo'
        path = tmp_path / 'corpus.json'
        path.write_text(json.dumps(broken), encoding='utf-8')
        with pytest.raises(ValueError, match='estado invalido'):
            load_entity_corpus(path)
