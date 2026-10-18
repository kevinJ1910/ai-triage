"""
Deteccion de negacion clinica en espanol, al estilo de NegEx (Chapman et al., 2001).

Un hallazgo esta negado si un disparador lo precede dentro de una ventana de palabras ("no tiene
dolor en el pecho", "niega convulsiones", "sin fiebre ni vomito") o lo sigue de cerca ("toxicos
negativo"), sin un terminador de alcance en medio ("no tiene fiebre, pero vomita").

El disparador debe estar FUERA del hallazgo. "no respira" o "sin respuesta" describen hallazgos
presentes (apnea, inconsciencia): cuando el patron que se busca incluye la particula, no hay
disparador antes y el hallazgo cuenta como presente. Las pseudonegaciones ("no puede mover",
"casi no orino", "sin poder hablar") tampoco niegan lo que viene despues.

Todas las funciones esperan texto ya normalizado (minusculas y sin tildes, clinical_protocol._normalize_text).
"""
import re
from typing import Iterable, List, Optional, Tuple

WINDOW = 5  # Palabras que abarca un disparador previo.
POST_WINDOW = 3

PRE_TRIGGERS = (
    ('no',), ('niega',), ('negó',), ('nego',), ('niegan',), ('sin',), ('ni',), ('nunca',), ('tampoco',),
    ('descarta',), ('descartan',), ('ausencia', 'de'), ('libre', 'de'), ('ningun',), ('ninguna',),
    ('no', 'hay'), ('no', 'presenta'), ('no', 'refiere'),
)
POST_TRIGGERS = (('negativo',), ('negativa',), ('negativos',), ('descartado',), ('descartada',), ('ausente',))

# Verbos que, justo despues del disparador, lo convierten en descripcion de un hallazgo presente.
PSEUDO_VERBS_AFTER_NO = {
    'puede', 'puedo', 'pudo', 'pueden', 'podia', 'deja', 'para', 'paro', 'mejora', 'cede', 'quita',
    'tolera', 'tolero', 'despierta', 'responde', 'respira', 'reconoce', 'siente', 'abre', 'encuentro',
    'solo', 'logra', 'logro', 'sabe', 'dan', 'da', 'pasa',
}
PSEUDO_AFTER_SIN = {'poder', 'respirar', 'respuesta', 'responder', 'despertar', 'parar', 'embargo', 'control'}
# Pronombres atonos entre el "no" y el verbo: "no se le quita" (pseudo), "no se le corre al brazo" (niega).
CLITICS = {'se', 'le', 'les', 'me', 'te', 'lo', 'la', 'nos'}
# "casi no orino": la particula previa "casi" anula la negacion.
PSEUDO_BEFORE = {'no': {'casi'}}
# Tras "no he" / "no ha" el verbo decide: "no he vomitado" niega; "no he podido comer" no.
NEGATING_AFTER_HABER = {'tenido', 'presentado', 'vomitado', 'perdido', 'tomado', 'sentido', 'notado',
                        'pensado', 'hecho', 'bajado', 'cambiado', 'sangrado'}

# 'y'/'e' cierran el alcance: la negacion coordinada en espanol usa 'ni' ("sin fiebre ni tos"),
# mientras que "no tengo fiebre y me duele la cabeza" afirma la cefalea.
TERMINATOR_WORDS = {'pero', 'aunque', 'excepto', 'salvo', 'mientras', 'refiere', 'presenta', 'con', 'ahora', 'y', 'e'}
TERMINATOR_PHRASES = (('sin', 'embargo'),)
TERMINATOR_PUNCT = {'.', ',', ';', ':', '!', '?'}

_TOKEN_RE = re.compile(r"\w+|[.,;:!?]")


