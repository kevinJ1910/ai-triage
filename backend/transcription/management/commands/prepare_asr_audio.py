"""
Automatizacion del conjunto acustico de 40 audios para la evaluacion WER de Faster-Whisper:

1. Auditar estado de los audios presentes/faltantes:
    python manage.py prepare_asr_audio --manifest data/asr/manifest.json --status

2. Sincronizar guiones conversacionales paciente-enfermero generados externamente (JSON)
   con manifest.json y exportar guion Multi-Speaker listo para Google AI Studio TTS:
    python manage.py prepare_asr_audio --manifest data/asr/manifest.json --update-scripts data/asr/dialogos.json

3. Sintetizar automaticamente los 20 archivos `<CASE>_ruido.wav` a partir de `<CASE>_silencio.*`
   mezclando ruido hospitalario de urgencias calibrado a SNR exacto (por defecto 12 dB: ventilacion
   HVAC + murmullo de sala de espera + pitidos intermitentes de monitor multiparametrico):
    python manage.py prepare_asr_audio --manifest data/asr/manifest.json --mix-noise --snr-db 12
"""
import array
import hashlib
import json
import math
import random
import re
import sys
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError

SPEAKER_PREFIX_RE = re.compile(
    r"(?im)^\s*(?:enfermer[oa]|medic[oa]|doctor[a]?|pacient[ea]|acompanante|speaker\s*\d+|locutor\s*\d+)\s*:\s*"
)


def strip_speaker_labels(dialogue_text: str) -> str:
    """Convierte un guion con etiquetas ('Enfermero: ...\\nPaciente: ...') en la transcripcion literal hablada."""
    cleaned_lines = []
    for raw_line in (dialogue_text or "").splitlines():
        line = SPEAKER_PREFIX_RE.sub("", raw_line).strip()
        line = re.sub(r"\[[^\]]+\]", " ", line)  # remueve acotaciones escenicas [tose], [pausa] si las hubiera
        line = " ".join(line.split())
        if line:
            cleaned_lines.append(line)
    return " ".join(cleaned_lines)


def read_pcm16_mono(path: Path, target_sr: int = 16000) -> Tuple[List[float], int]:
    """
    Lee un archivo WAV PCM (mono o estereo) en muestras float [-1.0, 1.0].
    Si el archivo es MP3/M4A/WebM o WAV comprimido, intenta decodificar con faster_whisper.audio.decode_audio.
    """
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as reader:
                if reader.getsampwidth() == 2 and reader.getcomptype() == "NONE":
                    n_ch = reader.getnchannels()
                    sr = reader.getframerate()
                    raw = array.array("h")
                    raw.frombytes(reader.readframes(reader.getnframes()))
                    if sys.byteorder != "little":
                        raw.byteswap()
                    if n_ch > 1:
                        mono = [
                            sum(raw[i + c] for c in range(n_ch)) / (n_ch * 32768.0)
                            for i in range(0, len(raw) - n_ch + 1, n_ch)
                        ]
                    else:
                        mono = [s / 32768.0 for s in raw]
                    return mono, sr
        except wave.Error:
            pass

    try:
        from faster_whisper.audio import decode_audio
        arr = decode_audio(str(path), sampling_rate=target_sr)
        return [float(x) for x in arr], target_sr
    except Exception as exc:
        raise CommandError(
            f"No se pudo decodificar {path.name} ({exc}). Guarde los audios limpios en WAV PCM 16-bit o ejecute dentro del contenedor worker-asr."
        ) from exc


def write_pcm16_wav(path: Path, samples: List[float], sample_rate: int) -> None:
    pcm = array.array("h", [max(-32767, min(32767, int(round(s * 32767.0)))) for s in samples])
    if sys.byteorder != "little":
        pcm.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(pcm.tobytes())


