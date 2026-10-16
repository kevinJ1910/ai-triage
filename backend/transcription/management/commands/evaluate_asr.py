"""
Evaluacion del ASR (paso 4.3 del plan): WER, CER, error en terminos clinicos y latencia de Faster-Whisper
con la misma configuracion que la aplicacion (idioma, prompt clinico, beam, VAD).

1. Preparar el guion de grabacion (casos del corpus, dos condiciones acusticas):

    python manage.py evaluate_asr --prepare --out-dir data/asr

   Crea data/asr/guion_grabacion.md (texto a leer) y data/asr/manifest.json (nombres de archivo esperados).
   Graben cada caso en silencio y con ruido de fondo (TV, conversacion, ventilador) y guarden los audios
   (wav, m4a, mp3, webm) en data/asr/ con el nombre indicado. data/ esta en .gitignore: no se versionan voces.

2. Evaluar:

    python manage.py evaluate_asr --manifest data/asr/manifest.json --output data/asr/resultado_small_cpu.json
    python manage.py evaluate_asr --manifest data/asr/manifest.json --chunk-seconds 4      # como el streaming
    python manage.py evaluate_asr --manifest data/asr/manifest.json --no-prompt            # ablacion del prompt
    python manage.py evaluate_asr --manifest data/asr/manifest.json --model-size large-v3-turbo --device cuda

WER = (sustituciones + borrados + inserciones) / palabras de referencia, sobre texto en minusculas y sin
puntuacion (con --strip-accents tambien sin tildes). Los numeros dichos en letra frente a cifras cuentan como
error: la referencia del guion esta escrita como se debe leer.
"""
import json
import re
import statistics
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

CONDITIONS = ('silencio', 'ruido')


# ----------------------------------------------------------------------------- metricas

def normalize_for_wer(text: str, strip_accents: bool = False) -> str:
    text = (text or '').lower()
    if strip_accents:
        text = ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))
    text = re.sub(r'[^\w\s%/]', ' ', text)
    return ' '.join(text.split())


def edit_counts(reference, hypothesis):
    """(sustituciones, borrados, inserciones) de la alineacion de Levenshtein entre dos secuencias."""
    n, m = len(reference), len(hypothesis)
    # dp[i][j] = (coste, S, D, I)
    previous = [(j, 0, 0, j) for j in range(m + 1)]
    for i in range(1, n + 1):
        current = [(i, 0, i, 0)]
        for j in range(1, m + 1):
            if reference[i - 1] == hypothesis[j - 1]:
                current.append(previous[j - 1])
                continue
            sub, dele, ins = previous[j - 1], previous[j], current[j - 1]
            best = min(
                (sub[0] + 1, sub[1] + 1, sub[2], sub[3]),
                (dele[0] + 1, dele[1], dele[2] + 1, dele[3]),
                (ins[0] + 1, ins[1], ins[2], ins[3] + 1),
            )
            current.append(best)
        previous = current
    _, s, d, i = previous[m]
    return s, d, i


def wer_counts(reference: str, hypothesis: str, strip_accents: bool = False) -> dict:
    ref = normalize_for_wer(reference, strip_accents).split()
    hyp = normalize_for_wer(hypothesis, strip_accents).split()
    s, d, i = edit_counts(ref, hyp)
    ref_chars = list(''.join(ref))
    cs, cd, ci = edit_counts(ref_chars, list(''.join(hyp)))
    return {'words': len(ref), 'substitutions': s, 'deletions': d, 'insertions': i,
            'chars': len(ref_chars), 'char_errors': cs + cd + ci}


def clinical_terms(text: str) -> list:
    from transcription.terminology import find_concepts
    return [m.concept.term for m in find_concepts(text or '') if m.concept.category not in ('Administrativo',)]


def clinical_term_errors(reference: str, hypothesis: str) -> dict:
    """Terminos clinicos del catalogo presentes en la referencia que no sobreviven a la transcripcion."""
    ref_terms = clinical_terms(reference)
    hyp_terms = clinical_terms(hypothesis)
    remaining = list(hyp_terms)
    missed = []
    for term in ref_terms:
        if term in remaining:
            remaining.remove(term)
        else:
            missed.append(term)
    return {'terms': len(ref_terms), 'missed': missed}


