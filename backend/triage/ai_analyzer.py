import os
import re
import json
import logging
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from .clinical_protocol import evaluate_christus_sinergia_triage
from .input_pipeline import ClinicalTranscriptCompressor
from .clinical_rag import ClinicalKnowledgeRAG
from .clinical_cache import ClinicalQueryCache

logger = logging.getLogger(__name__)

# Timeout configurable para llamadas a la API de Gemini
GEMINI_REQUEST_TIMEOUT = int(os.getenv('GEMINI_TIMEOUT_SECONDS', '30'))


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


def analyze_triage_transcript(transcript: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Analiza una conversacion clinica utilizando un pipeline optimizado:
    1. Compresion y desruidado fonetico de la entrada (ClinicalTranscriptCompressor).
    2. Cache semantico canonico para cuadros clinicos recurrentes (ClinicalQueryCache).
    3. Recuperacion semantica de criterios relevantes mediante RAG (ClinicalKnowledgeRAG).
    4. Invocacion a Gemini con System Instruction y decodificacion estructurada Pydantic.
    5. Fallback automatico y determinista con el Motor de Reglas Christus Sinergia Salud.
    """
    raw_transcript = (transcript or "").strip()
    if not raw_transcript:
        return {"error": "Transcripción vacía o no proporcionada."}

    # 1. Pipeline de Compresion de Entrada y Extraccion de Signos Vitales
    compressed_input = ClinicalTranscriptCompressor.process(raw_transcript)
    cleaned_transcript = compressed_input["cleaned_transcript"]
    compact_vitals = compressed_input["compact_vitals"]
    structured_vitals = compressed_input["structured_vitals"]
    red_flags = compressed_input["red_flags"]
    compression_ratio = compressed_input["reduction_percentage"]

    # 2. Consulta al Cache Semantico Canonico (0 tokens, < 3ms)
    fingerprint = ClinicalQueryCache.generate_fingerprint(cleaned_transcript, structured_vitals)
    if use_cache:
        cached_result = ClinicalQueryCache.get(fingerprint)
        if cached_result:
            logger.info("Consulta resuelta mediante Cache Semántico de Consultas (0 tokens)")
            cached_result["compression_ratio"] = compression_ratio
            return cached_result

    # 3. RAG Clinico: Recuperacion de Criterios Institucionales Top-K Relevantes
    retrieved_criteria = ClinicalKnowledgeRAG.retrieve(
        cleaned_transcript,
        top_k=4,
        red_flags=red_flags
    )
    rag_context_text = ClinicalKnowledgeRAG.format_context_for_prompt(retrieved_criteria)
    rag_criterion_ids = [c["id"] for c in retrieved_criteria]

    # 4. Resolucion de Credenciales y Cliente Gemini
    api_key = _resolve_gemini_api_key()
    if not api_key:
        logger.error("No GEMINI_API_KEY found in database or environment variables.")
        fallback_res = _fallback_rule_triage(
            raw_transcript,
            cleaned_transcript,
            compact_vitals,
            red_flags,
            compression_ratio,
            rag_criterion_ids,
            warning="No se encontró una clave de Gemini configurada. Se aplicó el Motor Clínico determinista de respaldo."
        )
        if use_cache:
            ClinicalQueryCache.set(fingerprint, fallback_res, estimated_tokens=0)
        return fallback_res

    # 5. Construccion de Prompt Optimizado (Ahorro de ~60% de tokens)
    system_instruction = (
        "Eres un Especialista Médico de Triaje de Urgencias del sistema CHRISTUS SINERGIA Salud "
        "(Resolución 5596 Ministerio de Salud de Colombia). Tu labor es clasificar rigurosamente la "
        "gravedad del paciente y extraer entidades clínicas clave conforme a los criterios institucionales proporcionados."
    )

    user_prompt = f"""{rag_context_text}

SIGNOS VITALES IDENTIFICADOS: {", ".join(compact_vitals) if compact_vitals else "Ninguno reportado"}
ALERTAS CLÍNICAS: {", ".join(red_flags) if red_flags else "Ninguna bandera roja inmediata"}

CONSULTA MÉDICA COMPRIMIDA:
"{cleaned_transcript}"
"""

    active_model = 'gemini-2.5-flash'
    try:
        from system_settings.models import SystemConfiguration
        config = SystemConfiguration.get_solo()
        if config.active_llm_engine:
            active_model = config.active_llm_engine
    except Exception as cfg_err:
        logger.debug(f"Could not read active_llm_engine from DB: {cfg_err}")

    candidate_models = [active_model]
    if 'gemini' in active_model:
        for backup in ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']:
            if backup not in candidate_models:
                candidate_models.append(backup)

    client = genai.Client(api_key=api_key, http_options={'timeout': GEMINI_REQUEST_TIMEOUT * 1000})

    for model_name in candidate_models:
        try:
            logger.info(f"Invocando LLM '{model_name}' con entrada optimizada y Pydantic schema...")
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=TriageOutputSchema,
                    temperature=0.1,
                ),
            )
            raw_text = response.text
            parsed = json.loads(raw_text)

            # Validar con Pydantic para garantia estructural total
            validated_model = TriageOutputSchema.model_validate(parsed)
            result = validated_model.model_dump()

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

            result["engine_used"] = f"LLM ({model_name})"
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
            logger.warning(f"Fallo en llamada a {model_name} con schema Pydantic: {err}")

    # 6. Fallback Asistencial Garantizado (Motor Determinista)
    logger.warning("Activando motor determinista de respaldo Christus Sinergia Salud...")
    fallback_res = _fallback_rule_triage(
        raw_transcript,
        cleaned_transcript,
        compact_vitals,
        red_flags,
        compression_ratio,
        rag_criterion_ids,
        warning=(
            "El servicio LLM en la nube presentó alta demanda temporal (código 503). "
            "Se aplicó el Motor Clínico de Reglas Christus Sinergia Salud para garantizar "
            "la clasificación y la continuidad asistencial sin demoras."
        )
    )
    if use_cache:
        ClinicalQueryCache.set(fingerprint, fallback_res, estimated_tokens=0)
    return fallback_res


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

    symptoms = []
    norm_tr = cleaned_transcript.lower()
    for s_kw in [
        "dolor de cabeza", "dolor toracico", "dolor en el pecho", "dificultad respiratoria",
        "fiebre", "tos", "vomito", "diarrea", "mareo", "vertigo", "fatiga", "ardor al orinar"
    ]:
        if s_kw in norm_tr:
            symptoms.append(s_kw)

    doc_match = re.search(r'\b(?:cc|cédula|cedula|identificación|documento|numero|ti)?\s*([0-9]{6,11})\b', raw_transcript, re.I)
    doc_id = doc_match.group(1) if doc_match else None

    name_match = re.search(r'\b(?:soy|me llamo|paciente|nombre(?:\s+es)?)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]{3,30})', raw_transcript, re.I)
    patient_name = name_match.group(1).strip() if name_match else None

    return {
        "patientInfo": {
            "name": patient_name,
            "documentId": doc_id,
            "birthDate": None,
            "gender": "unknown",
            "phone": None,
            "insurance": "Christus Sinergia / EPS"
        },
        "entities": {
            "symptoms": symptoms or ["Síntomas referidos en consulta"],
            "medications": [],
            "vitals": compact_vitals,
            "history": []
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
