"""
Verifica los identificadores SNOMED CT de los catalogos contra un servidor terminologico FHIR
(CodeSystem/$lookup): que existan, que esten activos y que su FSN coincida con el guardado en snomed.json.

    python manage.py verify_snomed                      # solo informa
    python manage.py verify_snomed --update             # reescribe FSN y edicion en snomed.json

Por defecto usa el servidor publico de HL7 (tx.fhir.org), que publica la International Edition.
"""
import json
import time
import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from transcription.terminology import CATALOG_DIR, _surface_entries, clear_caches

DEFAULT_SERVER = 'https://tx.fhir.org/r4'
FSN_USE = '900000000000003001'


def lookup(server: str, code: str, timeout: int = 30) -> dict:
    query = urllib.parse.urlencode({'system': 'http://snomed.info/sct', 'code': code})
    request = urllib.request.Request(f'{server}/CodeSystem/$lookup?{query}', headers={'Accept': 'application/fhir+json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.load(response)
    result = {'fsn': None, 'display': None, 'version': None, 'inactive': None}
    for param in data.get('parameter', []):
        name = param.get('name')
        if name == 'display':
            result['display'] = param.get('valueString')
        elif name == 'version':
            result['version'] = param.get('valueString')
        elif name in ('designation', 'property'):
            parts = {p.get('name'): p for p in param.get('part', [])}
            if name == 'designation' and parts.get('use', {}).get('valueCoding', {}).get('code') == FSN_USE:
                result['fsn'] = parts.get('value', {}).get('valueString')
            if name == 'property' and parts.get('code', {}).get('valueCode') == 'inactive':
                result['inactive'] = parts.get('value', {}).get('valueBoolean')
    return result


class Command(BaseCommand):
    help = 'Verifica los codigos SNOMED CT del catalogo terminologico contra un servidor FHIR.'

    def add_arguments(self, parser):
        parser.add_argument('--server', default=DEFAULT_SERVER)
        parser.add_argument('--pause', type=float, default=0.4, help='Segundos entre consultas.')
        parser.add_argument('--update', action='store_true', help='Guarda FSN y edicion verificados en snomed.json.')

    def handle(self, *args, **options):
        target = CATALOG_DIR / 'snomed.json'
        catalog = json.loads(target.read_text(encoding='utf-8'))
        codes = sorted({c.snomed for _, c, _ in _surface_entries() if c.snomed}, key=int)

        problems, verified, versions = [], {}, set()
        for index, code in enumerate(codes):
            if index and options['pause']:
                time.sleep(options['pause'])
            try:
                found = lookup(options['server'], code)
            except Exception as err:
                problems.append(f'{code}: no encontrado ({str(err)[:80]})')
                continue
            if found['inactive']:
                problems.append(f'{code}: inactivo ({found["fsn"] or found["display"]})')
                continue
            fsn = found['fsn'] or found['display']
            stored = catalog['codigos'].get(code)
            if stored and stored != fsn:
                problems.append(f'{code}: FSN cambio de {stored!r} a {fsn!r}')
            verified[code] = fsn
            if found['version']:
                versions.add(found['version'].rsplit('/', 1)[-1])

        self.stdout.write(f'{len(verified)} de {len(codes)} codigos activos en {options["server"]}.')
        for problem in problems:
            self.stdout.write(self.style.WARNING(problem))

        if options['update']:
            if problems:
                raise CommandError('Hay codigos sin verificar: corrija los catalogos antes de actualizar snomed.json.')
            catalog['codigos'] = dict(sorted(verified.items(), key=lambda kv: int(kv[0])))
            if versions:
                catalog['edicion'] = 'SNOMED CT International Edition ' + ', '.join(sorted(versions))
            target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            clear_caches()
            self.stdout.write(self.style.SUCCESS(f'snomed.json actualizado con {len(verified)} codigos.'))
        elif problems:
            raise CommandError(f'{len(problems)} codigos con problemas.')
