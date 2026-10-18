import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from error_analysis import audit_corpus, classify_errors, error_report, main  # noqa: E402
from ner_data import (  # noqa: E402
    Document, Span, augment_documents, cv_summary, span_prf, span_prf_partial, unpunctuated_variant,
)

TEXT = 'Me duele el pecho, mucho. Niega fiebre; toma losartán.'
CORPUS = Path(__file__).resolve().parents[3] / 'backend/triage/benchmark/corpus_entidades.json'


def _texts(doc):
    return [(doc.text[s.start:s.end], s.label) for s in doc.spans]


class TestPartialMetric:
    def test_boundary_error_is_a_hit_only_in_partial_mode(self):
        gold = {'a': [Span(3, 17, 'SINTOMA')]}  # «duele el pecho»
        pred = {'a': [Span(0, 17, 'SINTOMA')]}  # «Me duele el pecho»
        assert span_prf(gold, pred)['micro']['f1'] == 0.0
        assert span_prf_partial(gold, pred)['micro']['f1'] == 1.0

    def test_partial_needs_the_same_label(self):
        report = span_prf_partial({'a': [Span(0, 5, 'SINTOMA')]}, {'a': [Span(0, 5, 'ENFERMEDAD')]})
        assert report['SINTOMA']['fn'] == 1 and report['ENFERMEDAD']['fp'] == 1

    def test_one_long_prediction_does_not_hit_two_gold_spans(self):
        gold = {'a': [Span(0, 5, 'SINTOMA'), Span(8, 14, 'SINTOMA')]}
        report = span_prf_partial(gold, {'a': [Span(0, 14, 'SINTOMA')]})
        assert (report['micro']['tp'], report['micro']['fn'], report['micro']['fp']) == (1, 1, 0)

    def test_cv_summary_mean_and_deviation(self):
        reports = [span_prf({'a': [Span(0, 5, 'SINTOMA')]}, {'a': [Span(0, 5, 'SINTOMA')]}),
                   span_prf({'a': [Span(0, 5, 'SINTOMA')]}, {'a': []})]
        summary = cv_summary(reports)
        assert summary['micro']['f1'] == {'media': 0.5, 'desviacion': 0.5}
        assert summary['FARMACO']['f1'] is None


class TestErrorTypes:
    def test_each_error_type(self):
        gold = [Span(0, 17, 'SINTOMA'), Span(32, 38, 'SINTOMA'), Span(45, 53, 'FARMACO'), Span(26, 31, 'SINTOMA')]
        pred = [Span(3, 17, 'SINTOMA'), Span(32, 38, 'ENFERMEDAD'), Span(45, 53, 'FARMACO'), Span(40, 44, 'FARMACO')]
        kinds = {row['tipo'] for row in classify_errors(TEXT, gold, pred)}
        assert kinds == {'limites', 'etiqueta', 'exacto', 'omitido', 'espurio'}

    def test_report_from_predictions_file(self, tmp_path, capsys):
        predictions = {'a': {'text': TEXT, 'gold': [[0, 17, 'SINTOMA'], [45, 53, 'FARMACO']],
                             'pred': [[3, 17, 'SINTOMA'], [45, 53, 'FARMACO']]}}
        report = error_report(predictions)
        assert report['exacto']['micro']['f1'] == 0.5
        assert report['parcial']['micro']['f1'] == 1.0
        assert report['patrones_de_limites'] == {'predicho_mas_corto': 1}
        path = tmp_path / 'pred.json'
        path.write_text(json.dumps(predictions), encoding='utf-8')
        main(['errores', str(path)])
        assert 'limites' in capsys.readouterr().out


