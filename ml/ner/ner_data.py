"""
Preparacion de datos para el NER clinico (RoBERTa biomedico-clinico en espanol). Solo biblioteca estandar:
se prueba en local sin torch y el notebook lo importa en Colab/Kaggle.

Etiquetas (esquema BIO):
  SINTOMA     sintomas, signos y hallazgos  (SympTEMIST; symptoms del corpus propio)
  ENFERMEDAD  enfermedades, lesiones y antecedentes patologicos  (DisTEMIST; diagnoses e history)
  FARMACO     medicamentos y sustancias  (PharmaCoNER NORMALIZABLES/NO_NORMALIZABLES; medications y allergies)

El modelo detecta menciones; si una mencion esta negada, es un antecedente o una alergia lo decide despues
el pipeline (negation.py y las reglas de contexto), igual que en los corpus publicos, que anotan las
menciones negadas.

SympTEMIST, DisTEMIST y PharmaCoNER anotan los mismos casos clinicos de SPACCC, cada uno con un solo tipo.
Entrenar con un corpus suelto ensena al modelo que las entidades de los otros tipos son 'O'. Por eso los
documentos se fusionan por nombre de fichero y, por defecto, solo se usan los que tienen los tres tipos.
"""
import csv
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

ENTITY_LABELS = ('SINTOMA', 'ENFERMEDAD', 'FARMACO')
LABELS = ['O'] + [f'{prefix}-{label}' for label in ENTITY_LABELS for prefix in ('B', 'I')]
LABEL2ID = {label: idx for idx, label in enumerate(LABELS)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}
IGNORE_INDEX = -100

# Etiqueta original de cada corpus -> etiqueta del modelo (None = se descarta).
SOURCE_LABEL_MAP = {
    'symptemist': {'SINTOMA': 'SINTOMA'},
    'distemist': {'ENFERMEDAD': 'ENFERMEDAD'},
    'pharmaconer': {'NORMALIZABLES': 'FARMACO', 'NO_NORMALIZABLES': 'FARMACO', 'PROTEINAS': None, 'UNCLEAR': None},
}
# Tipos del corpus propio (triage/benchmark/corpus_entidades.json). vitals queda en 'O': lo extrae el regex.
CORPUS_TYPE_MAP = {
    'symptoms': 'SINTOMA', 'diagnoses': 'ENFERMEDAD', 'history': 'ENFERMEDAD',
    'medications': 'FARMACO', 'allergies': 'FARMACO',
}
# Ante un solape entre corpus gana el span mas largo; si miden igual, este orden.
LABEL_PRIORITY = {'ENFERMEDAD': 0, 'SINTOMA': 1, 'FARMACO': 2}


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    label: str


@dataclass
class Document:
    doc_id: str
    text: str
    spans: List[Span] = field(default_factory=list)
    sources: set = field(default_factory=set)


# --------------------------------------------------------------------------- lectura de corpus publicos

def _first(row: dict, *names: str) -> Optional[str]:
    for name in names:
        if name in row and row[name] not in (None, ''):
            return row[name]
    return None


