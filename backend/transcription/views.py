import uuid
import logging
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from core.permissions import CanUseTranscriber
from core.task_runner import TaskUnavailable, run_task
from django.conf import settings
from .normalizer import normalize_with_rules
from .tasks import get_asr_status, normalize_clinical_text_task, transcribe_audio, worker_mode
from .whisper_engine import reset_session_context

logger = logging.getLogger(__name__)

# La inferencia Whisper se ejecuta en el worker 'asr' (o en linea sin broker): la vista solo
# valida, encola y devuelve el resultado. Los errores internos nunca se exponen al cliente.

@api_view(['POST'])
@permission_classes([IsAuthenticated, CanUseTranscriber])
def transcribe_chunk(request) -> JsonResponse:
    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({"error": "No audio file provided under key 'audio'"}, status=400)

    session_id = request.data.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.warning(f"No session_id provided. Using generated UUID: {session_id}")

    audio_bytes = audio_file.read()
    if len(audio_bytes) == 0:
        return JsonResponse({"error": "Empty audio file received"}, status=400)

    try:
        return JsonResponse(transcribe_audio(audio_bytes, session_id))
    except TaskUnavailable:
        return JsonResponse({"error": "Whisper Engine could not be initialized"}, status=503)
    except Exception as e:
        logger.error(f"Error in transcribe_chunk view: {e}", exc_info=True)
        return JsonResponse({"error": "Internal transcription failure"}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated, CanUseTranscriber])
def reset_session(request) -> JsonResponse:
    # El contexto vive en la cache compartida: se borra sin cargar el modelo ni pasar por el worker.
    session_id = request.data.get('session_id')
    if not session_id:
        return JsonResponse({"error": "Missing parameter 'session_id'"}, status=400)

    try:
        reset_session_context(session_id)
        return JsonResponse({"status": "success", "message": f"Session {session_id} reset successfully"})
    except Exception as e:
        logger.error(f"Error in reset_session view: {e}", exc_info=True)
        return JsonResponse({"error": "Failed to reset session"}, status=500)

@require_http_methods(["GET"])
def health_check(request: HttpRequest) -> JsonResponse:
    """
    Publico (healthcheck de Docker). El proceso web esta sano si responde y alcanza la cache;
    el estado del ASR se informa aparte: 'degraded' si el motor no esta cargado.
    """
    try:
        asr = get_asr_status()
    except Exception as e:
        logger.critical(f"Health check failed: {e}", exc_info=True)
        return JsonResponse({"status": "unhealthy", "error": "Whisper Engine could not be initialized"}, status=503)

    from triage.ner_model import get_ner_status
    # El NER es opcional (sin modelo se usan el catalogo y las reglas): se informa sin degradar el estado.
    return JsonResponse({
        "status": "healthy" if asr.get("model_loaded") else "degraded",
        "inference_mode": "worker" if worker_mode() else "inline",
        "asr": asr,
        "ner": get_ner_status(),
    })


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

    custom_instruction = str(data.get("custom_instruction", "") or "")[:1000]

    try:
        normalized_data = run_task(
            normalize_clinical_text_task, raw_text, custom_instruction, timeout=settings.LLM_TASK_TIMEOUT
        )
    except TaskUnavailable:
        # Sin worker disponible se responde igualmente con el catalogo determinista.
        normalized_data = normalize_with_rules(raw_text)

    return JsonResponse(normalized_data)
