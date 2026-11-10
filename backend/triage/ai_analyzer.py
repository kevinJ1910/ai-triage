import os
import re
import json
import time
import hashlib
import logging
from typing import List, Optional, Literal, Dict, Any, Tuple
from django.conf import settings
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from transcription.normalizer import concept_mappings

from .clinical_protocol import evaluate_christus_sinergia_triage, is_rule_fallback
from .input_pipeline import ClinicalTranscriptCompressor
from .clinical_rag import ClinicalKnowledgeRAG
from .clinical_cache import ClinicalQueryCache
from .entity_fusion import canonicalize_entities, entities_from_terms, fuse_entities
from .metrics import combine_levels
from . import ner_model

logger = logging.getLogger(__name__)

# Timeout configurable para llamadas a la API de Gemini
GEMINI_REQUEST_TIMEOUT = int(os.getenv('GEMINI_TIMEOUT_SECONDS', '30'))

# Modelos de respaldo si falla el modelo activo (configurable, separados por coma).
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.getenv('GEMINI_FALLBACK_MODELS', 'gemini-2.5-flash,gemini-3.5-flash-lite').split(',') if m.strip()
]

LLM_TEMPERATURE = 0.1

# Version del prompt de triaje en produccion. Las metricas de evaluacion registran la version usada:
# cambiar el texto de un prompt existente invalida sus resultados, asi que cada cambio es una version nueva.
PROMPT_VERSION = os.getenv('TRIAGE_PROMPT_VERSION', 'v1')

# Politica de combinacion LLM + reglas en produccion (triage.metrics.COMBINE_POLICIES). Se fija con los
# resultados de dev antes de evaluar test.
TRIAGE_COMBINE_POLICY = os.getenv('TRIAGE_COMBINE_POLICY', 'llm')

_SYSTEM_INSTRUCTION_V1 = (
    "Especialista de Triaje de Urgencias CHRISTUS SINERGIA (Res. 5596 Minsalud Colombia). "
    "Clasifica rigurosamente el nivel de gravedad y extrae entidades clínicas con máxima fidelidad a los criterios institucionales. "
    "Los hallazgos negados van en negated_findings y nunca en symptoms; 'no respira' o 'no responde' son hallazgos presentes."
)

# v1: prompt original. v2: la pauta del motor de reglas actua como suelo de urgencia (hipotesis del plan de
# evaluacion: el LLM copiaba pautas de reglas equivocadas hacia niveles menos urgentes).
PROMPT_TEMPLATES = {
    'v1': {
        'system': _SYSTEM_INSTRUCTION_V1,
        'guideline': (
            "PAUTA CLÍNICA BASE (CHRISTUS SINERGIA / RES. 5596):\n"
            "Nivel {level} ({name}) | Ventana: {attention_time}\n"
            "Criterio: {justification}"
        ),
    },
    'v2': {
        'system': _SYSTEM_INSTRUCTION_V1 + (
            " La pauta del motor de reglas es un suelo de urgencia cuando hay coincidencia léxica o vital: puedes "
            "asignar un nivel más urgente cuando el relato lo justifique, pero solo asignas uno menos urgente si citas "
            "en la justificación el criterio del protocolo que lo permite. Cuando el motor de reglas no tiene "
            "coincidencia léxica (descarte por defecto), clasifica según el relato completo y los criterios "
            "institucionales sin anclarte en Nivel 4 o 5."
        ),
        'guideline': (
            "PAUTA CLÍNICA BASE (CHRISTUS SINERGIA / RES. 5596, SUELO DE URGENCIA):\n"
            "Nivel {level} ({name}) | Ventana: {attention_time}\n"
            "Criterio: {justification}"
        ),
        'unmatched_guideline': (
            "PAUTA CLÍNICA BASE (CHRISTUS SINERGIA / RES. 5596, SUELO DE URGENCIA):\n"
            "Sin coincidencia léxica directa en el motor de reglas (posible paráfrasis coloquial; descarte léxico Nivel {level}).\n"
            "Criterio: Evalúa los criterios institucionales recuperados, signos vitales y gravedad real sin asumir Nivel 4 o 5 por defecto."
        ),
    },
}

_USER_TEMPLATE = (
    "{rag}{guideline}"
    "SIGNOS VITALES: {vitals} | ALERTAS: {alerts}\n"
    "TÉRMINOS NORMALIZADOS (catálogo local): {terms}\n"
    "MENCIONES NER (RoBERTa clínico): {ner}\n"
    "CONSULTA COMPRIMIDA:\n"
    "\"{text}\"\n"
)


class LLMUnavailableError(RuntimeError):
    """No hay ningun LLM utilizable (sin clave o sin servidor local). Solo se lanza con strict_llm=True."""

# Seudonimizacion de identificadores antes de enviar texto a un LLM externo (Ley 1581 de 2012).
_PHONE_RE = re.compile(r'\b3(?:[\s.,-]{0,2}\d){9}(?!\d)')
_DOCUMENT_RE = re.compile(r'\b\d(?:[\s.,-]{0,2}\d){5,10}(?!\d)')
_PHONE_CUE_RE = re.compile(
    r'(?i)\b(?:tel[eé]fono|celular|m[oó]vil|contacto|whatsapp|n[uú]mero\s+de\s+(?:tel[eé]fono|celular|contacto))'
    r'(?:\s+(?:es|el|n[uú]mero))?[\s:.,-]*((?:\d[\s.,-]*){7,10})(?!\d)'
)
_DOC_CUE_RE = re.compile(
    r'(?i)\b(?:c[eé]dula(?:\s+de\s+ciudadan[ií]a)?|documento(?:\s+de\s+identidad)?|identificaci[oó]n|'
    r'n[uú]mero\s+de\s+(?:documento|c[eé]dula|identificaci[oó]n)|c\.?c\.?|t\.?i\.?)'
    r'(?:\s+(?:es|el|la|n[uú]mero))?[\s:.,-]*((?:\d[\s.,-]*){6,11})(?!\d)'
)
_DATE_LIKE_RE = re.compile(r'^\d{1,2}[\s/\-.]+\d{1,2}[\s/\-.]+\d{2,4}$')
_MONTH_MAP = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_SPOKEN_TENS = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
}
_SPOKEN_UNITS = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "primero": 1, "dos": 2, "tres": 3,
    "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
    "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "dieciséis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiun": 21, "veintiún": 21, "veintiuno": 21,
    "veintidos": 22, "veintidós": 22, "veintitres": 23, "veintitrés": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintiséis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
}
_SPOKEN_HUNDREDS = {
    "cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300,
    "cuatrocientos": 400, "quinientos": 500, "seiscientos": 600,
    "setecientos": 700, "ochocientos": 800, "novecientos": 900,
}


