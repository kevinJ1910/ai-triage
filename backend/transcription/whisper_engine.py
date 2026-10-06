import os
import sys
import tempfile
import logging
import threading
import time
from typing import Dict, Any

# --- Dynamic Path Resolution for CUDA/cuDNN DLLs on Windows ---
if sys.platform == 'win32':
    import site
    try:
        sp = [p for p in site.getsitepackages() if 'site-packages' in p][0]
        cublas_bin = os.path.join(sp, "nvidia", "cublas", "bin")
        cudnn_bin = os.path.join(sp, "nvidia", "cudnn", "bin")
        paths_to_add = []
        if os.path.exists(cublas_bin): paths_to_add.append(cublas_bin)
        if os.path.exists(cudnn_bin): paths_to_add.append(cudnn_bin)
        if paths_to_add:
            os.environ["PATH"] = ";".join(paths_to_add) + ";" + os.environ.get("PATH", "")
    except Exception:
        pass
# -------------------------------------------------------------

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from django.conf import settings
from django.core.cache import cache
from .medical_prompts import CLINICAL_INITIAL_PROMPT

logger = logging.getLogger(__name__)

# El contexto de cada sesion vive en la cache compartida (Redis en Docker): cualquier proceso
# del worker puede continuar una sesion y la expiracion por TTL la gestiona la propia cache.
_CONTEXT_KEY = "asr:ctx:{}"
# Solo se usan los ultimos 400 caracteres en el prompt; se guarda algo mas de margen.
_MAX_CONTEXT_CHARS = 2000


def _context_key(session_id: str) -> str:
    return _CONTEXT_KEY.format(session_id)


def get_session_context(session_id: str) -> str:
    return cache.get(_context_key(session_id), "")


def append_session_context(session_id: str, text: str) -> None:
    previous = get_session_context(session_id)
    combined = f"{previous} {text}".strip() if previous else text
    cache.set(_context_key(session_id), combined[-_MAX_CONTEXT_CHARS:], timeout=settings.ASR_SESSION_TTL)


def reset_session_context(session_id: str) -> None:
    """Borra el contexto de una sesion sin necesidad de cargar el modelo Whisper."""
    cache.delete(_context_key(session_id))

# FIX-TEC-007: Logging centralizado en settings.py LOGGING. Sin FileHandler manual duplicado.


class WhisperEngine:
    """
    Motor ASR de alta eficiencia basado en Faster-Whisper.
    Implementa patron Singleton con Thread Lock, contexto por sesion en cache compartida con TTL,
    filtro de actividad de voz (VAD) de baja latencia y fallback seguro para host local.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WhisperEngine, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self) -> None:
        model_size = getattr(settings, 'WHISPER_MODEL_SIZE', 'large-v3-turbo')
        try:
            from system_settings.models import SystemConfiguration
            cfg = SystemConfiguration.get_solo()
            # 'auto' respeta WHISPER_MODEL_SIZE del equipo; otro valor es una eleccion explicita del admin.
            if cfg.active_asr_model and cfg.active_asr_model != 'auto':
                model_size = cfg.active_asr_model
        except Exception:
            pass
        device = getattr(settings, 'WHISPER_DEVICE', 'auto')
        compute_type = getattr(settings, 'WHISPER_COMPUTE_TYPE', 'default')
        cpu_threads = getattr(settings, 'WHISPER_CPU_THREADS', 4)
        
        logger.info(f"Cargando modelo '{model_size}' en '{device}' (compute_type: {compute_type}, hilos: {cpu_threads})")
        start_time = time.perf_counter()
        
        try:
            if WhisperModel is None:
                raise RuntimeError('faster_whisper no disponible en entorno local')
            self.model = WhisperModel(
                model_size, 
                device=device, 
                compute_type=compute_type,
                cpu_threads=cpu_threads
            )
            self.device_used = device
            self.compute_type_used = compute_type
            logger.info(f"Modelo cargado en {time.perf_counter() - start_time:.2f}s en '{device}' ({compute_type})")
        except Exception as e:
            logger.warning(f"Fallo carga con device='{device}' ({e}). Intentando fallback CPU int8.")
            try:
                if WhisperModel is None:
                    raise RuntimeError('faster_whisper no disponible en entorno local')
                self.model = WhisperModel(
                    model_size, 
                    device='cpu', 
                    compute_type='int8',
                    cpu_threads=cpu_threads
                )
                self.device_used = 'cpu'
                self.compute_type_used = 'int8'
                logger.info(f"Modelo fallback CPU (int8) cargado en {time.perf_counter() - start_time:.2f}s")
            except Exception as cpu_err:
                logger.error(f"Fallo inicializacion de WhisperEngine: {cpu_err}")
                self.model = None
                self.device_used = 'unavailable'
                self.compute_type_used = 'unavailable'
        self.model_size_used = model_size

    def transcribe_chunk(self, audio_bytes: bytes, session_id: str) -> Dict[str, Any]:
        """
        Transcribe un chunk de audio asegurando baja latencia mediante VAD Silero ajustado
        a 500ms y busqueda greedy beam_size=1 (o configurado).
        """
        if self.model is None:
            raise RuntimeError("Whisper Engine no disponible en entorno actual")

        logger.info(f"Procesando chunk de audio para sesion {session_id} ({len(audio_bytes)} bytes)")
        start_time = time.perf_counter()
        temp_file_path = ""
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file_path = temp_file.name

            # Construir prompt con historial clinico reciente (ultimos 400 caracteres)
            previous_context = get_session_context(session_id)
            history_slice = previous_context[-400:] if len(previous_context) > 400 else previous_context
            full_prompt = CLINICAL_INITIAL_PROMPT
            if history_slice:
                full_prompt += "\nHistorial previo de la conversacion: " + history_slice

            # beam_size=1 para velocidad ultra-rapida en chunks; configurable via settings
            beam_size = getattr(settings, 'WHISPER_BEAM_SIZE', 1)

            # Transcripcion con VAD Silero optimizado
            segments, info = self.model.transcribe(
                temp_file_path,
                language="es",
                initial_prompt=full_prompt,
                beam_size=beam_size,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            text_segments = [segment.text for segment in segments]
            transcribed_text = " ".join(text_segments).strip()

            # Actualizar buffer de contexto de la sesion
            if transcribed_text:
                append_session_context(session_id, transcribed_text)

            elapsed_time_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"Chunk transcrito para sesion {session_id} en {elapsed_time_ms}ms: '{transcribed_text}'")

            return {
                "text": transcribed_text,
                "session_id": session_id,
                "language": info.language,
                "language_probability": info.language_probability,
                "processing_time_ms": elapsed_time_ms
            }

        except Exception as e:
            logger.error(f"Error transcribiendo chunk: {e}", exc_info=True)
            raise e
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as cleanup_err:
                    logger.error(f"Fallo al eliminar archivo temporal {temp_file_path}: {cleanup_err}")

    def reset_session(self, session_id: str) -> None:
        reset_session_context(session_id)
        logger.info(f"Contexto reseteado para sesion {session_id}")

    def get_status(self) -> Dict[str, Any]:
        # No se exponen identificadores de sesion: el health check es publico.
        return {
            "model_size": getattr(self, 'model_size_used', getattr(settings, 'WHISPER_MODEL_SIZE', 'large-v3-turbo')),
            "device": getattr(self, 'device_used', 'unknown'),
            "compute_type": getattr(self, 'compute_type_used', 'unknown'),
            "model_loaded": getattr(self, 'model', None) is not None,
        }
