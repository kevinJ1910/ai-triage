"""
Validacion externa de la normalizacion CIE-10 con CodiEsp (CLEF eHealth 2020, Zenodo 3837305, CC BY 4.0):
1.000 casos clinicos en espanol codificados a mano por expertos. Rompe la circularidad de la metrica de
codigos del corpus propio, cuyos codigos se prerrellenaron desde el mismo catalogo.

    python manage.py evaluate_normalization --download              # descarga y verifica el ZIP (11 MB)
    python manage.py evaluate_normalization --split dev
    python manage.py evaluate_normalization --split test --output resultados.json
    python manage.py evaluate_normalization --engine llm --split dev --limit 20 --pause 13
    python manage.py evaluate_normalization --engine llm --model local:gemma4:e4b-it-qat --split dev --limit 20

Metricas (solo diagnosticos: el catalogo no codifica procedimientos):
  documento  P/R/F1 de los codigos del caso (pista D) a nivel de categoria (3 caracteres, p. ej. R07) y de
             subcategoria (4 caracteres, R07.4) cuando el codigo anotado la tiene.
  cobertura  fraccion de categorias anotadas que existen en cie10.json: el techo del catalogo.
  mencion    de las menciones diagnosticas anotadas (pista X), cuantas detecta la normalizacion y, de esas,
             cuantas reciben la categoria correcta.

Advertencias:
  - CodiEsp usa la CIE10 espanola (CIE-10-ES, basada en ICD-10-CM), no la CIE-10 de la OMS que usa
    Colombia. Por eso se compara por categoria y subcategoria truncando los codigos, que es donde ambas
    coinciden casi siempre.
  - Son casos clinicos escritos, no habla transcrita: el catalogo esta pensado para coloquialismos, asi que
    el recall sera bajo. Mide la transferencia a texto clinico formal, no el uso previsto.
  - No ajustar el catalogo mirando el split test de CodiEsp: invalidaria esta validacion externa.
"""
import csv
import hashlib
import json
import re
import statistics
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from transcription.terminology import CIE10, cie10_catalog

CODIESP_URL = 'https://zenodo.org/api/records/3837305/files/codiesp.zip/content'
CODIESP_MD5 = '0642277ab2e7234f7053316b57c5e28c'
DEFAULT_DIR = Path(__file__).resolve().parents[3] / 'data' / 'codiesp'
SPLITS = ('train', 'dev', 'test')


def who_level(code: str, level: int = 3):
    """Trunca un codigo CIE-10 (OMS o CIE-10-ES) a categoria (3) o subcategoria (4): 's82.101a' -> 'S82' / 'S82.1'."""
    found = re.match(r'^([A-Z])(\d{2})\.?([0-9A-Z])?', (code or '').strip().upper())
    if not found:
        return None
    letter, digits, sub = found.groups()
    if level == 3:
        return f'{letter}{digits}'
    return f'{letter}{digits}.{sub}' if sub and sub.isdigit() else None


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall) if precision and recall else 0.0) \
        if precision is not None and recall is not None else None
    rnd = lambda x: round(x, 3) if x is not None else None  # noqa: E731
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': rnd(precision), 'recall': rnd(recall), 'f1': rnd(f1)}


def find_split_dir(root: Path, split: str) -> Path:
    candidates = [p for p in Path(root).rglob(split) if p.is_dir() and (p / 'text_files').is_dir()]
    if not candidates:
        raise CommandError(f'No se encontro {split}/text_files bajo {root}. Use --download o --codiesp-dir.')
    return sorted(candidates, key=lambda p: len(p.parts))[0]


def load_split(split_dir: Path, split: str) -> dict:
    """{documento: {'text', 'codes': [...], 'mentions': [(start, end, code, texto)]}} solo con diagnosticos."""
    docs = {p.stem: {'text': p.read_text(encoding='utf-8'), 'codes': [], 'mentions': []}
            for p in (split_dir / 'text_files').glob('*.txt')}
    with open(split_dir / f'{split}D.tsv', encoding='utf-8', newline='') as handle:
        for row in csv.reader(handle, delimiter='\t'):
            if len(row) >= 2 and row[0] in docs:
                docs[row[0]]['codes'].append(row[1])
    x_path = split_dir / f'{split}X.tsv'
    if x_path.exists():
        with open(x_path, encoding='utf-8', newline='') as handle:
            for row in csv.reader(handle, delimiter='\t'):
                if len(row) < 5 or row[0] not in docs or row[1].upper() != 'DIAGNOSTICO':
                    continue
                first = row[4].split(';')[0].split()
                docs[row[0]]['mentions'].append((int(first[0]), int(first[1]), row[2], row[3]))
    return docs


def download(target: Path, stdout) -> None:
    target.mkdir(parents=True, exist_ok=True)
    archive = target / 'codiesp.zip'
    if not archive.exists() or hashlib.md5(archive.read_bytes()).hexdigest() != CODIESP_MD5:
        stdout.write(f'Descargando CodiEsp en {archive}')
        urllib.request.urlretrieve(CODIESP_URL, archive)
    if hashlib.md5(archive.read_bytes()).hexdigest() != CODIESP_MD5:
        raise CommandError('MD5 de CodiEsp incorrecto: descarga corrupta o version distinta.')
    zipfile.ZipFile(archive).extractall(target)