def _normalize_spoken_numbers(text: str) -> str:
    """
    Convierte palabras numericas en espanol ('uno uno cinco...', 'quince de mayo de mil novecientos ochenta')
    a digitos para permitir la union determinista de documento, telefono y fecha de nacimiento.
    """
    if not text:
        return ""
    import unicodedata
    out = text

    def _strip_accents(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

    # 1. Años hablados: 'mil novecientos ochenta y cinco' -> '1985', 'dos mil cuatro' -> '2004'
    tens_pat = "|".join(_SPOKEN_TENS.keys())
    units_pat = "|".join(_SPOKEN_UNITS.keys())

    def _replace_1900(m: re.Match) -> str:
        ten_w = _strip_accents(m.group(1) or "").lower()
        unit_w = _strip_accents(m.group(2) or "").lower()
        val = 1900 + _SPOKEN_TENS.get(ten_w, 0) + _SPOKEN_UNITS.get(unit_w, 0)
        return str(val)

    out = re.sub(
        rf"(?i)\bmil\s+novecientos(?:\s+({tens_pat})(?:\s+y\s+({units_pat}))?|\s+({units_pat}))?\b",
        lambda m: str(
            1900
            + (_SPOKEN_TENS.get(_strip_accents(m.group(1) or "").lower(), 0) if m.group(1) else 0)
            + (_SPOKEN_UNITS.get(_strip_accents(m.group(2) or m.group(3) or "").lower(), 0))
        ),
        out,
    )
    out = re.sub(
        rf"(?i)\bdos\s+mil(?:\s+({tens_pat})(?:\s+y\s+({units_pat}))?|\s+({units_pat}))?\b",
        lambda m: str(
            2000
            + (_SPOKEN_TENS.get(_strip_accents(m.group(1) or "").lower(), 0) if m.group(1) else 0)
            + (_SPOKEN_UNITS.get(_strip_accents(m.group(2) or m.group(3) or "").lower(), 0))
        ),
        out,
    )

    # 2. Decenas compuestas: 'treinta y cinco' -> '35'
    out = re.sub(
        rf"(?i)\b({tens_pat})\s+y\s+({units_pat})\b",
        lambda m: str(
            _SPOKEN_TENS[_strip_accents(m.group(1)).lower()]
            + _SPOKEN_UNITS[_strip_accents(m.group(2)).lower()]
        ),
        out,
    )

    # 3. Centenas + decenas/unidades: 'trescientos quince' -> '315'
    hundreds_pat = "|".join(_SPOKEN_HUNDREDS.keys())
    out = re.sub(
        rf"(?i)\b({hundreds_pat})(?:\s+(\d{{1,2}}|{tens_pat}|{units_pat}))?\b",
        lambda m: str(
            _SPOKEN_HUNDREDS[_strip_accents(m.group(1)).lower()]
            + (
                int(m.group(2))
                if (m.group(2) and m.group(2).isdigit())
                else _SPOKEN_TENS.get(_strip_accents(m.group(2) or "").lower(), 0)
                + _SPOKEN_UNITS.get(_strip_accents(m.group(2) or "").lower(), 0)
            )
        ),
        out,
    )

    # 4. Decenas simples ('ochenta' -> '80') y numeros 2..29 ('quince' -> '15', 'dos' -> '2')
    safe_number_words = {
        k: v for k, v in {**_SPOKEN_TENS, **_SPOKEN_UNITS}.items() if k not in ("un", "una")
    }
    safe_pat = "|".join(sorted(safe_number_words.keys(), key=len, reverse=True))
    out = re.sub(
        rf"(?i)\b({safe_pat})\b",
        lambda m: str(safe_number_words[_strip_accents(m.group(1)).lower()]),
        out,
    )
    # 'punto', 'guion', 'mil' o 'millones' entre digitos -> separador numerico
    out = re.sub(r"(?i)\bmil\s+(?=\d{1,3}\b)", "1 ", out)
    out = re.sub(r"(?<=\d)\s+(?:punto|guion|millones|mill[oó]n|mil)\s+(?=\d)", ".", out, flags=re.I)
    return out


def _extract_phone_number(text: str) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    """Extrae y une los digitos del telefono (incluso si el ASR los separo con espacios, puntos o comas)."""
    for source_text in (text or "", _normalize_spoken_numbers(text or "")):
        cue_match = _PHONE_CUE_RE.search(source_text)
        if cue_match:
            digits = re.sub(r"\D", "", cue_match.group(1))
            if 7 <= len(digits) <= 10:
                return digits, (cue_match.start(1), cue_match.end(1))
        for match in _PHONE_RE.finditer(source_text):
            raw_chunk = match.group(0).strip()
            if _DATE_LIKE_RE.match(raw_chunk):
                continue
            digits = re.sub(r"\D", "", raw_chunk)
            if len(digits) == 10 and digits.startswith("3"):
                return digits, (match.start(), match.end())
    return None, None


def _extract_document_id(text: str, exclude_phone: Optional[str] = None) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    """Extrae y une los digitos del documento de identidad (6 a 11 digitos, unidos aunque tengan pausas o puntos)."""
    for source_text in (text or "", _normalize_spoken_numbers(text or "")):
        cue_match = _DOC_CUE_RE.search(source_text)
        if cue_match:
            digits = re.sub(r"\D", "", cue_match.group(1))
            if 6 <= len(digits) <= 11 and digits != exclude_phone:
                return digits, (cue_match.start(1), cue_match.end(1))
        for match in _DOCUMENT_RE.finditer(source_text):
            raw_chunk = match.group(0).strip()
            if _DATE_LIKE_RE.match(raw_chunk):
                continue
            digits = re.sub(r"\D", "", raw_chunk)
            if 6 <= len(digits) <= 11 and digits != exclude_phone:
                return digits, (match.start(), match.end())
    return None, None


def _format_valid_birth_date(year: int, month: int, day: int) -> Optional[str]:
    if year < 100:
        year = 2000 + year if year <= 26 else 1900 + year
    if not (1900 <= year <= 2026 and 1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _extract_birth_date(text: str) -> Optional[str]:
    """Extrae y normaliza la fecha de nacimiento a YYYY-MM-DD desde formatos hablados o numericos."""
    if not text:
        return None
    norm = _normalize_spoken_numbers(text)

    # 1. Formato ISO YYYY-MM-DD o YYYY/MM/DD
    iso_m = re.search(r"\b(19\d{2}|20[0-2]\d)[\s/\-.]+(0?[1-9]|1[0-2])[\s/\-.]+(0?[1-9]|[12]\d|3[01])\b", norm)
    if iso_m:
        res = _format_valid_birth_date(int(iso_m.group(1)), int(iso_m.group(2)), int(iso_m.group(3)))
        if res:
            return res

    # 2. Mes en espanol: '15 de mayo de 1980', '15 mayo 1980', '15 de mayo del 80'
    months_pat = "|".join(_MONTH_MAP.keys())
    es_m = re.search(
        rf"(?i)\b(\d{{1,2}})\s*(?:de|del|,|\s)\s*({months_pat})\s*(?:de|del|,|\s)\s*(\d{{2,4}})\b",
        norm,
    )
    if es_m:
        res = _format_valid_birth_date(int(es_m.group(3)), _MONTH_MAP[es_m.group(2).lower()], int(es_m.group(1)))
        if res:
            return res

    es_m2 = re.search(
        rf"(?i)\b({months_pat})\s+(\d{{1,2}})\s*(?:de|del|,|\s)\s*(\d{{2,4}})\b",
        norm,
    )
    if es_m2:
        res = _format_valid_birth_date(int(es_m2.group(3)), _MONTH_MAP[es_m2.group(1).lower()], int(es_m2.group(2)))
        if res:
            return res

    # 3. Contexto explicito de nacimiento con numeros separados por espacio, punto, barra, guion o 'del'
    cue_m = re.search(
        r"(?i)\b(?:fecha\s+de\s+nacimiento|nac[ií]|naci[oó]|nacid[oa](?:\s+el)?|cumplea[ñn]os)"
        r"(?:\s+(?:es|el))?[\s:.,-]*"
        r"(\d{1,2})(?:\s*(?:[/\-.]|de|del)\s*|\s+)(\d{1,2})(?:\s*(?:[/\-.]|de|del)\s*|\s+)(19\d{2}|20[0-2]\d|\d{2})\b",
        norm,
    )
    if cue_m:
        res = _format_valid_birth_date(int(cue_m.group(3)), int(cue_m.group(2)), int(cue_m.group(1)))
        if res:
            return res

    # 4. Formato numerico estandar DD/MM/YYYY o DD-MM-YYYY o DD.MM.YYYY
    dmy_m = re.search(r"\b(0?[1-9]|[12]\d|3[01])\s*[/\-.]\s*(0?[1-9]|1[0-2])\s*[/\-.]\s*(19\d{2}|20[0-2]\d)\b", norm)
    if dmy_m:
        res = _format_valid_birth_date(int(dmy_m.group(3)), int(dmy_m.group(2)), int(dmy_m.group(1)))
        if res:
            return res

    return None
_NAME_RE = re.compile(
    r'(?i:\b(?:me llamo|mi nombre(?:\s+completo)?\s+es|se llama|su nombre es|el paciente se llama|la paciente se llama)\s+)'
    r'([A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+){0,3})'
)
_SOY_PROPER_NAME_RE = re.compile(
    r'\b(?:[Ss]oy)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,18}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,18}){1,3})\b'
)
_PLACEHOLDERS = ("[NOMBRE]", "[DOCUMENTO]", "[TELEFONO]")

# Vocabulario clinico, funcional y de rol que nunca puede formar parte de un nombre propio de paciente.
_NON_NAME_WORDS = frozenset({
    "alergico", "alergica", "alergicos", "alergicas", "alergia", "alergias",
    "hipertenso", "hipertensa", "hipertension", "diabetico", "diabetica", "diabetes",
    "asmatico", "asmatica", "asma", "epileptico", "epileptica", "epilepsia",
    "cardiopata", "anticoagulado", "anticoagulada", "operado", "operada",
    "diagnosticado", "diagnosticada", "cronico", "cronica", "embarazada", "gestante",
    "fumador", "fumadora", "oncologico", "oncologica", "renal", "dialisis",
    "dolor", "fiebre", "tos", "mareo", "infarto", "pecho", "brazo", "cabeza",
    "presion", "tension", "pulso", "saturacion", "vitales", "antecedentes", "antecedente",
    "penicilina", "losartan", "losartanicos", "metformina", "mefortormina", "omeprazol",
    "insulina", "acetaminofen", "ibuprofeno", "aspirina", "dipirona", "amoxicilina",
    "sangrado", "vomito", "nauseas", "disnea", "ahogo", "asfixia", "fractura", "herida",
    "quemadura", "epoc", "gastritis", "migrana", "convulsion", "desmayo", "conocimiento",
    "yo", "tu", "el", "ella", "un", "una", "unos", "unas", "los", "las", "lo", "al", "a",
    "ante", "bajo", "con", "contra", "desde", "durante", "en", "entre", "hacia", "hasta",
    "mediante", "para", "por", "segun", "sin", "sobre", "tras", "y", "e", "ni", "o", "u",
    "pero", "sino", "que", "como", "cuando", "donde", "porque", "pues", "si", "no", "ya",
    "muy", "mas", "menos", "tambien", "tampoco", "solo", "tengo", "tiene", "siento", "siente",
    "sufro", "sufre", "padezco", "padece", "tomo", "toma", "vengo", "viene", "estoy", "esta",
    "fui", "fue", "he", "ha", "hace", "ayer", "hoy", "dias", "horas", "anos", "meses",
    "semanas", "paciente", "usuario", "medico", "doctor", "doctora", "enfermero", "enfermera",
    "profesional", "hombre", "mujer", "senor", "senora", "joven", "adulto", "mayor",
    "nino", "nina", "bebe", "desconocido", "desconocida", "ninguno", "ninguna", "null", "none",
    "urgencias", "admision", "consulta", "hospital", "clinica", "eps", "cedula", "documento",
})
_NAME_CONNECTORS = frozenset({"de", "del", "la"})


def _fold_word(word: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFKD", word or "") if not unicodedata.combining(c)
    ).lower()


def _sanitize_patient_name(candidate: Optional[str], require_two_words: bool = False) -> Optional[str]:
    """
    Valida y limpia un candidato a nombre de paciente. Descarta frases clinicas ('alergico a la penicilina'),
    roles ('Paciente Desconocido', 'Usuario') o conectores gramaticales.
    """
    if not candidate or not isinstance(candidate, str):
        return None
    if any(ph in candidate for ph in _PLACEHOLDERS):
        return None
    first_clause = re.split(r"[,.;:()\-/\n]", candidate.strip())[0].strip()
    if not first_clause:
        return None
    raw_words = first_clause.split()
    valid_tokens: List[str] = []
    for idx, w in enumerate(raw_words):
        clean_w = re.sub(r"[^A-Za-zÁÉÍÓÚáéíóúñÑ]", "", w)
        if not clean_w or len(clean_w) < 2:
            break
        folded = _fold_word(clean_w)
        if folded in _NAME_CONNECTORS:
            # Solo se admite 'de'/'del'/'la' entre dos nombres propios validos (ej. 'Maria del Carmen')
            if not valid_tokens or idx + 1 >= len(raw_words):
                break
            next_folded = _fold_word(re.sub(r"[^A-Za-zÁÉÍÓÚáéíóúñÑ]", "", raw_words[idx + 1]))
            if not next_folded or next_folded in _NON_NAME_WORDS or next_folded in _NAME_CONNECTORS:
                break
            valid_tokens.append(folded)
            continue
        if folded in _NON_NAME_WORDS:
            break
        valid_tokens.append(clean_w.capitalize())
        if len(valid_tokens) >= 4:
            break

    while valid_tokens and _fold_word(valid_tokens[-1]) in _NAME_CONNECTORS:
        valid_tokens.pop()

    proper_count = sum(1 for t in valid_tokens if _fold_word(t) not in _NAME_CONNECTORS)
    min_required = 2 if require_two_words else 1
    if proper_count < min_required:
        return None
    return " ".join(valid_tokens)


def _extract_valid_patient_name(text: str) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    """Busca un nombre propio explicito en el relato y devuelve (nombre_limpio, (start, end))."""
    cleaned_speakers = re.sub(
        r"(?i)\b(?:usuario|paciente|m[eé]dico|doctor(?:a)?|enfermer[oa])\s*:\s*",
        " ",
        text or "",
    )
    for match in _NAME_RE.finditer(cleaned_speakers):
        sanitized = _sanitize_patient_name(match.group(1), require_two_words=False)
        if sanitized:
            # Calcular el fin real sobre el texto segun los tokens aceptados
            raw_tokens = match.group(1).split()[:len(sanitized.split())]
            end_pos = match.start(1) + len(" ".join(raw_tokens))
            return sanitized, (match.start(1), end_pos)
    for match in _SOY_PROPER_NAME_RE.finditer(cleaned_speakers):
        sanitized = _sanitize_patient_name(match.group(1), require_two_words=True)
        if sanitized:
            raw_tokens = match.group(1).split()[:len(sanitized.split())]
            end_pos = match.start(1) + len(" ".join(raw_tokens))
            return sanitized, (match.start(1), end_pos)
    return None, None


def _pseudonymize(text: str) -> Dict[str, Any]:
    """
    Reemplaza nombre, telefono y documento por marcadores y devuelve los valores originales,
    que se reinyectan localmente en patientInfo sin salir del servidor.
    """
    found: Dict[str, Optional[str]] = {"name": None, "phone": None, "documentId": None}

    name_match = _NAME_RE.search(text)
    if name_match:
        sanitized = _sanitize_patient_name(name_match.group(1), require_two_words=False)
        if sanitized:
            found["name"] = sanitized
            raw_tokens = name_match.split() if hasattr(name_match, "split") else name_match.group(1).split()[:len(sanitized.split())]
            end_idx = name_match.start(1) + len(" ".join(raw_tokens))
            text = text[:name_match.start(1)] + "[NOMBRE] " + text[end_idx:].lstrip()

    phone_digits, _ = _extract_phone_number(text)
    if phone_digits:
        found["phone"] = phone_digits
    text = _PHONE_RE.sub("[TELEFONO]", text)

    doc_digits, _ = _extract_document_id(text, exclude_phone=found["phone"])
    if doc_digits:
        found["documentId"] = doc_digits
    text = _DOCUMENT_RE.sub("[DOCUMENTO]", text)

    return {"text": text, "identifiers": found}


def _restore_identifiers(patient_info: Dict[str, Any], identifiers: Dict[str, Optional[str]], raw_transcript: str) -> Dict[str, Any]:
    """Sustituye marcadores devueltos por el LLM con los valores reales extraidos localmente y sanea el nombre."""
    local = _extract_patient_info_rules(raw_transcript)
    raw_llm_name = patient_info.get("name")
    sanitized_llm_name = _sanitize_patient_name(str(raw_llm_name)) if raw_llm_name else None
    patient_info["name"] = sanitized_llm_name or identifiers.get("name") or local.get("name")

    for field in ("documentId", "phone"):
        raw_val = patient_info.get(field)
        clean_llm_digits = (
            re.sub(r"\D", "", str(raw_val))
            if raw_val and not any(ph in str(raw_val) for ph in _PLACEHOLDERS)
            else ""
        )
        best_local = local.get(field) or identifiers.get(field) or ""
        if best_local and len(best_local) >= len(clean_llm_digits):
            patient_info[field] = best_local
        elif clean_llm_digits:
            patient_info[field] = clean_llm_digits
        else:
            patient_info[field] = None

    raw_bdate = patient_info.get("birthDate")
    normalized_llm_bdate = _extract_birth_date(str(raw_bdate)) if raw_bdate else None
    patient_info["birthDate"] = local.get("birthDate") or normalized_llm_bdate or (
        str(raw_bdate) if raw_bdate and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(raw_bdate)) else None
    )

    if not patient_info.get("gender") or patient_info.get("gender") == "unknown":
        if local.get("gender") and local["gender"] != "unknown":
            patient_info["gender"] = local["gender"]
    return patient_info


# --- Esquemas Pydantic v2 para Decodificacion Estructurada Estricta ---

class PatientInfoSchema(BaseModel):
    name: Optional[str] = Field(default=None, description="Nombre del paciente o null si no se menciona")
    documentId: Optional[str] = Field(default=None, description="Numero de documento de identidad numerico o null")
    birthDate: Optional[str] = Field(default=None, description="Fecha de nacimiento en formato YYYY-MM-DD o null")
    gender: Literal["male", "female", "other", "unknown"] = Field(default="unknown", description="Genero del paciente")
    phone: Optional[str] = Field(default=None, description="Telefono de contacto o null")
    insurance: Optional[str] = Field(default="Christus Sinergia / EPS", description="Aseguradora o EPS")


class EntitiesSchema(BaseModel):
    symptoms: List[str] = Field(
        default_factory=list,
        description=(
            "Sintomas y signos clinicos presentes en terminologia medica canonica (ej. 'dolor torácico opresivo', "
            "'disnea', 'irradiación a miembro superior', 'mareo'); nunca incluir hallazgos negados ni verbos "
            "conversacionales ('temo que', 'me falta')"
        ),
    )
    diagnoses: List[str] = Field(
        default_factory=list,
        description=(
            "Enfermedades agudas, sospechas diagnosticas, lesiones o estados del episodio actual completos "
            "(ej. 'infarto agudo de miocardio', 'fractura', 'quemadura', 'gestacion'); nunca dividir una misma "
            "entidad en dos items"
        ),
    )
    medications: List[str] = Field(
        default_factory=list,
        description=(
            "Medicamentos o principios activos de uso habitual o prescritos en forma farmacologica normalizada "
            "(ej. 'losartán', 'metformina'), corrigiendo errores foneticos del ASR"
        ),
    )
    allergies: List[str] = Field(default_factory=list, description="Sustancias o farmacos a los que el paciente refiere alergia")
    vitals: List[str] = Field(
        default_factory=list,
        description="Constantes vitales detectadas en formato compacto estandar (ej. 'PA: 175 mmHg', 'FC: 115 lpm')",
    )
    history: List[str] = Field(
        default_factory=list,
        description="Antecedentes patologicos cronicos o quirurgicos normalizados (ej. 'hipertensión arterial', 'diabetes mellitus')",
    )
    negated_findings: List[str] = Field(
        default_factory=list,
        description=(
            "Hallazgos negados explicitamente como sustantivos clinicos ('fiebre', 'pérdida de conciencia', "
            "'dolor torácico'); no van en symptoms"
        ),
    )


class TriageDetailsSchema(BaseModel):
    level: int = Field(ge=1, le=5, description="Nivel de triaje del 1 al 5 segun escala Christus Sinergia Salud")
    name: Literal["Reanimación", "Emergencia", "Urgencia", "Consulta Prioritaria", "Consulta Externa"] = Field(
        description="Nombre institucional del nivel de triaje"
    )
    attention_time: Literal[
        "Inmediata",
        "Dentro de los siguientes 30 minutos",
        "Hasta 120 minutos",
        "Direccionamiento a su EPS"
    ] = Field(description="Tiempo maximo estandar de atencion")
    justification: str = Field(description="Justificacion medica concisa fundamentada en el protocolo")


class TriageOutputSchema(BaseModel):
    patientInfo: PatientInfoSchema
    entities: EntitiesSchema
    triage: TriageDetailsSchema
    confidence: float = Field(ge=0.0, le=1.0, default=0.95, description="Puntaje de certeza clinica entre 0.0 y 1.0")
    protocol: str = Field(default="Christus Sinergia Salud")


import copy

def _sanitize_schema_for_gemini(model_cls) -> Dict[str, Any]:
    """
    Convierte el modelo Pydantic v2 en un diccionario JSON Schema estricto
    removiendo title, $defs y referencias anidadas para máxima compatibilidad con Google AI SDK.
    """
    raw_schema = model_cls.model_json_schema()
    defs = raw_schema.pop("$defs", {}) if "$defs" in raw_schema else raw_schema.pop("definitions", {})

    def _sanitize(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_key = obj["$ref"].split("/")[-1]
                if ref_key in defs:
                    resolved = copy.deepcopy(defs[ref_key])
                    return _sanitize(resolved)
            cleaned = {}
            for k, v in obj.items():
                if k in ("title", "$defs", "definitions"):
                    continue
                cleaned[k] = _sanitize(v)
            return cleaned
        elif isinstance(obj, list):
            return [_sanitize(item) for item in obj]
        return obj

    return _sanitize(raw_schema)


def _resolve_gemini_api_key() -> str:
    """Recupera la clave API de Gemini desde la base de datos o variables de entorno."""
    api_key = ""
    try:
        from system_settings.models import APIKeyCredential
        cred = APIKeyCredential.objects.filter(provider='gemini', is_active=True).first()
        if cred:
            api_key = cred.get_key()
    except Exception as db_err:
        logger.warning(f"Could not retrieve Gemini API key from DB: {db_err}")

    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip("'")

    return api_key


def prompt_sha256(version: str = PROMPT_VERSION, rule_hint: bool = True, rag: bool = True) -> str:
    """Huella del prompt (instruccion de sistema + plantillas + opciones), para registrarla en las evaluaciones."""
    template = PROMPT_TEMPLATES[version]
    payload = {"system": template['system'], "guideline": template['guideline'],
               "user": _USER_TEMPLATE, "rule_hint": rule_hint, "rag": rag,
               "temperature": LLM_TEMPERATURE}
    if 'unmatched_guideline' in template:
        payload['unmatched_guideline'] = template['unmatched_guideline']
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def build_triage_prompt(
    rag_context_text: str,
    rule_baseline: Dict[str, Any],
    compact_vitals: List[str],
    red_flags: List[str],
    normalized_terms: List[Dict[str, Any]],
    ner_spans: List[Dict[str, Any]],
    pseudonymized_text: str,
    version: str = PROMPT_VERSION,
    rule_hint: bool = True,
    rag: bool = True,
) -> tuple:
    """
    (system_instruction, user_prompt) del triaje. Es el mismo prompt para Gemini y para el LLM local.
    rule_hint=False y rag=False quitan la pauta del motor de reglas y los criterios recuperados
    (ablacion 'LLM sin pauta' de la evaluacion; en produccion siempre van los dos).
    """
    if version not in PROMPT_TEMPLATES:
        raise ValueError(f"Version de prompt desconocida: {version}")
    template = PROMPT_TEMPLATES[version]
    guideline = ""
    if rule_hint:
        use_unmatched = 'unmatched_guideline' in template and is_rule_fallback(rule_baseline)
        guideline_tpl = template['unmatched_guideline'] if use_unmatched else template['guideline']
        guideline = guideline_tpl.format(
            level=rule_baseline['level'], name=rule_baseline['name'],
            attention_time=rule_baseline['attention_time'], justification=rule_baseline['justification'],
        ) + "\n\n"
    user_prompt = _USER_TEMPLATE.format(
        rag=f"{rag_context_text}\n\n" if rag else "",
        guideline=guideline,
        vitals=", ".join(compact_vitals) if compact_vitals else "Sin reporte",
        alerts=", ".join(red_flags) if red_flags else "Sin banderas rojas",
        terms=_format_terms_for_prompt(normalized_terms),
        ner="; ".join(f"[{span['label']}] {span['text']}" for span in ner_spans) if ner_spans else "Sin modelo NER",
        text=pseudonymized_text,
    )
    return template['system'], user_prompt


def _llm_candidates(model: Optional[str], active_model: str) -> List[tuple]:
    """Lista de (proveedor, modelo) a probar en orden. model fija un unico modelo, sin respaldos."""
    from . import local_llm
    if model:
        if model == 'local' or model.startswith('local:'):
            return [('local', model.partition(':')[2] or local_llm.active_model())]
        return [('gemini', model)]
    if active_model == 'local':
        # Quien elige el motor local lo hace por privacidad: nunca se cae a Gemini.
        return [('local', local_llm.active_model())]
    candidates = [('gemini', active_model)]
    if 'gemini' in active_model:
        candidates += [('gemini', m) for m in GEMINI_FALLBACK_MODELS if m != active_model]
    return candidates


def _call_gemini(client, model_name: str, system_instruction: str, user_prompt: str) -> Dict[str, Any]:
    start = time.perf_counter()
    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=_sanitize_schema_for_gemini(TriageOutputSchema),
            temperature=LLM_TEMPERATURE,
        ),
    )
    usage = getattr(response, "usage_metadata", None)
    p_tokens = (getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
    c_tokens = (getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
    thoughts = (getattr(usage, "thoughts_token_count", 0) or 0) if usage else 0
    total = (getattr(usage, "total_token_count", None) or (p_tokens + c_tokens + thoughts)) if usage else 0
    model_version = getattr(response, "model_version", None)
    return {
        "text": response.text,
        "prompt_tokens": p_tokens,
        "completion_tokens": c_tokens,
        "thoughts_tokens": thoughts,
        "total_tokens": total,
        "model_version": model_version if isinstance(model_version, str) else model_name,
        "latency_ms": round((time.perf_counter() - start) * 1000),
    }


def _call_local(model_name: str, system_instruction: str, user_prompt: str) -> Dict[str, Any]:
    from . import local_llm
    return local_llm.chat_json(model_name, system_instruction, user_prompt,
                               schema=_sanitize_schema_for_gemini(TriageOutputSchema), temperature=LLM_TEMPERATURE)


def _coerce_llm_output(parsed: Any) -> List[str]:
    """
    Corrige desvios de formato que no cambian el contenido clinico, antes de validar con Pydantic.
    Ollama impone la estructura del esquema pero no los limites numericos: Qwen devuelve la confianza en
    porcentaje (95 en vez de 0.95). Devuelve los campos corregidos; el nivel de triaje nunca se toca.
    """
    fixed = []
    if isinstance(parsed, dict):
        confidence = parsed.get("confidence")
        if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 1 < confidence <= 100:
            parsed["confidence"] = confidence / 100
            fixed.append("confidence")
    return fixed


def _apply_combine_policy(result: Dict[str, Any], rule_baseline: Dict[str, Any], policy: str) -> Dict[str, Any]:
    """Registra el nivel del LLM y el de reglas y, con min_critico, deja prevalecer un nivel critico de reglas."""
    llm_level = int(result["triage"]["level"])
    final_level = combine_levels(llm_level, rule_baseline["level"], policy)
    result["llm_level"] = llm_level
    result["rule_level"] = rule_baseline["level"]
    result["combine_policy"] = policy
    if final_level != llm_level:
        result["triage"] = {
            "level": final_level,
            "name": rule_baseline["name"],
            "attention_time": rule_baseline["attention_time"],
            "justification": (
                f"{rule_baseline['justification']} Prevalece el criterio crítico del motor de reglas sobre la "
                f"propuesta del LLM (nivel {llm_level}): {result['triage'].get('justification', '')}"
            ).strip(),
        }
    return result


def analyze_triage_transcript(
    transcript: str, use_cache: bool = True, allow_llm: bool = True, model: Optional[str] = None,
    use_ner: Optional[bool] = None, strict_llm: bool = False, include_raw: bool = False,
    prompt_version: Optional[str] = None, rule_hint: bool = True, rag: bool = True,
    combine_policy: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analiza una conversacion clinica utilizando un pipeline optimizado:
    1. Evaluacion determinista previa de Christus Sinergia Salud como pauta prioritaria.
    2. Compresion y desruidado fonetico de la entrada (ClinicalTranscriptCompressor) y normalizacion
       terminologica determinista (catalogo de transcription/terminology), previa a la extraccion.
    3. Cache semantico canonico para cuadros clinicos recurrentes (ClinicalQueryCache).
    4. Recuperacion semantica de criterios relevantes mediante RAG (ClinicalKnowledgeRAG).
    5. Invocacion al LLM (Gemini o un servidor local compatible con OpenAI) con System Instruction y
       decodificacion estructurada sanitizada.
    6. Fallback automatico garantizado con el Motor de Reglas Christus Sinergia Salud.

    allow_llm=False omite el LLM y aplica directamente el motor de reglas (lo usa la vista
    cuando el worker de inferencia no responde, para no dejar al clinico sin clasificacion).

    model fija un unico modelo, sin modelos de respaldo: lo usan los comandos de evaluacion para
    que las metricas de un modelo no mezclen respuestas de otro. 'local:<modelo>' usa el servidor local.
    Si falla, aplica el motor de reglas.

    use_ner: None usa el NER (RoBERTa) si NER_MODEL_PATH esta configurado; False lo desactiva (lo usan los
    evaluadores para medir cada motor por separado). Sin modelo, las entidades salen del catalogo y del LLM.

    Opciones de evaluacion (en produccion se dejan por defecto):
    - strict_llm: si el LLM falla o no esta disponible se relanza el error en vez de aplicar el respaldo,
      para que un caso resuelto por reglas no se cuente como resultado del modelo.
    - include_raw: anade el texto JSON devuelto por el LLM (llm_raw). Nunca se persiste en la sesion.
    - prompt_version, rule_hint, rag: version del prompt y ablaciones (ver build_triage_prompt).
    - combine_policy: politica LLM + reglas (por defecto TRIAGE_COMBINE_POLICY).
    """
    raw_transcript = (transcript or "").strip()
    if not raw_transcript:
        return {"error": "Transcripción vacía o no proporcionada."}

    version = prompt_version or PROMPT_VERSION
    policy = combine_policy or TRIAGE_COMBINE_POLICY

    # 1. Evaluacion de Reglas Institucionales Christus Sinergia Salud (Prioridad Base)
    rule_baseline = evaluate_christus_sinergia_triage(raw_transcript)

    # 2. Pipeline de Compresion de Entrada y Extraccion de Signos Vitales
    compressed_input = ClinicalTranscriptCompressor.process(raw_transcript)
    cleaned_transcript = compressed_input["cleaned_transcript"]
    compact_vitals = compressed_input["compact_vitals"]
    structured_vitals = compressed_input["structured_vitals"]
    red_flags = compressed_input["red_flags"]
    compression_ratio = compressed_input["reduction_percentage"]
    # Capas deterministas de la normalizacion (sin LLM): pistas para el LLM y entidades del respaldo.
    normalized_terms = concept_mappings(cleaned_transcript)
    ner_spans, ner_engine = _run_ner(cleaned_transcript, use_ner)

    active_model = 'gemini-2.5-flash'
    try:
        from system_settings.models import SystemConfiguration
        config = SystemConfiguration.get_solo()
        if config.active_llm_engine:
            active_model = config.active_llm_engine
    except Exception as cfg_err:
        logger.debug(f"Could not read active_llm_engine from DB: {cfg_err}")
    candidates = _llm_candidates(model, active_model) if allow_llm else []

    # 3. Consulta al Cache Semantico Canonico (0 tokens, < 3ms)
    # El motor NER, el LLM, la version del prompt y la politica forman parte de la huella: un resultado de
    # otra configuracion no se sirve cuando cambia la activa.
    target = f"{candidates[0][0]}:{candidates[0][1]}" if candidates else "reglas"
    variant = f"{ner_engine or ''}|{target}|{version}|{int(rule_hint)}{int(rag)}|{policy}"
    fingerprint = ClinicalQueryCache.generate_fingerprint(cleaned_transcript, structured_vitals, variant=variant)
    if use_cache:
        cached_result = ClinicalQueryCache.get(fingerprint)
        if cached_result:
            logger.info("Consulta resuelta mediante Cache Semántico de Consultas (0 tokens)")
            # La cache no guarda datos del paciente: se extraen de ESTA transcripcion.
            cached_result["patientInfo"] = _extract_patient_info_rules(raw_transcript)
            cached_result["compression_ratio"] = compression_ratio
            cached_result["normalized_terms"] = normalized_terms
            return cached_result

    # 4. RAG Clinico: Recuperacion de Criterios Institucionales Top-K Relevantes
    retrieved_criteria = ClinicalKnowledgeRAG.retrieve(
        cleaned_transcript,
        top_k=4,
        red_flags=red_flags
    )
    rag_context_text = ClinicalKnowledgeRAG.format_context_for_prompt(retrieved_criteria)
    rag_criterion_ids = [c["id"] for c in retrieved_criteria]

    def _fallback(warning: str) -> Dict[str, Any]:
        result = _fallback_rule_triage(
            raw_transcript, cleaned_transcript, compact_vitals, red_flags, compression_ratio,
            rag_criterion_ids, normalized_terms, ner_spans, ner_engine, warning=warning,
        )
        result["rule_level"] = rule_baseline["level"]
        return result

    # 5. Resolucion de Credenciales: Gemini necesita clave; el servidor local, una URL configurada.
    from . import local_llm
    api_key = _resolve_gemini_api_key() if any(p == 'gemini' for p, _ in candidates) else ""
    usable = [(p, m) for p, m in candidates if (p == 'gemini' and api_key) or (p == 'local' and local_llm.configured())]
    if not usable:
        if not allow_llm:
            warning = (
                "El servicio de inferencia no respondió a tiempo. Se aplicó el Motor Clínico determinista "
                "de respaldo Christus Sinergia Salud para garantizar la continuidad asistencial."
            )
        elif candidates and candidates[0][0] == 'local':
            logger.error("LOCAL_LLM_BASE_URL no esta configurada.")
            warning = ("No hay un servidor LLM local configurado (LOCAL_LLM_BASE_URL). Se aplicó el Motor Clínico "
                       "determinista de respaldo Christus Sinergia Salud.")
        else:
            logger.error("No GEMINI_API_KEY found in database or environment variables.")
            warning = "No se encontró una clave de Gemini configurada. Se aplicó el Motor Clínico determinista de respaldo Christus Sinergia Salud."
        if strict_llm and allow_llm:
            raise LLMUnavailableError(warning)
        fallback_res = _fallback(warning)
        # Solo se cachea la falta de configuracion; un worker caido es transitorio y debe reintentarse.
        if use_cache and allow_llm:
            ClinicalQueryCache.set(fingerprint, fallback_res, estimated_tokens=0)
        return fallback_res

    # 6. Construccion de Prompt Optimizado con Prioridad Christus Sinergia Salud
    pseudonymized = _pseudonymize(cleaned_transcript)
    system_instruction, user_prompt = build_triage_prompt(
        rag_context_text, rule_baseline, compact_vitals, red_flags, normalized_terms, ner_spans,
        pseudonymized['text'], version=version, rule_hint=rule_hint, rag=rag,
    )

    client = None
    last_error: Optional[Exception] = None
    for provider, model_name in usable:
        try:
            logger.info(f"Invocando LLM '{provider}:{model_name}' con entrada optimizada y schema sanitizado...")
            if provider == 'gemini':
                if client is None:
                    client = genai.Client(api_key=api_key, http_options={'timeout': GEMINI_REQUEST_TIMEOUT * 1000})
                call = _call_gemini(client, model_name, system_instruction, user_prompt)
            else:
                call = _call_local(model_name, system_instruction, user_prompt)
            raw_text = call["text"]
            parsed = json.loads(raw_text)
            coerced = _coerce_llm_output(parsed)

            # Validar con Pydantic para garantia estructural total
            validated_model = TriageOutputSchema.model_validate(parsed)
            result = validated_model.model_dump()
            result["output_coerced"] = coerced
            result["patientInfo"] = _restore_identifiers(
                result.get("patientInfo") or {}, pseudonymized["identifiers"], raw_transcript
            )

            # Fusionar signos vitales extraidos por regex limpiando duplicados coloquiales del LLM
            if compact_vitals:
                current_v = result.get("entities", {}).get("vitals", [])
                compact_numbers = {num for cv in compact_vitals for num in re.findall(r"\d{2,3}", cv)}
                filtered_v = list(compact_vitals)
                for v in current_v:
                    if v not in filtered_v and not any(n in re.findall(r"\d{2,3}", v) for n in compact_numbers):
                        filtered_v.append(v)
                result["entities"]["vitals"] = filtered_v

            label = f"LLM local ({model_name})" if provider == 'local' else f"LLM ({model_name})"
            result["engine_used"] = f"{label} + Christus Sinergia"
            result["llm_provider"] = provider
            result["cached"] = False
            # Telemetria de Tokens y de la llamada
            result["prompt_tokens"] = call["prompt_tokens"]
            result["completion_tokens"] = call["completion_tokens"]
            result["thoughts_tokens"] = call["thoughts_tokens"]
            result["total_tokens"] = call["total_tokens"]
            result["model_version"] = call["model_version"]
            result["llm_latency_ms"] = call["latency_ms"]
            result["prompt_version"] = version
            result["compression_ratio"] = compression_ratio
            result["rag_context"] = rag_criterion_ids
            result["normalized_terms"] = normalized_terms
            result["ner_spans"] = []
            llm_entities = result["entities"]
            if ner_engine:
                # Hibrido: las menciones del NER y la negacion determinista mandan; el LLM desempata.
                fused, details = fuse_entities(cleaned_transcript, ner_spans, normalized_terms, llm_entities,
                                               min_score=getattr(settings, "NER_MIN_SCORE", 0.6))
                result["entities"] = {**fused, "vitals": llm_entities.get("vitals", [])}
                result["ner_spans"] = details
            else:
                result["entities"] = {
                    **canonicalize_entities(llm_entities, text=cleaned_transcript),
                    "vitals": llm_entities.get("vitals", []),
                }
            result["ner_engine"] = ner_engine
            result = _apply_combine_policy(result, rule_baseline, policy)

            # Guardar en Cache Semantico para proximas consultas (sin la respuesta cruda)
            if use_cache:
                ClinicalQueryCache.set(fingerprint, result, estimated_tokens=call["total_tokens"])
            if include_raw:
                result = {**result, "llm_raw": raw_text}
            return result

        except Exception as err:
            last_error = err
            logger.warning(f"Fallo en llamada a {provider}:{model_name} con schema Pydantic: {err}")

    if strict_llm and last_error is not None:
        raise last_error

    # 7. Fallback Asistencial Garantizado (Motor Determinista)
    logger.warning("Activando motor determinista de respaldo Christus Sinergia Salud...")
    # No se cachea: es un fallo transitorio y la proxima consulta debe reintentar el LLM.
    return _fallback(
        f"{_describe_llm_failure(last_error)} "
        "Se aplicó el Motor Clínico de Reglas Christus Sinergia Salud para garantizar "
        "la clasificación y la continuidad asistencial sin demoras."
    )


def _describe_llm_failure(err: Optional[Exception]) -> str:
    """Mensaje para el usuario segun el tipo real de fallo del LLM (sin detalles internos)."""
    text = str(err or "").lower()
    if "503" in text or "unavailable" in text or "overloaded" in text:
        return "El servicio LLM en la nube presentó alta demanda temporal (código 503)."
    if "429" in text or "resource_exhausted" in text or "quota" in text:
        return "Se alcanzó el límite de cuota del servicio LLM (código 429)."
    if "401" in text or "403" in text or "api key" in text or "permission" in text:
        return "La clave del servicio LLM fue rechazada o no tiene permisos."
    if "timeout" in text or "timed out" in text or "deadline" in text:
        return "El servicio LLM no respondió dentro del tiempo límite."
    if isinstance(err, (json.JSONDecodeError, ValueError)):
        return "El servicio LLM devolvió una respuesta que no cumple el esquema clínico."
    return "El servicio LLM no respondió correctamente."


def _extract_patient_info_rules(raw_transcript: str) -> Dict[str, Any]:
    """Extrae documento, nombre, telefono, fecha de nacimiento y genero del paciente por reglas deterministas."""
    from .demographics import derive as derive_demographics

    phone, _ = _extract_phone_number(raw_transcript)
    doc_id, _ = _extract_document_id(raw_transcript, exclude_phone=phone)
    birth_date = _extract_birth_date(raw_transcript)
    patient_name, _ = _extract_valid_patient_name(raw_transcript)

    demo = derive_demographics(raw_transcript)
    sex_map = {"femenino": "female", "masculino": "male"}
    gender = sex_map.get(demo.get("sexo") or "", "unknown")

    return {
        "name": patient_name,
        "documentId": doc_id,
        "birthDate": birth_date,
        "gender": gender,
        "phone": phone,
        "insurance": "Christus Sinergia / EPS"
    }


def _run_ner(cleaned_transcript: str, use_ner: Optional[bool]) -> tuple:
    """(menciones, etiqueta del motor) o ([], None) sin modelo. Un fallo del NER nunca interrumpe el triaje."""
    if use_ner is False:
        return [], None
    if use_ner is None:
        try:
            from system_settings.models import SystemConfiguration
            if SystemConfiguration.get_solo().active_ner_model == 'catalogo':
                return [], None
        except Exception:
            pass
    engine = ner_model.get_engine()
    if engine is None:
        return [], None
    try:
        return engine.extract(cleaned_transcript), ner_model.engine_label()
    except Exception as err:
        logger.warning(f"Fallo del NER: {err}. Se usan el catalogo y el LLM.")
        return [], None


def _format_terms_for_prompt(normalized_terms: List[Dict[str, Any]]) -> str:
    parts = []
    for item in normalized_terms:
        code = f" [{item['code']}]" if item["code"] else ""
        prefix = "NEGADO " if item["negated"] else ("ALERGIA " if item["allergy"] else "")
        parts.append(f"{prefix}\"{item['raw_term']}\" -> {item['medical_term']}{code}")
    return "; ".join(parts) if parts else "Ninguno"


def _fallback_rule_triage(
    raw_transcript: str,
    cleaned_transcript: str,
    compact_vitals: List[str],
    red_flags: List[str],
    compression_ratio: float,
    rag_criterion_ids: List[str],
    normalized_terms: List[Dict[str, Any]],
    ner_spans: List[Dict[str, Any]],
    ner_engine: Optional[str],
    warning: str
) -> Dict[str, Any]:
    """Genera la respuesta estandarizada mediante el motor determinista Christus Sinergia."""
    rule_triage = evaluate_christus_sinergia_triage(raw_transcript)
    ner_details: List[Dict[str, Any]] = []
    if ner_engine:
        entities, ner_details = fuse_entities(cleaned_transcript, ner_spans, normalized_terms,
                                              min_score=getattr(settings, "NER_MIN_SCORE", 0.6))
    else:
        entities = entities_from_terms(normalized_terms)

    return {
        "patientInfo": _extract_patient_info_rules(raw_transcript),
        "entities": {
            "symptoms": entities["symptoms"] or ["Síntomas referidos en consulta"],
            "diagnoses": entities["diagnoses"],
            "medications": entities["medications"],
            "allergies": entities["allergies"],
            "vitals": compact_vitals,
            "history": entities["history"],
            "negated_findings": entities["negated_findings"],
        },
        "triage": {
            "level": rule_triage["level"],
            "name": rule_triage["name"],
            "attention_time": rule_triage["attention_time"],
            "justification": rule_triage["justification"]
        },
        "confidence": rule_triage["confidence"],
        "protocol": "Christus Sinergia Salud",
        "engine_used": "Motor de Reglas Clínico (Christus Sinergia)",
        "cached": False,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "compression_ratio": compression_ratio,
        "rag_context": rag_criterion_ids,
        "normalized_terms": normalized_terms,
        "ner_engine": ner_engine,
        "ner_spans": ner_details,
        "warning": warning
    }
