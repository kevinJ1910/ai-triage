import os
import re
import json
import logging
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from .clinical_protocol import evaluate_christus_sinergia_triage, _normalize_text
from .input_pipeline import ClinicalTranscriptCompressor
from .negation import split_affirmed_negated
from .clinical_rag import ClinicalKnowledgeRAG
from .clinical_cache import ClinicalQueryCache

logger = logging.getLogger(__name__)

# Timeout configurable para llamadas a la API de Gemini
GEMINI_REQUEST_TIMEOUT = int(os.getenv('GEMINI_TIMEOUT_SECONDS', '30'))

# Modelos de respaldo si falla el modelo activo (configurable, separados por coma).
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.getenv('GEMINI_FALLBACK_MODELS', 'gemini-2.5-flash,gemini-3.5-flash-lite').split(',') if m.strip()
]

# Seudonimizacion de identificadores antes de enviar texto a un LLM externo (Ley 1581 de 2012).
_PHONE_RE = re.compile(r'\b3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}\b')
_DOCUMENT_RE = re.compile(r'\b\d{6,11}\b')
_NAME_RE = re.compile(
    r'(?i:\b(?:me llamo|mi nombre es|se llama|su nombre es)\s+)'
    r'((?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s?){1,4})'
)
_PLACEHOLDERS = ("[NOMBRE]", "[DOCUMENTO]", "[TELEFONO]")


def _pseudonymize(text: str) -> Dict[str, Any]:
    """
    Reemplaza nombre, telefono y documento por marcadores y devuelve los valores originales,
    que se reinyectan localmente en patientInfo sin salir del servidor.
    """
    found: Dict[str, Optional[str]] = {"name": None, "phone": None, "documentId": None}

    name_match = _NAME_RE.search(text)
    if name_match:
        found["name"] = name_match.group(1).strip()
        text = text[:name_match.start(1)] + "[NOMBRE] " + text[name_match.end(1):]

    phone_match = _PHONE_RE.search(text)
    if phone_match:
        found["phone"] = re.sub(r'\D', '', phone_match.group(0))
    text = _PHONE_RE.sub("[TELEFONO]", text)

    doc_match = _DOCUMENT_RE.search(text)
    if doc_match:
        found["documentId"] = doc_match.group(0)
    text = _DOCUMENT_RE.sub("[DOCUMENTO]", text)

    return {"text": text, "identifiers": found}


def _restore_identifiers(patient_info: Dict[str, Any], identifiers: Dict[str, Optional[str]], raw_transcript: str) -> Dict[str, Any]:
    """Sustituye marcadores devueltos por el LLM con los valores reales extraidos localmente."""
    local = _extract_patient_info_rules(raw_transcript)
    for field in ("name", "documentId", "phone"):
        value = patient_info.get(field)
        if not value or any(ph in str(value) for ph in _PLACEHOLDERS):
            patient_info[field] = identifiers.get(field) or (local.get(field) if field != "phone" else None)
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
    symptoms: List[str] = Field(default_factory=list, description="Lista de sintomas clinicos expresados")
    medications: List[str] = Field(default_factory=list, description="Medicamentos de uso habitual o prescritos")
    vitals: List[str] = Field(default_factory=list, description="Constantes vitales detectadas en consulta")
    history: List[str] = Field(default_factory=list, description="Antecedentes patologicos o quirurgicos")


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


