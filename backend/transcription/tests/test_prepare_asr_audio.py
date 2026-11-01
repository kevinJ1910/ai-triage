import array
import io
import json
import math
import wave
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.core.management import call_command
from django.test import override_settings

from transcription.management.commands.prepare_asr_audio import (
    generate_hospital_noise,
    mix_at_snr,
    read_pcm16_mono,
    strip_speaker_labels,
    write_pcm16_wav,
)
from transcription.medical_prompts import CLINICAL_HOTWORDS, CLINICAL_INITIAL_PROMPT
from transcription.whisper_engine import WhisperEngine, normalize_wav_bytes


def _make_sine_wav_bytes(freq_hz: float, amplitude: float, duration_s: float = 0.5, sr: int = 16000) -> bytes:
    n = int(duration_s * sr)
    pcm = array.array(
        "h",
        [int(round(amplitude * 32767.0 * math.sin(2.0 * math.pi * freq_hz * i / sr))) for i in range(n)],
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def _wav_rms_dbfs(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as r:
        pcm = array.array("h")
        pcm.frombytes(r.readframes(r.getnframes()))
    rms = math.sqrt(sum(float(x) * float(x) for x in pcm) / len(pcm))
    return 20.0 * math.log10(rms / 32767.0)


class TestAcousticPreprocessingAndHotwords:
    def test_clinical_hotwords_contains_pharmacological_and_asr_targets(self):
        lower = CLINICAL_HOTWORDS.lower()
        assert "losartán" in lower
        assert "metformina" in lower
        assert "glucometría" in lower
        # Presupuesto conjunto (prompt + hotwords) acotado para no desbordar max_length=448 de Whisper
        assert len(CLINICAL_INITIAL_PROMPT) + len(CLINICAL_HOTWORDS) <= 600

    def test_normalize_wav_bytes_amplifies_quiet_voice_and_preserves_non_wav(self):
        # Tono vocal de 440 Hz muy bajo (~ -38 dBFS) -> debe amplificarse hacia ~ -20 dBFS (tope 10x = +20 dB)
        quiet_wav = _make_sine_wav_bytes(freq_hz=440.0, amplitude=0.015, duration_s=0.6)
        before_db = _wav_rms_dbfs(quiet_wav)
        processed = normalize_wav_bytes(quiet_wav, target_dbfs=-20.0)
        after_db = _wav_rms_dbfs(processed)
        assert after_db > before_db + 12.0
        assert -24.0 <= after_db <= -18.0

        # Bytes no WAV o cabecera truncada pasan intactos
        assert normalize_wav_bytes(b"fake-webm-bytes") == b"fake-webm-bytes"
        assert normalize_wav_bytes(b"RIFFshort") == b"RIFFshort"

    @pytest.mark.django_db
    def test_whisper_engine_passes_hotwords_and_respects_disable_flag(self, monkeypatch):
        engine = WhisperEngine()
        fake_model = MagicMock()
        fake_model.transcribe.return_value = (
            [SimpleNamespace(text="tomo losartán cincuenta miligramos")],
            SimpleNamespace(language="es", language_probability=0.99),
        )
        monkeypatch.setattr(engine, "model", fake_model)

        engine.transcribe_chunk(b"fake-audio", "sid-hw-1")
        assert "hotwords" in fake_model.transcribe.call_args.kwargs
        assert "losartán" in fake_model.transcribe.call_args.kwargs["hotwords"]

        with override_settings(WHISPER_USE_HOTWORDS=False):
            engine.transcribe_chunk(b"fake-audio", "sid-hw-2")
            assert "hotwords" not in fake_model.transcribe.call_args.kwargs

    @pytest.mark.django_db
    @override_settings(WHISPER_MODEL_SIZE="large-v3-turbo", WHISPER_DEVICE="cuda", WHISPER_COMPUTE_TYPE="float16")
    def test_cuda_float16_failure_falls_back_to_cuda_int8_float16_before_cpu(self, mocker):
        calls = []

        def side_effect(model_size, device=None, compute_type=None, cpu_threads=None):
            calls.append((model_size, device, compute_type))
            if device == "cuda" and compute_type == "float16":
                raise RuntimeError("CUDA OOM in float16")
            return MagicMock()

        mocker.patch("transcription.whisper_engine.WhisperModel", side_effect=side_effect)
        engine = object.__new__(WhisperEngine)
        engine._initialize()

        assert calls == [
            ("large-v3-turbo", "cuda", "float16"),
            ("large-v3-turbo", "cuda", "int8_float16"),
        ]
        assert engine.device_used == "cuda"
        assert engine.compute_type_used == "int8_float16"


class TestPrepareAsrAudioCommand:
    def test_strip_speaker_labels_cleans_roles_and_stage_notes(self):
        raw = (
            "Enfermero: Buenas tardes, ¿qué le pasó hoy?\n"
            "Paciente: [tose] Siento que me aprieta el pecho y tomo losartán.\n"
            "Enfermera: ¿Desde hace cuánto?"
        )
        assert strip_speaker_labels(raw) == (
            "Buenas tardes, ¿qué le pasó hoy? "
            "Siento que me aprieta el pecho y tomo losartán. "
            "¿Desde hace cuánto?"
        )

    def test_mix_at_snr_matches_target_decibels(self):
        sr = 16000
        clean = [0.25 * math.sin(2.0 * math.pi * 440.0 * i / sr) for i in range(sr)]
        noise = generate_hospital_noise(sr, sr, seed_key="test-case")
        mixed = mix_at_snr(clean, noise, snr_db=12.0)
        residual_noise = [m - c for m, c in zip(mixed, clean)]
        sig_rms = math.sqrt(sum(c * c for c in clean) / len(clean))
        err_rms = math.sqrt(sum(r * r for r in residual_noise) / len(residual_noise))
        measured_snr = 20.0 * math.log10(sig_rms / err_rms)
        assert abs(measured_snr - 12.0) < 0.5

    @pytest.mark.django_db
    def test_update_scripts_and_mix_noise_end_to_end(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        manifest = [
            {"audio": "B006_silencio.wav", "case_id": "B006", "condicion": "silencio", "locutor": "", "reference": "base"},
            {"audio": "B006_ruido.wav", "case_id": "B006", "condicion": "ruido", "locutor": "", "reference": "base"},
        ]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        scripts_path = tmp_path / "dialogos.json"
        scripts_path.write_text(
            json.dumps(
                [
                    {
                        "case_id": "B006",
                        "locutor": "gemini-tts-multispeaker",
                        "dialogue": "Enfermero: Cuénteme por qué consulta.\nPaciente: Tengo un dolor opresivo en el pecho.",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # 1. Sincronizar guiones
        out1 = StringIO()
        call_command(
            "prepare_asr_audio",
            "--manifest",
            str(manifest_path),
            "--update-scripts",
            str(scripts_path),
            stdout=out1,
        )
        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert all(
            e["reference"] == "Cuénteme por qué consulta. Tengo un dolor opresivo en el pecho." for e in updated
        )
        assert all(e["locutor"] == "gemini-tts-multispeaker" for e in updated)
        assert (tmp_path / "guion_tts_multispeaker.md").exists()

        # 2. Guardar audio limpio y mezclar ruido hospitalario a 12 dB
        sr = 16000
        clean_samples = [0.2 * math.sin(2.0 * math.pi * 380.0 * i / sr) for i in range(sr)]
        write_pcm16_wav(tmp_path / "B006_silencio.wav", clean_samples, sr)

        out2 = StringIO()
        call_command(
            "prepare_asr_audio",
            "--manifest",
            str(manifest_path),
            "--mix-noise",
            "--snr-db",
            "12",
            "--status",
            stdout=out2,
        )
        assert (tmp_path / "B006_ruido.wav").exists()
        noisy_samples, noisy_sr = read_pcm16_mono(tmp_path / "B006_ruido.wav")
        assert noisy_sr == sr and len(noisy_samples) == sr
        assert "2/2 audios disponibles" in out2.getvalue()

    @pytest.mark.django_db
    def test_update_scripts_accepts_clinical_case_key_and_default_locutor(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(
            json.dumps([
                {"audio": "N001_silencio.wav", "case_id": "N001", "condicion": "silencio", "locutor": "", "reference": "x"}
            ]),
            encoding="utf-8",
        )
        scripts_path = tmp_path / "dialogos.json"
        scripts_path.write_text(
            json.dumps([
                {
                    "case_id": "N001",
                    "level": 1,
                    "clinical_case": "Enfermero: ¿Cuántos años tiene?\nPaciente: Tiene cuarenta y cinco años.",
                }
            ], ensure_ascii=False),
            encoding="utf-8",
        )
        call_command(
            "prepare_asr_audio",
            "--manifest",
            str(manifest_path),
            "--update-scripts",
            str(scripts_path),
            stdout=StringIO(),
        )
        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert updated[0]["reference"] == "¿Cuántos años tiene? Tiene cuarenta y cinco años."
        assert updated[0]["locutor"] == "gemini-2.5-flash-tts-multispeaker"