def summarize(rows) -> dict:
    words = sum(r['words'] for r in rows)
    errors = sum(r['substitutions'] + r['deletions'] + r['insertions'] for r in rows)
    chars = sum(r['chars'] for r in rows)
    terms = sum(r['terms'] for r in rows)
    audio = sum(r['audio_seconds'] for r in rows)
    processing = sum(r['processing_seconds'] for r in rows)
    return {
        'audios': len(rows),
        'wer': round(errors / words, 4) if words else None,
        'cer': round(sum(r['char_errors'] for r in rows) / chars, 4) if chars else None,
        'substitutions': sum(r['substitutions'] for r in rows),
        'deletions': sum(r['deletions'] for r in rows),
        'insertions': sum(r['insertions'] for r in rows),
        'wer_media_por_audio': round(statistics.mean(r['wer'] for r in rows), 4) if rows else None,
        'error_terminos_clinicos': round(sum(len(r['missed_terms']) for r in rows) / terms, 4) if terms else None,
        'terminos_clinicos': terms,
        'rtf': round(processing / audio, 3) if audio else None,
        'latencia_media_s': round(statistics.mean(r['processing_seconds'] for r in rows), 2) if rows else None,
    }


# ----------------------------------------------------------------------------- transcripcion

class Transcriber:
    """Faster-Whisper con los parametros de WhisperEngine.transcribe_chunk."""

    def __init__(self, model_size, device, compute_type, use_prompt=True):
        from faster_whisper import WhisperModel
        from transcription.medical_prompts import CLINICAL_INITIAL_PROMPT
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type,
                                  cpu_threads=getattr(settings, 'WHISPER_CPU_THREADS', 4))
        self.prompt = CLINICAL_INITIAL_PROMPT if use_prompt else None
        self.beam_size = getattr(settings, 'WHISPER_BEAM_SIZE', 1)

    def _run(self, audio, prompt):
        segments, info = self.model.transcribe(
            audio, language='es', initial_prompt=prompt, beam_size=self.beam_size, temperature=0.0,
            condition_on_previous_text=False, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
        return ' '.join(s.text for s in segments).strip(), info.duration

    def transcribe(self, path: Path, chunk_seconds: float = 0):
        """(texto, duracion del audio). Con chunk_seconds emula el streaming: fragmentos con el contexto previo."""
        if not chunk_seconds:
            return self._run(str(path), self.prompt)
        from faster_whisper.audio import decode_audio
        audio = decode_audio(str(path), sampling_rate=16000)
        step = int(chunk_seconds * 16000)
        history, texts = '', []
        for start in range(0, len(audio), step):
            prompt = self.prompt
            if prompt and history:
                prompt += "\nHistorial previo de la conversacion: " + history[-400:]
            text, _ = self._run(audio[start:start + step], prompt)
            if text:
                texts.append(text)
                history = f'{history} {text}'.strip()
        return ' '.join(texts), len(audio) / 16000


# ----------------------------------------------------------------------------- comando

class Command(BaseCommand):
    help = 'Prepara el guion de grabacion o evalua el WER del ASR sobre audios grabados.'

    def add_arguments(self, parser):
        parser.add_argument('--prepare', action='store_true', help='Genera guion y manifiesto de grabacion.')
        parser.add_argument('--out-dir', type=Path, default=Path('data/asr'))
        parser.add_argument('--split', choices=('dev', 'test'), default='dev',
                            help='Casos del corpus para el guion (por defecto dev).')
        parser.add_argument('--per-level', type=int, default=4)
        parser.add_argument('--manifest', type=Path)
        parser.add_argument('--model-size', default=None, help='Por defecto WHISPER_MODEL_SIZE.')
        parser.add_argument('--device', default='cpu')
        parser.add_argument('--compute-type', default='int8')
        parser.add_argument('--chunk-seconds', type=float, default=0.0)
        parser.add_argument('--no-prompt', action='store_true', help='Sin el prompt clinico (ablacion).')
        parser.add_argument('--strip-accents', action='store_true')
        parser.add_argument('--output', type=Path)

    def handle(self, *args, **options):
        if options['prepare']:
            return self._prepare(options)
        if not options.get('manifest'):
            raise CommandError('Use --prepare para crear el guion o --manifest para evaluar.')
        return self._evaluate(options)

    def _prepare(self, options):
        import hashlib
        from triage.entity_corpus import load_entity_corpus
        cases = load_entity_corpus(split=options['split'])
        by_level = defaultdict(list)
        for case in cases:
            by_level[case['reference_level']].append(case)
        chosen = []
        for level in sorted(by_level):
            ordered = sorted(by_level[level], key=lambda c: hashlib.sha256(f"asr:{c['id']}".encode()).hexdigest())
            chosen.extend(ordered[:options['per_level']])
        out = options['out_dir']
        out.mkdir(parents=True, exist_ok=True)
        manifest = [{'audio': f"{c['id']}_{cond}.wav", 'case_id': c['id'], 'condicion': cond, 'locutor': '',
                     'reference': c['transcript']} for c in chosen for cond in CONDITIONS]
        (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        lines = ['# Guion de grabacion para el WER del ASR', '',
                 f'{len(chosen)} casos ({options["per_level"]} por nivel, split {options["split"]}) x 2 condiciones '
                 f'= {len(manifest)} audios.', '',
                 '- Lean el texto tal cual, con naturalidad, como lo diria el paciente o el acompanante.',
                 '- `silencio`: habitacion tranquila. `ruido`: TV, conversacion o ventilador de fondo a volumen moderado.',
                 '- Graben con el celular o el microfono del portatil a 30-50 cm. Cualquier formato de audio sirve.',
                 '- Anoten quien lee en `locutor` dentro de manifest.json (idealmente al menos dos personas).', '']
        for c in chosen:
            lines += [f"## {c['id']} (nivel {c['reference_level']})", '',
                      f"Archivos: `{c['id']}_silencio.wav` y `{c['id']}_ruido.wav`", '', f"> {c['transcript']}", '']
        (out / 'guion_grabacion.md').write_text('\n'.join(lines), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Guion y manifiesto en {out} ({len(manifest)} audios por grabar).'))

    def _load_transcriber(self, options):
        return Transcriber(options['model_size'] or getattr(settings, 'WHISPER_MODEL_SIZE', 'small'),
                           options['device'], options['compute_type'], use_prompt=not options['no_prompt'])

    def _evaluate(self, options):
        manifest_path = options['manifest']
        entries = json.loads(manifest_path.read_text(encoding='utf-8'))
        base = manifest_path.parent
        present = []
        for e in entries:
            audio = base / e['audio']
            if not audio.exists():
                # Acepta cualquier extension con el mismo nombre (m4a, mp3, webm...).
                alternatives = sorted(base.glob(f"{Path(e['audio']).stem}.*"))
                audio = next((a for a in alternatives if a.suffix != '.json'), None)
            if audio:
                present.append((e, audio))
        if not present:
            raise CommandError(f'No hay audios del manifiesto en {base}.')
        missing = len(entries) - len(present)

        transcriber = self._load_transcriber(options)
        rows = []
        for index, (entry, audio) in enumerate(present, start=1):
            start = time.perf_counter()
            hypothesis, duration = transcriber.transcribe(audio, options['chunk_seconds'])
            elapsed = time.perf_counter() - start
            counts = wer_counts(entry['reference'], hypothesis, options['strip_accents'])
            terms = clinical_term_errors(entry['reference'], hypothesis)
            errors = counts['substitutions'] + counts['deletions'] + counts['insertions']
            rows.append({**entry, 'audio_file': audio.name, 'hypothesis': hypothesis, **counts,
                         'wer': round(errors / counts['words'], 4) if counts['words'] else 0.0,
                         'terms': terms['terms'], 'missed_terms': terms['missed'],
                         'audio_seconds': round(duration, 2), 'processing_seconds': round(elapsed, 2)})
            self.stderr.write(f"[{index}/{len(present)}] {audio.name}: WER {rows[-1]['wer']}")

        by_condition = {cond: summarize([r for r in rows if r.get('condicion') == cond])
                        for cond in sorted({r.get('condicion') for r in rows})}
        result = {
            'model_size': options['model_size'] or getattr(settings, 'WHISPER_MODEL_SIZE', 'small'),
            'device': options['device'], 'compute_type': options['compute_type'],
            'chunk_seconds': options['chunk_seconds'], 'initial_prompt': not options['no_prompt'],
            'strip_accents': options['strip_accents'], 'audios_faltantes': missing,
            'global': summarize(rows), 'por_condicion': by_condition, 'audios': rows,
        }
        g = result['global']
        self.stdout.write(f"Modelo {result['model_size']} en {result['device']} ({result['compute_type']}) | "
                          f"{'fragmentos de %ss' % options['chunk_seconds'] if options['chunk_seconds'] else 'archivo completo'}"
                          f" | prompt clinico {'si' if result['initial_prompt'] else 'no'}")
        self.stdout.write(f"  Global: WER {g['wer']} | CER {g['cer']} | error en terminos clinicos "
                          f"{g['error_terminos_clinicos']} | RTF {g['rtf']} ({g['audios']} audios)")
        for cond, s in by_condition.items():
            self.stdout.write(f"  {cond}: WER {s['wer']} | terminos clinicos {s['error_terminos_clinicos']}")
        if missing:
            self.stdout.write(self.style.WARNING(f'{missing} audios del manifiesto no se encontraron.'))
        if options.get('output'):
            options['output'].parent.mkdir(parents=True, exist_ok=True)
            options['output'].write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            self.stdout.write(f"Detalle guardado en {options['output']}")
