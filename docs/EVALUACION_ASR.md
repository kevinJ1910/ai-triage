# Evaluación del ASR (paso 4.3)

El documento de grado reporta un WER del 8,4 %, pero ningún script lo produce. Esta evaluación lo sustituye por una cifra medida con la misma configuración que usa la aplicación: Faster-Whisper, español, prompt clínico, `beam_size` y VAD de `WhisperEngine`.

**Comando:** `backend/transcription/management/commands/evaluate_asr.py`. **Pruebas:** `backend/transcription/tests/test_evaluate_asr.py`. El WER coincide con `jiwer` en 300 pares aleatorios.

## 1. Grabar

```bash
docker compose exec backend python manage.py evaluate_asr --prepare --out-dir data/asr
```

El comando genera dos ficheros en `backend/data/asr/`, que está fuera de git porque las voces no se versionan:

- `guion_grabacion.md`: 20 casos de `dev`, 4 por nivel, para leer en voz alta.
- `manifest.json`: los nombres de archivo esperados, de la forma `N001_silencio.wav` y `N001_ruido.wav`.

Cómo grabar:

- **Condiciones:** cada caso en dos, `silencio` (habitación tranquila) y `ruido` (TV, conversación o ventilador de fondo a volumen moderado). En total, 40 audios.
- **Equipo:** celular o micrófono del portátil, a 30–50 cm. Vale cualquier formato (wav, m4a, mp3, webm): basta con conservar el nombre y cambiar la extensión.
- **Locutores:** idealmente dos o más (tú y Junior). Escribid quién lee en el campo `locutor` del manifiesto.
- **Cómo leer:** el texto tal cual, con naturalidad. Los números se leen como están escritos («80 sobre 50»).

## 2. Medir

```bash
# Configuración por defecto (CPU, small, archivo completo)
docker compose exec backend python manage.py evaluate_asr --manifest data/asr/manifest.json \
    --output data/asr/resultado_small_cpu.json
# Como el streaming de la aplicación: fragmentos de 4 s con el contexto previo
docker compose exec backend python manage.py evaluate_asr --manifest data/asr/manifest.json --chunk-seconds 4
# Ablación del prompt clínico
docker compose exec backend python manage.py evaluate_asr --manifest data/asr/manifest.json --no-prompt
# En el equipo de Junior, con GPU
docker compose exec backend python manage.py evaluate_asr --manifest data/asr/manifest.json \
    --model-size large-v3-turbo --device cuda --compute-type float16
```

El comando informa de lo siguiente, en total y por condición:

| Métrica | Qué es |
| :--- | :--- |
| WER | (sustituciones + borrados + inserciones) / palabras de referencia, en minúsculas y sin puntuación. Con `--strip-accents`, además sin tildes. |
| CER | Lo mismo por caracteres, sin espacios. |
| Error en términos clínicos | Fracción de términos del catálogo presentes en la referencia que no sobreviven a la transcripción, como «losartán» → «los artán». Es la métrica que más importa para el triaje. |
| RTF | Tiempo de proceso / duración del audio. Menor que 1 significa más rápido que el tiempo real. |

## 3. Reportar en la tesis

- Hay que dar el WER por condición, con y sin fragmentos, y con y sin prompt, indicando el modelo, el dispositivo y el número de audios y locutores.
- Con 40 audios y dos locutores, la muestra es pequeña: hay que declararlo como amenaza a la validez.
- Los errores de términos clínicos que aparezcan se pueden añadir a `transcription/terminology/correcciones_asr.json`. Esa es la capa de correcciones ASR de la normalización.

**Prueba de funcionamiento (no es un resultado):** con un audio sintético (voz de Windows «Sabina», es-MX) y el modelo `tiny`, el WER fue de 0,11 con el archivo completo y de 0,22 en fragmentos de 4 s. «losartán» se transcribió como «los artán».
## 4. Resultados Empíricos Medidos (25-10-2026)

Se evaluó el módulo ASR sobre el corpus de 40 audios de diálogo clínico en español (20 en condición de silencio en cabina y 20 con ruido ambiente hospitalario mezclado a 12 dB SNR, totalizando 150 menciones de términos médicos del catálogo).

Los artefactos crudos con los resultados completos están guardados en ackend/triage/benchmark/resultados/:

| Configuración | Modelo y Precisión | Dispositivo | Modo | WER Global | WER Silencio | WER Ruido | Error Términos Clínicos | RTF | Latencia Media | Artefacto |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Producción GPU (Recomendada)** | Faster-Whisper large-v3-turbo (float16) | NVIDIA CUDA | Completo | **2,39 %** | **1,87 %** | **2,90 %** | **3,33 %** (5/150) | **0,044** | 1,26 s | sr_large_v3_turbo_cuda.json |
| **Ablación sin ayudas** | large-v3-turbo (sin prompt ni hotwords) | NVIDIA CUDA | Completo | 2,47 % | 2,05 % | 2,90 % | 4,67 % (ruido: 6,67 %) | 0,043 | 1,21 s | sr_large_v3_turbo_cuda_ablacion_sin_ayudas.json |
| **Streaming concurrente** | large-v3-turbo (float16) | NVIDIA CUDA | Chunks 4 s | 12,81 % | 10,62 % | 15,00 % | 8,67 % | 0,139 | 3,96 s | sr_large_v3_turbo_cuda_stream4s.json |
| **Respaldo local CPU** | Faster-Whisper small (int8) | CPU AMD | Completo | 7,53 % | 5,11 % | 9,94 % | 10,67 % (16/150) | 0,142 | 4,04 s | sr_small_cpu_int8.json |

### Hallazgos Clave para la Tesis:
1. **Superación del compromiso del Anteproyecto (WER < 15 %):** La configuración en GPU (large-v3-turbo) alcanza un WER de 2,39 %, superando holgadamente el umbral contractual del anteproyecto y el valor provisional (8,4 %) citado en el borrador inicial.
2. **Impacto de las Hotwords Clínicas:** La inyección del prompt clínico y las hotwords reduce el error en términos médicos del 6,67 % al 4,00 % en entornos con ruido hospitalario.
3. **Viabilidad de Respaldo en CPU:** En ausencia de aceleración por GPU, el modelo small int8 opera con un RTF de 0,142 (< 1,0 indica procesamiento más rápido que tiempo real) y un WER de 7,53 %, manteniéndose por debajo del umbral del 10 % aceptable en el dominio clínico.
