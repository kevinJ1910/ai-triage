import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from transcription.management.commands import evaluate_asr
from transcription.management.commands.evaluate_asr import clinical_term_errors, edit_counts, wer_counts


class TestWer:
    def test_known_alignment(self):
        # 'b' -> 'x' (sustitucion) y 'e' sobra (insercion). Coincide con jiwer en 300 pares aleatorios.
        assert edit_counts('a b c d'.split(), 'a x c e d'.split()) == (1, 0, 1)
        assert edit_counts('el paciente tiene fiebre'.split(), 'paciente tiene mucha fiebre'.split()) == (0, 1, 1)
        assert edit_counts([], ['a']) == (0, 0, 1) and edit_counts(['a'], []) == (0, 1, 0)

    def test_normalization_ignores_case_and_punctuation(self):
        counts = wer_counts('Tengo fiebre, y tos.', 'tengo fiebre y tos')
        assert counts['words'] == 4 and counts['substitutions'] + counts['deletions'] + counts['insertions'] == 0

    def test_accents_count_unless_stripped(self):
        assert wer_counts('dolor torácico', 'dolor toracico')['substitutions'] == 1
        assert wer_counts('dolor torácico', 'dolor toracico', strip_accents=True)['substitutions'] == 0

    def test_clinical_term_errors(self):
        result = clinical_term_errors('me falta el aire y tomo losartán', 'me falta el aire y tomo los artan')
        assert result == {'terms': 2, 'missed': ['losartán']}


class FakeTranscriber:
    def __init__(self, outputs):
        self.outputs = outputs

    def transcribe(self, path, chunk_seconds=0):
        return self.outputs[path.stem], 4.0


@pytest.mark.django_db
class TestCommand:
    def test_prepare_writes_script_and_manifest(self, tmp_path):
        call_command('evaluate_asr', '--prepare', '--out-dir', str(tmp_path), '--per-level', '2', stdout=StringIO())
        manifest = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
        assert len(manifest) == 5 * 2 * 2
        assert {m['condicion'] for m in manifest} == {'silencio', 'ruido'}
        assert '## ' in (tmp_path / 'guion_grabacion.md').read_text(encoding='utf-8')

    def test_evaluate_reports_wer_by_condition(self, tmp_path, monkeypatch):
        manifest = [
            {'audio': 'C1_silencio.wav', 'case_id': 'C1', 'condicion': 'silencio', 'locutor': 'a',
             'reference': 'tengo fiebre y tos'},
            {'audio': 'C1_ruido.wav', 'case_id': 'C1', 'condicion': 'ruido', 'locutor': 'a',
             'reference': 'tengo fiebre y tos'},
            {'audio': 'C2_silencio.wav', 'case_id': 'C2', 'condicion': 'silencio', 'locutor': 'a',
             'reference': 'no grabado'},
        ]
        (tmp_path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        (tmp_path / 'C1_silencio.wav').write_bytes(b'x')
        (tmp_path / 'C1_ruido.m4a').write_bytes(b'x')  # otra extension con el mismo nombre
        fake = FakeTranscriber({'C1_silencio': 'tengo fiebre y tos', 'C1_ruido': 'tengo fiebre tos'})
        monkeypatch.setattr(evaluate_asr.Command, '_load_transcriber', lambda self, options: fake)
        out = StringIO()
        output = tmp_path / 'r.json'
        call_command('evaluate_asr', '--manifest', str(tmp_path / 'manifest.json'), '--output', str(output), stdout=out)
        result = json.loads(output.read_text(encoding='utf-8'))
        assert result['por_condicion']['silencio']['wer'] == 0.0
        assert result['por_condicion']['ruido']['wer'] == 0.25
        assert result['global']['wer'] == 0.125 and result['audios_faltantes'] == 1
        assert result['global']['rtf'] is not None

    def test_requires_mode(self):
        with pytest.raises(CommandError):
            call_command('evaluate_asr', stdout=StringIO())
