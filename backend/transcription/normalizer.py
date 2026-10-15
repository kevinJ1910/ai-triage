"""
Normalizacion por capas de texto clinico coloquial a terminologia estandarizada (CIE-10 / ATC).

  1-3. Catalogos deterministas (transcription/terminology): correcciones ASR, abreviaturas y diccionario
       de coloquialismos. Siempre se ejecutan y no consumen tokens.
  4.   Gemini Flash-Lite, solo para los terminos clinicos que el catalogo no resolvio. Opcional: si no
       hay clave o la llamada falla, queda el resultado de las capas 1-3.
  5.   Validacion: cada codigo se verifica contra el catalogo local; un codigo invalido se marca, no se
       corrige, y un termino que no aparece en el relato se descarta.

Se ejecuta en el worker 'llm'; la vista solo encola la tarea. El analisis de triaje usa solo las capas
deterministas (concept_mappings) para no gastar una segunda llamada al LLM por consulta.
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from triage.negation import is_negated

from .terminology import (
    ATC, CIE10, SOURCES, catalog_versions, find_concepts, fold, in_allergy_context, validate_code,
)

logger = logging.getLogger(__name__)

NORMALIZER_LLM_MODEL = os.getenv('NORMALIZER_LLM_MODEL', 'gemini-3.5-flash-lite')
LLM_SOURCE = 'llm'
_SOURCE_LABELS = {'correccion_asr': 'corrección ASR', 'abreviatura': 'abreviatura', 'diccionario': 'diccionario'}


class NormalizationMappingSchema(BaseModel):
    raw_term: str = Field(description="Termino copiado literalmente del relato")
    medical_term: str = Field(description="Termino medico formal equivalente")
    code: str = Field(default="", description="Codigo CIE-10 (formato OMS, p. ej. R06.0) o ATC para medicamentos; vacio si no hay certeza")
    category: Literal["Sintoma", "Signo", "Diagnostico", "Antecedente", "Medicamento"]


class NormalizationOutputSchema(BaseModel):
    normalized_text: str = Field(description="Relato completo redactado en lenguaje clinico formal")
    summary: str = Field(description="Resumen clinico en 1 o 2 lineas")
    mappings: List[NormalizationMappingSchema] = Field(default_factory=list)


def _mapping(raw_term: str, medical_term: str, code: Optional[str], code_system: Optional[str], category: str,
             source: str, negated: bool, allergy: bool) -> Dict[str, Any]:
    canonical, valid = validate_code(code, code_system)
    return {
        "raw_term": raw_term,
        "medical_term": medical_term,
        "code": canonical,
        "code_system": code_system if canonical else None,
        "category": category,
        "source": source,
        "valid": valid,
        "negated": negated,
        "allergy": allergy,
    }


def _concept_matches(text: str):
    """Coincidencias del catalogo; un alergeno solo cuenta si va precedido de 'alergico a'."""
    for match in find_concepts(text):
        allergy = match.concept.category in ('Medicamento', 'Alergeno') and in_allergy_context(text, match.start)
        if match.concept.category == 'Alergeno' and not allergy:
            continue
        yield match, allergy


def concept_mappings(text: str) -> List[Dict[str, Any]]:
    """Capas 1-3: conceptos del catalogo con codigo validado, negacion y contexto de alergia."""
    folded = fold(text or '')
    mappings = []
    for match, allergy in _concept_matches(text or ''):
        concept = match.concept
        mappings.append(_mapping(
            match.raw, concept.term, concept.code, concept.code_system, concept.category,
            match.source, is_negated(folded, match.start, match.end), allergy,
        ))
    return mappings


def _layer_counts(mappings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {source: 0 for source in (*SOURCES, LLM_SOURCE)}
    for item in mappings:
        counts[item['source']] += 1
    return counts


def _rules_summary(mappings: List[Dict[str, Any]]) -> str:
    if not mappings:
        return "Sin términos del catálogo local en el relato."
    counts = _layer_counts(mappings)
    detail = ", ".join(f"{n} por {_SOURCE_LABELS[s]}" for s, n in counts.items() if n and s in _SOURCE_LABELS)
    return f"{len(mappings)} términos normalizados con el catálogo local ({detail})."


def normalize_with_rules(raw_text: str) -> Dict[str, Any]:
    """Capas deterministas. Respaldo si no hay clave, falla la red o el worker no responde."""
    text = raw_text or ''
    mappings = concept_mappings(text)
    normalized = text
    # De atras hacia adelante para que los offsets sigan siendo validos al reemplazar.
    for match, _ in reversed(list(_concept_matches(text))):
        normalized = normalized[:match.start] + match.concept.term + normalized[match.end:]
    return {
        "normalized_text": normalized,
        "summary": _rules_summary(mappings),
        "mappings": mappings,
        "layers": _layer_counts(mappings),
        "engine": "Catálogo terminológico local",
        "catalog_version": catalog_versions(),
    }


def _resolve_gemini_key() -> str:
    try:
        from system_settings.models import APIKeyCredential
        cred = APIKeyCredential.objects.filter(provider='gemini', is_active=True).first()
        if cred:
            return cred.get_key()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip('"\'')


def _candidate_models() -> List[str]:
    models = [NORMALIZER_LLM_MODEL]
    try:
        from system_settings.models import SystemConfiguration
        active = SystemConfiguration.get_solo().active_llm_engine
        if active and 'gemini' in active and active not in models:
            models.append(active)
    except Exception:
        pass
    return models


def _locate(folded_text: str, raw_term: str) -> Optional[re.Match]:
    words = fold(raw_term).split()
    if not words:
        return None
    pattern = r'(?<![a-z0-9])' + r'\s+'.join(re.escape(w) for w in words) + r'(?![a-z0-9])'
    return re.search(pattern, folded_text)


def _residual_mappings(text: str, llm_mappings: List[NormalizationMappingSchema],
                       resolved: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Capa 5 sobre la salida del LLM: descarta lo inventado o ya resuelto y valida cada codigo."""
    folded = fold(text)
    taken = [(m.start, m.end) for m, _ in _concept_matches(text)]
    seen = {' '.join(fold(m['raw_term']).split()) for m in resolved}
    residual = []
    for item in llm_mappings:
        key = ' '.join(fold(item.raw_term).split())
        found = _locate(folded, item.raw_term)
        if not found or key in seen:
            continue
        # El catalogo gana ante un solape parcial; un termino del LLM que contiene por completo a uno
        # del catalogo ('dolor punzante en el talon' frente a 'dolor') lo precisa y se conserva junto a el.
        start_, end_ = found.start(), found.end()
        if any(start_ < end and start < end_ and not (start_ <= start and end <= end_ and (start, end) != (start_, end_))
               for start, end in taken):
            continue
        seen.add(key)
        taken.append((found.start(), found.end()))
        code_system = ATC if item.category == 'Medicamento' else CIE10
        residual.append(_mapping(
            text[found.start():found.end()], item.medical_term, item.code.strip() or None, code_system,
            item.category, LLM_SOURCE, is_negated(folded, found.start(), found.end()),
            item.category == 'Medicamento' and in_allergy_context(text, found.start()),
        ))
    return residual


