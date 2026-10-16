import json
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from triage import ner_model
from triage.ai_analyzer import analyze_triage_transcript
from triage.clinical_cache import ClinicalQueryCache
from triage.entity_fusion import fuse_entities
from triage.input_pipeline import ClinicalTranscriptCompressor
from transcription.normalizer import concept_mappings

ID2LABEL = {0: 'O', 1: 'B-SINTOMA', 2: 'I-SINTOMA', 3: 'B-ENFERMEDAD', 4: 'I-ENFERMEDAD', 5: 'B-FARMACO', 6: 'I-FARMACO'}

TRANSCRIPT = ("Paciente con dolor punzante en el talón desde ayer, antecedente de gota, toma colchicina, "
              "es alérgico a la penicilina y niega fiebre")


class FakeEngine:
    """Simula RoBERTa: devuelve las menciones indicadas buscandolas en el texto que recibe."""
    source = '/models/ner/fake'

    def __init__(self, mentions):
        self.mentions = mentions
        self.calls = []

    def extract(self, text):
        self.calls.append(text)
        spans = []
        for surface, label, score in self.mentions:
            start = text.find(surface)
            if start >= 0:
                spans.append({'start': start, 'end': start + len(surface), 'label': label, 'score': score,
                              'text': surface})
        return sorted(spans, key=lambda s: s['start'])


MENTIONS = [
    ('dolor punzante en el talón', 'SINTOMA', 0.93),
    ('gota', 'ENFERMEDAD', 0.95),
    ('colchicina', 'FARMACO', 0.88),
    ('penicilina', 'FARMACO', 0.91),
    ('fiebre', 'SINTOMA', 0.97),
    ('ayer', 'SINTOMA', 0.31),  # mencion espuria de baja confianza
]


@pytest.fixture
def fake_engine(monkeypatch):
    engine = FakeEngine(MENTIONS)
    monkeypatch.setattr(ner_model, 'get_engine', lambda: engine)
    monkeypatch.setattr(ner_model, 'engine_label', lambda: 'roberta:fake')
    return engine


class TestDecodeSpans:
    def test_bio_to_spans_with_mean_score(self):
        offsets = [(0, 0), (0, 5), (6, 8), (9, 15), (16, 20), (0, 0)]
        spans = ner_model.decode_spans(offsets, [0, 1, 2, 2, 5, 0], [1, 0.9, 0.7, 0.8, 0.6, 1], ID2LABEL)
        assert spans == [{'start': 0, 'end': 15, 'label': 'SINTOMA', 'score': 0.8},
                         {'start': 16, 'end': 20, 'label': 'FARMACO', 'score': 0.6}]

    def test_inside_tag_of_another_type_opens_a_new_entity(self):
        spans = ner_model.decode_spans([(0, 4), (5, 9)], [1, 4], [0.9, 0.9], ID2LABEL)
        assert [s['label'] for s in spans] == ['SINTOMA', 'ENFERMEDAD']


class TestEngineLoading:
    def setup_method(self):
        ner_model.NEREngine.reset()

    def teardown_method(self):
        ner_model.NEREngine.reset()

    def test_disabled_without_model_path(self, settings):
        settings.NER_MODEL_PATH = ''
        assert ner_model.get_engine() is None
        assert ner_model.get_ner_status()['model_loaded'] is False

    def test_missing_local_folder_fails_once_and_is_not_retried(self, settings, monkeypatch, tmp_path):
        settings.NER_MODEL_PATH = str(tmp_path / 'no_existe')
        calls = []
        original = ner_model.NEREngine.__init__

        def counting_init(self, source):
            calls.append(source)
            original(self, source)

        monkeypatch.setattr(ner_model.NEREngine, '__init__', counting_init)
        assert ner_model.get_engine() is None
        assert ner_model.get_engine() is None
        assert len(calls) == 1