def analyze_triage_transcript(
    transcript: str, use_cache: bool = True, allow_llm: bool = True, model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analiza una conversacion clinica utilizando un pipeline optimizado:
    1. Evaluacion determinista previa de Christus Sinergia Salud como pauta prioritaria.
    2. Compresion y desruidado fonetico de la entrada (ClinicalTranscriptCompressor).
    3. Cache semantico canonico para cuadros clinicos recurrentes (ClinicalQueryCache).
    4. Recuperacion semantica de criterios relevantes mediante RAG (ClinicalKnowledgeRAG).
    5. Invocacion a Gemini con System Instruction y decodificacion estructurada sanitizada.
    6. Fallback automatico garantizado con el Motor de Reglas Christus Sinergia Salud.

    allow_llm=False omite Gemini y aplica directamente el motor de reglas (lo usa la vista
    cuando el worker de inferencia no responde, para no dejar al clinico sin clasificacion).

    model fija un unico modelo, sin modelos de respaldo: lo usan los comandos de evaluacion para
    que las metricas de un modelo no mezclen respuestas de otro. Si falla, aplica el motor de reglas.
    """
    raw_transcript = (transcript or "").strip()
    if not raw_transcript:
        return {"error": "Transcripción vacía o no proporcionada."}

    # 1. Evaluacion de Reglas Institucionales Christus Sinergia Salud (Prioridad Base)
    rule_baseline = evaluate_christus_sinergia_triage(raw_transcript)

    # 2. Pipeline de Compresion de Entrada y Extraccion de Signos Vitales
    compressed_input = ClinicalTranscriptCompressor.process(raw_transcript)
    cleaned_transcript = compressed_input["cleaned_transcript"]
    compact_vitals = compressed_input["compact_vitals"]
    structured_vitals = compressed_input["structured_vitals"]
    red_flags = compressed_input["red_flags"]
    compression_ratio = compressed_input["reduction_percentage"]

    # 3. Consulta al Cache Semantico Canonico (0 tokens, < 3ms)
    fingerprint = ClinicalQueryCache.generate_fingerprint(cleaned_transcript, structured_vitals)
    if use_cache:
        cached_result = ClinicalQueryCache.get(fingerprint)
        if cached_result:
            logger.info("Consulta resuelta mediante Cache Semántico de Consultas (0 tokens)")
            # La cache no guarda datos del paciente: se extraen de ESTA transcripcion.
            cached_result["patientInfo"] = _extract_patient_info_rules(raw_transcript)
            cached_result["compression_ratio"] = compression_ratio
            return cached_result

    # 4. RAG Clinico: Recuperacion de Criterios Institucionales Top-K Relevantes
    retrieved_criteria = ClinicalKnowledgeRAG.retrieve(
        cleaned_transcript,
        top_k=4,
        red_flags=red_flags
    )
    rag_context_text = ClinicalKnowledgeRAG.format_context_for_prompt(retrieved_criteria)
    rag_criterion_ids = [c["id"] for c in retrieved_criteria]

    # 5. Resolucion de Credenciales y Cliente Gemini
    api_key = _resolve_gemini_api_key() if allow_llm else ""
    if not api_key:
        if allow_llm:
            logger.error("No GEMINI_API_KEY found in database or environment variables.")
            warning = "No se encontró una clave de Gemini configurada. Se aplicó el Motor Clínico determinista de respaldo Christus Sinergia Salud."
        else:
            warning = (
                "El servicio de inferencia no respondió a tiempo. Se aplicó el Motor Clínico determinista "
                "de respaldo Christus Sinergia Salud para garantizar la continuidad asistencial."
            )
        fallback_res = _fallback_rule_triage(
            raw_transcript,
            cleaned_transcript,
            compact_vitals,
            red_flags,
            compression_ratio,
            rag_criterion_ids,
            warning=warning
        )
        # Solo se cachea la falta de clave; un worker caido es transitorio y debe reintentarse.
        if use_cache and allow_llm:
            ClinicalQueryCache.set(fingerprint, fallback_res, estimated_tokens=0)
        return fallback_res

    # 6. Construccion de Prompt Optimizado con Prioridad Christus Sinergia Salud
    system_instruction = (
        "Especialista de Triaje de Urgencias CHRISTUS SINERGIA (Res. 5596 Minsalud Colombia). "
        "Clasifica rigurosamente el nivel de gravedad y extrae entidades clínicas con máxima fidelidad a los criterios institucionales."
    )

    pseudonymized = _pseudonymize(cleaned_transcript)
    vitals_str = ", ".join(compact_vitals) if compact_vitals else "Sin reporte"
    alerts_str = ", ".join(red_flags) if red_flags else "Sin banderas rojas"

    user_prompt = f"""{rag_context_text}

PAUTA CLÍNICA BASE (CHRISTUS SINERGIA / RES. 5596):
Nivel {rule_baseline['level']} ({rule_baseline['name']}) | Ventana: {rule_baseline['attention_time']}
Criterio: {rule_baseline['justification']}

SIGNOS VITALES: {vitals_str} | ALERTAS: {alerts_str}
CONSULTA COMPRIMIDA:
"{pseudonymized['text']}"
"""

    active_model = 'gemini-2.5-flash'
    try:
        from system_settings.models import SystemConfiguration
        config = SystemConfiguration.get_solo()
        if config.active_llm_engine:
            active_model = config.active_llm_engine
    except Exception as cfg_err:
        logger.debug(f"Could not read active_llm_engine from DB: {cfg_err}")

    if model:
        candidate_models = [model]
    else:
        candidate_models = [active_model]
        if 'gemini' in active_model:
            candidate_models += [m for m in GEMINI_FALLBACK_MODELS if m not in candidate_models]

    client = genai.Client(api_key=api_key, http_options={'timeout': GEMINI_REQUEST_TIMEOUT * 1000})
    gemini_schema = _sanitize_schema_for_gemini(TriageOutputSchema)

    last_error: Optional[Exception] = None
    for model_name in candidate_models:
        try:
            logger.info(f"Invocando LLM '{model_name}' con entrada optimizada y schema sanitizado...")
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=gemini_schema,
                    temperature=0.1,
                ),
            )
            raw_text = response.text
            parsed = json.loads(raw_text)

            # Validar con Pydantic para garantia estructural total
            validated_model = TriageOutputSchema.model_validate(parsed)
            result = validated_model.model_dump()
            result["patientInfo"] = _restore_identifiers(
                result.get("patientInfo") or {}, pseudonymized["identifiers"], raw_transcript
            )

            # Fusionar signos vitales extraidos por regex si el LLM no los capturo todos
            if compact_vitals:
                current_v = result.get("entities", {}).get("vitals", [])
                for cv in compact_vitals:
                    if cv not in current_v:
                        current_v.append(cv)
                result["entities"]["vitals"] = current_v

            # Telemetria de Tokens
            usage = getattr(response, "usage_metadata", None)
            p_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
            c_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
            t_tokens = getattr(usage, "total_token_count", p_tokens + c_tokens) if usage else 0

            result["engine_used"] = f"LLM ({model_name}) + Christus Sinergia"
            result["cached"] = False
            result["prompt_tokens"] = p_tokens
            result["completion_tokens"] = c_tokens
            result["total_tokens"] = t_tokens
            result["compression_ratio"] = compression_ratio
            result["rag_context"] = rag_criterion_ids

            # Guardar en Cache Semantico para proximas consultas
            if use_cache:
                ClinicalQueryCache.set(fingerprint, result, estimated_tokens=t_tokens)

            return result

        except Exception as err:
            last_error = err
            logger.warning(f"Fallo en llamada a {model_name} con schema Pydantic: {err}")

    # 7. Fallback Asistencial Garantizado (Motor Determinista)
    logger.warning("Activando motor determinista de respaldo Christus Sinergia Salud...")
    fallback_res = _fallback_rule_triage(
        raw_transcript,
        cleaned_transcript,
        compact_vitals,
        red_flags,
        compression_ratio,
        rag_criterion_ids,
        warning=(
            f"{_describe_llm_failure(last_error)} "
            "Se aplicó el Motor Clínico de Reglas Christus Sinergia Salud para garantizar "
            "la clasificación y la continuidad asistencial sin demoras."
        )
    )
    # No se cachea: es un fallo transitorio y la proxima consulta debe reintentar el LLM.
    return fallback_res


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
    """Extrae documento y nombre del paciente por regex, sin LLM."""
    doc_match = re.search(r'\b(?:cc|cédula|cedula|identificación|documento|numero|ti)?\s*([0-9]{6,11})\b', raw_transcript, re.I)
    doc_id = doc_match.group(1) if doc_match else None

    name_match = re.search(r'\b(?:soy|me llamo|paciente|nombre(?:\s+es)?)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]{3,30})', raw_transcript, re.I)
    patient_name = name_match.group(1).strip() if name_match else None

    return {
        "name": patient_name,
        "documentId": doc_id,
        "birthDate": None,
        "gender": "unknown",
        "phone": None,
        "insurance": "Christus Sinergia / EPS"
    }


def _fallback_rule_triage(
    raw_transcript: str,
    cleaned_transcript: str,
    compact_vitals: List[str],
    red_flags: List[str],
    compression_ratio: float,
    rag_criterion_ids: List[str],
    warning: str
) -> Dict[str, Any]:
    """Genera la respuesta estandarizada mediante el motor determinista Christus Sinergia."""
    rule_triage = evaluate_christus_sinergia_triage(raw_transcript)

    norm_tr = _normalize_text(cleaned_transcript)
    symptoms, negated_findings = split_affirmed_negated(norm_tr, [
        "dolor de cabeza", "dolor toracico", "dolor en el pecho", "dificultad respiratoria",
        "fiebre", "tos", "vomito", "diarrea", "mareo", "vertigo", "fatiga", "ardor al orinar"
    ])

    return {
        "patientInfo": _extract_patient_info_rules(raw_transcript),
        "entities": {
            "symptoms": symptoms or ["Síntomas referidos en consulta"],
            "medications": [],
            "vitals": compact_vitals,
            "history": [],
            "negated_findings": negated_findings,
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
        "warning": warning
    }
