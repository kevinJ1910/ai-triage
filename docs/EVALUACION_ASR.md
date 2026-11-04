# Evaluación del ASR

La evaluación empírica mide el módulo de reconocimiento automático del habla sobre la misma configuración que ejecuta la aplicación en producción: `faster-whisper`, idioma español, preprocesamiento acústico (filtro pasa-altos a 80 Hz y normalización RMS a −20 dBFS), prompt clínico con *hotwords*, `beam_size` y filtro VAD de `WhisperEngine`.

**Comando:** `backend/transcription/management/commands/evaluate_asr.py`.  
**Pruebas:** `backend/transcription/tests/test_evaluate_asr.py` (el cálculo de WER coincide exactamente con `jiwer` sobre 300 pares aleatorios).

## 1. Preparación de grabaciones

```bash
docker compose exec backend python manage.py evaluate_asr --prepare --out-dir data/asr
```

El comando genera dos ficheros en `backend/data/asr/` (excluido de control de versiones para no almacenar voces):

- `guion_grabacion.md`: 20 casos del split `dev` (4 por nivel de triaje) para lectura en voz alta.
- `manifest.json`: nombres de archivo esperados (`N001_silencio.wav` y `N001_ruido.wav`).

Protocolo de captura acústica:

- **Condiciones:** cada relato se registra en dos entornos: `silencio` (recinto silencioso) y `ruido` (ruido hospitalario mezclado a 12 dB SNR, equivalente a 60–65 dB SPL), conformando **40 grabaciones reales**.
- **Equipo:** micrófono de estación portátil o dispositivo móvil a 30–50 cm (formatos admitidos: `wav`, `m4a`, `mp3`, `webm`).
- **Locución:** lectura natural en español colombiano respetando las cifras numéricas de signos vitales tal como se dictan en consulta («80 sobre 50»).

## 2. Ejecución de mediciones

```bash
# Respaldo local en CPU (modelo small, int8, archivo completo)
docker compose exec backend python manage.py evaluate_asr --manifest data/asr/manifest.json \
    --output triage/benchmark/resultados/asr_small_cpu_int8.json

# Captura incremental por micro-lotes de 4 s (cuasi tiempo real) con contexto previo en Redis
docker compose exec backend python manage.py evaluate_asr --manifest data/asr/manifest.json \
    --model-size large-v3-turbo --device cuda --compute-type int8_float16 --chunk-seconds 4 \
    --output triage/benchmark/resultados/asr_large_v3_turbo_cuda_stream4s.json

# Ablación sin prompt clínico ni hotwords
docker compose exec backend python manage.py evaluate_asr --manifest data/asr/manifest.json \
    --model-size large-v3-turbo --device cuda --compute-type int8_float16 --no-prompt \
    --output triage/benchmark/resultados/asr_large_v3_turbo_cuda_ablacion_sin_ayudas.json

# Configuración recomendada en GPU NVIDIA (large-v3-turbo, CUDA)
docker compose exec backend python manage.py evaluate_asr --manifest data/asr/manifest.json \
    --model-size large-v3-turbo --device cuda --compute-type int8_float16 \
    --output triage/benchmark/resultados/asr_large_v3_turbo_cuda.json
```

Métricas calculadas en total y por condición acústica:

| Métrica | Definición técnica |
| :--- | :--- |
| **WER** | `(sustituciones + borrados + inserciones) / palabras de referencia`, en minúsculas y sin signos de puntuación. |
| **CER** | Tasa de error a nivel de carácter, excluyendo espacios. |
| **Error en términos clínicos** | Fracción de términos del catálogo clínico (150 menciones en los 40 audios) que sufren distorsión fonética o léxica en la transcripción (p. ej., «losartán» -> «los artán»). |
| **RTF** | *Real-Time Factor* (`tiempo de inferencia / duración del audio`). Valores `< 1,0` indican procesamiento más rápido que tiempo real. |

## 3. Resultados Empíricos Consolidados (25-10-2026)

La evaluación se ejecutó sobre **40 grabaciones clínicas reales** en español (20 en condición de silencio y 20 bajo ruido hospitalario a 12 dB SNR / 60–65 dB, con 150 menciones de términos médicos verificables). Los artefactos completos residen en `backend/triage/benchmark/resultados/`:

| Configuración | Modelo y Precisión | Dispositivo | Muestra y Modo | WER Global | WER Silencio | WER Ruido | Error Términos Clínicos | RTF | Latencia Media | Artefacto |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Producción GPU (Recomendada)** | `large-v3-turbo` (`int8_float16` / `float16`) | NVIDIA RTX 3070 (CUDA) | Mixta (40 audios, completo) | **2,39 %** | **1,87 %** | **2,90 %** | **3,33 %** (5/150) | **0,044** | **1,26 s** | `asr_large_v3_turbo_cuda.json` |
| **Ablación sin ayudas léxicas** | `large-v3-turbo` (sin prompt ni *hotwords*) | NVIDIA RTX 3070 (CUDA) | Mixta (40 audios, completo) | 2,47 % | 2,05 % | 2,90 % | 4,67 % (ruido: 6,67 %) | 0,043 | 1,21 s | `asr_large_v3_turbo_cuda_ablacion_sin_ayudas.json` |
| **Captura incremental (micro-lotes 4 s)** | `large-v3-turbo` (`int8_float16`) | NVIDIA RTX 3070 (CUDA) | Mixta (40 audios, chunks 4 s) | 12,81 % | 10,62 % | 15,00 % | 8,67 % | 0,139 | 3,96 s | `asr_large_v3_turbo_cuda_stream4s.json` |
| **Respaldo local CPU** | `small` (`int8`) | CPU x86_64 | Mixta (40 audios, completo) | 7,53 % | 5,11 % | 9,94 % | 10,67 % (16/150) | 0,142 | 4,04 s | `asr_small_cpu_int8.json` |

### Conclusiones técnicas

1. **Cumplimiento holgado del Anteproyecto (`WER < 15 %` y latencia `< 2 s`):** La configuración en GPU (`large-v3-turbo`) registra un WER global de **2,39 %** y una latencia media de **1,26 s** (`RTF 0,044`).
2. **Efecto del prompting clínico y *hotwords*:** La inyección léxica reduce el error sobre terminología médica bajo ruido hospitalario del **6,67 %** al **4,00 %** (y a **3,33 %** en la muestra global de 150 términos). Los fallos residuales recurrentes se corrigen determinísticamente en `backend/transcription/terminology/correcciones_asr.json` (42 reglas fonéticas).
3. **Viabilidad operativa en CPU:** En estaciones sin GPU NVIDIA, `small` (`int8`) mantiene un WER global de **7,53 %** y un `RTF` de **0,142** (7 veces más rápido que tiempo real).
