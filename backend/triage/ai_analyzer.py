import os
import re
import json
import logging
from google import genai
from google.genai import types
from .clinical_protocol import evaluate_christus_sinergia_triage

logger = logging.getLogger(__name__)

# FIX-TEC-006: Timeout y manejo explicitico de errores en llamadas a la API de Gemini.
GEMINI_REQUEST_TIMEOUT = int(os.getenv('GEMINI_TIMEOUT_SECONDS', '30'))


def analyze_triage_transcript(transcript: str) -> dict:
    """
    Calls Gemini API to analyze a clinical transcript and extract entities.
    Returns a dictionary matching the triage schema.
    """
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

    if not api_key:
        logger.error("No GEMINI_API_KEY found in database or environment variables.")
        return {"error": "No se encontro una GEMINI_API_KEY valida."}

    client = genai.Client(api_key=api_key, http_options={'timeout': 15000})

    from .clinical_protocol import CHRISTUS_SINERGIA_LEVELS, evaluate_christus_sinergia_triage

    prompt = f"""
    Eres un Especialista Medico de Triaje de Urgencias del sistema CHRISTUS SINERGIA Salud (conforme a la Resolucion 5596 del Ministerio de Salud de Colombia).
    Tu labor es clasificar rigurosamente la gravedad del paciente segun la siguiente escala institucional de 5 niveles:

    CATEGORIAS DE CLASIFICACION TRIAGE - CHRISTUS SINERGIA SALUD:
    - TRIAGE 1: REANIMACION (Rojo) - Atencion: Inmediata.
      Definicion: Riesgo vital que necesita maniobras de reanimacion por compromiso ventilatorio, respiratorio, hemodinamico o neurologico, perdida de miembro u organo.
      Criterios/Motivos: Ausencia de signos vitales, inconciencia, dificultad respiratoria severa, hipotermia severa, traumatismos severos multiples, quemaduras en todo el cuerpo, perdida de miembro u organo, hemorragia masiva, trabajo de parto expulsivo, abuso sexual < 72 horas.

    - TRIAGE 2: EMERGENCIA (Naranja) - Atencion: Dentro de los siguientes 30 minutos.
      Definicion: La condicion clinica puede evolucionar hacia un rapido deterioro o a la muerte, o incrementar el riesgo de perdida de miembro u organo.
      Criterios/Motivos: Alteracion aguda de signos vitales, estado convulsivo, dificultad respiratoria moderada, crisis hipertensiva, diabetes descompensada, dolor toracico con signos de alarma (sospecha SCA), trauma severo, quemadura de III grado, riesgo de perdida de miembro u organo, fractura expuesta, sangrado vaginal en embarazadas, trabajo de parto, abuso sexual > 72 horas, agitacion psicomotora, ingestion de sustancias toxicas o envenenamiento.

    - TRIAGE 3: URGENCIA (Amarillo) - Atencion: Hasta 120 minutos.
      Definicion: Requiere medidas diagnosticas y terapeuticas en urgencias. Pacientes estables fisiologicamente pero que necesitan examen complementario o tratamiento rapido porque su situacion puede empeorar si no se actua.
      Criterios/Motivos: Vertigo severo, dificultad respiratoria leve, vomito y diarrea con deshidratacion severa, sintomas asociados a dialisis, trauma moderado, quemadura de II o III grado localizada, reaccion alergica con brote generalizado, valoracion medico legal.

    - TRIAGE 4: CONSULTA PRIORITARIA (Verde) - Atencion: Direccionamiento a su EPS.
      Definicion: Condiciones que no comprometen su estado general ni representan riesgo vital o funcional evidente, con riesgo de secuelas si no recibe atencion correspondiente.
      Criterios/Motivos: Tos y congestion, faringitis o amigdalitis, vomito y diarrea sin deshidratacion, dolor leve a moderado de mas de 24 horas, trauma leve, signos de infeccion local, ardor al orinar, enfermedad venerea aguda, ansiedad y depresion.

    - TRIAGE 5: CONSULTA EXTERNA (Azul) - Atencion: Direccionamiento a su EPS.
      Definicion: Problemas agudos o cronicos sin evidencia de deterioro del estado general y sin riesgo evidente para la vida o la funcionalidad.
      Criterios/Motivos: Sintomas agudos sin compromiso general, dolor de cabeza cronico, tos cronica, inapetencia, diarrea cronica, estrenimiento, dolor abdominal cronico, dolor postraumatico leve, dermatitis, estres emocional, enfermedades cronicas, formulacion de medicamentos, lectura de examenes.

    Analiza la conversacion medica transcrita:
    "{transcript}"

    Responde ESTRICTAMENTE con un objeto JSON valido con este esquema exacto:
    {{
      "patientInfo": {{
        "name": "string o null",
        "documentId": "string numerico o null",
        "birthDate": "YYYY-MM-DD o null",
        "gender": "male | female | other | unknown",
        "phone": "string o null",
        "insurance": "string o null"
      }},
      "entities": {{
        "symptoms": ["string"],
        "medications": ["string"],
        "vitals": ["string"],
        "history": ["string"]
      }},
      "triage": {{
        "level": 1,
        "name": "Reanimacion | Emergencia | Urgencia | Consulta Prioritaria | Consulta Externa",
        "attention_time": "Inmediata | Dentro de los siguientes 30 minutos | Hasta 120 minutos | Direccionamiento a su EPS",
        "justification": "Explicacion clinica concisa fundamentada en el protocolo Christus Sinergia Salud"
      }},
      "confidence": 0.95,
      "protocol": "Christus Sinergia Salud"
    }}
    """

    active_model = 'gemini-2.5-flash'
    try:
        from system_settings.models import SystemConfiguration
        config = SystemConfiguration.get_solo()
        if config.active_llm_engine:
            active_model = config.active_llm_engine
    except Exception as cfg_err:
        logger.debug(f"Could not read active_llm_engine from DB: {cfg_err}")

    # Fallback models si el modelo principal sufre 503 (alta demanda)
    candidate_models = [active_model]
    if 'gemini' in active_model:
        for backup in ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']:
            if backup not in candidate_models:
                candidate_models.append(backup)

    for model_name in candidate_models:
        try:
            logger.info(f"Intentando clasificacion de triaje con LLM '{model_name}'...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            parsed = json.loads(response.text)
            if 'triage' in parsed and 'level' in parsed['triage']:
                parsed['engine_used'] = f"LLM ({model_name})"
                return parsed
        except json.JSONDecodeError as json_err:
            logger.warning(f"Respuesta JSON no valida de {model_name}: {json_err}")
        except Exception as api_err:
            logger.warning(f"Fallo en llamada a {model_name}: {api_err}")

    # Fallback Asistencial Garantizado: Motor de Reglas Christus Sinergia Salud
    logger.warning("Activando motor determinista de respaldo Christus Sinergia Salud...")
    rule_triage = evaluate_christus_sinergia_triage(transcript)

    # Extraccion heuristica basica de entidades y datos
    symptoms = []
    norm_tr = transcript.lower()
    for s_kw in ["dolor de cabeza", "dolor toracico", "dolor en el pecho", "dificultad respiratoria",
                 "fiebre", "tos", "vomito", "diarrea", "mareo", "vertigo", "fatiga"]:
        if s_kw in norm_tr:
            symptoms.append(s_kw)

    doc_match = re.search(r'\b(?:cc|cédula|cedula|identificación|documento|numero|ti)?\s*([0-9]{6,11})\b', transcript, re.I)
    doc_id = doc_match.group(1) if doc_match else None

    name_match = re.search(r'\b(?:soy|me llamo|paciente|nombre(?:\s+es)?)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]{3,30})', transcript, re.I)
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
            "vitals": [],
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
        "warning": (
            "El servicio LLM en la nube presentó alta demanda temporal (código 503). "
            "Se aplicó el Motor Clínico de Reglas Christus Sinergia Salud para garantizar "
            "la clasificación y la continuidad asistencial sin demoras."
        )
    }
