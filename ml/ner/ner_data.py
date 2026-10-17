"""
Preparacion de datos para el NER clinico (RoBERTa biomedico-clinico en espanol). Solo biblioteca estandar:
se prueba en local sin torch y el notebook lo importa en Colab/Kaggle.

Etiquetas (esquema BIO):
  SINTOMA     sintomas, signos y hallazgos  (SympTEMIST; symptoms del corpus propio)
  ENFERMEDAD  enfermedades, lesiones y antecedentes patologicos  (DisTEMIST; diagnoses e history)
  FARMACO     medicamentos  (DrugTEMIST; opcionalmente PharmaCoNER NORMALIZABLES/NO_NORMALIZABLES;
              medications y las allergies a medicamentos del corpus propio)

El modelo detecta menciones; si una mencion esta negada, es un antecedente o una alergia lo decide despues
el pipeline (negation.py y las reglas de contexto), igual que en los corpus publicos, que anotan las
menciones negadas.

SympTEMIST, DisTEMIST y DrugTEMIST (y PharmaCoNER) anotan los mismos casos clinicos de SPACCC, cada uno con
un solo tipo.
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
    # DrugTEMIST (MultiCardioNER, pista 2): guias especificas de medicamentos, como medications del corpus propio.
    'drugtemist': {'FARMACO': 'FARMACO', 'MEDICAMENTO': 'FARMACO', 'DRUG': 'FARMACO'},
}
# MultiCardioNER nombra los ficheros con el idioma delante ('es-S0004-...'); solo se usa el espanol.
_LANG_PREFIX = re.compile(r'^(es|en|it)[-_](?=.{4,})', re.IGNORECASE)


def split_language(stem: str) -> Tuple[Optional[str], str]:
    """('es', 'S0004-...') para 'es-S0004-...'; (None, stem) si no lleva prefijo de idioma."""
    found = _LANG_PREFIX.match(stem)
    return (found.group(1).lower(), stem[found.end():]) if found else (None, stem)
# Tipos del corpus propio (triage/benchmark/corpus_entidades.json). vitals queda en 'O': lo extrae el regex.
# allergies solo es FARMACO si la sustancia es un medicamento (campo farmaco); alimentos, polvo o picaduras
# quedan en 'O', porque DrugTEMIST solo anota medicamentos y el modelo no los puede aprender de ahi.
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
    texts = {}
    for path in Path(text_dir).rglob('*.txt'):
        lang, doc_id = split_language(path.stem)
        if lang not in (None, 'es'):
            stats[f'{source}:otro_idioma'] += 1
            continue
        texts[doc_id] = path
    mentions = {split_language(k)[1]: v for k, v in mentions.items() if split_language(k)[0] in (None, 'es')}
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
                  stats: Optional[Counter] = None, required: Optional[Iterable[str]] = None) -> List[Document]:
    """
    Fusiona por doc_id los documentos de varios corpus. Si el texto difiere entre corpus se reubican los
    spans por su texto (_reanchor) y, si no aparecen, se descartan. Con require_all solo quedan los documentos
    presentes en todos los corpus, para no tener entidades sin anotar tratadas como 'O'. required (nombres de
    corpus) exige solo esos; los demas suman sus spans cuando el documento existe.
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
    needed = set(required) if required is not None else (total_sources if require_all else set())
    result = []
    for doc in merged.values():
        if not needed <= doc.sources:
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
                if etype == 'allergies' and not item.get('farmaco', True):
                    continue
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


# --------------------------------------------------------------------------- aumento de datos

_PUNCTUATION = set(',.;:¿?¡!…"«»()')


def _remap(doc: Document, keep: Sequence[bool], text: str, suffix: str) -> Document:
    """Documento con los caracteres marcados en keep; los spans se trasladan y se recortan a lo conservado."""
    new_index, position = [], 0
    for kept in keep:
        new_index.append(position)
        position += kept
    new_index.append(position)
    spans = []
    for span in doc.spans:
        inside = [i for i in range(span.start, span.end) if keep[i]]
        if inside:
            start, end = new_index[inside[0]], new_index[inside[-1]] + 1
            while end > start and text[end - 1] == ' ':
                end -= 1
            if end > start:
                spans.append(Span(start, end, span.label))
    return Document(f'{doc.doc_id}#{suffix}', text, spans, set(doc.sources))


