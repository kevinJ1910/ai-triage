# Benchmark de triaje

`casos_sinteticos.json` contiene 65 casos de consulta (entre 11 y 15 por nivel) para medir de forma reproducible el motor de reglas y el pipeline completo con `evaluate_benchmark`.

```bash
python manage.py evaluate_benchmark triage/benchmark/casos_sinteticos.json --engine reglas
python manage.py evaluate_benchmark triage/benchmark/casos_sinteticos.json --engine pipeline --output resultados.json
docker compose exec backend python manage.py evaluate_benchmark triage/benchmark/casos_sinteticos.json
```

## Campos

| Campo | Descripción |
| :--- | :--- |
| `id` | Identificador estable del caso (`B001`…). |
| `transcript` | Relato de la consulta, en lenguaje clínico o coloquial colombiano. |
| `reference_level` | Nivel de referencia (1–5) según los criterios de la Resolución 5596 / Christus Sinergia. |
| `tipo` | `tipico` (vocabulario del protocolo), `coloquial` (paráfrasis), `negacion` (hallazgos negados) o `signos_vitales` (la gravedad depende de valores numéricos). |
| `criterio` | Criterio del protocolo que justifica el nivel de referencia. |

## Limitaciones

- **Casos sintéticos.** Los relatos y los niveles de referencia los redactó el equipo del proyecto a partir de los criterios del protocolo. No son casos reales ni están adjudicados por un panel clínico, así que **no** sirven como validación clínica. Para eso está la validación ciega en la aplicación (`reference_level`), o un conjunto etiquetado por expertos con el mismo formato.
- **No es un conjunto ciego para el motor de reglas.** Se redactó antes de corregir los patrones, pero esas correcciones se hicieron después de ver los fallos. Las cifras del motor de reglas sobre este conjunto son una línea base de regresión (`triage/tests/test_benchmark_dataset.py`), no una estimación de su rendimiento real.
- Los casos con `tipo = coloquial`, `negacion` o `signos_vitales` están pensados para exponer los límites del motor léxico; se espera que el pipeline con Gemini los resuelva mejor.

# Corpus de entidades clínicas

`corpus_entidades.json` mide la extracción de entidades (NER), la negación y la normalización. Tiene 250 casos, 50 por nivel, en dos lotes:

| Lote | Casos | Contenido | dev / test |
| :---: | :--- | :--- | :---: |
| 1 | 120 (`B001`–`B065`, `N001`–`N055`) | Los 65 de `casos_sinteticos.json`, con el mismo `id`, transcript y nivel, más 55 nuevos | 70 / 50 |
| 2 | 130 (`N056`–`N185`), campo `lote: 2` | 26 por nivel: 12 coloquiales, 5 típicos, 5 de negación y 4 de signos vitales | 80 / 50 |

**Por qué hay lotes.** La partición se calcula dentro de cada lote. Si se recalculara sobre los 250 casos, cambiaría el orden por hash y algunos casos de `dev` pasarían a `test`. Eso contaminaría `test`, porque el catálogo terminológico y las reglas se ajustaron mirando `dev`. Por la misma razón, la muestra de doble anotación se elige solo dentro del lote 1. Un lote nuevo lleva el siguiente número.

**Sesgo de autoría del lote 2.** Se redactó con asistencia de IA el 15-10-2026, después de crear el catálogo de `transcription/terminology/`. Para no favorecerlo, se usaron a propósito expresiones que no están en el catálogo («se fue de lado», «el pecho trancado», «la popó negra como brea»). En `dev`, el motor de reglas obtiene una micro-F1 de 0,876 en el lote 1 y de 0,614 en el lote 2: el lote 1 está sobreajustado al catálogo. `evaluate_extraction` informa del desglose por lote; en `test` hay que reportarlo. Como conserva los campos del benchmark, `evaluate_benchmark` también lo acepta:

```bash
python manage.py evaluate_benchmark triage/benchmark/corpus_entidades.json --engine reglas
```

