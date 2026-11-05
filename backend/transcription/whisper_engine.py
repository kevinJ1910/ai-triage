import array
import gc
import io
import logging
import math
import os
import re
import sys
import tempfile
import threading
import time
import wave
import zlib
from typing import Any, Dict, Tuple

# --- Dynamic Resolution for CUDA/cuDNN Libraries (Windows & Linux) ---
if sys.platform == 'win32':
    import site
    try:
        sp = [p for p in site.getsitepackages() if 'site-packages' in p][0]
        cublas_bin = os.path.join(sp, "nvidia", "cublas", "bin")
        cudnn_bin = os.path.join(sp, "nvidia", "cudnn", "bin")
        paths_to_add = []
        if os.path.exists(cublas_bin):
            paths_to_add.append(cublas_bin)
        if os.path.exists(cudnn_bin):
            paths_to_add.append(cudnn_bin)
        if paths_to_add:
            os.environ["PATH"] = ";".join(paths_to_add) + ";" + os.environ.get("PATH", "")
    except Exception:
        pass
elif sys.platform.startswith('linux'):
    import ctypes
    import glob
    import site
    try:
        for sp in site.getsitepackages():
            for pattern in (
                "nvidia/cublas/lib/libcublasLt.so*",
                "nvidia/cublas/lib/libcublas.so*",
                "nvidia/cudnn/lib/libcudnn.so*",
            ):
                for so_path in sorted(glob.glob(os.path.join(sp, pattern))):
                    ctypes.CDLL(so_path, mode=ctypes.RTLD_GLOBAL)
    except Exception:
        pass
# ---------------------------------------------------------------------

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from django.conf import settings
from django.core.cache import cache
from .medical_prompts import CLINICAL_HOTWORDS, CLINICAL_INITIAL_PROMPT

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


# Opciones de decodificacion, compartidas con evaluate_asr para que el WER mida lo mismo que la aplicacion.
# Con una sola temperatura (0.0), Whisper no puede reintentar: si la salida entra en bucle («me ha dado que me
# ha dado que...»), la devuelve tal cual. Con la escala de temperaturas, una salida demasiado repetitiva
# (compression_ratio > 2.4) o poco probable (avg_logprob < -1) se vuelve a decodificar con mas temperatura.
DECODE_OPTIONS = dict(
    language="es",
    temperature=(0.0, 0.2, 0.4, 0.6),
    compression_ratio_threshold=2.4,
    log_prob_threshold=-1.0,
    no_speech_threshold=0.6,
    condition_on_previous_text=False,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500),
)
# Una frase de 2 a 8 palabras repetida al menos 3 veces seguidas, o una palabra al menos 4 veces.
_REPEATED_PHRASE = re.compile(r"\b((?:\w+[\s,.;]+){1,7}?\w+)(?:[\s,.;]+\1\b){2,}", re.IGNORECASE)
_REPEATED_WORD = re.compile(r"\b(\w+)(?:[\s,.;]+\1\b){3,}", re.IGNORECASE)
# Frases que Whisper inventa sobre silencio o ruido, aprendidas de subtitulos de videos.
_STOCK_PHRASES = re.compile(
    r"subt[ií]tulos (?:realizados |hechos )?por (?:la comunidad de )?amara\.org|"
    r"gracias por ver(?: el video)?|suscr[ií]bete(?: al canal)?|no olvides suscribirte",
    re.IGNORECASE)
# Como el umbral de Whisper: un texto que se comprime mas de 2.4 veces es casi seguro un bucle.
MAX_COMPRESSION_RATIO = 2.4


def _compression_ratio(text: str) -> float:
    data = text.encode("utf-8")
    return len(data) / len(zlib.compress(data)) if data else 0.0


def clean_transcript(text: str) -> Tuple[str, bool]:
    """
    Quita las alucinaciones de Whisper. Devuelve (texto, hubo_alucinacion). Las repeticiones de una frase se
    reducen a una sola aparicion; si aun asi el texto es demasiado repetitivo, se descarta entero. Tambien se
    quitan las frases de subtitulos que inventa sobre silencio («Subtitulos por la comunidad de Amara.org»).
    Repeticiones naturales y cortas («me duele, me duele») se conservan.
    """
    cleaned = _STOCK_PHRASES.sub("", text)
    cleaned = _REPEATED_PHRASE.sub(r"\1", cleaned)
    cleaned = _REPEATED_WORD.sub(r"\1", cleaned)
    cleaned = " ".join(cleaned.split())
    if cleaned != " ".join(text.split()):
        cleaned = cleaned.strip(" .,;")
    repeated = cleaned != " ".join(text.split())
    if len(cleaned) > 60 and _compression_ratio(cleaned) > MAX_COMPRESSION_RATIO:
        return "", True
    return cleaned, repeated


