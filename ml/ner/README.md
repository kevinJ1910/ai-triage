# NER clínico con RoBERTa (paso 3.1 del plan)

Fine-tuning de [`PlanTL-GOB-ES/roberta-base-biomedical-clinical-es`](https://huggingface.co/PlanTL-GOB-ES/roberta-base-biomedical-clinical-es) (Apache-2.0) para detectar `SINTOMA`, `ENFERMEDAD` y `FARMACO` en transcripciones de triaje. Si la organización PlanTL deja de estar disponible, el código usa la réplica `BSC-LT/roberta-base-biomedical-clinical-es`.

| Fichero | Qué hace |
| :--- | :--- |
| `finetune_roberta_ner.ipynb` | Notebook para Colab o Kaggle (GPU T4): descarga, fusión, etapa 1, etapa 2, métricas y exportación. |
| `ner_data.py` | Lectura de los corpus (TSV y brat), fusión por documento, alineación BIO, métricas por span y particiones. Solo usa la biblioteca estándar. |
| `train_ner.py` | Tokenización con ventanas solapadas, `Trainer`, predicción por documento y guardado. Incluye `--smoke`. |
| `make_bundle.py` | Empaqueta el código y el corpus propio para subirlos al notebook, porque el repositorio es privado. |
| `tests/test_ner_data.py` | Pruebas de la preparación de datos con corpus sintéticos en los formatos reales. |

## Datos

| Corpus | Zenodo | Licencia | Etiqueta original → modelo |
| :--- | :--- | :--- | :--- |
| SympTEMIST v4 (2024-02-08) | [10635215](https://zenodo.org/records/10635215) | CC BY 4.0 | `SINTOMA` → `SINTOMA` |
| DisTEMIST v5.1 (2022-05-09) | [7614764](https://zenodo.org/records/7614764) | CC BY 4.0 | `ENFERMEDAD` → `ENFERMEDAD` |
| DrugTEMIST, dentro de MultiCardioNER (2024-05-28) | [11368861](https://zenodo.org/records/11368861) | CC BY 4.0 | `FARMACO` → `FARMACO`; solo los ficheros en español (prefijo `es-` o sin prefijo) |
| PharmaCoNER v1.1 (2020-11-12), opcional | [4270158](https://zenodo.org/records/4270158) | CC BY 4.0 | `NORMALIZABLES` y `NO_NORMALIZABLES` → `FARMACO`; `PROTEINAS` y `UNCLEAR` se descartan |
| Corpus propio, split `dev` | `backend/triage/benchmark/corpus_entidades.json` | del proyecto | `symptoms` → `SINTOMA`; `diagnoses` y `history` → `ENFERMEDAD`; `medications` y `allergies` → `FARMACO`; `vitals` → `O` (lo extrae el regex) |

Las licencias se comprobaron en la API de Zenodo el 15-10-2026. CC BY 4.0 exige citar los corpus en la tesis.

**`FARMACO` sale de DrugTEMIST.** Sus guías anotan medicamentos, igual que `medications` del corpus propio, y anota los mismos 1.000 documentos que DisTEMIST. PharmaCoNER también incluye sustancias químicas, proteínas y genes; se puede sumar con `USE_PHARMACONER = True`, a costa de quedarse solo con los documentos presentes en los cuatro corpus.

**Por qué se fusionan.** Los corpus anotan los mismos casos clínicos de SPACCC, pero cada uno solo un tipo de entidad. Si se entrenara con uno suelto, el modelo aprendería que los síntomas de DisTEMIST son `O`. `merge_corpora` une las tres capas por nombre de fichero y, por defecto, solo usa los documentos que están en los tres corpus. Si un texto difiere entre versiones, reubica los spans por su contenido. Cuando dos spans se solapan, se queda el más largo, porque BIO no admite solapes. El notebook muestra cuántos documentos y spans se descartaron.

## Protocolo

1. **Etapa 1.** Se entrena con los tres corpus fusionados, usando todos sus splits con anotación gold, y se aparta un 10 % de documentos para validación. Hiperparámetros: 3 épocas, lr 5e-5, lote 16, 512 tokens con *stride* de 128, semilla 42.
2. **Transferencia sin adaptar.** El modelo de la etapa 1 se evalúa sobre `dev` del corpus propio. Mide cuánto se pierde al pasar de texto clínico escrito a habla transcrita.
3. **Etapa 2.** Validación cruzada de 5 particiones sobre `dev`: cada partición parte del modelo de la etapa 1, con 10 épocas, lr 2e-5 y lote 8. Se reporta la media ± desviación.
4. **Modelo final.** Etapa 1 + todo `dev`. Se guarda con `metrics.json`, `training_config.json` y `ner_labels.json`.

La métrica principal es por **span exacto** (inicio, fin y etiqueta), comparable con las métricas del resto del proyecto. La F1 por entidad sobre las etiquetas de cada ventana (equivalente a `seqeval`, verificada en 200 casos aleatorios, pero sin depender de él) solo sirve para elegir el mejor checkpoint de la etapa 1.

**El split `test` del corpus propio no se usa en ningún momento.** Se evalúa una sola vez, con el sistema híbrido completo, en el paso 4.1.

## Cómo ejecutarlo

1. En tu equipo, genera el paquete:

   ```bash
   python ml/ner/make_bundle.py
   ```

2. Abre `finetune_roberta_ner.ipynb` en Colab, activa la GPU T4 y ejecuta todas las celdas. Sube `ml/ner/output/ner_bundle.zip` cuando el notebook lo pida. En Kaggle, súbelo como *Dataset*.
3. Descarga `ai_triage_ner_roberta.zip`, o súbelo a un repositorio privado de Hugging Face Hub (celda 10). **El modelo nunca se versiona en git**: `ml/ner/output/` está en `.gitignore`.
4. Descomprímelo en `ml/ner/output/ai_triage_ner_roberta/`. La primera vez hay que reconstruir la imagen, que ahora incluye torch para CPU; el worker LLM usa la imagen del backend:

   ```bash
   docker compose up -d --build backend worker-llm
   ```

   Si después solo cambias el modelo, basta con `docker compose restart worker-llm`.

   Comprueba que cargó con `curl -k https://localhost/api/health_check/`: debe aparecer `"ner": {"model_loaded": true, ...}`. Si usas el Hub, define en `.env` `NER_MODEL_PATH=TU_USUARIO/ai-triage-ner-roberta` y `HF_TOKEN`.

## Integración en el backend (paso 3.2)

| Pieza | Dónde |
| :--- | :--- |
| Motor (singleton, CPU, carga perezosa, estado en `ner:engine_status`) | `backend/triage/ner_model.py` |
| Fusión híbrida (pura, sin red) | `backend/triage/entity_fusion.py` |
| Uso en el análisis (`use_ner`, `ner_engine`, `ner_spans`) | `backend/triage/ai_analyzer.py` |
| PyTorch solo para CPU (también en la imagen con GPU) | `backend/requirements-ner.txt` |
| Carga en el arranque del worker LLM y memoria de 2 GB | `docker-compose.yml` (`NER_MODEL_PATH`, `NER_PRELOAD`) |

La fusión sigue estas reglas:

1. **El modelo aporta la mención y su posición exacta.** Si una mención tiene una confianza menor que `NER_MIN_SCORE` (0,6), se descarta, salvo que la confirmen el catálogo o Gemini.
2. **El catálogo normaliza la mención** («calentura» → fiebre) solo si la cubre casi por completo. Así, un término genérico como «dolor» no sustituye a «dolor punzante en el talón».
3. **`negation.py` decide qué está negado** y manda tanto sobre el modelo como sobre el LLM.
4. **El contexto asigna el papel.** Un `FARMACO` precedido de «alérgico a» es una alergia. Una `ENFERMEDAD` con señal de antecedente («antecedente de», «sufre de», «crónico») o con categoría `Antecedente` en el catálogo va a `history`.
5. **Se añade lo que el modelo no vio:** siglas, alérgenos no farmacológicos y otros términos del catálogo.
6. **Gemini (modo híbrido)** desempata las menciones dudosas y aporta términos extra, pero solo si tienen apoyo literal en el relato. Eso evita incorporar entidades alucinadas.

**Si no hay modelo, el comportamiento es el de antes.** Ocurre si falta torch, si `NER_MODEL_PATH` está vacío o la carpeta no existe, o si el modelo falla. En esos casos el triaje usa el catálogo, las reglas y Gemini, y una ruta ausente no se reintenta en cada consulta. El NER solo se carga en el worker LLM: el proceso web no tiene `NER_MODEL_PATH`, y su respaldo sin worker usa las reglas.

Para medir cada motor por separado:

```bash
python manage.py evaluate_extraction --engine roberta --split dev
python manage.py evaluate_extraction --engine hibrido --model gemini-2.5-flash --split dev
```

## Verificación local, sin GPU

```bash
backend/.venv/Scripts/python.exe -m pytest ml/ner/tests -p no:django
python ml/ner/train_ner.py --smoke
```

La prueba de humo necesita `torch`, `transformers` (4 o 5) y `datasets` en un entorno aparte. No se instalan en el backend; en el paso 3.2 el backend solo tendrá `torch` para CPU. La prueba usa el tokenizador real y un RoBERTa diminuto con pesos aleatorios, y comprueba tres cosas:

- Las etiquetas BIO reconstruyen exactamente los spans de 12 casos de `dev`.
- El entrenamiento, la evaluación y el guardado funcionan.
- Un documento largo se procesa en varias ventanas solapadas.

Además, el notebook se simuló completo, de la celda 4 a la 9, con corpus falsos que reproducen la estructura de los ZIP, incluidas las carpetas de traducciones y *background* de SympTEMIST, que tienen los mismos nombres de fichero.

## Limitaciones que hay que declarar

- El corpus propio es pequeño (150 casos en `dev`, en dos lotes) y está anotado con asistencia de IA; la revisión humana está pendiente.
- `ENFERMEDAD` agrupa diagnósticos del episodio y antecedentes, y `FARMACO` agrupa medicamentos y alérgenos farmacológicos. La distinción la hacen después las reglas de contexto.
- Los corpus públicos son casos clínicos escritos, no diálogos de triaje.
- Los alérgenos que no son fármacos, como «camarones», no están cubiertos por PharmaCoNER: los cubren el catálogo y Gemini.
