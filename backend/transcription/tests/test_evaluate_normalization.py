import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from transcription.management.commands.evaluate_normalization import load_split, who_level

TEXT = 'Paciente con disnea y fiebre de tres días. Antecedente de hipertensión arterial. Sin vómito.'


@pytest.fixture
def codiesp(tmp_path):
    """Estructura real de codiesp.zip: TSV sin cabecera y codigos CIE-10-ES en minuscula."""
    split = tmp_path / 'final_dataset_v4_to_publish' / 'dev'
    (split / 'text_files').mkdir(parents=True)
    (split / 'text_files' / 'S0001-1.txt').write_text(TEXT, encoding='utf-8')
    (split / 'devD.tsv').write_text('S0001-1\tr06.00\nS0001-1\tr50.9\nS0001-1\ti10\nS0001-1\tk35.80\n', encoding='utf-8')
    (split / 'devP.tsv').write_text('S0001-1\tbw03zzz\n', encoding='utf-8')
    disnea = TEXT.index('disnea')
    apendicitis_fake = (0, 8)
    (split / 'devX.tsv').write_text(
        f'S0001-1\tDIAGNOSTICO\tr06.00\tdisnea\t{disnea} {disnea + 6}\n'
        f'S0001-1\tDIAGNOSTICO\tk35.80\tPaciente\t{apendicitis_fake[0]} {apendicitis_fake[1]};20 25\n'
        f'S0001-1\tPROCEDIMIENTO\tbw03zzz\tradiografia\t1 2\n',
        encoding='utf-8')
    return tmp_path


class TestCodeLevels:
    @pytest.mark.parametrize('code, level, expected', [
        ('r06.00', 3, 'R06'), ('r06.00', 4, 'R06.0'), ('S82.101A', 4, 'S82.1'), ('I10', 4, None),
        ('R51X', 3, 'R51'), ('bw03zzz', 3, None),
    ])
    def test_who_level(self, code, level, expected):
        assert who_level(code, level) == expected


class TestLoad:
    def test_only_diagnoses_and_first_fragment(self, codiesp):
        docs = load_split(codiesp / 'final_dataset_v4_to_publish' / 'dev', 'dev')
        doc = docs['S0001-1']
        assert doc['codes'] == ['r06.00', 'r50.9', 'i10', 'k35.80']
        assert [m[2] for m in doc['mentions']] == ['r06.00', 'k35.80']
        assert doc['mentions'][1][:2] == (0, 8)


class TestCommand:
    def test_reports_category_subcategory_coverage_and_mentions(self, codiesp, tmp_path):
        output = tmp_path / 'r.json'
        out = StringIO()
        call_command('evaluate_normalization', '--codiesp-dir', str(codiesp), '--split', 'dev',
                     '--output', str(output), stdout=out)
        result = json.loads(output.read_text(encoding='utf-8'))
        # Catalogo: disnea R06.0, fiebre R50.9, HTA I10; 'vomito' esta negado y no cuenta.
        assert result['categoria_3'] == {'tp': 3, 'fp': 0, 'fn': 1, 'precision': 1.0, 'recall': 0.75, 'f1': 0.857}
        assert result['subcategoria_4']['tp'] == 2  # R06.0 y R50.9; I10 no tiene subcategoria
        assert result['cobertura_catalogo'] == 0.75  # K35 (apendicitis aguda) no esta en el catalogo
        assert result['menciones'] == {'anotadas': 2, 'detectadas': 1, 'recall_deteccion': 0.5,
                                       'exactitud_codigo_en_detectadas': 1.0}
        assert 'CodiEsp dev | 1 documentos' in out.getvalue()

    def test_missing_data_explains_how_to_get_it(self, tmp_path):
        with pytest.raises(CommandError, match='--download'):
            call_command('evaluate_normalization', '--codiesp-dir', str(tmp_path), stdout=StringIO())