class Command(BaseCommand):
    help = 'Valida la normalizacion CIE-10 contra los codigos expertos de CodiEsp.'

    def add_arguments(self, parser):
        parser.add_argument('--codiesp-dir', type=Path, default=DEFAULT_DIR)
        parser.add_argument('--download', action='store_true', help='Descarga y verifica el ZIP de Zenodo.')
        parser.add_argument('--split', choices=SPLITS, default='dev')
        parser.add_argument('--engine', choices=('catalogo', 'llm'), default='catalogo',
                            help='catalogo: capas deterministas; llm: tambien Gemini o LLM local para lo residual.')
        parser.add_argument('--model', default=None,
                            help="Modelo explicito cuando --engine llm (p. ej. 'local:gemma4:e4b-it-qat').")
        parser.add_argument('--limit', type=int)
        parser.add_argument('--pause', type=float, default=0.0, help='Segundos entre llamadas al LLM.')
        parser.add_argument('--output', type=Path)

    def handle(self, *args, **options):
        if options['download']:
            download(options['codiesp_dir'], self.stdout)
        split = options['split']
        docs = load_split(find_split_dir(options['codiesp_dir'], split), split)
        ids = sorted(docs)[:options['limit']] if options.get('limit') else sorted(docs)
        explicit_model = options.get('model')
        if options['engine'] == 'llm':
            from transcription.normalizer import normalize_clinical_text
            normalize = lambda text: normalize_clinical_text(text, model=explicit_model)  # noqa: E731
        else:
            from transcription.normalizer import normalize_with_rules as normalize

        catalog_categories = {who_level(code) for code in cie10_catalog()['codigos']}
        counts = defaultdict(int)
        latencies, per_doc = [], []
        for index, doc_id in enumerate(ids):
            if index and options['engine'] == 'llm' and options['pause']:
                time.sleep(options['pause'])
            doc = docs[doc_id]
            start = time.perf_counter()
            mappings = [m for m in normalize(doc['text'])['mappings']
                        if m.get('code_system') == CIE10 and m.get('code') and not m.get('negated')]
            latencies.append((time.perf_counter() - start) * 1000)

            gold3 = {c for c in (who_level(code) for code in doc['codes']) if c}
            pred3 = {c for c in (who_level(m['code']) for m in mappings) if c}
            counts['tp3'] += len(gold3 & pred3)
            counts['fp3'] += len(pred3 - gold3)
            counts['fn3'] += len(gold3 - pred3)
            gold4 = {c for c in (who_level(code, 4) for code in doc['codes']) if c}
            pred4 = {c for c in (who_level(m['code'], 4) for m in mappings) if c}
            counts['tp4'] += len(gold4 & pred4)
            counts['fp4'] += len(pred4 - gold4)
            counts['fn4'] += len(gold4 - pred4)
            counts['gold_categories'] += len(gold3)
            counts['covered_categories'] += len(gold3 & catalog_categories)

            for m_start, m_end, code, _ in doc['mentions']:
                counts['mentions'] += 1
                hits = [m for m in mappings if m['start'] < m_end and m_start < m['end']]
                if hits:
                    counts['mentions_detected'] += 1
                    if any(who_level(m['code']) == who_level(code) for m in hits):
                        counts['mentions_correct_code'] += 1
            per_doc.append({'id': doc_id, 'gold': sorted(gold3), 'predicted': sorted(pred3)})

        summary = {
            'engine': options['engine'], 'model': explicit_model, 'split': split, 'documentos': len(ids),
            'categoria_3': _prf(counts['tp3'], counts['fp3'], counts['fn3']),
            'subcategoria_4': _prf(counts['tp4'], counts['fp4'], counts['fn4']),
            'cobertura_catalogo': round(counts['covered_categories'] / counts['gold_categories'], 3)
            if counts['gold_categories'] else None,
            'menciones': {
                'anotadas': counts['mentions'],
                'detectadas': counts['mentions_detected'],
                'recall_deteccion': round(counts['mentions_detected'] / counts['mentions'], 3) if counts['mentions'] else None,
                'exactitud_codigo_en_detectadas': round(counts['mentions_correct_code'] / counts['mentions_detected'], 3)
                if counts['mentions_detected'] else None,
            },
            'latencia_ms_media': round(statistics.mean(latencies), 1) if latencies else None,
            'catalogo_cie10_completo': bool(cie10_catalog().get('completo')),
        }
        self._report(summary)
        if options.get('output'):
            options['output'].parent.mkdir(parents=True, exist_ok=True)
            options['output'].write_text(json.dumps({**summary, 'casos': per_doc}, ensure_ascii=False, indent=2),
                                         encoding='utf-8')
            self.stdout.write(f"Detalle guardado en {options['output']}")

    def _report(self, s):
        model_tag = f" ({s['model']})" if s.get('model') else ""
        self.stdout.write(f"CodiEsp {s['split']} | {s['documentos']} documentos | motor: {s['engine']}{model_tag}")
        for key, label in (('categoria_3', 'Categoria (3)'), ('subcategoria_4', 'Subcategoria (4)')):
            v = s[key]
            self.stdout.write(f"  {label:<17} P {v['precision']} / R {v['recall']} / F1 {v['f1']} "
                              f"(tp={v['tp']} fp={v['fp']} fn={v['fn']})")
        self.stdout.write(f"  Cobertura del catalogo (techo del recall por categoria): {s['cobertura_catalogo']}")
        m = s['menciones']
        self.stdout.write(f"  Menciones: {m['detectadas']} de {m['anotadas']} detectadas ({m['recall_deteccion']}); "
                          f"categoria correcta en {m['exactitud_codigo_en_detectadas']} de las detectadas")
        self.stdout.write(f"  Latencia media por documento: {s['latencia_ms_media']} ms")