def generate_hospital_noise(num_samples: int, sample_rate: int, seed_key: str) -> List[float]:
    """
    Sintetiza ruido ambiental determinista de sala de urgencias:
    - Banda baja HVAC / ventilacion hospitalaria (filtro paso-bajo recursivo).
    - Murmullo modulado en banda vocal (300-3000 Hz) simulando conversaciones lejanas.
    - Pitidos sinusoidales suaves de monitor de signos vitales (~980 Hz, 55 ms cada ~2.6 s).
    """
    seed = int.from_bytes(hashlib.sha256(seed_key.encode("utf-8")).digest()[:8], "little")
    rng = random.Random(seed)
    noise = [0.0] * num_samples
    hvac_state = 0.0
    babble_lp = 0.0
    babble_hp_prev_x = 0.0
    babble_hp_state = 0.0

    beep_period = max(1, int(2.6 * sample_rate))
    beep_len = max(1, int(0.055 * sample_rate))
    beep_offset = rng.randint(0, beep_period // 2)
    two_pi_f = 2.0 * math.pi * 980.0 / max(1, sample_rate)

    for i in range(num_samples):
        white = rng.uniform(-1.0, 1.0)
        # HVAC rumble (~180 Hz low-pass)
        hvac_state = 0.94 * hvac_state + 0.06 * white
        # Speech-band babble envelope (modulated at ~3.2 Hz + ~1.1 Hz)
        t = i / max(1, sample_rate)
        env = 0.55 + 0.30 * math.sin(2.0 * math.pi * 3.2 * t) + 0.15 * math.cos(2.0 * math.pi * 1.1 * t + 0.7)
        babble_lp = 0.65 * babble_lp + 0.35 * white
        babble_hp_state = 0.85 * (babble_hp_state + babble_lp - babble_hp_prev_x)
        babble_hp_prev_x = babble_lp

        sample = 0.45 * hvac_state + 0.55 * env * babble_hp_state
        pos_in_cycle = (i + beep_offset) % beep_period
        if pos_in_cycle < beep_len:
            # Ventana de Hann para evitar clics del monitor
            win = 0.5 * (1.0 - math.cos(2.0 * math.pi * pos_in_cycle / max(1, beep_len - 1)))
            sample += 0.18 * win * math.sin(two_pi_f * i)
        noise[i] = sample
    return noise


def mix_at_snr(clean: List[float], noise: List[float], snr_db: float) -> List[float]:
    """Mezcla `clean` y `noise` a una relacion senal-ruido exacta `snr_db` sobre los cuadros con voz activa."""
    if not clean:
        return []
    frame = 320
    frame_energies = [
        sum(s * s for s in clean[i:i + frame]) / max(1, len(clean[i:i + frame]))
        for i in range(0, len(clean), frame)
    ]
    max_e = max(frame_energies) if frame_energies else 0.0
    active_e = [e for e in frame_energies if e >= max_e * 0.02] or frame_energies
    sig_rms = math.sqrt(sum(active_e) / max(1, len(active_e)))
    noise_rms = math.sqrt(sum(n * n for n in noise) / max(1, len(noise)))
    if sig_rms <= 1e-7 or noise_rms <= 1e-7:
        return list(clean)

    target_noise_rms = sig_rms / (10.0 ** (snr_db / 20.0))
    scale = target_noise_rms / noise_rms
    mixed = [c + n * scale for c, n in zip(clean, noise)]
    peak = max((abs(x) for x in mixed), default=0.0)
    if peak > 0.98:
        norm = 0.98 / peak
        mixed = [x * norm for x in mixed]
    return mixed


def find_case_audio(base_dir: Path, stem: str) -> Optional[Path]:
    exact = base_dir / f"{stem}.wav"
    if exact.exists():
        return exact
    for cand in sorted(base_dir.glob(f"{stem}.*")):
        if cand.suffix.lower() not in (".json", ".md", ".txt"):
            return cand
    return None


class Command(BaseCommand):
    help = "Prepara, sincroniza guiones y mezcla ruido hospitalario calibrado para los 40 audios de evaluate_asr."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", type=Path, default=Path("data/asr/manifest.json"))
        parser.add_argument("--status", action="store_true", help="Muestra checklist de audios listos y faltantes.")
        parser.add_argument("--mix-noise", action="store_true", help="Genera <CASE>_ruido.wav desde <CASE>_silencio.*.")
        parser.add_argument("--snr-db", type=float, default=12.0, help="SNR en dB para --mix-noise (por defecto 12 dB).")
        parser.add_argument("--overwrite", action="store_true", help="Sobrescribe <CASE>_ruido.wav existentes.")
        parser.add_argument(
            "--update-scripts",
            type=Path,
            default=None,
            help="JSON {case_id: dialogo} o [{'case_id': ..., 'dialogue'|'clinical_case': ...}] para actualizar reference.",
        )
        parser.add_argument(
            "--default-locutor",
            default="gemini-2.5-flash-tts-multispeaker",
            help="Locutor por defecto cuando el JSON de --update-scripts omite el campo 'locutor'.",
        )

    def handle(self, *args, **options):
        manifest_path: Path = options["manifest"]
        if not manifest_path.exists():
            raise CommandError(
                f"No existe {manifest_path}. Ejecute primero: python manage.py evaluate_asr --prepare --out-dir {manifest_path.parent}"
            )
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        base_dir = manifest_path.parent

        if options.get("update_scripts"):
            entries = self._apply_scripts(
                manifest_path,
                base_dir,
                entries,
                options["update_scripts"],
                default_locutor=options["default_locutor"],
            )

        if options.get("mix_noise"):
            self._mix_noise(base_dir, entries, snr_db=options["snr_db"], overwrite=options["overwrite"])

        if options.get("status") or (not options.get("mix_noise") and not options.get("update_scripts")):
            self._report_status(base_dir, entries)

    @staticmethod
    def _extract_dialogue_fields(val: dict, default_locutor: str) -> Tuple[str, str]:
        text = (
            val.get("dialogue")
            or val.get("clinical_case")
            or val.get("script")
            or val.get("text")
            or val.get("reference")
            or ""
        )
        locutor = val.get("locutor") or default_locutor
        return text, locutor

    def _apply_scripts(
        self,
        manifest_path: Path,
        base_dir: Path,
        entries: List[dict],
        scripts_path: Path,
        default_locutor: str = "gemini-2.5-flash-tts-multispeaker",
    ) -> List[dict]:
        if not scripts_path.exists():
            raise CommandError(f"No existe el archivo de guiones {scripts_path}.")
        raw_payload = json.loads(scripts_path.read_text(encoding="utf-8"))
        by_case: Dict[str, Tuple[str, str]] = {}
        if isinstance(raw_payload, dict):
            for cid, val in raw_payload.items():
                if isinstance(val, str):
                    by_case[cid] = (val, default_locutor)
                elif isinstance(val, dict):
                    by_case[cid] = self._extract_dialogue_fields(val, default_locutor)
        elif isinstance(raw_payload, list):
            for row in raw_payload:
                cid = row.get("case_id") or row.get("id")
                if cid:
                    by_case[cid] = self._extract_dialogue_fields(row, default_locutor)
        else:
            raise CommandError("Formato invalido en --update-scripts: use objeto JSON o lista de objetos.")

        updated_cases = set()
        digit_cases = []
        for entry in entries:
            cid = entry["case_id"]
            if cid in by_case:
                dialogue, locutor = by_case[cid]
                spoken = strip_speaker_labels(dialogue)
                if not spoken:
                    raise CommandError(f"El guion de {cid} quedo vacio tras limpiar etiquetas.")
                if re.search(r"\d", spoken) and cid not in digit_cases:
                    digit_cases.append(cid)
                entry["reference"] = spoken
                if locutor:
                    entry["locutor"] = locutor
                updated_cases.add(cid)

        if not updated_cases:
            raise CommandError(
                f"Ningun case_id de {scripts_path} coincidio con {manifest_path} o faltan claves de texto."
            )
        if digit_cases:
            self.stdout.write(
                self.style.WARNING(
                    f"Aviso WER: se detectaron digitos numericos en {', '.join(digit_cases)} (conviene escribirlos en letras)."
                )
            )

        manifest_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        md_lines = [
            "# Guiones Multi-Speaker para Google AI Studio (Gemini 2.5 Flash TTS)",
            "",
            "Pegue cada bloque en Google AI Studio -> Generate media -> Gemini Speech Generation (modo Multi-speaker: `Enfermero` y `Paciente`),",
            "descargue el WAV resultante como `<CASE>_silencio.wav` en esta carpeta y ejecute `--mix-noise`.",
            "",
        ]
        seen = set()
        for entry in entries:
            cid = entry["case_id"]
            if cid in seen:
                continue
            seen.add(cid)
            raw_diag = by_case[cid][0] if cid in by_case else f"Paciente: {entry['reference']}"
            md_lines += [f"## {cid} -> guardar como `{cid}_silencio.wav`", "", "```text", raw_diag.strip(), "```", ""]
        (base_dir / "guion_tts_multispeaker.md").write_text("\n".join(md_lines), encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(
                f"Actualizados {len(updated_cases)} casos en {manifest_path} y generado guion_tts_multispeaker.md."
            )
        )
        return entries

    def _mix_noise(self, base_dir: Path, entries: List[dict], snr_db: float, overwrite: bool) -> None:
        case_ids = list(dict.fromkeys(e["case_id"] for e in entries))
        generated, skipped_missing, skipped_existing = 0, 0, 0
        for cid in case_ids:
            clean_path = find_case_audio(base_dir, f"{cid}_silencio")
            if clean_path is None:
                skipped_missing += 1
                continue
            noisy_path = base_dir / f"{cid}_ruido.wav"
            if noisy_path.exists() and not overwrite:
                skipped_existing += 1
                continue
            samples, sr = read_pcm16_mono(clean_path)
            noise = generate_hospital_noise(len(samples), sr, seed_key=f"er-noise:{cid}:{snr_db}")
            mixed = mix_at_snr(samples, noise, snr_db=snr_db)
            write_pcm16_wav(noisy_path, mixed, sr)
            generated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Mezcla de ruido hospitalario (SNR={snr_db} dB): {generated} generados, "
                f"{skipped_existing} ya existian, {skipped_missing} sin audio limpio base."
            )
        )

    def _report_status(self, base_dir: Path, entries: List[dict]) -> None:
        by_cond = {"silencio": [0, 0], "ruido": [0, 0]}
        missing_files = []
        for entry in entries:
            cond = entry["condicion"]
            by_cond.setdefault(cond, [0, 0])[1] += 1
            found = find_case_audio(base_dir, Path(entry["audio"]).stem)
            if found:
                by_cond[cond][0] += 1
            else:
                missing_files.append(entry["audio"])
        total_ready = sum(v[0] for v in by_cond.values())
        self.stdout.write(f"Estado ASR en {base_dir}: {total_ready}/{len(entries)} audios disponibles.")
        for cond, (ok, tot) in sorted(by_cond.items()):
            self.stdout.write(f"  {cond:<10}: {ok}/{tot}")
        if missing_files:
            preview = ", ".join(missing_files[:8])
            more = f" (+{len(missing_files) - 8} mas)" if len(missing_files) > 8 else ""
            self.stdout.write(f"  Faltantes : {preview}{more}")