La carga y la validación están en `triage/entity_corpus.py` (`load_entity_corpus(split=...)`), y `triage/tests/test_entity_corpus.py` falla si el archivo deja de cumplir las reglas de esta guía.

## Estado: borrador pendiente de revisión

Todos los casos tienen `estado: "borrador"`. Las entidades de los 250 casos, y el nivel y el criterio de los 185 que no vienen de `casos_sinteticos.json`, se redactaron con asistencia de IA. **Antes de usar el corpus para reportar resultados**, el equipo debe revisar cada caso y cambiar `estado` a `"revisado"`. Si el corpus que evalúa a un LLM lo anotó otro LLM sin revisión humana, la evaluación no es defendible. Los cambios de la revisión se registran en el historial de git.

**Cómo se revisa.**
1. `python manage.py export_corpus_review --split test` genera `revision/revision_test.csv`, una planilla para Excel o Google Sheets que no incluye predicciones.
2. El revisor la llena siguiendo [`revision/GUIA_REVISION_ETIQUETAS.md`](revision/GUIA_REVISION_ETIQUETAS.md).
3. `python manage.py apply_corpus_review revision/revision_test.csv` la aplica al corpus.

Si la revisión cambia un nivel, el original se guarda en `nivel_particion`, para que ningún caso cambie de partición. El clínico que hará la validación ciega no debe revisar *test*.

**Códigos CIE-10 (`cie10`).** El 15-10-2026 se rellenaron de forma automática 176 entidades del lote 1 (119 de 208 en `dev` y 57 de 136 en `test`) y otras 176 del lote 2. El código se tomó del catálogo `transcription/terminology/` cuando la forma `normalized` de la entidad coincide con un término o una variante del catálogo. Las demás entidades, los signos vitales y los medicamentos (que se codifican con ATC, no con CIE-10) quedan en `null`. Hay tres cosas que tener en cuenta:

- **Son propuestas, no anotaciones.** El revisor debe confirmar o corregir cada código al pasar el caso a `revisado`, consultando la tabla CIE-10 oficial y no el catálogo.
- **La métrica es circular mientras no se revisen.** El código esperado sale del mismo catálogo que usa la normalización, así que `cie10_accuracy` en `evaluate_extraction` mide la **cobertura** del catálogo (si encuentra la mención), no si el código es clínicamente correcto. Solo después de la revisión humana mide exactitud.
- **El catálogo se amplió mirando `dev`, no `test`.** Por eso las cifras de `dev` de la normalización y del NER por reglas están infladas, y la cifra que se reporta es la de `test`.

## Campos adicionales

| Campo | Descripción |
| :--- | :--- |
| `split` | `dev` (150 casos) o `test` (100). Lo fija una regla, no se elige: por cada lote y nivel, los ids se ordenan por su SHA-256 y el primer 40 % va a `test`. El test de validación falla si un caso se mueve a mano. |
| `lote` | Lote de anotación (sin campo = 1). Ver arriba. |
| `estado` | `borrador` o `revisado`. |
| `entities` | Seis listas: `symptoms`, `diagnoses`, `medications`, `allergies`, `vitals`, `history`. |

Cada entidad tiene esta forma:

```json
{"text": "dolor en el pecho", "normalized": "dolor torácico", "negated": true, "cie10": null}
```

Las alergias llevan además `farmaco`:

```json
{"text": "camarones", "normalized": "mariscos", "negated": false, "cie10": null, "farmaco": false}
```

## Guía de anotación

Los límites de cada mención (qué palabras entran y cuáles no) están en [`GUIA_LIMITES.md`](GUIA_LIMITES.md). Es una propuesta del 17-10-2026, pendiente de que la apruebe el clínico. Si se aprueba, cambia dos criterios de esta guía: el evento traumático se anota (L8) y los hallazgos normales se anotan siempre como negados (L7).

**Span (`text`).** Es la mención mínima, copiada **literalmente** del transcript, con sus errores de transcripción (`"posartan"`). No incluye la partícula de negación: en «no tiene dolor en el pecho», el span es `dolor en el pecho`. El span tiene que aparecer en el transcript; eso permite calcular los offsets para entrenar el NER en formato BIO.

