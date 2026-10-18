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
