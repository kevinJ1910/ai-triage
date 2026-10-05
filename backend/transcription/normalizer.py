"""
Normalizacion de texto clinico coloquial a terminologia estandarizada (SNOMED-CT / CIE-10).
Usa Gemini si hay clave disponible y, si no hay clave o la llamada falla, un catalogo determinista.
Se ejecuta en el worker 'llm'; la vista solo encola la tarea.
"""
import json
import logging
import os
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

_FALLBACK_TERMS = [
    ("aprieta el pecho", "opresion toracica", "29857009", "Sintoma"),
    ("falta el aire", "disnea de medianos esfuerzos", "267036007", "Sintoma"),
    ("posartan", "losartan potasico", "318851002", "Medicamento"),
    ("presion alta", "hipertension arterial sistemica", "38341003", "Antecedente"),
    ("chilla el pecho", "sibilancias respiratorias", "52655008", "Signo"),
    ("dolor en la boca del estomago", "epigastralgia", "79890006", "Sintoma"),
    ("calentura", "hipertermia febril", "386661006", "Signo"),
    ("mareo", "vertigo / inestabilidad postural", "404640003", "Sintoma"),
    ("pastilla pal azucar", "hipoglicemiante oral (metformina)", "372567009", "Medicamento"),
    ("sudor frio", "diaforesis profusa", "52613005", "Signo"),
    ("fatiga", "astenia / adinamia", "84229001", "Sintoma"),
    ("palpitaciones", "taquicardia percibida", "80313002", "Signo"),
]


def _resolve_gemini_key() -> str:
    try:
        from system_settings.models import APIKeyCredential
        cred = APIKeyCredential.objects.filter(provider='gemini', is_active=True).first()
        if cred:
            return cred.get_key()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip('"\'')


def _normalize_with_gemini(raw_text: str, custom_instruction: str, api_key: str) -> Dict[str, Any]:
    from google import genai
    client = genai.Client(api_key=api_key)
    prompt = f"""
Eres un motor de normalizacion clinica hospitalaria de alta precision para sistemas de triaje de urgencias.
Tu objetivo es traducir el siguiente relato crudo o coloquial a terminologia medica profesional:
"{raw_text}"

Instruccion adicional: {custom_instruction or 'Estandarizar sintomas, signos, medicamentos y antecedentes segun SNOMED-CT.'}

Debes responder UNICAMENTE en formato JSON con la siguiente estructura:
{{
  "normalized_text": "Texto completo y coherente redactado en lenguaje clinico formal",
  "summary": "Resumen diagnostico en 1 o 2 lineas",
  "mappings": [
    {{
      "raw_term": "termino coloquial detectado",
      "medical_term": "termino medico formal",
      "code_snomed": "codigo numerico o identicador SNOMED-CT / CIE-10",
      "category": "Sintoma | Signo | Medicamento | Antecedente"
    }}
  ]
}}
"""
    active_engine = 'gemini-2.5-flash'
    try:
        from system_settings.models import SystemConfiguration
        cfg = SystemConfiguration.get_solo()
        if cfg.active_llm_engine:
            active_engine = cfg.active_llm_engine
    except Exception:
        pass

    response = client.models.generate_content(
        model=active_engine,
        contents=prompt,
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(response.text) if response.text else None


def normalize_with_rules(raw_text: str) -> Dict[str, Any]:
    """Motor determinista de respaldo si no hay API Key, falla la red o el worker no responde."""
    mappings = []
    norm_text = raw_text
    for raw, med, code, cat in _FALLBACK_TERMS:
        if raw.lower() in raw_text.lower():
            mappings.append({
                "raw_term": raw,
                "medical_term": med,
                "code_snomed": code,
                "category": cat
            })
            norm_text = re.compile(re.escape(raw), re.IGNORECASE).sub(med, norm_text)

    return {
        "normalized_text": norm_text,
        "summary": "Relato clinico estandarizado conforme a catalogo SNOMED-CT.",
        "mappings": mappings
    }


def normalize_clinical_text(raw_text: str, custom_instruction: str = "") -> Dict[str, Any]:
    api_key = _resolve_gemini_key()
    if api_key:
        try:
            normalized = _normalize_with_gemini(raw_text, custom_instruction, api_key)
            if normalized:
                return normalized
        except Exception as gemini_err:
            logger.warning(f"Fallo en llamada a Gemini normalizer: {gemini_err}. Usando motor de respaldo.")
    return normalize_with_rules(raw_text)
