"""
Fusion hibrida de entidades (paso 3.2 del plan):

  RoBERTa (ner_model)  menciones de SINTOMA, ENFERMEDAD y FARMACO con su span exacto.
  Catalogo             normaliza cada mencion al termino clinico (y aporta lo que el modelo no vio).
  negation.py          decide si la mencion esta negada; manda sobre el modelo y sobre el LLM.
  Contexto             FARMACO tras 'alergico a' -> alergia; ENFERMEDAD con senal de antecedente -> history.
  Gemini (opcional)    confirma las menciones de baja confianza y aporta alergias y antecedentes; sus
                       terminos extra solo se aceptan si tienen apoyo literal en el relato.

Funciones puras: no cargan el modelo ni llaman a la red.
"""
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from transcription.terminology import fold, in_allergy_context

from .negation import is_negated, is_preserved_or_privative

ENTITY_KEYS = ("symptoms", "diagnoses", "medications", "allergies", "history", "negated_findings")
_CATEGORY_TO_ENTITY = {
    "Sintoma": "symptoms", "Signo": "symptoms", "Diagnostico": "diagnoses",
    "Antecedente": "history", "Medicamento": "medications",
}
_HISTORY_CUE = re.compile(
    r"\b(antecedentes?|sufre|sufro|padece|padezco|conocid[oa]|diagnosticad[oa]|cronic[oa]|historia)\b"
    r"(?:\s+\w+){0,5}\s*$"
)
_STOPWORDS = {"de", "del", "la", "el", "los", "las", "un", "una", "en", "y", "a", "al", "con", "por", "que",
              "se", "le", "me", "mi", "su", "lo", "muy", "mas", "tipo"}


