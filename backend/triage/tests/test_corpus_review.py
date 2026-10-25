import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from triage.corpus_review import apply_review, entities_summary, export_rows, read_csv, to_csv
from triage.entity_corpus import (
    CORPUS_PATH,
    double_annotation_sample,
    load_entity_corpus,
    validate_entity_corpus,
)


def _corpus():
    return json.loads(CORPUS_PATH.read_text(encoding='utf-8'))


def _test_case(cases, level):
    return next(c for c in cases if c['split'] == 'test' and c['reference_level'] == level)


def _row(case, **changes):
    return {'id': case['id'], 'transcript': case['transcript'], 'nivel_revisado': '', 'criterio_revisado': '',
            'entidades_ok': 'si', 'comentario': '', 'revisado_por': 'KJ', **changes}


class TestExport:
    def test_rows_have_no_predictions_and_readable_entities(self):
        rows = export_rows(load_entity_corpus(split='test'))
        assert len(rows) == 100
        forbidden = {'predicted_level', 'rule_level', 'llm_level', 'justification', 'engine_used'}
        assert not forbidden & set(rows[0])
        summary = entities_summary({'symptoms': [{'text': 'dolor en el pecho', 'normalized': 'dolor torácico',
                                                  'negated': True, 'cie10': 'R07.4'}]})
        assert summary == 'Síntomas: «dolor en el pecho» → dolor torácico [R07.4] (NEGADO)'

    @pytest.mark.parametrize('delimiter', [';', ','])
    def test_csv_roundtrip_with_excel_or_sheets_delimiter(self, delimiter):
        rows = export_rows(load_entity_corpus(split='test')[:3])
        text = to_csv(rows)
        assert text.startswith('﻿') and text.splitlines()[0].count(';') == 12
        if delimiter == ',':
            import csv, io
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
            text = buffer.getvalue()
        parsed = read_csv(text)
        assert [r['id'] for r in parsed] == [r['id'] for r in rows]
        assert parsed[0]['transcript'] == rows[0]['transcript']


class TestApplyReview:
    def test_level_change_keeps_every_split_and_the_double_annotation_sample(self):
        cases = _corpus()
        splits = {c['id']: c['split'] for c in cases}
        sample = double_annotation_sample(cases)
        target = _test_case(cases, 3)
        updated, report = apply_review(cases, [_row(target, nivel_revisado='2',
                                                     criterio_revisado='Dificultad respiratoria moderada')],
                                       today='2026-10-21')
        changed = next(c for c in updated if c['id'] == target['id'])
        assert changed['reference_level'] == 2 and changed['nivel_particion'] == 3
        assert changed['estado'] == 'revisado' and changed['revisado_por'] == 'KJ'
        assert changed['revisado_el'] == '2026-10-21'
        assert report['level_changes'] == [(target['id'], 3, 2)]
        assert validate_entity_corpus(updated) == []
        assert {c['id']: c['split'] for c in updated} == splits
        assert double_annotation_sample(updated) == sample
        # Una segunda revision conserva el nivel original de la particion.
        again, _ = apply_review(updated, [_row(changed, nivel_revisado='1', criterio_revisado='Inconciencia')])
        assert next(c for c in again if c['id'] == target['id'])['nivel_particion'] == 3

    def test_agreement_marks_reviewed_without_changes(self):
        cases = _corpus()
        target = _test_case(cases, 1)
        updated, report = apply_review(cases, [_row(target)])
        changed = next(c for c in updated if c['id'] == target['id'])
        assert changed['estado'] == 'revisado' and 'nivel_particion' not in changed
        assert changed['criterio'] == target['criterio'] and report['level_changes'] == []

    def test_entity_problems_stay_in_draft_and_rows_without_reviewer_are_skipped(self):
        cases = _corpus()
        first, second = _test_case(cases, 4), _test_case(cases, 5)
        updated, report = apply_review(cases, [_row(first, entidades_ok='no', comentario='falta antecedente'),
                                               _row(second, revisado_por='')])
        assert next(c for c in updated if c['id'] == first['id'])['estado'] == 'borrador'
        assert report['entity_fixes'] == [(first['id'], 'falta antecedente')]
        assert report['skipped'] == [second['id']]
        assert next(c for c in updated if c['id'] == second['id']) == second

    @pytest.mark.parametrize('changes,message', [
        ({'nivel_revisado': '7'}, 'nivel_revisado'),
        ({'nivel_revisado': '1'}, 'criterio_revisado'),
        ({'entidades_ok': 'quizas'}, 'entidades_ok'),
        ({'transcript': 'otro texto'}, 'no coincide'),
        ({'id': 'ZZZ'}, 'no esta en el corpus'),
    ])
    def test_invalid_rows_reject_the_whole_sheet(self, changes, message):
        cases = _corpus()
        target = _test_case(cases, 3)
        with pytest.raises(ValueError, match=message):
            apply_review(cases, [_row(_test_case(cases, 2)), _row(target, **changes)])


class TestReviewCommands:
    def test_export_apply_dry_run_and_write(self, tmp_path):
        corpus = tmp_path / 'corpus.json'
        corpus.write_text(CORPUS_PATH.read_text(encoding='utf-8'), encoding='utf-8')
        sheet = tmp_path / 'revision_test.csv'
        call_command('export_corpus_review', '--corpus', str(corpus), '--split', 'test', '--output', str(sheet),
                     stdout=StringIO())
        rows = read_csv(sheet.read_text(encoding='utf-8'))
        assert len(rows) == 100
        rows[0].update({'nivel_revisado': '', 'entidades_ok': 'si', 'revisado_por': 'KJ'})
        sheet.write_text(to_csv(rows), encoding='utf-8')

        before = corpus.read_text(encoding='utf-8')
        out = StringIO()
        call_command('apply_corpus_review', str(sheet), '--corpus', str(corpus), '--dry-run', stdout=out)
        assert "Pasan a 'revisado': 1" in out.getvalue()
        assert corpus.read_text(encoding='utf-8') == before

        call_command('apply_corpus_review', str(sheet), '--corpus', str(corpus), stdout=StringIO())
        updated = json.loads(corpus.read_text(encoding='utf-8'))
        assert next(c for c in updated if c['id'] == rows[0]['id'])['estado'] == 'revisado'
        assert sum(c['estado'] == 'revisado' for c in updated) == 1
        assert validate_entity_corpus(updated) == []

    def test_invalid_sheet_does_not_touch_the_corpus(self, tmp_path):
        corpus = tmp_path / 'corpus.json'
        corpus.write_text(CORPUS_PATH.read_text(encoding='utf-8'), encoding='utf-8')
        target = _test_case(_corpus(), 3)
        sheet = tmp_path / 'r.csv'
        sheet.write_text(to_csv([{**export_rows([target])[0], 'nivel_revisado': '1', 'entidades_ok': 'si',
                                  'revisado_por': 'KJ'}]), encoding='utf-8')
        before = corpus.read_text(encoding='utf-8')
        with pytest.raises(CommandError, match='criterio_revisado'):
            call_command('apply_corpus_review', str(sheet), '--corpus', str(corpus), stdout=StringIO())
        assert corpus.read_text(encoding='utf-8') == before
