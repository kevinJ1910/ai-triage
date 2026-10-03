import json
import uuid
import logging
import os
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from core.permissions import CanUseTranscriber
from .whisper_engine import WhisperEngine

logger = logging.getLogger(__name__)

# FIX-TEC-004: Variable global engine eliminada. El Singleton de WhisperEngine
# garantiza una sola instancia con threading.Lock sin necesidad de estado global en el modulo.
# FIX-TEC-007: Logging centralizado en settings.py LOGGING. Sin FileHandler manual.

@api_view(['POST'])
@permission_classes([IsAuthenticated, CanUseTranscriber])
def transcribe_chunk(request) -> JsonResponse:
    # FIX-TEC-004: Usar Singleton directamente, sin variable global mutable en el modulo.
    try:
        engine = WhisperEngine()
    except Exception as engine_err:
        logger.critical(f"Could not initialize WhisperEngine: {engine_err}", exc_info=True)
        return JsonResponse({"error": "Whisper Engine could not be initialized"}, status=503)
        
    try:
        audio_file = request.FILES.get('audio')
        if not audio_file:
            return JsonResponse({"error": "No audio file provided under key 'audio'"}, status=400)
            
        session_id = request.data.get('session_id')
        if not session_id:
            # Generate a temporary session_id if none was provided
            session_id = str(uuid.uuid4())
            logger.warning(f"No session_id provided. Using generated UUID: {session_id}")

        # Read the file content bytes
        audio_bytes = audio_file.read()
        if len(audio_bytes) == 0:
            return JsonResponse({"error": "Empty audio file received"}, status=400)

        # Transcribe chunk using singleton engine
        result = engine.transcribe_chunk(audio_bytes, session_id)
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error in transcribe_chunk view: {e}", exc_info=True)
        return JsonResponse({"error": "Internal transcription failure"}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated, CanUseTranscriber])
def reset_session(request) -> JsonResponse:
    # FIX-TEC-004: Singleton directo, sin estado global mutable.
    try:
        engine = WhisperEngine()
    except Exception:
        return JsonResponse({"error": "Whisper Engine is not initialized"}, status=503)

    try:
        # request.data acepta JSON y form-data; el JSON invalido lo rechaza DRF con 400.
        session_id = request.data.get('session_id')

        if not session_id:
            return JsonResponse({"error": "Missing parameter 'session_id'"}, status=400)

        engine.reset_session(session_id)
        return JsonResponse({"status": "success", "message": f"Session {session_id} reset successfully"})

    except Exception as e:
        logger.error(f"Error in reset_session view: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to reset session"}, status=500)

@require_http_methods(["GET"])
def health_check(request: HttpRequest) -> JsonResponse:
    try:
        engine = WhisperEngine()
    except Exception as engine_err:
        logger.critical(f"Could not initialize WhisperEngine in health check: {engine_err}", exc_info=True)
        return JsonResponse({
            "status": "unhealthy", 
            "error": "Whisper Engine could not be initialized"
        }, status=503)
        
    try:
        status_info = engine.get_status()
        status_info["status"] = "healthy"
        return JsonResponse(status_info)
    except Exception as e:
        logger.error(f"Error in health_check view: {e}", exc_info=True)
        return JsonResponse({
            "status": "unhealthy",
            "error": "Failed to get Whisper Engine status"
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def normalize_text(request) -> JsonResponse:
    """
    Normaliza texto clinico crudo/coloquial a terminologia medica estandarizada (SNOMED-CT / CIE-10).
    Utiliza Gemini o motor de reglas clinicas estructuradas.
    """
    data = request.data
    if not isinstance(data, dict):
        return JsonResponse({"error": "Formato JSON invalido"}, status=400)

    from core.validation import validate_payload, NormalizeTextSchema
    try:
        validated = validate_payload(NormalizeTextSchema, data)
        raw_text = validated.raw_text.strip()
    except Exception as e:
        return JsonResponse(getattr(e, 'detail', {"error": str(e)}), status=400)

    custom_instruction = data.get("custom_instruction", "")

    # Intentar usar Gemini API si esta disponible
    api_key = ""
    try:
        from system_settings.models import APIKeyCredential
        cred = APIKeyCredential.objects.filter(provider='gemini', is_active=True).first()
        if cred:
            api_key = cred.get_key()
    except Exception:
        pass

    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip('"\'')

    normalized_data = None
    if api_key:
        try:
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
            if response.text:
                normalized_data = json.loads(response.text)
        except Exception as gemini_err:
            logger.warning(f"Fallo en llamada a Gemini normalizer: {gemini_err}. Usando motor de respaldo.")

    # Motor determinista de respaldo si no hay API Key o falla la red
    if not normalized_data:
        fallbacks = [
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
            ("palpitaciones", "taquicardia percibida", "80313002", "Signo")
        ]

        mappings = []
        norm_text = raw_text
        for raw, med, code, cat in fallbacks:
            if raw.lower() in raw_text.lower():
                mappings.append({
                    "raw_term": raw,
                    "medical_term": med,
                    "code_snomed": code,
                    "category": cat
                })
                # Reemplazar en texto normalizado
                import re
                pattern = re.compile(re.escape(raw), re.IGNORECASE)
                norm_text = pattern.sub(med, norm_text)

        normalized_data = {
            "normalized_text": norm_text,
            "summary": "Relato clinico estandarizado conforme a catalogo SNOMED-CT.",
            "mappings": mappings
        }

    return JsonResponse(normalized_data)