def lowercase_variant(doc: Document) -> Optional[Document]:
    """Todo en minusculas, como los fragmentos del ASR. None si cambia la longitud (no pasa en espanol)."""
    text = doc.text.lower()
    if len(text) != len(doc.text):
        return None
    return Document(f'{doc.doc_id}#minusculas', text, list(doc.spans), set(doc.sources))


def unpunctuated_variant(doc: Document) -> Document:
    """Sin signos de puntuacion y con espacios simples, como una transcripcion sin puntuar."""
    keep = [ch not in _PUNCTUATION for ch in doc.text]
    previous_space = True
    for i, ch in enumerate(doc.text):
        if keep[i] and ch.isspace():
            keep[i] = not previous_space
        if keep[i]:
            previous_space = ch.isspace()
    for i in range(len(keep) - 1, -1, -1):  # sin espacio final
        if keep[i] and not doc.text[i].isspace():
            break
        keep[i] = False
    text = ''.join(' ' if ch.isspace() else ch for ch, kept in zip(doc.text, keep) if kept)
    return _remap(doc, keep, text, 'sin_puntuacion')


def augment_documents(docs: Sequence[Document], variants: Sequence[str] = ('minusculas', 'sin_puntuacion')
                      ) -> List[Document]:
    """
    Originales mas variantes con estilo de transcripcion. Solo para entrenar: las particiones de validacion
    se evaluan siempre sobre el texto original.
    """
    result = list(docs)
    for doc in docs:
        if 'minusculas' in variants:
            variant = lowercase_variant(doc)
            if variant is not None:
                result.append(variant)
        if 'sin_puntuacion' in variants:
            result.append(unpunctuated_variant(doc))
        if 'ambas' in variants:
            lowered = lowercase_variant(doc)
            if lowered is not None:
                both = unpunctuated_variant(lowered)
                result.append(Document(f'{doc.doc_id}#ambas', both.text, both.spans, set(doc.sources)))
    return result


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


# Palabras que nunca son una mencion por si solas. El modelo a veces marca una suelta («una», «al»); ningun
# span gold del corpus propio esta formado solo por ellas.
FUNCTION_WORDS = frozenset({
    'a', 'al', 'como', 'con', 'de', 'del', 'el', 'en', 'es', 'esta', 'está', 'la', 'las', 'le', 'les', 'lo', 'los',
    'me', 'mi', 'muy', 'ni', 'no', 'o', 'para', 'pero', 'por', 'que', 'se', 'si', 'su', 'te', 'un', 'una', 'unas',
    'unos', 'y', 'ya',
})


def drop_function_word_spans(text: str, spans: Sequence[Span]) -> List[Span]:
    """Quita los spans formados solo por palabras funcionales."""
    return [s for s in spans if not all(w in FUNCTION_WORDS for w in re.findall(r'\w+', text[s.start:s.end].lower()))]


def clean_predictions(text: str, spans: Sequence[Span]) -> List[Span]:
    """Posproceso de las predicciones, igual que en backend/triage/ner_model.py: palabras completas y sin
    spans de solo palabras funcionales."""
    return drop_function_word_spans(text, snap_to_words(text, spans))


def snap_to_words(text: str, spans: Sequence[Span]) -> List[Span]:
    """
    Extiende cada span predicho hasta palabras completas: el modelo etiqueta subtokens y a veces abre o cierra
    una entidad dentro de una palabra («itando» por «vomitando»). Ningun span gold corta una palabra, asi que
    un span asi nunca seria exacto. Si al extenderse dos spans se pisan, se unen si tienen la misma etiqueta
    y, si no, gana el mas largo.
    """
    snapped: List[Span] = []
    for span in sorted(spans, key=lambda s: (s.start, s.end)):
        start, end = span.start, span.end
        while start > 0 and text[start - 1].isalnum() and text[start].isalnum():
            start -= 1
        while end < len(text) and text[end].isalnum() and text[end - 1].isalnum():
            end += 1
        if snapped and start < snapped[-1].end:
            previous = snapped[-1]
            if previous.label == span.label:
                snapped[-1] = Span(previous.start, max(previous.end, end), previous.label)
            elif end - start > previous.end - previous.start:
                snapped[-1] = Span(min(start, previous.start), end, span.label)
            continue
        snapped.append(Span(start, end, span.label))
    return snapped


# --------------------------------------------------------------------------- metricas y particiones

