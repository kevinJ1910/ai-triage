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

`corpus_entidades.json` mide la extracción de entidades (NER), la negación y la normalización. Tiene 120 casos: los 65 de `casos_sinteticos.json`, con el mismo `id`, transcript y nivel, más 55 nuevos (`N001`…). Hay 24 casos por nivel. Como conserva los campos del benchmark, `evaluate_benchmark` también lo acepta:

```bash
python manage.py evaluate_benchmark triage/benchmark/corpus_entidades.json --engine reglas
```

La carga y la validación están en `triage/entity_corpus.py` (`load_entity_corpus(split=...)`), y `triage/tests/test_entity_corpus.py` falla si el archivo deja de cumplir las reglas de esta guía.

## Estado: borrador pendiente de revisión

Todos los casos tienen `estado: "borrador"`. Las entidades de los 120 casos, y el nivel y el criterio de los 55 nuevos, se redactaron con asistencia de IA. **Antes de usar el corpus para reportar resultados**, el equipo debe revisar cada caso y cambiar `estado` a `"revisado"`. Si el corpus que evalúa a un LLM lo anotó otro LLM sin revisión humana, la evaluación no es defendible. Los cambios de la revisión se registran en el historial de git.

`cie10` vale `null` en todas las entidades. Los códigos se asignan en el paso de normalización contra el catálogo CIE-10 oficial, no de memoria.

## Campos adicionales

| Campo | Descripción |
| :--- | :--- |
| `split` | `dev` (70 casos) o `test` (50). Lo fija una regla, no se elige: por cada nivel, los ids se ordenan por su SHA-256 y el primer 40 % va a `test`. El test de validación falla si un caso se mueve a mano. |
| `estado` | `borrador` o `revisado`. |
| `entities` | Seis listas: `symptoms`, `diagnoses`, `medications`, `allergies`, `vitals`, `history`. |

Cada entidad tiene esta forma:

```json
{"text": "dolor en el pecho", "normalized": "dolor torácico", "negated": true, "cie10": null}
```

## Guía de anotación

**Span (`text`).** Es la mención mínima, copiada **literalmente** del transcript, con sus errores de transcripción (`"posartan"`). No incluye la partícula de negación: en «no tiene dolor en el pecho», el span es `dolor en el pecho`. El span tiene que aparecer en el transcript; eso permite calcular los offsets para entrenar el NER en formato BIO.

**Tipos.**
- `symptoms`: síntomas y signos referidos u observados: dolor, fiebre, sangrado, palidez, disartria.
- `diagnoses`: enfermedades, lesiones o estados del episodio actual que se nombran como tales: fractura, quemadura, herida, gripa, gestación, intoxicación, abuso sexual. El mecanismo («se cayó de la moto») no se anota, salvo que sea la propia condición («se atoró con comida», que es obstrucción de vía aérea).
- `medications`: fármacos por nombre o clase explícita (losartán, insulina, inhalador). «Las pastillas», sin más contexto, no se anota.
- `allergies`: sustancia a la que se declara alergia, o reacción adversa explícita a un fármaco (B031). Si el fármaco también se menciona como medicamento, se anota en los dos tipos.
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

## Doble anotación

Para medir el acuerdo entre anotadores, un segundo anotador etiqueta a ciegas 30 casos: 6 por nivel, elegidos con `double_annotation_sample()` por hash y repartidos entre `dev` y `test`. Trabaja sobre `doble_anotacion/plantilla_segundo_anotador.json`, que no incluye las entidades ni el nivel de la primera anotación, y sigue esta misma guía. **No debe abrir `corpus_entidades.json` antes de terminar.** El acuerdo se calcula con el evaluador de entidades.
