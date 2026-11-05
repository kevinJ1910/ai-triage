"""
Pruebas de humo de inferencia real sin dobles de prueba (mocks/stubs).

En integracion continua (GitHub Actions) la suite unitaria aisla los pesos neuronales para correr
de forma determinista sin GPU ni red. Cuando se define RUN_REAL_INFERENCE=1 en un entorno con los
motores instalados (contenedores worker-asr / worker-llm / llm-local o estacion con GPU/CPU), estas
pruebas ejecutan de verdad:
  1. WhisperEngine.transcribe_chunk() con CTranslate2 (faster-whisper) sobre audio PCM16 real.
  2. ner_model.extract_mentions() + fuse_entities() con el modelo RoBERTa clinico real.
  3. analyze_triage_transcript(..., strict_llm=True) contra Ollama local o Gemini sin MockTransport.
"""
import io
import math
import os
import struct
import wave

import pytest

from transcription.normalizer import concept_mappings
from transcription.whisper_engine import WhisperEngine, reset_session_context
from triage import ner_model
from triage.ai_analyzer import TriageOutputSchema, analyze_triage_transcript
from triage.clinical_cache import ClinicalQueryCache
from triage.entity_fusion import fuse_entities


def real_inference_enabled() -> bool:
    return os.environ.get("RUN_REAL_INFERENCE", "").strip() == "1"


def build_pcm16_wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 16000, freq_hz: float = 220.0) -> bytes:
    """Genera un contenedor WAV PCM de 16 bits valido para ejercitar el pipeline acustico real."""
    total_samples = max(1, int(duration_seconds * sample_rate))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for idx in range(total_samples):
            sample = int(3200 * math.sin(2.0 * math.pi * freq_hz * (idx / sample_rate)))
            frames.extend(struct.pack("<h", sample))
        wav_file.writeframes(bytes(frames))
    return buf.getvalue()


class TestRealInferenceHarness:
    """Verifica siempre en CI el generador WAV PCM16 y la compuerta de activacion explicita."""

    def test_pcm16_wav_header_and_duration_are_valid(self):
        raw = build_pcm16_wav_bytes(duration_seconds=0.5, sample_rate=16000)
        with wave.open(io.BytesIO(raw), "rb") as parsed:
            assert parsed.getnchannels() == 1
            assert parsed.getsampwidth() == 2
            assert parsed.getframerate() == 16000
            assert parsed.getnframes() == 8000

    def test_real_inference_gate_defaults_to_disabled(self, monkeypatch):
        monkeypatch.delenv("RUN_REAL_INFERENCE", raising=False)
        assert real_inference_enabled() is False
        monkeypatch.setenv("RUN_REAL_INFERENCE", "1")
        assert real_inference_enabled() is True


@pytest.mark.real_inference
@pytest.mark.skipif(not real_inference_enabled(), reason="Definir RUN_REAL_INFERENCE=1 para ejecutar inferencia neuronal real.")
@pytest.mark.django_db
class TestRealInferencePipelines:
    def test_real_whisper_asr_pipeline_without_mocks(self):
        pytest.importorskip("faster_whisper")
        engine = WhisperEngine()
        status_info = engine.get_status()
        if not status_info.get("model_loaded"):
            engine.reload()
        assert engine.get_status()["model_loaded"] is True

        session_id = "real-asr-smoke"
        reset_session_context(session_id)
        try:
            wav_bytes = build_pcm16_wav_bytes(duration_seconds=1.2)
            result = engine.transcribe_chunk(wav_bytes, session_id)
            assert isinstance(result["text"], str)
            assert "language" in result
            assert "repetition_filtered" in result
        finally:
            reset_session_context(session_id)

    def test_real_roberta_ner_and_fusion_without_mocks(self):
        pytest.importorskip("transformers")
        ner_model.NEREngine.reset()
        engine = ner_model.get_engine()
        if engine is None:
            pytest.skip("NER_MODEL_PATH no disponible en este entorno.")

        narrative = (
            "Paciente masculino con dolor opresivo en el pecho desde hace 40 minutos, "
            "toma losartan, alergico a penicilina y niega fiebre."
        )
        mentions = ner_model.extract_mentions(narrative)
        assert isinstance(mentions, list) and len(mentions) >= 1
        fused = fuse_entities(
            narrative,
            concept_mappings(narrative),
            roberta_mentions=mentions,
            llm_entities={},
        )
        assert any("pecho" in s.lower() or "dolor" in s.lower() for s in fused["symptoms"])
        assert any("fiebre" in s.lower() for s in fused["negated_findings"])

    def test_real_llm_triage_pipeline_enforces_schema_and_min_critico(self):
        ClinicalQueryCache.clear()
        narrative = (
            "Paciente de 64 anos con dificultad respiratoria severa, saturacion 84%, "
            "frecuencia cardiaca 128 lpm, presion arterial 85/50 mmHg, niega alergias."
        )
        result = analyze_triage_transcript(
            narrative,
            use_cache=False,
            strict_llm=True,
        )
        validated = TriageOutputSchema.model_validate({
            "patientInfo": result["patientInfo"],
            "entities": {
                "symptoms": result["entities"]["symptoms"],
                "diagnoses": result["entities"].get("diagnoses", []),
                "medications": result["entities"]["medications"],
                "allergies": result["entities"].get("allergies", []),
                "vitals": result["entities"]["vitals"],
                "history": result["entities"]["history"],
                "negated_findings": result["entities"].get("negated_findings", []),
            },
            "triage": result["triage"],
            "confidence": result["confidence"],
        })
        assert validated.triage.level in (1, 2)
        assert len(validated.triage.justification.strip()) >= 15
        assert not result["engine_used"].startswith("Motor de Reglas")