def prf_from_counts(c: Counter) -> Dict:
    precision = c['tp'] / (c['tp'] + c['fp']) if c['tp'] + c['fp'] else None
    recall = c['tp'] / (c['tp'] + c['fn']) if c['tp'] + c['fn'] else None
    if precision is None or recall is None:
        # Sin predicciones o sin entidades reales: F1 es 0 si hubo algun error y no definido si no hubo nada.
        f1 = 0.0 if c['fn'] or c['fp'] else None
    else:
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    rnd = lambda x: round(x, 3) if x is not None else None  # noqa: E731
    return {'tp': c['tp'], 'fp': c['fp'], 'fn': c['fn'], 'precision': rnd(precision), 'recall': rnd(recall), 'f1': rnd(f1)}


def _report(counts: Dict[str, Counter]) -> Dict[str, Dict]:
    report = {label: prf_from_counts(c) for label, c in counts.items()}
    report['micro'] = prf_from_counts(sum(counts.values(), Counter()))
    return report


def span_prf(gold: Dict[str, Sequence[Span]], predicted: Dict[str, Sequence[Span]]) -> Dict[str, Dict]:
    """
    P/R/F1 por etiqueta y micro con coincidencia exacta de inicio, fin y etiqueta. Se compara por tuplas y no
    por igualdad de dataclass: tras un importlib.reload(ner_data) (habitual en Colab) los spans creados antes
    y despues son de clases distintas y nunca serian iguales.
    """
    counts = {label: Counter() for label in ENTITY_LABELS}
    for doc_id in set(gold) | set(predicted):
        g = {(s.start, s.end, s.label) for s in gold.get(doc_id, [])}
        p = {(s.start, s.end, s.label) for s in predicted.get(doc_id, [])}
        for label in ENTITY_LABELS:
            gl = {s for s in g if s[2] == label}
            pl = {s for s in p if s[2] == label}
            counts[label]['tp'] += len(gl & pl)
            counts[label]['fp'] += len(pl - gl)
            counts[label]['fn'] += len(gl - pl)
    return _report(counts)


def span_prf_partial(gold: Dict[str, Sequence[Span]], predicted: Dict[str, Sequence[Span]]) -> Dict[str, Dict]:
    """
    P/R/F1 con coincidencia parcial: un predicho acierta si se solapa con un gold de la misma etiqueta.
    Emparejamiento uno a uno, primero los pares con mas solape, para que un span largo no acierte varios gold
    ni varios predichos acierten el mismo gold.
    """
    counts = {label: Counter() for label in ENTITY_LABELS}
    for doc_id in set(gold) | set(predicted):
        g = sorted({(s.start, s.end, s.label) for s in gold.get(doc_id, [])})
        p = sorted({(s.start, s.end, s.label) for s in predicted.get(doc_id, [])})
        pairs = sorted(((min(a[1], b[1]) - max(a[0], b[0]), i, j) for i, a in enumerate(g) for j, b in enumerate(p)
                        if a[2] == b[2] and min(a[1], b[1]) > max(a[0], b[0])), reverse=True)
        used_g, used_p = set(), set()
        for _, i, j in pairs:
            if i not in used_g and j not in used_p:
                used_g.add(i)
                used_p.add(j)
                counts[g[i][2]]['tp'] += 1
        for i, s in enumerate(g):
            if i not in used_g:
                counts[s[2]]['fn'] += 1
        for j, s in enumerate(p):
            if j not in used_p:
                counts[s[2]]['fp'] += 1
    return _report(counts)


def kfold(ids: Sequence[str], k: int, seed: int = 42) -> List[Tuple[List[str], List[str]]]:
    """Particiones (train, val) deterministas para validacion cruzada sobre el split dev."""
    shuffled = sorted(ids)
    random.Random(seed).shuffle(shuffled)
    folds = [shuffled[i::k] for i in range(k)]
    return [([x for j, f in enumerate(folds) if j != i for x in f], folds[i]) for i in range(k)]


def cv_summary(reports: Sequence[Dict[str, Dict]]) -> Dict[str, Dict]:
    """Media y desviacion (poblacional) de P/R/F1 por etiqueta y micro sobre las particiones."""
    import statistics

    def summary(label, key):
        values = [r[label][key] for r in reports if r[label][key] is not None]
        return {'media': round(statistics.mean(values), 3),
                'desviacion': round(statistics.pstdev(values), 3)} if values else None

    return {label: {key: summary(label, key) for key in ('precision', 'recall', 'f1')}
            for label in (*ENTITY_LABELS, 'micro')}


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