def normalize_wav_bytes(audio_bytes: bytes, target_dbfs: float = -20.0) -> bytes:
    """
    Preprocesado acustico ligero para contenedores WAV PCM de 16 bits:
    1. Filtro paso-alto IIR de 1er orden (~80 Hz) para atenuar retumbo de ventilacion/microfono.
    2. Normalizacion RMS hacia target_dbfs con limitador de pico sin clipping y techo de ganancia (10x).
    Si los bytes son WebM/MP3 o un mock de prueba, retorna audio_bytes intacto sin lanzar error.
    """
    if not audio_bytes or len(audio_bytes) < 44 or audio_bytes[:4] != b"RIFF":
        return audio_bytes
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as reader:
            if reader.getsampwidth() != 2 or reader.getcomptype() != "NONE":
                return audio_bytes
            n_channels = reader.getnchannels()
            framerate = reader.getframerate()
            frames = reader.readframes(reader.getnframes())
        samples = array.array("h")
        samples.frombytes(frames)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            return audio_bytes

        rc = 1.0 / (2.0 * math.pi * 80.0)
        dt = 1.0 / max(8000, framerate)
        alpha = rc / (rc + dt)

        filtered = array.array("h", [0] * len(samples))
        prev_x = [0.0] * n_channels
        prev_y = [0.0] * n_channels
        sum_sq = 0.0
        peak = 1
        for idx, x_int in enumerate(samples):
            ch = idx % n_channels
            x = float(x_int)
            y = alpha * (prev_y[ch] + x - prev_x[ch])
            prev_x[ch] = x
            prev_y[ch] = y
            yi = max(-32767, min(32767, int(round(y))))
            filtered[idx] = yi
            sum_sq += yi * yi
            if abs(yi) > peak:
                peak = abs(yi)

        rms = math.sqrt(sum_sq / len(filtered))
        if rms < 40.0:
            return audio_bytes
        target_rms = 32767.0 * (10.0 ** (target_dbfs / 20.0))
        gain = min(10.0, target_rms / rms, 32000.0 / peak)
        if 0.85 <= gain <= 1.15:
            out_samples = filtered
        else:
            out_samples = array.array(
                "h", [max(-32767, min(32767, int(round(s * gain)))) for s in filtered]
            )
        if sys.byteorder != "little":
            out_samples.byteswap()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as writer:
            writer.setnchannels(n_channels)
            writer.setsampwidth(2)
            writer.setframerate(framerate)
            writer.writeframes(out_samples.tobytes())
        return buf.getvalue()
    except Exception:
        return audio_bytes


def reset_session_context(session_id: str) -> None:
    """Borra el contexto de una sesion sin necesidad de cargar el modelo Whisper."""
    cache.delete(_context_key(session_id))


# FIX-TEC-007: Logging centralizado en settings.py LOGGING. Sin FileHandler manual duplicado.