def _key(term: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", fold(term or "")).split())


def _same(a: str, b: str) -> bool:
    ka, kb = _key(a), _key(b)
    return bool(ka and kb) and (ka == kb or f" {ka} " in f" {kb} " or f" {kb} " in f" {ka} ")


def _add(entities: Dict[str, List[str]], key: Optional[str], term: str) -> None:
    if key and term and not any(_same(term, existing) for existing in entities[key]):
        entities[key].append(term)


def _overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _covers(term: Dict[str, Any], bounds: Tuple[int, int], ratio: float = 0.7) -> bool:
    """El concepto del catalogo cubre la mencion si se solapa con al menos el 70 % de ella."""
    overlap = min(term["end"], bounds[1]) - max(term["start"], bounds[0])
    return overlap >= ratio * (bounds[1] - bounds[0])


def entities_from_terms(normalized_terms: Iterable[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Entidades solo con el catalogo: los negados van aparte y un farmaco tras 'alergico a' es una alergia."""
    entities: Dict[str, List[str]] = {key: [] for key in ENTITY_KEYS}
    for item in normalized_terms:
        if item["negated"]:
            # Un farmaco negado ("no toma losartan") no es un hallazgo descartado.
            key = None if item["category"] in ("Medicamento", "Alergeno", "Administrativo") else "negated_findings"
        elif item["allergy"]:
            key = "allergies"
        else:
            key = _CATEGORY_TO_ENTITY.get(item["category"])
        _add(entities, key, item["medical_term"])
    return entities


def _entity_key(label: str, text: str, start: int, catalog: List[Dict[str, Any]]) -> Optional[str]:
    if label == "SINTOMA":
        return "symptoms"
    if label == "FARMACO":
        return "allergies" if in_allergy_context(text, start) else "medications"
    if label == "ENFERMEDAD":
        if any(t["category"] == "Antecedente" for t in catalog):
            return "history"
        return "history" if _HISTORY_CUE.search(fold(text[max(0, start - 60):start])) else "diagnoses"
    return None


def _support_state(term: str, folded_text: str) -> Optional[bool]:
    """
    Estado de respaldo literal de un termino del LLM en el relato plegado:
    - None si ninguna palabra de contenido (4+ letras) aparece en el relato.
    - False si el termino es privativo/funcion conservada o alguna palabra clave aparece solo negada.
    - True si sus palabras encontradas en el relato tienen al menos una ocurrencia afirmada.
    """
    folded_term = _key(term)
    if folded_term and is_preserved_or_privative(folded_term, 0, len(folded_term)):
        return False
    words = [w for w in folded_term.split() if len(w) >= 4 and w not in _STOPWORDS]
    matched_groups = []
    for w in words:
        stem = re.escape(w[:max(4, len(w) - 2)])
        matches = list(re.finditer(rf"\b{stem}\w*", folded_text))
        if matches:
            matched_groups.append(matches)
    if not matched_groups:
        return None
    for matches in matched_groups:
        if all(
            is_negated(folded_text, m.start(), m.end()) or is_preserved_or_privative(folded_text, m.start(), m.end())
            for m in matches
        ):
            return False
    return True


def _supported(term: str, folded_text: str) -> bool:
    """Un termino del LLM tiene apoyo afirmado si aparece en el relato y no esta negado."""
    return _support_state(term, folded_text) is True


def fuse_entities(text: str, ner_spans: List[Dict[str, Any]], normalized_terms: List[Dict[str, Any]],
                  llm_entities: Optional[Dict[str, List[str]]] = None,
                  min_score: float = 0.6) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
    """
    Devuelve (entidades, detalle por mencion del NER). text debe ser el mismo sobre el que se calcularon
    ner_spans y normalized_terms (el relato limpio del triaje).
    """
    folded = fold(text)
    llm_entities = llm_entities or {}
    llm_terms = [t for key in ("symptoms", "diagnoses", "medications", "allergies", "history")
                 for t in llm_entities.get(key) or []]
    entities: Dict[str, List[str]] = {key: [] for key in ENTITY_KEYS}
    details: List[Dict[str, Any]] = []
    covered: List[Tuple[int, int]] = []

    for span in ner_spans:
        bounds = (span["start"], span["end"])
        catalog = [t for t in normalized_terms if _overlaps(bounds, (t["start"], t["end"]))]
        # Solo un concepto que cubre la mencion la normaliza: 'dolor' no sustituye a 'dolor punzante en el talon'.
        equivalent = [t for t in catalog if _covers(t, bounds)]
        raw = text[span["start"]:span["end"]].strip()
        llm_confirms = any(_same(raw, t) or any(_same(c["medical_term"], t) for c in catalog) for t in llm_terms)
        kept = span["score"] >= min_score or bool(catalog) or llm_confirms
        negated = is_negated(folded, *bounds) or (
            span["label"] != "FARMACO" and is_preserved_or_privative(folded, *bounds)
        )
        term = max(equivalent, key=lambda t: t["end"] - t["start"])["medical_term"] if equivalent else raw
        key = _entity_key(span["label"], text, span["start"], equivalent)
        if negated:
            key = None if span["label"] == "FARMACO" else "negated_findings"
        details.append({**span, "term": term, "negated": negated, "entity": key if kept else None,
                        "confirmed_by": [s for s, ok in (("catalogo", bool(catalog)), ("llm", llm_confirms)) if ok],
                        "kept": kept})
        if kept:
            covered.append(bounds)
            _add(entities, key, term)

    # Lo que el catalogo detecto y el modelo no (p. ej. antecedentes en sigla o alergenos no farmacologicos).
    remaining = [t for t in normalized_terms if not any(_overlaps((t["start"], t["end"]), c) for c in covered)]
    for key, terms in entities_from_terms(remaining).items():
        for term in terms:
            _add(entities, key, term)

    # Terminos del LLM sin mencion del NER ni del catalogo: solo si el relato los respalda y no estan negados.
    for key in ("symptoms", "diagnoses", "medications", "allergies", "history"):
        for term in llm_entities.get(key) or []:
            if any(_same(term, neg) for neg in entities["negated_findings"]):
                continue
            if any(_same(term, existing) for k in ENTITY_KEYS for existing in entities[k]):
                continue
            support = _support_state(term, folded)
            if support is True:
                _add(entities, key, term)
            elif support is False and key not in ("medications", "allergies"):
                _add(entities, "negated_findings", term)
    for term in llm_entities.get("negated_findings") or []:
        if not any(_same(term, existing) for k in ENTITY_KEYS for existing in entities[k]):
            _add(entities, "negated_findings", term)
    return entities, details
