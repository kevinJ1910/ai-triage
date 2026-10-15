"""
Sustituye el subconjunto local de la CIE-10 por una tabla completa (p. ej. la tabla de referencia de
Minsalud/SISPRO exportada a CSV). Con el catalogo completo, un codigo ausente pasa a ser invalido.

    python manage.py import_cie10 TablaReferencia_CIE10.csv --code-column Codigo --name-column Nombre
"""
import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from transcription.terminology import CATALOG_DIR, canonical_cie10, clear_caches


class Command(BaseCommand):
    help = 'Importa una tabla CIE-10 completa (CSV) al catalogo local de la normalizacion.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--code-column', default=None, help='Columna del codigo (por defecto, la primera).')
        parser.add_argument('--name-column', default=None, help='Columna de la descripcion (por defecto, la segunda).')
        parser.add_argument('--encoding', default='utf-8-sig')
        parser.add_argument('--source', default='Tabla de referencia CIE-10 de Minsalud/SISPRO')
        parser.add_argument('--table-version', default=None, help='Version o fecha de la tabla importada.')

    def handle(self, *args, **options):
        path = Path(options['csv_path'])
        if not path.exists():
            raise CommandError(f'No existe {path}')
        text = path.read_text(encoding=options['encoding'])
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=';,\t|')
        rows = list(csv.reader(text.splitlines(), dialect))
        header, body = rows[0], rows[1:]
        code_idx = header.index(options['code_column']) if options['code_column'] else 0
        name_idx = header.index(options['name_column']) if options['name_column'] else 1

        codes, skipped = {}, 0
        for row in body:
            if len(row) <= max(code_idx, name_idx):
                skipped += 1
                continue
            code = canonical_cie10(row[code_idx])
            if not code or not row[name_idx].strip():
                skipped += 1
                continue
            codes[code] = row[name_idx].strip()
        if not codes:
            raise CommandError('No se encontro ningun codigo CIE-10 valido: revise las columnas.')

        target = CATALOG_DIR / 'cie10.json'
        previous = json.loads(target.read_text(encoding='utf-8'))
        missing = sorted(set(previous['codigos']) - set(codes))
        target.write_text(json.dumps({
            'version': options['table_version'] or previous.get('version'),
            'completo': True,
            'fuente': f"{options['source']} ({path.name})",
            'codigos': dict(sorted(codes.items())),
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        clear_caches()

        self.stdout.write(self.style.SUCCESS(f'{len(codes)} codigos importados ({skipped} filas omitidas).'))
        if missing:
            self.stdout.write(self.style.WARNING(
                'Codigos usados por los catalogos que no estan en la tabla importada: ' + ', '.join(missing)
            ))
