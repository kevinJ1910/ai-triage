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

from transcription.terminology import fold, in_allergy_context, lookup_term

from .negation import is_negated, is_preserved_or_privative

ENTITY_KEYS = ("symptoms", "diagnoses", "medications", "allergies", "history", "negated_findings")
_CATEGORY_TO_ENTITY = {
    "Sintoma": "symptoms", "Signo": "symptoms", "Diagnostico": "diagnoses",
    "Antecedente": "history", "Medicamento": "medications",
}
_HISTORY_TRIGGER_RE = re.compile(
    r"\b("
    r"antecedentes?|historia\s+clinica|historia\s+de|de\s+base|patologias?\s+de\s+base|"
    r"enfermedades?\s+de\s+base|comorbilidad(?:es)?|sufre|sufro|sufrimos|padece|padezco|"
    r"conocid[oa]|diagnosticad[oa]|cronic[oa]s?|operad[oa]s?|me\s+operaron|le\s+operaron|"
    r"cirugia\s+(?:previa|de)|tuve\s+un[a]?|tuvo\s+un[a]?|ya\s+me\s+dio|ya\s+le\s+dio|"
    r"en\s+tratamiento\s+(?:con|para|por)|en\s+manejo\s+(?:con|para|por)|"
    r"soy\s+(?:hipertens[oa]|diabet[ic][oa]|asmat[ic][oa]|epilept[ic][oa]|hipotiroid[e][oa]|cardiopata|ren[al]|oncologic[oa])"
    r")\b",
    re.I,
)
_ACUTE_TRANSITION_RE = re.compile(
    r"\b("
    r"pero\s+hoy|hoy\s+vengo|vengo\s+por|consulta\s+por|motivo\s+de\s+consulta|"
    r"actualmente|ahora\s+(?:tengo|tiene|siento|siente|presenta)|en\s+este\s+momento|"
    r"acaba\s+de|temo\s+que\s+sea|creo\s+que\s+(?:es|sea)|sospecha\s+de|"
    r"impresion\s+diagnostica|cuadro\s+agudo|episodio\s+actual"
    r")\b",
    re.I,
)
_POST_HISTORY_CUE_RE = re.compile(
    r"^\s*(?:desde\s+hace\s+\d+\s*(?:anos|meses)|hace\s+\d+\s*anos|cronic[oa]s?|"
    r"de\s+base|controlad[oa]|en\s+tratamiento|en\s+manejo|diagnosticad[oa]\s+hace)\b",
    re.I,
)
_ACUTE_CONDITION_RE = re.compile(
    r"\b("
    r"agud[oa]s?|crisis|ataque|estatus|estado\s+epileptico|infarto\s+agudo|"
    r"fractura|esguince|luxacion|herida|quemadura|contusion|traumatismo|"
    r"mordedura|picadura|cuerpo\s+extrano|atragantamiento|intoxicacion|sobredosis|"
    r"autolesion|suicidio|abuso|accidente|anafilaxia|choque|shock|paro|"
    r"hemorragia|sangrado|apendicitis\s+aguda|colico|peritonitis|parto|aborto|ectopico"
    r")\b",
    re.I,
)
_CHRONIC_BACKGROUND_RE = re.compile(
    r"\b("
    r"hipertension|hipertens[oa]|hta|diabetes|diabet[ic][oa]|dm[12]?|"
    r"asma|asmat[ic][oa]|epoc|enfisema|hipotiroidismo|hipertiroidismo|tiroides|"
    r"dislipidemia|colesterol|trigliceridos|gota|artritis|artrosis|fibromialgia|"
    r"lupus|epilepsia|epilept[ic][oa]|insuficiencia\s+renal|enfermedad\s+renal|"
    r"dialisis|hemodialisis|insuficiencia\s+cardiaca|falla\s+cardiaca|cardiopatia|"
    r"arritmia|fibrilacion\s+auricular|marcapasos|protesis\s+valvular|"
    r"gastritis|reflujo|erge|ulcera\s+gastrica|cirrosis|hepatitis|vih|sida|"
    r"tuberculosis|cancer|neoplasia|tumor\s+maligno|obesidad|obes[oa]|"
    r"tabaquismo|fumador[a]?|alcoholismo|alzheimer|parkinson|demencia|"
    r"hiperplasia\s+prostatica|prostata|anticoagulad[oa]|infarto\s+antiguo|secuelas"
    r")\b",
    re.I,
)
_STOPWORDS = {"de", "del", "la", "el", "los", "las", "un", "una", "en", "y", "a", "al", "con", "por", "que",
              "se", "le", "me", "mi", "su", "lo", "muy", "mas", "tipo"}