class WhisperEngine:
    """
    Motor ASR de alta eficiencia basado en Faster-Whisper.
    Implementa patron Singleton con Thread Lock, contexto por sesion en cache compartida con TTL,
    hotwords clinicos, filtro de actividad de voz (VAD) de baja latencia y fallback escalonado GPU->CPU.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WhisperEngine, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    @staticmethod
    def configured_model_size() -> str:
        """Modelo que pide la configuracion: 'auto' respeta WHISPER_MODEL_SIZE del equipo; otro valor lo impone el admin."""
        model_size = getattr(settings, 'WHISPER_MODEL_SIZE', 'small')
        try:
            from system_settings.models import SystemConfiguration
            cfg = SystemConfiguration.get_solo()
            if cfg.active_asr_model and cfg.active_asr_model != 'auto':
                model_size = cfg.active_asr_model
        except Exception:
            pass
        return model_size

    def reload(self) -> Dict[str, Any]:
        """
        Vuelve a cargar Whisper con el modelo configurado, sin reiniciar el worker. Se libera el modelo anterior
        antes de cargar el nuevo para no tener dos en memoria; si el nuevo falla, se aplican los mismos respaldos
        que al arrancar (CUDA int8_float16, CPU int8 y luego 'small').
        """
        with self._lock:
            self.model = None
            gc.collect()
            self._initialize()
        return self.get_status()

    def _initialize(self) -> None:
        model_size = self.configured_model_size()
        # Lo que se pidio, aunque luego se cargue un respaldo: asi se distingue "cargando" de "no se pudo cargar".
        self.requested_model_size = model_size
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
            # Si fallo en CUDA por memoria/tipo (p. ej. float16 en GPU compartida de 8 GB), probar int8_float16 en CUDA antes de caer a CPU.
            if device == 'cuda' and compute_type != 'int8_float16' and WhisperModel is not None:
                try:
                    self.model = WhisperModel(
                        model_size,
                        device='cuda',
                        compute_type='int8_float16',
                        cpu_threads=cpu_threads,
                    )
                    self.device_used = 'cuda'
                    self.compute_type_used = 'int8_float16'
                    self.model_size_used = model_size
                    logger.info(
                        f"Modelo cargado en CUDA (int8_float16) en {time.perf_counter() - start_time:.2f}s"
                    )
                    return
                except Exception as cuda_int8_err:
                    logger.warning(f"Fallo respaldo CUDA int8_float16 ({cuda_int8_err}).")

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
                if model_size != 'small':
                    logger.warning(f"Fallo fallback con '{model_size}' ({cpu_err}). Intentando con modelo liviano 'small'.")
                    try:
                        self.model = WhisperModel(
                            'small',
                            device='cpu',
                            compute_type='int8',
                            cpu_threads=cpu_threads
                        )
                        self.device_used = 'cpu'
                        self.compute_type_used = 'int8'
                        model_size = 'small'
                        logger.info("Modelo de rescate 'small' cargado exitosamente")
                    except Exception as rescue_err:
                        logger.error(f"Fallo inicializacion de WhisperEngine: {rescue_err}")
                        self.model = None
                        self.device_used = 'unavailable'
                        self.compute_type_used = 'unavailable'
                else:
                    logger.error(f"Fallo inicializacion de WhisperEngine: {cpu_err}")
                    self.model = None
                    self.device_used = 'unavailable'
                    self.compute_type_used = 'unavailable'
        self.model_size_used = model_size

    def transcribe_chunk(self, audio_bytes: bytes, session_id: str) -> Dict[str, Any]:
        """
        Transcribe un chunk de audio asegurando baja latencia mediante VAD Silero ajustado
        a 500ms, hotwords clinicos y busqueda greedy beam_size=1 (o configurado).
        """
        if self.model is None:
            raise RuntimeError("Whisper Engine no disponible en entorno actual")

        logger.info(f"Procesando chunk de audio para sesion {session_id} ({len(audio_bytes)} bytes)")
        start_time = time.perf_counter()
        temp_file_path = ""

        try:
            processed_bytes = normalize_wav_bytes(audio_bytes) if getattr(settings, 'WHISPER_AUDIO_NORMALIZE', True) else audio_bytes
            suffix = ".wav" if processed_bytes[:4] == b"RIFF" else ".webm"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_file.write(processed_bytes)
                temp_file_path = temp_file.name

            # Presupuesto de ventana de Whisper (448 tokens): hotwords + prompt + historial <= ~180 tokens
            previous_context = get_session_context(session_id)
            history_slice = previous_context[-220:] if len(previous_context) > 220 else previous_context
            full_prompt = CLINICAL_INITIAL_PROMPT
            if history_slice:
                full_prompt += "\nHistorial previo de la conversacion: " + history_slice

            # beam_size=1 para velocidad ultra-rapida en chunks; configurable via settings
            beam_size = getattr(settings, 'WHISPER_BEAM_SIZE', 1)
            use_hotwords = getattr(settings, 'WHISPER_USE_HOTWORDS', True)
            extra_decode = dict(DECODE_OPTIONS)
            if use_hotwords and CLINICAL_HOTWORDS:
                extra_decode["hotwords"] = CLINICAL_HOTWORDS

            # Transcripcion con VAD Silero optimizado y reintento por temperatura ante bucles
            segments, info = self.model.transcribe(
                temp_file_path,
                initial_prompt=full_prompt,
                beam_size=beam_size,
                **extra_decode,
            )

            text_segments = [segment.text for segment in segments]
            transcribed_text, repetition_filtered = clean_transcript(" ".join(text_segments).strip())
            if repetition_filtered:
                logger.warning(f"Repeticion de Whisper filtrada en la sesion {session_id}")

            # El texto con repeticiones no entra en el contexto: si entrara en el prompt del siguiente
            # fragmento, Whisper tenderia a continuar el mismo bucle.
            if transcribed_text and not repetition_filtered:
                append_session_context(session_id, transcribed_text)

            elapsed_time_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"Chunk transcrito para sesion {session_id} en {elapsed_time_ms}ms: '{transcribed_text}'")

            return {
                "text": transcribed_text,
                "session_id": session_id,
                "language": info.language,
                "language_probability": info.language_probability,
                "processing_time_ms": elapsed_time_ms,
                "repetition_filtered": repetition_filtered,
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
            "requested": getattr(self, 'requested_model_size', None),
        }