def _tokens(text: str) -> List[Tuple[str, int, int]]:
    return [(m.group(), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def _is_terminator(tokens, idx) -> bool:
    word = tokens[idx][0]
    if word in TERMINATOR_PUNCT or word in TERMINATOR_WORDS:
        return True
    return any(tuple(t[0] for t in tokens[idx:idx + len(p)]) == p for p in TERMINATOR_PHRASES)


def _trigger_at(tokens, idx, triggers) -> Optional[int]:
    """Longitud del disparador que empieza en idx, o None."""
    for trigger in sorted(triggers, key=len, reverse=True):
        if tuple(t[0] for t in tokens[idx:idx + len(trigger)]) == trigger:
            return len(trigger)
    return None


def _is_pseudo(tokens, idx, length) -> bool:
    word = tokens[idx][0]
    if length != 1:
        return False
    if idx > 0 and tokens[idx - 1][0] in PSEUDO_BEFORE.get(word, ()):
        return True
    nxt = idx + 1
    if word == 'sin':
        return nxt < len(tokens) and tokens[nxt][0] in PSEUDO_AFTER_SIN
    if word != 'no':
        return False
    while nxt < len(tokens) and tokens[nxt][0] in CLITICS:
        nxt += 1
    if nxt >= len(tokens):
        return False
    verb = tokens[nxt][0]
    if verb in ('he', 'ha', 'han', 'hemos'):
        # "no he vomitado" niega; "no he podido comer" describe un hallazgo presente.
        return nxt + 1 < len(tokens) and tokens[nxt + 1][0] not in NEGATING_AFTER_HABER
    return verb in PSEUDO_VERBS_AFTER_NO


def _negating_triggers(tokens):
    """Posiciones (inicio, longitud) de los disparadores previos que realmente niegan."""
    found = []
    for idx in range(len(tokens)):
        length = _trigger_at(tokens, idx, PRE_TRIGGERS)
        if length and not _is_pseudo(tokens, idx, length):
            found.append((idx, length))
    return found


def is_negated(text: str, start: int, end: int, window: int = WINDOW) -> bool:
    """True si el span text[start:end] esta dentro del alcance de una negacion."""
    tokens = _tokens(text)
    first = next((i for i, t in enumerate(tokens) if t[2] > start), len(tokens))
    last = next((i for i in range(len(tokens) - 1, -1, -1) if tokens[i][1] < end), -1)

    for trig_idx, length in _negating_triggers(tokens):
        trig_end = trig_idx + length
        if trig_end > first:
            continue
        between = range(trig_end, first)
        words_between = sum(1 for i in between if tokens[i][0] not in TERMINATOR_PUNCT)
        if words_between < window and not any(_is_terminator(tokens, i) for i in between):
            return True

    for idx in range(last + 1, min(len(tokens), last + 1 + POST_WINDOW)):
        if _is_terminator(tokens, idx):
            break
        if _trigger_at(tokens, idx, POST_TRIGGERS):
            return True
    return False


def find_affirmed(pattern: str, text: str, flags: int = 0) -> Optional[re.Match]:
    """Primera coincidencia del patron que no esta negada (sustituye a re.search en las reglas)."""
    for match in re.finditer(pattern, text, flags):
        if not is_negated(text, match.start(), match.end()):
            return match
    return None


def split_affirmed_negated(text: str, terms: Iterable[str]) -> Tuple[List[str], List[str]]:
    """Separa los terminos que aparecen en el texto en presentes y negados."""
    affirmed, negated = [], []
    for term in terms:
        matches = list(re.finditer(rf"\b{re.escape(term)}\b", text))
        if not matches:
            continue
        if any(not is_negated(text, m.start(), m.end()) for m in matches):
            affirmed.append(term)
        else:
            negated.append(term)
    return affirmed, negated


def strip_negated(text: str, window: int = WINDOW) -> str:
    """Elimina disparadores y su alcance: deja solo lo afirmado (para la recuperacion del RAG)."""
    tokens = _tokens(text)
    drop = set()
    for trig_idx, length in _negating_triggers(tokens):
        drop.update(range(trig_idx, trig_idx + length))
        words = 0
        for idx in range(trig_idx + length, len(tokens)):
            if _is_terminator(tokens, idx) or words >= window:
                break
            drop.add(idx)
            words += 1
    return ' '.join(t[0] for i, t in enumerate(tokens) if i not in drop and t[0] not in TERMINATOR_PUNCT)
