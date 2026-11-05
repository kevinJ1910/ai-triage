import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from revision_corpus import main, render_markdown, review_candidates  # noqa: E402


def case(cid, transcript, split='dev', **entities):
    base = {etype: [] for etype in ('symptoms', 'diagnoses', 'medications', 'allergies', 'vitals', 'history')}
    for etype, items in entities.items():
        base[etype] = [{'text': t, 'normalized': t, 'negated': neg, 'cie10': None} for t, neg in items]
    return {'id': cid, 'split': split, 'transcript': transcript, 'entities': base}


def proposals(rows, rule):
    return [(r['caso'], r['actual'], r['propuesta']) for r in rows if r['regla'] == rule]


class TestSpanRules:
    def test_rules_combine_into_one_proposal(self):
        rows = review_candidates([case('c1', 'Sigue muy dormido desde ayer.', symptoms=[('Sigue muy dormido', False)])])
        assert proposals(rows, 'L3') == [('c1', 'Sigue muy dormido', 'dormido')]
        assert len(rows) == 1

    def test_each_span_rule(self):
        rows = review_candidates([
            case('c1', 'Dolor de cabeza muy fuerte, un lunar nuevo.',
                 symptoms=[('Dolor de cabeza muy fuerte', False)], diagnoses=[('un lunar', False)]),
            case('c2', 'Me corté la muñeca con un vidrio y vomitó cinco veces.',
                 diagnoses=[('Me corté la muñeca con un vidrio', False)], symptoms=[('vomitó cinco veces', False)]),
        ])
        assert proposals(rows, 'L1') == [('c1', 'Dolor de cabeza muy fuerte', 'Dolor de cabeza')]
        assert proposals(rows, 'L2') == [('c1', 'un lunar', 'lunar')]
        assert proposals(rows, 'L4') == [('c2', 'Me corté la muñeca con un vidrio', 'Me corté la muñeca')]
        assert proposals(rows, 'L5') == [('c2', 'vomitó cinco veces', 'vomitó')]

    def test_exceptions_from_the_guide_are_not_flagged(self):
        rows = review_candidates([case(
            'c1', 'Se atoró con un pedazo de comida, respira muy de vez en cuando, tiene que pujar y tomó un poco de pastillas.',
            diagnoses=[('Se atoró con un pedazo de comida', False), ('un poco de pastillas', False)],
            symptoms=[('respira muy de vez en cuando', False), ('tiene que pujar', False)])])
        assert not rows


class TestTranscriptRules:
    def test_missing_trauma_gestation_and_normal_findings(self):
        rows = review_candidates([
            case('c1', 'Se cayó de la bicicleta, está consciente.', split='test', diagnoses=[], symptoms=[]),
            case('c2', 'Gestante de 34 semanas con dolor.', symptoms=[('dolor', False)]),
            case('c3', 'Después de una caída, saturación normal.', diagnoses=[('caída', False)]),
        ])
        assert ('c1', '', 'añadir diagnoses: «Se cayó de la bicicleta»') in proposals(rows, 'L8')
        assert ('c1', '', 'añadir symptoms: «consciente» (negated: true)') in proposals(rows, 'L7')
        assert proposals(rows, 'L6') == [('c2', '', 'añadir diagnoses: «Gestante de 34 semanas»')]
        assert not [r for r in rows if r['caso'] == 'c3' and r['regla'] == 'L8']  # la caída ya está anotada

    def test_label_rules(self):
        rows = review_candidates([case('c1', 'Signos de deshidratación y la muñeca me quedó chueca.',
                                       symptoms=[('Signos de deshidratación', False)],
                                       diagnoses=[('la muñeca me quedó chueca', False)])])
        assert [r['actual'] for r in rows if r['regla'] == 'L9'] == ['la muñeca me quedó chueca']


def test_markdown_and_cli(tmp_path):
    import json
    cases = [case('c1', 'Está hinchada.', symptoms=[('Está hinchada', False)])]
    text = render_markdown(review_candidates(cases), 'corpus.json')
    assert '| L3 · Verbo de marco inicial | 1 |' in text and '`Está hinchada` | hinchada' in text
    corpus = tmp_path / 'corpus.json'
    corpus.write_text(json.dumps(cases), encoding='utf-8')
    main(['--corpus', str(corpus), '--output', str(tmp_path / 'out.md')])
    assert (tmp_path / 'out.md').read_text(encoding='utf-8').startswith('# Casos a revisar')
