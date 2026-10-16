import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ner_data import (  # noqa: E402
    split_language,
    IGNORE_INDEX, LABEL2ID, Span, bio_labels, corpus_to_documents, kfold, load_brat_corpus, load_tsv_corpus,
    merge_corpora, pick_text_dir, read_brat_ann, resolve_overlaps, span_prf, spans_from_bio,
)

CORPUS = Path(__file__).resolve().parents[3] / 'backend/triage/benchmark/corpus_entidades.json'
TEXT = 'Paciente con fiebre y diabetes, toma metformina.'


@pytest.fixture
def public_corpora(tmp_path):
    """Un mismo caso clinico anotado por los tres corpus, cada uno con su formato y su unico tipo."""
    for name in ('sym', 'dis', 'pharma'):
        (tmp_path / name / 'txt').mkdir(parents=True)
        (tmp_path / name / 'txt' / 'caso1.txt').write_text(TEXT, encoding='utf-8')
    (tmp_path / 'sym' / 'train.tsv').write_text(
        'filename\tann_id\tlabel\tstart_span\tend_span\ttext\ncaso1\tT1\tSINTOMA\t13\t19\tfiebre\n', encoding='utf-8')
    (tmp_path / 'dis' / 'train.tsv').write_text(
        'filename\tmark\tlabel\toff0\toff1\tspan\ncaso1\tT1\tENFERMEDAD\t22\t30\tdiabetes\n', encoding='utf-8')
    (tmp_path / 'pharma' / 'txt' / 'caso1.ann').write_text(
        'T1\tNORMALIZABLES 37 47\tmetformina\nT2\tPROTEINAS 0 8\tPaciente\n#1\tAnnotatorNotes T1\tnota\n',
        encoding='utf-8')
    stats = Counter()
    return [
        load_tsv_corpus(tmp_path / 'sym' / 'train.tsv', tmp_path / 'sym' / 'txt', 'symptemist', stats),
        load_tsv_corpus(tmp_path / 'dis' / 'train.tsv', tmp_path / 'dis' / 'txt', 'distemist', stats),
        load_brat_corpus(tmp_path / 'pharma' / 'txt', 'pharmaconer', stats),
    ], stats


class TestPublicCorpora:
    def test_merges_the_three_annotation_layers_of_the_same_document(self, public_corpora):
        corpora, stats = public_corpora
        docs = merge_corpora(corpora, stats=stats)
        assert [(s.start, s.end, s.label) for s in docs[0].spans] == [
            (13, 19, 'SINTOMA'), (22, 30, 'ENFERMEDAD'), (37, 47, 'FARMACO')]
        assert stats['pharmaconer:descartada:PROTEINAS'] == 1

    def test_partial_documents_are_dropped_by_default(self, public_corpora, tmp_path):
        corpora, _ = public_corpora
        (tmp_path / 'sym' / 'txt' / 'caso2.txt').write_text('solo sintomas', encoding='utf-8')
        sym = load_tsv_corpus(tmp_path / 'sym' / 'train.tsv', tmp_path / 'sym' / 'txt', 'symptemist')
        stats = Counter()
        docs = merge_corpora([sym, *corpora[1:]], stats=stats)
        assert [d.doc_id for d in docs] == ['caso1']
        assert stats['documento_parcial_descartado'] == 1
        assert len(merge_corpora([sym, *corpora[1:]], require_all=False)) == 2

    def test_reanchors_spans_when_a_corpus_has_a_different_text_version(self, public_corpora, tmp_path):
        corpora, _ = public_corpora
        (tmp_path / 'dis' / 'txt' / 'caso1.txt').write_text('  ' + TEXT, encoding='utf-8')
        (tmp_path / 'dis' / 'train.tsv').write_text(
            'filename\tmark\tlabel\toff0\toff1\tspan\ncaso1\tT1\tENFERMEDAD\t24\t32\tdiabetes\n', encoding='utf-8')
        dis = load_tsv_corpus(tmp_path / 'dis' / 'train.tsv', tmp_path / 'dis' / 'txt', 'distemist')
        docs = merge_corpora([corpora[0], dis, corpora[2]])
        assert Span(22, 30, 'ENFERMEDAD') in docs[0].spans

    def test_discontinuous_brat_spans_are_skipped(self, tmp_path):
        ann = tmp_path / 'x.ann'
        ann.write_text('T1\tNORMALIZABLES 0 5;9 12\tdolor torax\nT2\tNORMALIZABLES 20 25\tnolot\n', encoding='utf-8')
        mentions, discontinuous = read_brat_ann(ann)
        assert discontinuous == 1 and mentions == [(20, 25, 'NORMALIZABLES', 'nolot')]