**Tipos.**
- `symptoms`: síntomas y signos referidos u observados: dolor, fiebre, sangrado, palidez, disartria.
- `diagnoses`: enfermedades, lesiones o estados del episodio actual que se nombran como tales: fractura, quemadura, herida, gripa, gestación, intoxicación, abuso sexual. El mecanismo («se cayó de la moto») no se anota, salvo que sea la propia condición («se atoró con comida», que es obstrucción de vía aérea); la regla L8 de `GUIA_LIMITES.md` propone cambiarlo.
- `medications`: fármacos por nombre o clase explícita (losartán, insulina, inhalador). «Las pastillas», sin más contexto, no se anota.
- `allergies`: sustancia a la que se declara alergia, o reacción adversa explícita a un fármaco (B031). Si el fármaco también se menciona como medicamento, se anota en los dos tipos. `farmaco` es `true` si la sustancia es un medicamento (penicilina, sulfas, dipirona) y `false` si es un alimento, un alérgeno ambiental o un veneno (camarones, maní, polvo, abejas). Para el NER, solo las de `farmaco: true` son `FARMACO`, como en DrugTEMIST; las demás las cubren el catálogo y Gemini. Para la evaluación de `allergies` cuentan todas.
- `vitals`: el valor medido. `normalized` usa el formato compacto de `input_pipeline` (`PA: 70/40 mmHg`, `FC: 140 lpm`, `SpO2: 78%`, `T: 38.9°C`, `FR: 32 rpm`, `GLU: 520 mg/dL`, `GCS: 7/15`), para compararlo directamente con lo que extrae el regex.
- `history`: antecedentes crónicos o previos: hipertensión, diabetes, asma, EPOC, diálisis, tabaquismo.

**Negación (`negated`).** Es `true` cuando el hallazgo se niega explícitamente («sin fiebre», «niega convulsiones», «no perdió el conocimiento») o por su contrario normal («respiro bien» niega la disnea; «lo mueve bien» niega la impotencia funcional).

Los casos difíciles son a propósito. Algunas frases **parecen negaciones pero describen un hallazgo presente**, y se anotan con `negated: false`:

| Frase | Hallazgo presente |
| :--- | :--- |
| «no respira» | apnea |
| «no responde», «sin respuesta» | inconsciencia |
| «sin poder hablar» | disnea que impide hablar |
| «no puede mover el brazo» | paresia |
| «no siente la pierna» | hipoestesia |
| «no me dan ganas de comer» | hiporexia |
| «casi no orino», «no he orinado» | oliguria |

Un detector de negación ingenuo, que marque todo lo que va detrás de «no» o «sin», falla en estos casos. Por eso sirven para medirlo.

**Forma normalizada (`normalized`).** Es el término clínico en español, en minúsculas salvo nombres propios: «disnea», no «falta de aire». Para los medicamentos se usa el principio activo: `posartan` → `losartán`, `aspirina` → `ácido acetilsalicílico`.

## Evaluación de la extracción

```bash
python manage.py evaluate_extraction --engine reglas --split dev
python manage.py evaluate_extraction --engine gemini --model gemini-2.5-flash --split dev --pause 1 \
    --output triage/benchmark/resultados/linea_base_dev_gemini-2.5-flash.json
python manage.py evaluate_extraction --agreement doble_anotacion/segundo_anotador.json
```

- **Motores.** Con `reglas`, el analizador corre sin LLM: entidades por palabras clave y regex, nivel por el motor de reglas. Con `gemini`, corre el análisis completo sin caché y con **un único modelo** (`--model`), sin modelos de respaldo, para que las cifras de un modelo no mezclen respuestas de otro. Si una llamada falla, el caso se resuelve con reglas y se cuenta en `llm_failures`.
- **Una llamada por caso** alimenta a la vez las métricas de entidades y las de triaje, así que no se paga la API dos veces.
- **Emparejamiento** (`--match`):
  - `strict`: la predicción coincide, sin tildes ni mayúsculas, con el span o con la forma normalizada.
  - `relaxed` (el modo por defecto): además, uno contiene al otro o comparten al menos la mitad de sus palabras de contenido.
  - Signos vitales: se comparan el tipo y los valores numéricos (`PA: 70/40 mmHg` empareja con «presión 70 sobre 40»).