def _normalize_with_gemini(raw_text: str, custom_instruction: str, api_key: str,
                           base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    from google import genai
    from triage.ai_analyzer import GEMINI_REQUEST_TIMEOUT, _pseudonymize, _sanitize_schema_for_gemini

    # Sin timeout, una llamada colgada bloquearia indefinidamente un hilo del worker LLM.
    client = genai.Client(api_key=api_key, http_options={'timeout': GEMINI_REQUEST_TIMEOUT * 1000})
    pseudonymized = _pseudonymize(raw_text)
    resolved = "\n".join(
        f'- "{m["raw_term"]}" -> {m["medical_term"]}' + (f' ({m["code"]})' if m["code"] else '')
        for m in base["mappings"]
    ) or "- (ninguno)"
    prompt = f"""Eres un normalizador terminológico clínico para triaje de urgencias en Colombia.

RELATO:
"{pseudonymized['text']}"

TÉRMINOS YA NORMALIZADOS POR EL CATÁLOGO (no los repitas):
{resolved}

TAREA:
1. En mappings incluye SOLO los términos clínicos del relato que no estén en la lista anterior: síntomas, signos, diagnósticos, antecedentes y medicamentos.
2. raw_term se copia literalmente del relato.
3. code: CIE-10 en formato OMS (p. ej. R06.0) para conceptos clínicos y ATC para medicamentos. Si no conoces el código con certeza, déjalo vacío; nunca lo inventes.
4. normalized_text: el relato completo en lenguaje clínico formal, conservando las negaciones y los marcadores entre corchetes.
5. summary: resumen clínico en 1 o 2 líneas.

Instrucción adicional: {custom_instruction or 'ninguna'}
"""
    last_error: Optional[Exception] = None
    for model_name in _candidate_models():
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': _sanitize_schema_for_gemini(NormalizationOutputSchema),
                },
            )
            if not response.text:
                continue
            # Una respuesta que no cumple el contrato lanza ValidationError y se prueba el siguiente modelo.
            parsed = NormalizationOutputSchema.model_validate(json.loads(response.text))
        except Exception as err:
            last_error = err
            logger.warning(f"Fallo del normalizador con {model_name}: {err}")
            continue

        normalized_text = parsed.normalized_text
        for placeholder, field in (("[NOMBRE]", "name"), ("[TELEFONO]", "phone"), ("[DOCUMENTO]", "documentId")):
            value = pseudonymized['identifiers'].get(field)
            if value:
                normalized_text = normalized_text.replace(placeholder, value)

        mappings = base["mappings"] + _residual_mappings(raw_text, parsed.mappings, base["mappings"])
        mappings.sort(key=lambda m: fold(raw_text).find(fold(m["raw_term"])))
        return {
            **base,
            "normalized_text": normalized_text or base["normalized_text"],
            "summary": parsed.summary or base["summary"],
            "mappings": mappings,
            "layers": _layer_counts(mappings),
            "engine": f"Catálogo terminológico local + LLM ({model_name})",
        }
    if last_error:
        raise last_error
    return None


def normalize_clinical_text(raw_text: str, custom_instruction: str = "") -> Dict[str, Any]:
    base = normalize_with_rules(raw_text)
    api_key = _resolve_gemini_key()
    if api_key:
        try:
            enriched = _normalize_with_gemini(raw_text, custom_instruction, api_key, base)
            if enriched:
                return enriched
        except Exception as gemini_err:
            logger.warning(f"Fallo en llamada a Gemini normalizer: {gemini_err}. Usando solo el catálogo.")
    return base
