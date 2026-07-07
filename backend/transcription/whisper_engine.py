import threading
import time
import tempfile
import os
import sys
import logging
from typing import Dict, Any, Tuple

# --- INJECT NVIDIA DLLs TO PATH FOR WINDOWS ---
if os.name == 'nt':
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
    except Exception as e:
        pass
# ----------------------------------------------

from faster_whisper import WhisperModel
from django.conf import settings
from .medical_prompts import CLINICAL_INITIAL_PROMPT

logger = logging.getLogger(__name__)

_log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(_log_dir, exist_ok=True)
fh = logging.FileHandler(os.path.join(_log_dir, 'backend_debug.log'))
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)
class WhisperEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WhisperEngine, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self) -> None:
        logger.info("Initializing WhisperEngine model...")
        model_size = getattr(settings, 'WHISPER_MODEL_SIZE', 'large-v3-turbo')
        device = getattr(settings, 'WHISPER_DEVICE', 'auto')
        compute_type = getattr(settings, 'WHISPER_COMPUTE_TYPE', 'default')
        cpu_threads = getattr(settings, 'WHISPER_CPU_THREADS', 4)
        
        logger.info(f"Loading Faster-Whisper model '{model_size}' on device '{device}' using compute_type '{compute_type}' and cpu_threads {cpu_threads}")
        start_time = time.perf_counter()
        
        try:
            self.model = WhisperModel(
                model_size, 
                device=device, 
                compute_type=compute_type,
                cpu_threads=cpu_threads
            )
            self.device_used = device
            self.compute_type_used = compute_type
            logger.info(f"Model loaded successfully in {time.perf_counter() - start_time:.2f} seconds on device '{device}' with compute_type '{compute_type}'")
        except Exception as e:
            logger.warning(f"Failed to load WhisperModel with device='{device}' and compute_type='{compute_type}': {e}. Falling back to CPU with int8.")
            try:
                self.model = WhisperModel(
                    model_size, 
                    device='cpu', 
                    compute_type='int8',
                    cpu_threads=cpu_threads
                )
                self.device_used = 'cpu'
                self.compute_type_used = 'int8'
                logger.info(f"Fallback model loaded successfully on CPU (int8) in {time.perf_counter() - start_time:.2f} seconds")
            except Exception as cpu_err:
                logger.error(f"Failed to initialize WhisperEngine fallback on CPU: {cpu_err}")
                raise RuntimeError(f"Failed to load Whisper model on both settings and CPU fallback: {cpu_err}") from cpu_err

        # Session contexts: session_id -> running transcribed text
        self._session_contexts: Dict[str, str] = {}
        self._session_lock = threading.Lock()

    def transcribe_chunk(self, audio_bytes: bytes, session_id: str) -> Dict[str, Any]:
        logger.info(f"==> Receiving chunk for session {session_id}. Size: {len(audio_bytes)} bytes")
        start_time = time.perf_counter()
        temp_file_path = ""
        
        try:
            # 1. Write the audio bytes to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file_path = temp_file.name

            # 2. Build the initial prompt with historical context (last 500 characters)
            with self._session_lock:
                previous_context = self._session_contexts.get(session_id, "")
            
            # Format the prompt, concatenating the static clinical prompt with session history
            history_slice = previous_context[-500:] if len(previous_context) > 500 else previous_context
            full_prompt = CLINICAL_INITIAL_PROMPT
            if history_slice:
                full_prompt += "\nHistorial previo de la conversación: " + history_slice

            beam_size = getattr(settings, 'WHISPER_BEAM_SIZE', 3)
            logger.info(f"Starting self.model.transcribe with beam_size={beam_size}...")
            # 3. Perform transcription
            # Forced Spanish language, beam_size, vad_filter to prevent hallucination loops on silence
            segments, info = self.model.transcribe(
                temp_file_path,
                language="es",
                initial_prompt=full_prompt,
                beam_size=beam_size,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=1000)
            )
            logger.info("Transcription completed.")

            # 4. Extract and join the transcribed text
            text_segments = []
            for segment in segments:
                text_segments.append(segment.text)
            
            transcribed_text = " ".join(text_segments).strip()

            # 5. Update session context
            if transcribed_text:
                with self._session_lock:
                    if session_id in self._session_contexts:
                        self._session_contexts[session_id] += " " + transcribed_text
                    else:
                        self._session_contexts[session_id] = transcribed_text

            elapsed_time_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"Chunk transcribed for session {session_id} in {elapsed_time_ms}ms: '{transcribed_text}'")

            return {
                "text": transcribed_text,
                "session_id": session_id,
                "language": info.language,
                "language_probability": info.language_probability,
                "processing_time_ms": elapsed_time_ms
            }

        except Exception as e:
            logger.error(f"Error transcribing chunk: {e}", exc_info=True)
            raise e
        finally:
            # Clean up the temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as cleanup_err:
                    logger.error(f"Failed to delete temp audio file {temp_file_path}: {cleanup_err}")

    def reset_session(self, session_id: str) -> None:
        with self._session_lock:
            if session_id in self._session_contexts:
                del self._session_contexts[session_id]
                logger.info(f"Context cleared for session {session_id}")

    def get_status(self) -> Dict[str, Any]:
        with self._session_lock:
            active_sessions = list(self._session_contexts.keys())
        
        return {
            "model_size": getattr(settings, 'WHISPER_MODEL_SIZE', 'large-v3-turbo'),
            "device": getattr(self, 'device_used', 'unknown'),
            "compute_type": getattr(self, 'compute_type_used', 'unknown'),
            "active_sessions_count": len(active_sessions),
            "active_session_ids": active_sessions
        }