class TestDrugTemist:
    def test_language_prefix_is_stripped_and_other_languages_skipped(self, public_corpora, tmp_path):
        corpora, _ = public_corpora
        drug = tmp_path / 'drug' / 'brat'
        drug.mkdir(parents=True)
        (drug / 'es-caso1.txt').write_text(TEXT, encoding='utf-8')
        (drug / 'es-caso1.ann').write_text('T1\tFARMACO 37 47\tmetformina\n', encoding='utf-8')
        (drug / 'en-caso1.txt').write_text('Patient with fever and diabetes, takes metformin.', encoding='utf-8')
        (drug / 'en-caso1.ann').write_text('T1\tFARMACO 39 48\tmetformin\n', encoding='utf-8')
        stats = Counter()
        drugtemist = load_brat_corpus(drug, 'drugtemist', stats)
        assert list(drugtemist) == ['caso1']
        assert stats['drugtemist:otro_idioma'] == 1
        docs = merge_corpora([corpora[0], corpora[1], drugtemist], required={'symptemist', 'distemist', 'drugtemist'})
        assert Span(37, 47, 'FARMACO') in docs[0].spans

    def test_optional_corpus_adds_spans_without_being_required(self, public_corpora):
        corpora, _ = public_corpora
        docs = merge_corpora(corpora, required={'symptemist', 'distemist'})
        assert docs[0].sources == {'symptemist', 'distemist', 'pharmaconer'}


class TestPickTextDir:
    def test_ignores_translations_and_background(self, tmp_path):
        for folder, names in {
            'symptemist_train/txt': ['c1', 'c2'],
            'symptemist_test/txt': ['c3'],
            'multilingual/en/txt': ['c1', 'c2'],
            'background/txt': ['c1', 'c2', 'c9'],
        }.items():
            (tmp_path / folder).mkdir(parents=True)
            for name in names:
                (tmp_path / folder / f'{name}.txt').write_text('x', encoding='utf-8')
        assert pick_text_dir(tmp_path, ['c1', 'c2']) == tmp_path / 'symptemist_train' / 'txt'


class TestOverlaps:
    def test_longest_span_wins(self):
        kept, dropped = resolve_overlaps([Span(0, 15, 'SINTOMA'), Span(0, 5, 'ENFERMEDAD')])
        assert kept == [Span(0, 15, 'SINTOMA')] and dropped == 1

    def test_priority_breaks_ties(self):
        kept, _ = resolve_overlaps([Span(0, 8, 'SINTOMA'), Span(0, 8, 'ENFERMEDAD')])
        assert kept == [Span(0, 8, 'ENFERMEDAD')]


class TestBioAlignment:
    OFFSETS = [(0, 0), (0, 5), (6, 8), (9, 15), (15, 16), (17, 21), (0, 0)]  # <s> dolor de cabeza , leve </s>

    def test_labels_every_subtoken_and_ignores_special_tokens(self):
        spans = [Span(0, 15, 'SINTOMA')]
        labels = bio_labels(self.OFFSETS, spans)
        assert labels == [IGNORE_INDEX, LABEL2ID['B-SINTOMA'], LABEL2ID['I-SINTOMA'], LABEL2ID['I-SINTOMA'],
                          LABEL2ID['O'], LABEL2ID['O'], IGNORE_INDEX]

    def test_round_trip(self):
        spans = [Span(0, 5, 'SINTOMA'), Span(9, 15, 'SINTOMA'), Span(17, 21, 'ENFERMEDAD')]
        assert spans_from_bio(self.OFFSETS, bio_labels(self.OFFSETS, spans)) == spans

    def test_orphan_inside_tag_opens_an_entity(self):
        labels = [IGNORE_INDEX, LABEL2ID['I-FARMACO'], LABEL2ID['O'], 0, 0, 0, IGNORE_INDEX]
        assert spans_from_bio(self.OFFSETS, labels) == [Span(0, 5, 'FARMACO')]


class TestOwnCorpus:
    def test_dev_documents_have_literal_spans(self):
        docs = corpus_to_documents(CORPUS, split='dev')
        assert len(docs) == len([c for c in json.loads(CORPUS.read_text(encoding='utf-8')) if c['split'] == 'dev'])
        for doc in docs:
            for span in doc.spans:
                assert doc.text[span.start:span.end].strip() == doc.text[span.start:span.end]

    def test_types_map_to_model_labels(self):
        docs = {d.doc_id: d for d in corpus_to_documents(CORPUS, split='dev')}
        labels = {s.label for d in docs.values() for s in d.spans}
        assert labels == {'SINTOMA', 'ENFERMEDAD', 'FARMACO'}


class TestMetricsAndFolds:
    def test_span_prf_is_exact_match(self):
        gold = {'a': [Span(0, 5, 'SINTOMA'), Span(9, 15, 'FARMACO')]}
        pred = {'a': [Span(0, 5, 'SINTOMA'), Span(9, 14, 'FARMACO')]}
        report = span_prf(gold, pred)
        assert report['SINTOMA']['f1'] == 1.0
        assert report['FARMACO']['f1'] == 0.0
        assert report['micro']['precision'] == 0.5

    def test_false_positives_without_gold_give_zero_f1(self):
        report = span_prf({'a': []}, {'a': [Span(0, 5, 'FARMACO')]})
        assert report['FARMACO']['f1'] == 0.0
        assert report['ENFERMEDAD']['f1'] is None

    def test_kfold_partitions_every_id_once(self):
        ids = [f'c{i}' for i in range(23)]
        folds = kfold(ids, 5)
        validation = [x for _, val in folds for x in val]
        assert sorted(validation) == sorted(ids)
        assert all(not set(train) & set(val) for train, val in folds)
        assert folds == kfold(ids, 5)
