import os
import json
from google import genai
from google.genai import types

def analyze_triage_transcript(transcript: str) -> dict:
    """
    Calls Gemini API to analyze a clinical transcript and extract entities.
    Returns a dictionary matching the triage schema.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Eres un Asistente Médico de Triaje basado en el protocolo AI-Triage (similar a ESI y Manchester).
    Analiza la siguiente conversación transcrita entre un médico y un paciente.
    Extrae la siguiente información:
    1. "patientInfo": Información básica del paciente mencionada en la conversación.
       - "name": Nombre completo del paciente.
       - "documentId": Documento de identidad (cédula, pasaporte, etc.). Extrae únicamente dígitos numéricos.
       - "birthDate": Fecha de nacimiento (YYYY-MM-DD).
       - "gender": "male", "female", "other", o "unknown".
       - "phone": Número de teléfono (solo dígitos).
       - "insurance": Aseguradora médica o EPS.
       Si un campo no se menciona, omítelo o devuelve null.

    2. "entities":
       - "symptoms": Lista de síntomas mencionados.
       - "medications": Lista de medicamentos mencionados.
       - "vitals": Constantes vitales o signos físicos descritos.
       - "history": Antecedentes médicos o diagnósticos previos.

    Asigna un nivel de prioridad de triaje clínico del 1 al 5 (1=Resucitación, 5=No Urgente)
    y una justificación clínica concisa.

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

    Transcripción:
    "{transcript}"
    """

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {"error": "Invalid response format from AI"}
