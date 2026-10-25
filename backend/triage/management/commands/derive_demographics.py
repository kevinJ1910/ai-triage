"""
Deriva el sexo y el grupo de edad de cada caso del corpus para el analisis descriptivo de sesgo.

Uso:
    python manage.py derive_demographics
    python manage.py derive_demographics --output triage/benchmark/demografia.json

Escribe benchmark/demografia.json ({id: {sexo, edad, grupo_edad, fuente}}). Las entradas que alguien revise a
mano se marcan con fuente 'revisado' y el comando las conserva al volver a ejecutarse. evaluate_extraction usa el
archivo, si existe, para desglosar el triaje por sexo y por grupo de edad (by_sexo, by_grupo_edad). No mira
ninguna prediccion del sistema, asi que puede ejecutarse sobre test.
"""
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from triage.demographics import DEMOGRAPHICS_PATH, derive_all, load_demographics
from triage.entity_corpus import CORPUS_PATH, load_entity_corpus


class Command(BaseCommand):
    help = "Deriva sexo y grupo de edad de los casos del corpus (benchmark/demografia.json)."

    def add_arguments(self, parser):
        parser.add_argument('--corpus', type=Path, default=CORPUS_PATH)
        parser.add_argument('--output', type=Path, default=DEMOGRAPHICS_PATH)

    def handle(self, *args, **options):
        try:
            cases = load_entity_corpus(options['corpus'])
            previous = load_demographics(options['output'])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        data = derive_all(cases, previous)
        options['output'].write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
                                     encoding='utf-8')
        by_split = {}
        for case in cases:
            by_split.setdefault(case['split'], []).append(data[case['id']])
        for split, rows in sorted(by_split.items()):
            sexes = Counter(r['sexo'] for r in rows)
            groups = Counter(r['grupo_edad'] for r in rows)
            self.stdout.write(f"{split}: sexo {dict(sorted(sexes.items()))} | edad {dict(sorted(groups.items()))}")
        reviewed = sum(1 for r in data.values() if r.get('fuente') == 'revisado')
        self.stdout.write(f"{len(data)} casos ({reviewed} revisados a mano). Guardado en {options['output']}")