- **Negación.** Un hallazgo anotado como negado que el motor reporta como presente cuenta como falso positivo y como error de negación. `negation_accuracy` es el porcentaje de negados que **no** se reportaron como presentes. `negated_detection_recall` es el porcentaje que el motor reportó explícitamente como negados en `negated_findings`.
- **F1 por tipo.** Si hay entidades anotadas de un tipo y el motor no acierta ninguna, el F1 vale 0. Ese 0 entra en el macro-F1.
- **Intervalos de confianza al 95 %** por bootstrap (1.000 remuestreos de casos, semilla fija) para el micro-F1, el Kappa y la sensibilidad en niveles 1–2.
- **Acuerdo entre anotadores** (`--agreement`): F1 por pares entre la primera y la segunda anotación (Hripcsak y Rothschild, 2005), más el acuerdo en la negación de las entidades emparejadas. Se usa F1 y no Kappa porque Kappa no está bien definido para spans: no hay «negativos» que contar.
- **El split `test` se usa una sola vez**, en la evaluación final. Ajustar reglas o prompts mirando sus resultados invalida la medición.

- **Cuota de la API y reanudación.** Con `gemini` o `hibrido`, cada caso evaluado se guarda en `resultados/crudos/<run_id>.jsonl`, con la salida cruda del modelo, `model_version`, tokens y latencia. Así una corrida cortada se reanuda con el mismo comando, y `--fresh` empieza de cero. Las opciones para no pasarse de la cuota son estas:
  - `--rpm 5` limita las peticiones por minuto.
  - `--max-calls N` corta la tanda.
  - Si Gemini responde con la cuota diaria agotada, el comando se detiene sin perder casos.

  Un caso cuyo LLM falla **queda pendiente**; nunca se resuelve con reglas. Mientras falten casos, el resumen se escribe con `complete: false` y el panel no lo muestra. `--summarize-only` recalcula el resumen desde el checkpoint sin llamar a la API: sirve para probar `--policy min_critico` o para repuntuar tras corregir etiquetas.

El procedimiento completo está en [`docs/EVALUACION_TRIAJE.md`](../../../docs/EVALUACION_TRIAJE.md): el orden de las corridas, el prompt versionado (`--prompt-version`), las ablaciones (`--no-rule-hint`, `--no-rag`), el LLM local (`--model local:<modelo>`), el costo, la comparativa (`compare_engines`) y la validación clínica (`import_blind_review` y `export_blind_review`). `evaluate_benchmark --engine pipeline` exige `--split`, porque `casos_sinteticos.json` comparte casos con el *test* del corpus.

Los resultados se guardan en `resultados/`. La línea base del motor de reglas sobre *dev* (`dev_reglas_lotes.json`, 150 casos) se reproduce exactamente con el comando de arriba. Las corridas con Gemini y con el LLM local siguen el procedimiento de `docs/EVALUACION_TRIAJE.md`.

`demografia.json` guarda el sexo y el grupo de edad derivados de cada transcript (`python manage.py derive_demographics`), para el desglose descriptivo de sesgo. Las entradas revisadas a mano llevan `"fuente": "revisado"`.

## Doble anotación

Para medir el acuerdo entre anotadores, un segundo anotador etiqueta a ciegas 30 casos: 6 por nivel, elegidos con `double_annotation_sample()` por hash y repartidos entre `dev` y `test`. Trabaja sobre `doble_anotacion/plantilla_segundo_anotador.json`, que no incluye las entidades ni el nivel de la primera anotación, y sigue esta misma guía. **No debe abrir `corpus_entidades.json` antes de terminar.** El acuerdo se calcula con el evaluador de entidades.
