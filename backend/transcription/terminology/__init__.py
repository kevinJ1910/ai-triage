"""
Catalogos terminologicos versionados de la normalizacion por capas (ver README.md de este directorio).

Capas deterministas, en orden de prioridad ante empates de longitud:
  1. correccion_asr  errores foneticos de la transcripcion ('posartan' -> losartan).
  2. abreviatura     siglas clinicas ('HTA' -> hipertension arterial).
  3. diccionario     coloquialismos ('me falta el aire' -> disnea).
Se busca siempre la coincidencia mas larga, sin solapes y con limites de palabra, sobre el texto sin
tildes ni mayusculas. Las posiciones de cada coincidencia se refieren al texto original.
"""
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CATALOG_DIR = Path(__file__).resolve().parent

CATEGORIES = ('Sintoma', 'Signo', 'Diagnostico', 'Antecedente', 'Medicamento', 'Alergeno', 'Administrativo')
SOURCES = ('correccion_asr', 'abreviatura', 'diccionario')
CIE10 = 'CIE-10'
ATC = 'ATC'

_CIE10_RE = re.compile(r'^([A-Z])(\d{2})(?:\.?(\d))?$')
# Niveles 1 a 5 del ATC: A, A10, A10B, A10BA, A10BA02.
_ATC_RE = re.compile(r'^[A-Z](?:\d{2}(?:[A-Z](?:[A-Z](?:\d{2})?)?)?)?$')
_ALLERGY_CONTEXT_RE = re.compile(
    r'\balergi(?:a|as|co|ca|cos|cas)\b(?:\s+(?:a|al|con))?(?:[\s,]+[a-z]+){0,6}[\s,]*$'
)


@dataclass(frozen=True)
class Concept:
    term: str
    category: str
    code: Optional[str]
    code_system: Optional[str]


@dataclass(frozen=True)
class Match:
    start: int
    end: int
    raw: str
    concept: Concept
    source: str


def fold(text: str) -> str:
    """Minusculas y sin tildes, conservando la longitud para que los spans sirvan sobre el original."""
    out = []
    for ch in text:
        base = ''.join(c for c in unicodedata.normalize('NFKD', ch) if not unicodedata.combining(c)).lower()
        out.append(base if len(base) == 1 else ' ')
    return ''.join(out)


def _key(surface: str) -> str:
    return ' '.join(fold(surface).split())


def _read(name: str) -> dict:
    return json.loads((CATALOG_DIR / name).read_text(encoding='utf-8'))


def _concept(entry: dict) -> Concept:
    if entry.get('atc'):
        return Concept(entry['termino'], entry['categoria'], entry['atc'], ATC)
    if entry.get('cie10'):
        return Concept(entry['termino'], entry['categoria'], entry['cie10'], CIE10)
    return Concept(entry['termino'], entry['categoria'], None, None)


def _surface_entries() -> List[Tuple[str, Concept, str]]:
    """(forma de superficie, concepto, capa) de los tres catalogos, sin resolver conflictos."""
    entries = []
    for item in _read('coloquialismos.json')['terminos']:
        concept = _concept(item)
        for surface in [item['termino'], *item['variantes']]:
            entries.append((surface, concept, 'diccionario'))
    for item in _read('abreviaturas.json')['abreviaturas']:
        concept = _concept(item)
        for surface in [item['abreviatura'], *item['variantes']]:
            entries.append((surface, concept, 'abreviatura'))
    return entries


@lru_cache(maxsize=1)
def _lexicon() -> Dict[str, Tuple[Concept, str]]:
    lexicon: Dict[str, Tuple[Concept, str]] = {}
    for surface, concept, source in _surface_entries():
        lexicon.setdefault(_key(surface), (concept, source))
    for item in _read('correcciones_asr.json')['correcciones']:
        target = lexicon.get(_key(item['correccion']))
        if target:
            lexicon.setdefault(_key(item['error']), (target[0], 'correccion_asr'))
    return lexicon


@lru_cache(maxsize=1)
def _pattern() -> re.Pattern:
    # Mas largas primero: la alternancia de re devuelve la primera que casa en cada posicion.
    keys = sorted(_lexicon(), key=len, reverse=True)
    body = '|'.join(r'\s+'.join(re.escape(word) for word in key.split()) for key in keys)
    return re.compile(rf'(?<![a-z0-9])(?:{body})(?![a-z0-9])')


