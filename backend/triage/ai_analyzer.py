import os
import re
import json
import time
import hashlib
import logging
from typing import List, Optional, Literal, Dict, Any
from django.conf import settings
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from transcription.normalizer import concept_mappings

from .clinical_protocol import evaluate_christus_sinergia_triage, is_rule_fallback
from .input_pipeline import ClinicalTranscriptCompressor
from .clinical_rag import ClinicalKnowledgeRAG
from .clinical_cache import ClinicalQueryCache
from .entity_fusion import entities_from_terms, fuse_entities
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
    symptoms: List[str] = Field(default_factory=list, description="Sintomas y signos presentes (nunca los negados)")
    diagnoses: List[str] = Field(
        default_factory=list,
        description="Enfermedades, lesiones o estados del episodio actual nombrados como tales (fractura, quemadura, gripa, gestacion)",
    )
    medications: List[str] = Field(default_factory=list, description="Medicamentos de uso habitual o prescritos")
    allergies: List[str] = Field(default_factory=list, description="Sustancias a las que el paciente refiere alergia")
    vitals: List[str] = Field(default_factory=list, description="Constantes vitales detectadas en consulta")
    history: List[str] = Field(default_factory=list, description="Antecedentes patologicos o quirurgicos")
    negated_findings: List[str] = Field(
        default_factory=list,
        description="Hallazgos negados explicitamente ('niega dolor toracico', 'sin fiebre'); no van en symptoms",
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

            # Fusionar signos vitales extraidos por regex si el LLM no los capturo todos
            if compact_vitals:
                current_v = result.get("entities", {}).get("vitals", [])
                for cv in compact_vitals:
                    if cv not in current_v:
                        current_v.append(cv)
                result["entities"]["vitals"] = current_v

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
            if ner_engine:
                # Hibrido: las menciones del NER y la negacion determinista mandan; el LLM desempata.
                llm_entities = result["entities"]
                fused, details = fuse_entities(cleaned_transcript, ner_spans, normalized_terms, llm_entities,
                                               min_score=getattr(settings, "NER_MIN_SCORE", 0.6))
                result["entities"] = {**fused, "vitals": llm_entities.get("vitals", [])}
                result["ner_spans"] = details
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
