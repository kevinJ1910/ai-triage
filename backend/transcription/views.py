import json
import uuid
import logging
import os
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .whisper_engine import WhisperEngine

logger = logging.getLogger(__name__)

_log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(_log_dir, exist_ok=True)
fh = logging.FileHandler(os.path.join(_log_dir, 'backend_debug.log'))
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)
# Initialize WhisperEngine at module loading to warm up the model early
try:
    engine = WhisperEngine()
except Exception as engine_err:
    logger.critical(f"Could not initialize WhisperEngine on start: {engine_err}", exc_info=True)
    engine = None

@csrf_exempt
@require_http_methods(["POST"])
def transcribe_chunk(request: HttpRequest) -> JsonResponse:
    if engine is None:
        return JsonResponse({"error": "Whisper Engine is not initialized"}, status=503)
        
    try:
        audio_file = request.FILES.get('audio')
        if not audio_file:
            return JsonResponse({"error": "No audio file provided under key 'audio'"}, status=400)
            
        session_id = request.POST.get('session_id')
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
        return JsonResponse({"error": "Internal transcription failure", "details": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def reset_session(request: HttpRequest) -> JsonResponse:
    if engine is None:
        return JsonResponse({"error": "Whisper Engine is not initialized"}, status=503)

    try:
        # Check if json body or post request parameters
        if request.content_type == 'application/json':
            body = json.loads(request.body)
            session_id = body.get('session_id')
        else:
            session_id = request.POST.get('session_id')

        if not session_id:
            return JsonResponse({"error": "Missing parameter 'session_id'"}, status=400)

        engine.reset_session(session_id)
        return JsonResponse({"status": "success", "message": f"Session {session_id} reset successfully"})
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format in body"}, status=400)
    except Exception as e:
        logger.error(f"Error in reset_session view: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to reset session", "details": str(e)}, status=500)

@require_http_methods(["GET"])
def health_check(request: HttpRequest) -> JsonResponse:
    if engine is None:
        return JsonResponse({
            "status": "unhealthy", 
            "error": "Whisper Engine could not be loaded"
        }, status=503)
        
    try:
        status_info = engine.get_status()
        status_info["status"] = "healthy"
        return JsonResponse(status_info)
    except Exception as e:
        return JsonResponse({
            "status": "unhealthy",
            "details": str(e)
        }, status=500)