@lru_cache(maxsize=512)
def _find(text: str) -> Tuple[Match, ...]:
    folded = fold(text)
    lexicon = _lexicon()
    matches = []
    for found in _pattern().finditer(folded):
        concept, source = lexicon[' '.join(found.group(0).split())]
        matches.append(Match(found.start(), found.end(), text[found.start():found.end()], concept, source))
    return tuple(matches)


def find_concepts(text: str) -> List[Match]:
    """Conceptos del catalogo presentes en el texto, en orden de aparicion."""
    return list(_find(text or ''))


def in_allergy_context(text: str, start: int) -> bool:
    """True si el span que empieza en start sigue a 'alergico a', 'alergia al'... (hasta 6 palabras)."""
    prefix = fold(text[max(0, start - 80):start])
    return bool(_ALLERGY_CONTEXT_RE.search(prefix))


def lookup_term(term: str) -> Optional[Concept]:
    """Concepto cuyo termino o variante coincide exactamente con term (sin tildes ni mayusculas)."""
    found = _lexicon().get(_key(term or ''))
    return found[0] if found else None


@lru_cache(maxsize=1)
def cie10_catalog() -> dict:
    return _read('cie10.json')


@lru_cache(maxsize=1)
def _known_atc() -> frozenset:
    return frozenset(c.code for c, _ in _lexicon().values() if c.code_system == ATC)


def canonical_cie10(code: str) -> Optional[str]:
    """'R060', 'r06.0' -> 'R06.0'; 'R51X' (relleno de la tabla colombiana) -> 'R51'. None si no es CIE-10."""
    code = re.sub(r'\s', '', (code or '').upper())
    if len(code) == 4 and code.endswith('X'):
        code = code[:3]
    found = _CIE10_RE.match(code)
    if not found:
        return None
    letter, digits, sub = found.groups()
    return f'{letter}{digits}.{sub}' if sub else f'{letter}{digits}'


def validate_code(code: Optional[str], code_system: Optional[str]) -> Tuple[Optional[str], Optional[bool]]:
    """
    Devuelve (codigo canonico, valido). valido es True si el codigo esta en el catalogo local,
    False si esta mal formado (o falta en un catalogo completo) y None si no se puede verificar:
    sin codigo, o bien formado pero ausente de un catalogo parcial.
    """
    if not code:
        return None, None
    if code_system == ATC:
        normalized = re.sub(r'\s', '', code.upper())
        if not _ATC_RE.match(normalized):
            return code, False
        return normalized, True if normalized in _known_atc() else None
    canonical = canonical_cie10(code)
    if canonical is None:
        return code, False
    catalog = cie10_catalog()
    if canonical in catalog['codigos']:
        return canonical, True
    return canonical, False if catalog.get('completo') else None


def validate_catalogs() -> List[str]:
    """Errores de consistencia de los catalogos; vacio si son validos."""
    errors = []
    seen: Dict[str, str] = {}
    for surface, concept, source in _surface_entries():
        key = _key(surface)
        if concept.category not in CATEGORIES:
            errors.append(f'{concept.term!r}: categoria invalida {concept.category!r}')
        owner = seen.get(key)
        if owner and owner != concept.term:
            errors.append(f'{surface!r} pertenece a {owner!r} y a {concept.term!r}')
        seen[key] = concept.term
        _, valid = validate_code(concept.code, concept.code_system)
        if concept.code and not valid:
            errors.append(f'{concept.term!r}: codigo {concept.code} sin verificar en el catalogo local')
    for item in _read('correcciones_asr.json')['correcciones']:
        if _key(item['correccion']) not in seen:
            errors.append(f'correccion {item["error"]!r}: {item["correccion"]!r} no esta en los catalogos')
        if _key(item['error']) in seen:
            errors.append(f'correccion {item["error"]!r}: el error ya es una forma valida del catalogo')
    return errors


def catalog_versions() -> Dict[str, str]:
    return {name: _read(f'{name}.json')['version'] for name in ('coloquialismos', 'abreviaturas', 'correcciones_asr', 'cie10')}


def clear_caches() -> None:
    """Para pruebas o tras importar un catalogo nuevo en el mismo proceso."""
    for cached in (_lexicon, _pattern, _find, cie10_catalog, _known_atc):
        cached.cache_clear()
