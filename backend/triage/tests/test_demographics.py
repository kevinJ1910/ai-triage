import json
from io import StringIO

import pytest
from django.core.management import call_command

from triage.demographics import derive, derive_all


class TestDemographics:
    @pytest.mark.parametrize("text,sexo,grupo,edad", [
        ("Mujer de 30 años con disuria", 'femenino', 'adulto', 30),
        ("Traen a un señor de unos 60 años que se desplomó", 'masculino', 'adulto', 60),
        ("Paciente de 72 años de edad con disnea", 'desconocido', 'mayor', 72),
        ("El niño vomitó cinco veces", 'masculino', 'pediatrico', None),
        ("Bebé de 8 meses con fiebre", 'desconocido', 'pediatrico', 0),
        ("Tengo dolor de cabeza desde hace 3 años", 'desconocido', 'desconocido', None),
        ("La abuela se cayó en el baño", 'femenino', 'mayor', None),
        ("Mi esposo y mi hija tienen fiebre", 'desconocido', 'desconocido', None),
    ])
    def test_derive(self, text, sexo, grupo, edad):
        assert derive(text) == {'sexo': sexo, 'edad': edad, 'grupo_edad': grupo}

    def test_reviewed_entries_are_kept(self):
        cases = [{'id': 'a', 'transcript': 'Mujer de 30 años'}, {'id': 'b', 'transcript': 'Tengo tos'}]
        previous = {'b': {'sexo': 'masculino', 'edad': 40, 'grupo_edad': 'adulto', 'fuente': 'revisado'}}
        out = derive_all(cases, previous)
        assert out['a']['fuente'] == 'regex' and out['b'] == previous['b']

    def test_command_writes_file(self, tmp_path):
        output = tmp_path / 'demografia.json'
        call_command('derive_demographics', '--output', str(output), stdout=StringIO())
        data = json.loads(output.read_text(encoding='utf-8'))
        assert len(data) == 250
        assert {d['grupo_edad'] for d in data.values()} <= {'pediatrico', 'adulto', 'mayor', 'desconocido'}

    def test_extraction_breaks_down_by_demographics(self, tmp_path, mocker):
        from triage.management.commands import evaluate_extraction
        mocker.patch.object(evaluate_extraction, 'load_demographics',
                            return_value={'B002': {'sexo': 'masculino', 'grupo_edad': 'adulto'}})
        output = tmp_path / 'r.json'
        call_command('evaluate_extraction', '--engine', 'reglas', '--split', 'dev', '--limit', '3',
                     '--output', str(output), stdout=StringIO(), stderr=StringIO())
        triage = json.loads(output.read_text(encoding='utf-8'))['triage']
        assert 'masculino' in triage['by_sexo'] and 'None' in triage['by_sexo']
        assert 'by_grupo_edad' in triage