_DANGLING_PREPOSITION_RE = re.compile(r"^(?:de|del|al|en|con|por|para)\s+\w+$", re.I)
_BRIDGE_CONNECTOR_RE = re.compile(r"^\s*(?:de|del|en el|en la|al)?\s*$", re.I)
_CONVERSATIONAL_PREFIX_RE = re.compile(
    r"^(?:temo que sea(?: un| una)?|creo que (?:es|sea|tengo)(?: un| una)?|"
    r"siento (?:mucho|mucha|un poco de)?|(?:no )?(?:he|ha) tenido|tenido|"
    r"(?:con )?antecedentes?(?: personales?)? de|historia de|"
    r"sufro(?: de)?|sufre(?: de)?|padezco(?: de)?|padece(?: de)?|"
    r"diagnosticad[oa] (?:con|de|por)|operad[oa] de)\s+",
    re.I,
)
_INTENSIFIER_RE = re.compile(r"\b(?:mucho|mucha|muchos|muchas|bastante|demasiado|un poco de|un poquito de)\b", re.I)


def _key(term: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", fold(term or "")).split())


def _canonical_term(term: str) -> str:
    """Si el termino coincide con una entrada del catalogo o correccion ASR, devuelve su forma canonica."""
    cleaned = _CONVERSATIONAL_PREFIX_RE.sub("", (term or "").strip()).strip()
    if not cleaned:
        return ""
    concept = lookup_term(cleaned)
    if concept:
        return concept.term
    deintensified = " ".join(_INTENSIFIER_RE.sub("", cleaned).split())
    if deintensified and deintensified != cleaned:
        concept = lookup_term(deintensified)
        if concept:
            return concept.term
    return cleaned


def _same(a: str, b: str) -> bool:
    ka, kb = _key(_canonical_term(a)), _key(_canonical_term(b))
    if not (ka and kb):
        return False
    if ka == kb or f" {ka} " in f" {kb} " or f" {kb} " in f" {ka} ":
        return True
    # Raiz compartida (>= 6 letras) para variantes morfologicas de una sola palabra (ej. losartan/losartanicos)
    if " " not in ka and " " not in kb and min(len(ka), len(kb)) >= 6:
        stem_len = min(len(ka), len(kb), 7)
        if ka[:stem_len] == kb[:stem_len]:
            return True
    return False


def _add(entities: Dict[str, List[str]], key: Optional[str], term: str) -> None:
    if not key or not term:
        return
    norm_term = _canonical_term(term)
    # Si llega un fragmento preposicional truncado ('de miocardio') y el antecedente inmediato es 'infarto agudo', unirlos.
    if _DANGLING_PREPOSITION_RE.match(_key(norm_term)):
        if entities[key]:
            combined = f"{entities[key][-1]} {norm_term}"
            concept = lookup_term(combined)
            if concept:
                entities[key][-1] = concept.term
            elif "infarto" in _key(entities[key][-1]) and "miocardio" in _key(norm_term):
                entities[key][-1] = "infarto agudo de miocardio"
        return
    if not any(_same(norm_term, existing) for existing in entities[key]):
        entities[key].append(norm_term)


def _merge_adjacent_spans(text: str, spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Une spans consecutivos de la misma etiqueta separados solo por conectores breves ('de', 'del')."""
    if not spans:
        return []
    merged: List[Dict[str, Any]] = []
    for span in sorted(spans, key=lambda s: (s["start"], s["end"])):
        if merged and merged[-1]["label"] == span["label"]:
            prev = merged[-1]
            gap = text[prev["end"]:span["start"]]
            if len(gap) <= 6 and _BRIDGE_CONNECTOR_RE.match(fold(gap)):
                prev["end"] = span["end"]
                prev["text"] = text[prev["start"]:prev["end"]]
                prev["score"] = round((prev["score"] + span["score"]) / 2, 4)
                continue
        merged.append(dict(span))
    return merged


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


def _in_history_context(text: str, start: int, end: Optional[int] = None) -> bool:
    """
    Determina si la mencion en [start, end] cumple funcion de antecedente patologico/quirurgico
    segun el contexto previo (incluyendo enumeraciones separadas por comas o 'y'), interno o posterior.
    """
    folded_text = fold(text or "")
    if not folded_text:
        return False
    span_end = end if end is not None else start
    span_slice = folded_text[start:span_end]
    if span_slice and _ACUTE_CONDITION_RE.search(span_slice):
        prefix_short = folded_text[max(0, start - 50):start]
        if not re.search(r"\b(?:tuve|tuvo|ya me dio|ya le dio|antigu[oa]|previ[oa]|operad[oa])\b", prefix_short):
            return False

    prefix = folded_text[max(0, start - 120):start]
    triggers = list(_HISTORY_TRIGGER_RE.finditer(prefix))
    if triggers:
        after_last_trigger = prefix[triggers[-1].end():]
        if not _ACUTE_TRANSITION_RE.search(after_last_trigger):
            return True

    if span_slice and _HISTORY_TRIGGER_RE.search(span_slice):
        return True

    if span_end < len(folded_text):
        suffix = folded_text[span_end:min(len(folded_text), span_end + 45)]
        if _POST_HISTORY_CUE_RE.search(suffix):
            return True
    return False


def _is_chronic_background_term(term: str) -> bool:
    folded = _key(term)
    if not folded or _ACUTE_CONDITION_RE.search(folded):
        return False
    return bool(_CHRONIC_BACKGROUND_RE.search(folded))


def _term_in_history_context(raw_term: str, norm_term: str, text: str) -> bool:
    if not text:
        return False
    folded_text = fold(text)
    for candidate in (raw_term, norm_term):
        key_cand = _key(candidate)
        if not key_cand:
            continue
        words = [w for w in key_cand.split() if len(w) >= 4 and w not in _STOPWORDS]
        for w in words:
            stem = re.escape(w[:max(4, len(w) - 2)])
            for match in re.finditer(rf"\b{stem}\w*", folded_text):
                if _in_history_context(text, match.start(), match.end()):
                    return True
    return False


def _resolve_bucket_for_term(default_key: str, raw_term: str, norm_term: str, text: str = "") -> str:
    if default_key in ("negated_findings", "allergies"):
        return default_key
    folded_raw = fold(raw_term or "")
    if _HISTORY_TRIGGER_RE.search(folded_raw) and not _ACUTE_CONDITION_RE.search(fold(norm_term)):
        return "history"
    concept = lookup_term(norm_term)
    if concept:
        if concept.category == "Antecedente":
            return "history"
        if concept.category == "Medicamento":
            return "medications"
        if concept.category in ("Sintoma", "Signo"):
            return "symptoms"
        if concept.category == "Diagnostico":
            if default_key == "history":
                return "history"
            if text and _term_in_history_context(raw_term, norm_term, text):
                return "history"
            return "diagnoses"
    if _is_chronic_background_term(norm_term):
        return "history"
    if default_key == "diagnoses" and text and _term_in_history_context(raw_term, norm_term, text):
        return "history"
    return default_key


def _entity_key(
    label: str,
    text: str,
    start: int,
    catalog: List[Dict[str, Any]],
    end: Optional[int] = None,
    norm_term: str = "",
) -> Optional[str]:
    if label == "SINTOMA":
        concept = lookup_term(norm_term) if norm_term else None
        if concept and concept.category == "Antecedente":
            return "history"
        return "symptoms"
    if label == "FARMACO":
        return "allergies" if in_allergy_context(text, start) else "medications"
    if label == "ENFERMEDAD":
        if any(t["category"] == "Antecedente" for t in catalog):
            return "history"
        concept = lookup_term(norm_term) if norm_term else None
        if concept:
            if concept.category == "Antecedente":
                return "history"
            if concept.category in ("Sintoma", "Signo"):
                return "symptoms"
            if concept.category == "Medicamento":
                return "allergies" if in_allergy_context(text, start) else "medications"
        if _is_chronic_background_term(norm_term) or _in_history_context(text, start, end):
            return "history"
        return "diagnoses"
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


def canonicalize_entities(raw_entities: Optional[Dict[str, Any]], text: str = "") -> Dict[str, List[str]]:
    """Normaliza, reclasifica segun proposito clinico, une fragmentos preposicionales y deduplica entidades."""
    cleaned: Dict[str, List[str]] = {key: [] for key in ENTITY_KEYS}
    if not isinstance(raw_entities, dict):
        return cleaned
    for key in ENTITY_KEYS:
        for term in raw_entities.get(key) or []:
            if isinstance(term, str) and term.strip():
                norm_term = _canonical_term(term)
                target_key = _resolve_bucket_for_term(key, term, norm_term, text=text)
                _add(cleaned, target_key, term)
    return cleaned


def fuse_entities(text: str, ner_spans: List[Dict[str, Any]], normalized_terms: List[Dict[str, Any]],
                  llm_entities: Optional[Dict[str, List[str]]] = None,
                  min_score: float = 0.6) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
    """
    Devuelve (entidades, detalle por mencion del NER). text debe ser el mismo sobre el que se calcularon
    ner_spans y normalized_terms (el relato limpio del triaje).
    """
    folded = fold(text)
    llm_entities = canonicalize_entities(llm_entities, text=text)
    llm_terms = [t for key in ("symptoms", "diagnoses", "medications", "allergies", "history")
                 for t in llm_entities.get(key) or []]
    entities: Dict[str, List[str]] = {key: [] for key in ENTITY_KEYS}
    details: List[Dict[str, Any]] = []
    covered: List[Tuple[int, int]] = []

    for span in _merge_adjacent_spans(text, ner_spans):
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
        term = max(equivalent, key=lambda t: t["end"] - t["start"])["medical_term"] if equivalent else _canonical_term(raw)
        key = _entity_key(span["label"], text, span["start"], catalog, end=span["end"], norm_term=term)
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