def read_mentions_tsv(path: Path) -> Dict[str, List[Tuple[int, int, str, str]]]:
    """
    TSV con cabecera, una mencion por linea. Acepta las columnas de SympTEMIST
    (filename, ann_id, label, start_span, end_span, text) y de DisTEMIST (filename, mark, label, off0, off1, span).
    """
    mentions: Dict[str, List[Tuple[int, int, str, str]]] = defaultdict(list)
    with open(path, encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            start, end = _first(row, 'start_span', 'off0'), _first(row, 'end_span', 'off1')
            if start is None or end is None:
                continue
            mentions[row['filename'].strip()].append(
                (int(start), int(end), row['label'].strip(), _first(row, 'text', 'span') or '')
            )
    return mentions


def read_brat_ann(path: Path) -> Tuple[List[Tuple[int, int, str, str]], int]:
    """Entidades 'T' de un .ann de brat. Los spans discontinuos ('0 5;9 12') se omiten y se cuentan."""
    mentions, discontinuous = [], 0
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.startswith('T'):
            continue
        parts = line.split('\t')
        if len(parts) < 3:
            continue
        label_and_offsets = parts[1]
        if ';' in label_and_offsets:
            discontinuous += 1
            continue
        label, start, end = label_and_offsets.split()
        mentions.append((int(start), int(end), label, parts[2]))
    return mentions, discontinuous


def _reanchor(text: str, start: int, end: int, surface: str, window: int = 60) -> Optional[Tuple[int, int]]:
    """Ajusta un span cuyo texto no coincide (p. ej. otra version del .txt) buscando la mencion cerca."""
    if not surface or text[start:end] == surface:
        return (start, end) if 0 <= start < end <= len(text) else None
    lo = max(0, start - window)
    found = text.find(surface, lo, min(len(text), end + window))
    return (found, found + len(surface)) if found >= 0 else None


def build_documents(text_dir: Path, mentions: Dict[str, List[Tuple[int, int, str, str]]], source: str,
                    stats: Optional[Counter] = None) -> Dict[str, Document]:
    """Une menciones y textos ({filename}.txt en text_dir o subcarpetas) con las etiquetas del modelo."""
    stats = stats if stats is not None else Counter()
    label_map = SOURCE_LABEL_MAP[source]
    texts = {p.stem: p for p in Path(text_dir).rglob('*.txt')}
    docs: Dict[str, Document] = {}
    for filename in sorted(set(mentions) | set(texts)):
        if filename not in texts:
            stats[f'{source}:sin_texto'] += 1
            continue
        text = texts[filename].read_text(encoding='utf-8')
        doc = Document(filename, text, sources={source})
        for start, end, label, surface in mentions.get(filename, []):
            target = label_map.get(label)
            if target is None:
                stats[f'{source}:descartada:{label}'] += 1
                continue
            anchored = _reanchor(text, start, end, surface)
            if anchored is None:
                stats[f'{source}:offset_invalido'] += 1
                continue
            doc.spans.append(Span(anchored[0], anchored[1], target))
            stats[f'{source}:{target}'] += 1
        docs[filename] = doc
    return docs


def load_brat_corpus(directory: Path, source: str, stats: Optional[Counter] = None) -> Dict[str, Document]:
    stats = stats if stats is not None else Counter()
    mentions = {}
    for ann in sorted(Path(directory).rglob('*.ann')):
        found, discontinuous = read_brat_ann(ann)
        mentions[ann.stem] = found
        stats[f'{source}:discontinuas'] += discontinuous
    return build_documents(directory, mentions, source, stats)


def load_tsv_corpus(tsv_path: Path, text_dir: Path, source: str, stats: Optional[Counter] = None) -> Dict[str, Document]:
    return build_documents(text_dir, read_mentions_tsv(tsv_path), source, stats)


# --------------------------------------------------------------------------- fusion y solapes

def resolve_overlaps(spans: Iterable[Span]) -> Tuple[List[Span], int]:
    """BIO no admite solapes: se queda el span mas largo (y, a igual longitud, por LABEL_PRIORITY)."""
    ordered = sorted(set(spans), key=lambda s: (-(s.end - s.start), LABEL_PRIORITY[s.label], s.start))
    kept: List[Span] = []
    dropped = 0
    for span in ordered:
        if any(span.start < other.end and other.start < span.end for other in kept):
            dropped += 1
            continue
        kept.append(span)
    return sorted(kept, key=lambda s: s.start), dropped


def merge_corpora(corpora: Sequence[Dict[str, Document]], require_all: bool = True,
                  stats: Optional[Counter] = None) -> List[Document]:
    """
    Fusiona por doc_id los documentos de varios corpus. Si el texto difiere entre corpus se reubican los
    spans por su texto (_reanchor) y, si no aparecen, se descartan. Con require_all solo quedan los documentos
    presentes en todos los corpus, para no tener entidades sin anotar tratadas como 'O'.
    """
    stats = stats if stats is not None else Counter()
    merged: Dict[str, Document] = {}
    for corpus in corpora:
        for doc_id, doc in corpus.items():
            if doc_id not in merged:
                merged[doc_id] = Document(doc_id, doc.text, list(doc.spans), set(doc.sources))
                continue
            base = merged[doc_id]
            if doc.text != base.text:
                stats['texto_distinto'] += 1
            for span in doc.spans:
                anchored = (span.start, span.end) if doc.text == base.text else _reanchor(
                    base.text, span.start, span.end, doc.text[span.start:span.end])
                if anchored is None:
                    stats['span_no_reubicado'] += 1
                    continue
                base.spans.append(Span(anchored[0], anchored[1], span.label))
            base.sources |= doc.sources
    total_sources = set().union(*(doc.sources for corpus in corpora for doc in corpus.values()))
    result = []
    for doc in merged.values():
        if require_all and doc.sources != total_sources:
            stats['documento_parcial_descartado'] += 1
            continue
        doc.spans, dropped = resolve_overlaps(doc.spans)
        stats['solape_descartado'] += dropped
        result.append(doc)
    stats['documentos'] = len(result)
    return sorted(result, key=lambda d: d.doc_id)


# --------------------------------------------------------------------------- corpus propio

def corpus_to_documents(corpus_path: Path, split: Optional[str] = None) -> List[Document]:
    """
    Casos de corpus_entidades.json como documentos. Cada span se busca literal en el transcript (la guia de
    anotacion lo garantiza); si el mismo texto se repite, se toma la siguiente aparicion libre.
    """
    cases = json.loads(Path(corpus_path).read_text(encoding='utf-8'))
    docs = []
    for case in cases:
        if split and case['split'] != split:
            continue
        text = case['transcript']
        used: List[Tuple[int, int]] = []
        spans = []
        for etype, label in CORPUS_TYPE_MAP.items():
            for item in case['entities'].get(etype, []):
                start = text.find(item['text'])
                while start >= 0 and any(start < e and s < start + len(item['text']) for s, e in used):
                    start = text.find(item['text'], start + 1)
                if start < 0:
                    continue
                used.append((start, start + len(item['text'])))
                spans.append(Span(start, start + len(item['text']), label))
        spans, _ = resolve_overlaps(spans)
        docs.append(Document(case['id'], text, spans, {'corpus_propio'}))
    return docs


# --------------------------------------------------------------------------- alineacion BIO

def bio_labels(offsets: Sequence[Tuple[int, int]], spans: Sequence[Span]) -> List[int]:
    """
    Etiqueta por token a partir de los offsets de caracter del tokenizador (return_offsets_mapping).
    Los tokens especiales (offset (0, 0)) reciben IGNORE_INDEX. Todo subtoken dentro de un span se etiqueta:
    B- el primero del span en la ventana, I- los demas.
    """
    labels = []
    previous_span = None
    for start, end in offsets:
        if start == end:
            labels.append(IGNORE_INDEX)
            previous_span = None
            continue
        current = next((s for s in spans if s.start <= start < s.end), None)
        if current is None:
            labels.append(LABEL2ID['O'])
        else:
            prefix = 'I' if current == previous_span else 'B'
            labels.append(LABEL2ID[f'{prefix}-{current.label}'])
        previous_span = current
    return labels


def spans_from_bio(offsets: Sequence[Tuple[int, int]], label_ids: Sequence[int]) -> List[Span]:
    """Reconstruye spans de caracter desde etiquetas por token. Un I- sin B- previo abre entidad (I suelto)."""
    spans: List[Span] = []
    current: Optional[List] = None
    for (start, end), label_id in zip(offsets, label_ids):
        if start == end or label_id == IGNORE_INDEX:
            continue
        label = ID2LABEL[int(label_id)]
        if label == 'O':
            if current:
                spans.append(Span(*current))
            current = None
            continue
        prefix, etype = label.split('-', 1)
        if current and prefix == 'I' and current[2] == etype:
            current[1] = end
        else:
            if current:
                spans.append(Span(*current))
            current = [start, end, etype]
    if current:
        spans.append(Span(*current))
    return spans


# --------------------------------------------------------------------------- metricas y particiones

def span_prf(gold: Dict[str, Sequence[Span]], predicted: Dict[str, Sequence[Span]]) -> Dict[str, Dict]:
    """P/R/F1 por etiqueta y micro con coincidencia exacta de inicio, fin y etiqueta."""
    counts = {label: Counter() for label in ENTITY_LABELS}
    for doc_id in set(gold) | set(predicted):
        g = set(gold.get(doc_id, []))
        p = set(predicted.get(doc_id, []))
        for label in ENTITY_LABELS:
            gl = {s for s in g if s.label == label}
            pl = {s for s in p if s.label == label}
            counts[label]['tp'] += len(gl & pl)
            counts[label]['fp'] += len(pl - gl)
            counts[label]['fn'] += len(gl - pl)

    def prf(c):
        precision = c['tp'] / (c['tp'] + c['fp']) if c['tp'] + c['fp'] else None
        recall = c['tp'] / (c['tp'] + c['fn']) if c['tp'] + c['fn'] else None
        if precision is None or recall is None:
            # Sin predicciones o sin entidades reales: F1 es 0 si hubo algun error y no definido si no hubo nada.
            f1 = 0.0 if c['fn'] or c['fp'] else None
        else:
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rnd = lambda x: round(x, 3) if x is not None else None  # noqa: E731
        return {'tp': c['tp'], 'fp': c['fp'], 'fn': c['fn'], 'precision': rnd(precision), 'recall': rnd(recall), 'f1': rnd(f1)}

    report = {label: prf(c) for label, c in counts.items()}
    report['micro'] = prf(sum(counts.values(), Counter()))
    return report


def kfold(ids: Sequence[str], k: int, seed: int = 42) -> List[Tuple[List[str], List[str]]]:
    """Particiones (train, val) deterministas para validacion cruzada sobre el split dev."""
    shuffled = sorted(ids)
    random.Random(seed).shuffle(shuffled)
    folds = [shuffled[i::k] for i in range(k)]
    return [([x for j, f in enumerate(folds) if j != i for x in f], folds[i]) for i in range(k)]


def holdout(docs: Sequence[Document], fraction: float = 0.1, seed: int = 42) -> Tuple[List[Document], List[Document]]:
    ids = sorted(d.doc_id for d in docs)
    random.Random(seed).shuffle(ids)
    val_ids = set(ids[:max(1, int(len(ids) * fraction))])
    return [d for d in docs if d.doc_id not in val_ids], [d for d in docs if d.doc_id in val_ids]


def corpus_summary(docs: Sequence[Document]) -> Dict[str, int]:
    summary = Counter(span.label for doc in docs for span in doc.spans)
    summary['documentos'] = len(docs)
    return dict(summary)


_EXCLUDED_DIRS = re.compile(r'background|silver|multilingual|gazetteer|__MACOSX', re.IGNORECASE)


def pick_text_dir(root: Path, filenames: Iterable[str]) -> Path:
    """
    Carpeta de .txt que corresponde a un TSV de menciones. El ZIP de SympTEMIST trae traducciones a 9 idiomas
    y un background set con los mismos nombres de fichero: se descartan esas carpetas y se elige la que mas
    nombres comparte con el TSV y menos ficheros ajenos tiene (la del mismo split).
    """
    wanted = set(filenames)
    best, best_score = None, None
    by_dir: Dict[Path, set] = defaultdict(set)
    for txt in Path(root).rglob('*.txt'):
        if not _EXCLUDED_DIRS.search(str(txt.parent)):
            by_dir[txt.parent].add(txt.stem)
    for directory, stems in by_dir.items():
        overlap = len(stems & wanted)
        score = (overlap, -len(stems - wanted))
        if overlap and (best_score is None or score > best_score):
            best, best_score = directory, score
    if best is None:
        raise FileNotFoundError(f'No hay carpeta de textos para {len(wanted)} documentos bajo {root}')
    return best


def find_files(root: Path, pattern: str) -> List[Path]:
    """Ayuda para localizar los ficheros dentro de los ZIP descomprimidos (la estructura cambia entre versiones)."""
    return sorted(p for p in Path(root).rglob(pattern) if not re.search(r'__MACOSX|/\.', str(p)))
