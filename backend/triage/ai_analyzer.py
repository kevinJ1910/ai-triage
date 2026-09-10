import os
import json
import logging
from google import genai
from google.genai import types

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

    client = genai.Client(api_key=api_key)

    prompt = f"""
    Eres un Asistente Medico de Triaje basado en el protocolo AI-Triage (similar a ESI y Manchester).
    Analiza la siguiente conversacion transcrita entre un medico y un paciente.
    Extrae la siguiente informacion:
    1. "patientInfo": Informacion basica del paciente mencionada en la conversacion.
       - "name": Nombre completo del paciente.
       - "documentId": Documento de identidad (cedula, pasaporte, etc.). Extrae unicamente digitos numericos.
       - "birthDate": Fecha de nacimiento (YYYY-MM-DD).
       - "gender": "male", "female", "other", o "unknown".
       - "phone": Numero de telefono (solo digitos).
       - "insurance": Aseguradora medica o EPS.
       Si un campo no se menciona, omitelo o devuelve null.

    2. "entities":
       - "symptoms": Lista de sintomas mencionados.
       - "medications": Lista de medicamentos mencionados.
       - "vitals": Constantes vitales o signos fisicos descritos.
       - "history": Antecedentes medicos o diagnosticos previos.

    Asigna un nivel de prioridad de triaje clinico del 1 al 5 (1=Resucitacion, 5=No Urgente)
    y una justificacion clinica concisa.

    Devuelve estrictamente un objeto JSON con esta estructura exacta:
    {{
      "patientInfo": {{
        "name": "string",
        "documentId": "string",
        "birthDate": "string",
        "gender": "male | female | other | unknown",
        "phone": "string",
        "insurance": "string"
      }},
      "entities": {{
        "symptoms": ["string"],
        "medications": ["string"],
        "vitals": ["string"],
        "history": ["string"]
      }},
      "triage": {{
        "level": 1,
        "justification": "string"
      }},
      "confidence": 0.95
    }}

    Transcripcion:
    "{transcript}"
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)
    except json.JSONDecodeError as json_err:
        logger.error(f"Gemini returned invalid JSON: {json_err}")
        return {"error": "Formato de respuesta invalido desde la API de IA"}
    except Exception as api_err:
        logger.error(f"Gemini API call failed: {api_err}", exc_info=True)
        return {"error": f"Servicio de IA temporalmente no disponible: {type(api_err).__name__}"}
