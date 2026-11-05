import os
from types import SimpleNamespace

import pytest
from django.core.cache import cache


class _StubWhisperModel:
    """Doble de prueba en memoria para evitar descargas y consumo de RAM en la suite unitaria/CI."""

    def __init__(self, model_size, device="cpu", compute_type="int8", **kwargs):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.kwargs = kwargs

    def transcribe(self, audio_path, **kwargs):
        return (
            [],
            SimpleNamespace(language="es", language_probability=1.0, duration=0.0),
        )


@pytest.fixture(autouse=True)
def _clear_cache():
    # La cache en memoria persiste entre tests: sin limpiarla, los contadores de throttling
    # (login 10/min, OTP 5/min) y la cache clinica se arrastrarian de un test a otro.
    cache.clear()
    yield


@pytest.fixture(autouse=True)
def _isolate_neural_models(request, monkeypatch):
    # En CI (Ubuntu) faster-whisper esta instalado; sin este aislamiento, cualquier health check o
    # cambio de active_asr_model (ej. large-v3) descarga GB de pesos desde HuggingFace y provoca OOM.
    # Las pruebas marcadas con @pytest.mark.real_inference bajo RUN_REAL_INFERENCE=1 usan el motor real.
    use_real = (
        request.node.get_closest_marker("real_inference") is not None
        and os.environ.get("RUN_REAL_INFERENCE", "").strip() == "1"
    )
    if use_real:
        yield
        return

    from transcription import whisper_engine
    from triage import ner_model

    whisper_engine.WhisperEngine._instance = None
    ner_model.NEREngine.reset()
    monkeypatch.setattr(whisper_engine, "WhisperModel", _StubWhisperModel)
    yield
    whisper_engine.WhisperEngine._instance = None
    ner_model.NEREngine.reset()