class TestFusion:
    def _fuse(self, llm_entities=None, mentions=MENTIONS):
        text = ClinicalTranscriptCompressor.process(TRANSCRIPT)['cleaned_transcript']
        spans = FakeEngine(mentions).extract(text)
        return fuse_entities(text, spans, concept_mappings(text), llm_entities)

    def test_roles_come_from_context_and_negation(self):
        entities, details = self._fuse()
        assert entities['symptoms'] == ['dolor punzante en el talón']
        assert entities['history'] == ['gota']
        assert entities['medications'] == ['colchicina']
        assert entities['allergies'] == ['penicilina']
        assert entities['negated_findings'] == ['fiebre']
        assert not next(d for d in details if d['text'] == 'ayer')['kept']

    def test_catalog_normalizes_ner_mentions(self):
        text = 'tengo calentura alta'
        spans = FakeEngine([('calentura', 'SINTOMA', 0.9)]).extract(text)
        entities, _ = fuse_entities(text, spans, concept_mappings(text))
        assert entities['symptoms'] == ['fiebre']

    def test_llm_confirms_low_confidence_mentions_and_extras_need_support(self):
        llm = {'symptoms': ['ayer', 'hemorragia digestiva'], 'diagnoses': [], 'medications': [],
               'allergies': [], 'history': ['gota'], 'negated_findings': []}
        entities, details = self._fuse(llm)
        assert next(d for d in details if d['text'] == 'ayer')['kept'] is True
        assert 'hemorragia digestiva' not in entities['symptoms']  # sin apoyo literal en el relato

    def test_negation_overrides_the_llm(self):
        llm = {'symptoms': ['fiebre'], 'negated_findings': []}
        entities, _ = self._fuse(llm)
        assert 'fiebre' not in entities['symptoms']
        assert entities['negated_findings'] == ['fiebre']


@pytest.mark.django_db
class TestAnalysisWithNer:
    def test_rules_engine_uses_ner_entities(self, fake_engine, monkeypatch):
        monkeypatch.setenv('GEMINI_API_KEY', '')
        result = analyze_triage_transcript(TRANSCRIPT, use_cache=False, allow_llm=False)
        assert result['ner_engine'] == 'roberta:fake'
        assert result['entities']['history'] == ['gota']
        assert result['entities']['allergies'] == ['penicilina']
        assert any(d['text'] == 'colchicina' and d['entity'] == 'medications' for d in result['ner_spans'])

    def test_use_ner_false_skips_the_model(self, fake_engine, monkeypatch):
        monkeypatch.setenv('GEMINI_API_KEY', '')
        result = analyze_triage_transcript(TRANSCRIPT, use_cache=False, allow_llm=False, use_ner=False)
        assert result['ner_engine'] is None and fake_engine.calls == []
        assert 'gota' not in result['entities']['history']  # el catalogo no conoce 'gota'

    def test_ner_failure_never_breaks_triage(self, monkeypatch):
        class Broken:
            source = 'x'

            def extract(self, text):
                raise RuntimeError('sin memoria')
        monkeypatch.setattr(ner_model, 'get_engine', lambda: Broken())
        monkeypatch.setenv('GEMINI_API_KEY', '')
        result = analyze_triage_transcript(TRANSCRIPT, use_cache=False, allow_llm=False)
        assert result['ner_engine'] is None and result['triage']['level']

    def test_hybrid_with_gemini(self, fake_engine, mocker):
        llm_output = {
            'patientInfo': {},
            'entities': {'symptoms': ['talalgia', 'hemorragia digestiva'], 'history': ['gota'],
                         'allergies': ['penicilina'], 'vitals': [], 'negated_findings': ['fiebre']},
            'triage': {'level': 4, 'name': 'Consulta Prioritaria', 'attention_time': 'Hasta 120 minutos',
                       'justification': 'Dolor de talón sin alarma'},
        }
        mocker.patch('triage.ai_analyzer._resolve_gemini_api_key', return_value='test-key')
        client_cls = mocker.patch('triage.ai_analyzer.genai.Client')
        generate = client_cls.return_value.models.generate_content
        generate.return_value = SimpleNamespace(text=json.dumps(llm_output), usage_metadata=None)

        result = analyze_triage_transcript(TRANSCRIPT, use_cache=False)

        assert '[ENFERMEDAD] gota' in generate.call_args.kwargs['contents']
        assert result['entities']['symptoms'][0] == 'dolor punzante en el talón'
        assert 'hemorragia digestiva' not in result['entities']['symptoms']
        assert result['entities']['medications'] == ['colchicina']
        assert result['ner_engine'] == 'roberta:fake'

    def test_cache_key_depends_on_the_ner_engine(self):
        plain = ClinicalQueryCache.generate_fingerprint('tos', {})
        assert ClinicalQueryCache.generate_fingerprint('tos', {}, variant='roberta:fake') != plain

    def test_health_check_reports_ner_without_degrading(self, settings):
        settings.NER_MODEL_PATH = ''
        response = APIClient().get('/api/health_check/')
        assert response.json()['ner']['model_loaded'] is False
