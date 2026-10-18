"""
Lista de casos a revisar segun la guia de limites (backend/triage/benchmark/GUIA_LIMITES.md).

Solo mira las anotaciones gold y los transcripts, nunca predicciones de un modelo: por eso puede recorrer
dev y test sin contaminar la evaluacion. Cada regla lleva el mismo identificador que en la guia. Las
propuestas son orientativas: decide el revisor aplicando la prueba de la mencion minima.

    python ml/ner/revision_corpus.py                      # escribe backend/triage/benchmark/revision/casos_a_revisar.md
    python ml/ner/revision_corpus.py --json revision.json
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from error_analysis import DEFAULT_CORPUS, _fold, audit_corpus  # noqa: E402

DEFAULT_OUTPUT = DEFAULT_CORPUS.parent / 'revision' / 'casos_a_revisar.md'
NER_TYPES = ('symptoms', 'diagnoses', 'history', 'medications', 'allergies')

_INTENSITY = r'muy|mucho|mucha|much[ií]sim[oa]|bastante|demasiado|un poco|un poquito|un poquitico|poquito'
_SEVERITY = r'leve|fuerte|intens[oa]|marcad[oa]|sever[oa]|grado \w+'

# Reglas sobre el texto de cada span: (id, tipos afectados, patron, como se propone el nuevo span).
SPAN_RULES = [
    ('L1', 'Intensidad o gravedad en el borde', NER_TYPES,
     re.compile(rf'^(?:{_INTENSITY})\s+(?!de\b)|(?:\s+(?:{_INTENSITY}))*\s+(?:{_INTENSITY}|{_SEVERITY})$',
                re.IGNORECASE)),
    ('L2', 'Artículo indefinido inicial', NER_TYPES,
     re.compile(r'^(?:un|una|unos|unas)\s+(?!poc|poquit)', re.IGNORECASE)),
    ('L3', 'Verbo de marco inicial', ('symptoms', 'diagnoses'),
     re.compile(r'^(?:tengo|tiene|est[aá]|estoy|sigue|sigo|se est[aá] poniendo|se puso|se pone|siento que|'
                r'siento como|me sali[oó]|le sali[oó])\s+(?!que\b)(?:como\s+)?', re.IGNORECASE)),
    ('L4', 'Instrumento o circunstancia de la lesión', ('diagnoses',),
     re.compile(r'\s+(?:con|pelando|jugando|cortando)\s+(?!comida\b).*$', re.IGNORECASE)),
    ('L5', 'Tiempo, número de veces o desencadenante', ('symptoms', 'diagnoses'),
     re.compile(r'\s+(?:desde|hace|cuando|ayer|anoche|\w+ veces)\b.*$', re.IGNORECASE)),
]
# Excepciones: la circunstancia es la propia condicion («se atoro con un pedazo de comida») y la frecuencia
# que define el hallazgo («respira muy de vez en cuando» es bradipnea).
EXCEPTIONS = {'L4': re.compile(r'^se atoró\b', re.IGNORECASE),
              'L5': re.compile(r'de vez en cuando', re.IGNORECASE)}

# Reglas sobre el transcript: menciones que la guia pide anotar y no tienen span.
TEXT_RULES = [
    ('L6', 'Gestación sin anotar (con su edad gestacional)', 'diagnoses',
     re.compile(r'\b(?:embarazad[ao]|gestante)(?:\s+de\s+[\w ]{1,20}?\s(?:semanas|meses))?|\b\w+\s+meses de embarazo',
                re.IGNORECASE)),
    ('L7', 'Hallazgo normal sin anotar como negado', 'symptoms',
     re.compile(r'\b(?:saturaci[oó]n normal|marcha conservada|consciente|orientad[oa]|alerta|respira bien|'
                r'lo mueve bien|camina bien|comiendo bien|come bien)\b', re.IGNORECASE)),
    ('L8', 'Evento traumático sin anotar', 'diagnoses',
     # El evento con su medio o altura («de la escalera», «por un bus»), que mide la energia del trauma.
     re.compile(r'\b(?:me ca[ií]|se cay[oó]|se ha ca[ií]do|ca[ií]da|choque|choc[oó]|atropell\w+|accidente)'
                r'(?:\s+(?:de|del|en|por)\s+(?:(?:la|el|un|una)\s+)?\w+)?', re.IGNORECASE)),
]

# L9: decisiones de tipo de la guia (signo observable -> symptoms; nombre de enfermedad o sindrome -> diagnoses).
LABEL_RULES = [
    (re.compile(r'^deshidrataci[oó]n$', re.IGNORECASE), 'symptoms', 'diagnoses',
     'nombre de síndrome; «signos de deshidratación» sí es symptoms'),
    (re.compile(r'c[oó]lico renal', re.IGNORECASE), 'symptoms', 'diagnoses', 'nombre de síndrome'),
    (re.compile(r'chuec|torcid', re.IGNORECASE), 'diagnoses', 'symptoms',
     'deformidad observada: es un signo aunque sugiera una fractura'),
]


def _span_positions(case: Dict, types: Sequence[str]) -> List[tuple]:
    text, found = case['transcript'], []
    for etype in types:
        for item in case['entities'].get(etype, []):
            pos = text.find(item['text'])
            if pos >= 0:
                found.append((pos, pos + len(item['text']), etype, item))
    return found


def review_candidates(cases: Sequence[Dict]) -> List[Dict]:
    """Una fila por propuesta: caso, split, regla, tipo, span actual y propuesta."""
    rows: List[Dict] = []

    def add(case, rule, title, etype, current, proposal, note=''):
        rows.append({'caso': case['id'], 'split': case['split'], 'regla': rule, 'titulo': title, 'tipo': etype,
                     'actual': current, 'propuesta': proposal, 'nota': note})

    for case in cases:
        for etype in NER_TYPES:
            for item in case['entities'].get(etype, []):
                text = item['text']
                applicable = [(rule, title, pattern) for rule, title, types, pattern in SPAN_RULES
                              if etype in types and not (rule in EXCEPTIONS and EXCEPTIONS[rule].search(text))]
                matched = [rule for rule in applicable if rule[2].search(text)]
                if matched:
                    # Una sola propuesta por span: todas las reglas, hasta que no cambie («sigue muy dormido»
                    # pierde el marco y despues la intensidad).
                    proposal, previous = text, None
                    while proposal != previous:
                        previous = proposal
                        for _, _, pattern in applicable:
                            proposal = pattern.sub('', proposal).strip()
                    others = [rule for rule, _, _ in matched[1:]]
                    note = 'comprobar que lo que queda sigue siendo el mismo hallazgo'
                    add(case, matched[0][0], matched[0][1], etype, text, proposal,
                        note + (f" (también {', '.join(others)})" if others else ''))
                for pattern, wrong, right, reason in LABEL_RULES:
                    if etype == wrong and pattern.search(text):
                        add(case, 'L9', 'Tipo de entidad', etype, text, f'{text} → {right}', reason)

        spans = _span_positions(case, ('symptoms', 'diagnoses', 'history', 'vitals'))
        for rule, title, etype, pattern in TEXT_RULES:
            for match in pattern.finditer(case['transcript']):
                covered = [s for s in spans if s[0] <= match.start() and match.end() <= s[1]]
                if covered:
                    continue
                overlapping = [s[3]['text'] for s in spans if s[0] < match.end() and match.start() < s[1]]
                note = f"se solapa con «{overlapping[0]}»: ampliar ese span" if overlapping else ''
                proposal = f"añadir {etype}: «{match.group(0)}»" + (' (negated: true)' if rule == 'L7' else '')
                add(case, rule, title, etype, '', proposal, note)

    audit = audit_corpus(cases)['detalle']
    by_id = {c['id']: c for c in cases}
    already = {(r['caso'], _fold(r['propuesta'])) for r in rows}
    for row in audit.get('anotado_aqui_no_alla', []):
        if any(caso == row['caso'] and _fold(row['texto']) in proposal for caso, proposal in already):
            continue
        add(by_id[row['caso']], 'A1', 'Texto anotado en otros casos y aquí no', '', '',
            f"valorar «{row['texto']}»", row['contexto'].strip())
    for row in audit.get('borde_sospechoso', []):
        add(by_id[row['caso']], 'A2', 'Borde en palabra funcional', row['tipo'], row['texto'], '',
            'el span parece incompleto')
    order = {rule: i for i, rule in enumerate(['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'L8', 'L9', 'A1', 'A2'])}
    return sorted(rows, key=lambda r: (order[r['regla']], r['split'], r['caso']))


def render_markdown(rows: Sequence[Dict], corpus_name: str) -> str:
    counts = Counter(r['regla'] for r in rows)
    per_split = Counter(r['split'] for r in rows)
    lines = [
        '# Casos a revisar según la guía de límites',
        '',
        f'Generado con `python ml/ner/revision_corpus.py` a partir de `{corpus_name}`. No edites este fichero a mano: '
        'cambia el corpus y vuelve a generarlo. La guía está en `GUIA_LIMITES.md`.',
        '',
        f"**{len(rows)} propuestas** ({per_split['dev']} en `dev`, {per_split['test']} en `test`). Son orientativas: "
        'decide el revisor aplicando la prueba de la mención mínima. Las del `test` se corrigen con las mismas reglas, '
        'sin mirar ningún resultado del sistema sobre esos casos.',
        '',
        '| Regla | Propuestas |',
        '| :--- | ---: |',
    ]
    titles = {}
    for row in rows:
        titles.setdefault(row['regla'], row['titulo'])
    lines += [f'| {rule} · {titles[rule]} | {counts[rule]} |' for rule in titles]
    for rule, title in titles.items():
        lines += ['', f'## {rule} · {title}', '', '| Caso | Split | Tipo | Span actual | Propuesta | Nota |',
                  '| :--- | :--- | :--- | :--- | :--- | :--- |']
        for row in rows:
            if row['regla'] != rule:
                continue
            cells = [row['caso'], row['split'], row['tipo'] or '—',
                     f"`{row['actual']}`" if row['actual'] else '—', row['propuesta'] or '—', row['nota'] or '']
            lines.append('| ' + ' | '.join(c.replace('|', '\\|') for c in cells) + ' |')
    return '\n'.join(lines) + '\n'


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--json', type=Path)
    options = parser.parse_args(argv)
    rows = review_candidates(json.loads(options.corpus.read_text(encoding='utf-8')))
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(render_markdown(rows, options.corpus.name), encoding='utf-8')
    if options.json:
        options.json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(rows)} propuestas -> {options.output}')
    print(dict(Counter(r['regla'] for r in rows)))


if __name__ == '__main__':
    main()