class TestCorpusAudit:
    def test_detects_inconsistent_annotations(self):
        case = lambda cid, text, symptoms, diagnoses=(): {  # noqa: E731
            'id': cid, 'split': 'dev', 'transcript': text,
            'entities': {'symptoms': [{'text': t} for t in symptoms], 'diagnoses': [{'text': t} for t in diagnoses]}}
        cases = [
            case('c1', 'Tiene fiebre y tos.', ['fiebre', 'tos']),
            case('c2', 'Fiebre alta desde ayer.', ['Fiebre alta']),
            case('c3', 'Dice que la fiebre empezó ayer, con tos.', ['tos']),         # fiebre sin anotar
            case('c4', 'Tos, mucha tos.', ['tos']),                                  # tos repetida
            case('c5', 'Asma y tos.', ['tos'], ['Asma']),
            case('c6', 'Le dio asma.', ['asma']),                                    # etiqueta distinta
            case('c7', 'Dolor de pecho y', ['pecho y']),                             # borde
            case('c8', 'Sin texto.', ['inexistente']),
            case('c9', 'Con fiebre.', ['fiebre']),
        ]
        summary = audit_corpus(cases)['resumen']
        details = audit_corpus(cases)['detalle']
        assert summary['repetido_sin_anotar'] == 1
        assert {row['texto'] for row in details['anotado_aqui_no_alla']} == {'fiebre'}
        assert details['etiqueta_inconsistente'][0]['texto'] == 'asma'
        assert summary['borde_sospechoso'] == 1 and summary['no_encontrado'] == 1


class TestAugmentation:
    def test_variants_keep_the_same_mentions(self):
        doc = Document('x', TEXT, [Span(0, 17, 'SINTOMA'), Span(32, 38, 'SINTOMA'), Span(45, 53, 'FARMACO')])
        variants = augment_documents([doc], ('minusculas', 'sin_puntuacion', 'ambas'))
        assert [v.doc_id for v in variants] == ['x', 'x#minusculas', 'x#sin_puntuacion', 'x#ambas']
        assert _texts(variants[3]) == [('me duele el pecho', 'SINTOMA'), ('fiebre', 'SINTOMA'),
                                       ('losartán', 'FARMACO')]
        assert variants[3].text == 'me duele el pecho mucho niega fiebre toma losartán'

    def test_punctuation_inside_a_span_is_removed_and_spaces_collapse(self):
        doc = Document('x', ' «Dolor,  fuerte» y tos. ', [Span(1, 17, 'SINTOMA'), Span(20, 23, 'SINTOMA')])
        variant = unpunctuated_variant(doc)
        assert variant.text == 'Dolor fuerte y tos'
        assert _texts(variant) == [('Dolor fuerte', 'SINTOMA'), ('tos', 'SINTOMA')]


class TestSnapToWords:
    def test_partial_words_are_completed_and_merged(self):
        from ner_data import snap_to_words
        text = 'Está vomitando y embarazada'
        spans = [Span(7, 14, 'SINTOMA'), Span(17, 21, 'ENFERMEDAD'), Span(22, 27, 'ENFERMEDAD')]
        assert snap_to_words(text, spans) == [Span(5, 14, 'SINTOMA'), Span(17, 27, 'ENFERMEDAD')]

    def test_whole_word_spans_are_unchanged(self):
        from ner_data import snap_to_words
        spans = [Span(0, 17, 'SINTOMA'), Span(45, 53, 'FARMACO')]
        assert snap_to_words(TEXT, spans) == spans


class TestPostprocessing:
    def test_function_word_spans_are_dropped(self):
        from ner_data import clean_predictions
        text = 'Tiene una herida y al moverse le duele'
        spans = [Span(6, 9, 'ENFERMEDAD'), Span(10, 16, 'ENFERMEDAD'), Span(19, 21, 'FARMACO'),
                 Span(30, 38, 'SINTOMA')]
        assert clean_predictions(text, spans) == [Span(10, 16, 'ENFERMEDAD'), Span(30, 38, 'SINTOMA')]

    def test_gold_spans_never_consist_only_of_function_words(self):
        from ner_data import corpus_to_documents, drop_function_word_spans
        for doc in corpus_to_documents(CORPUS):
            assert drop_function_word_spans(doc.text, doc.spans) == doc.spans, doc.doc_id

    def test_non_drug_allergens_are_not_farmaco(self):
        from ner_data import corpus_to_documents
        n015 = next(d for d in corpus_to_documents(CORPUS) if d.doc_id == 'N015')
        assert 'camarones' not in [n015.text[s.start:s.end] for s in n015.spans]
