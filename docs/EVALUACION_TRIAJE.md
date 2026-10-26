# Evaluación del triaje inteligente

Este documento describe cómo se mide el módulo de triaje de AI-Triage frente al criterio del anteproyecto (exactitud mayor al 80 % frente a expertos, con índice Kappa), qué motores se comparan, cómo reproducir cada cifra y el texto que justifica en la tesis las decisiones que se apartan del plan original.

Las tablas de resultados de la sección 8 las escribe el comando `compare_engines`. No se editan a mano.

## 1. Motores que se comparan

| Motor | Qué hace | Comando (`--engine` / `--model`) |
| :--- | :--- | :--- |
| Reglas | Motor determinista Christus Sinergia / Res. 5596, con umbrales de signos vitales y NegEx. No usa red. | `reglas` |
| Híbrido con Gemini (producción) | Reglas, RAG léxico, NER RoBERTa, Gemini con salida estructurada y fusión de entidades. Las reglas actúan como pauta y como respaldo. | `hibrido --model gemini-2.5-flash` |
| Gemini sin pauta (ablación) | Gemini sin la pauta de reglas ni los criterios recuperados. Mide cuánto aportan las reglas y el RAG. | `gemini --model gemini-2.5-flash --no-rule-hint --no-rag` |
| LLM local | El mismo prompt y el mismo esquema contra un servidor propio compatible con OpenAI (Ollama). Los datos no salen del servidor. | `hibrido --model local:qwen2.5:7b-instruct-q4_K_M` |
| Gemini Flash-Lite | La configuración de producción con un modelo más barato. | `hibrido --model gemini-3.5-flash-lite` |

Los modelos de Gemini verificados el 18-10-2026 son `gemini-2.5-flash` y `gemini-3.5-flash-lite`. `gemini-2.5-flash-lite` y `gemini-2.5-pro` aparecen en `models.list`, pero devuelven 404 en las cuentas nuevas.

## 2. Reglas del procedimiento

1. **El split *test* se usa una sola vez.** Primero se ajusta todo con *dev* (150 casos): la versión del prompt, la política que combina las reglas con el LLM y el modelo. Después se congela con un commit y solo entonces se evalúa *test* (100 casos). No se cambia nada mirando *test*.
2. **Un caso resuelto por reglas nunca cuenta como resultado del LLM.** En la evaluación, el analizador se llama con `strict_llm=True`. Si el LLM falla, el caso queda pendiente en el checkpoint y se reintenta en la siguiente tanda. Un resumen con casos pendientes se marca `complete: false` y no aparece en el panel.
3. **Todo es reproducible desde el repositorio.** Cada corrida guarda en `backend/triage/benchmark/resultados/crudos/<run_id>.jsonl` una línea por caso con:
   - la salida cruda del modelo (`llm_raw`) y el id exacto que sirvió la petición (`model_version`);
   - los tokens de entrada, de salida y de razonamiento, y la latencia.

   El JSON de resumen añade el bloque `run`: versión y SHA-256 del prompt, temperatura, política, plan del proveedor, commit de git, hardware y huella del corpus.

   `--summarize-only` recalcula el resumen desde el checkpoint sin llamar a la API. Así se cambia la política o se corrigen etiquetas del corpus sin pagar otra vez.
4. **Como mucho dos versiones nuevas del prompt sobre *dev*.** Cada cambio es una versión nueva en `PROMPT_TEMPLATES` (`backend/triage/ai_analyzer.py`). No se edita el texto de una versión ya medida.
   - `v1` es el prompt original.
   - `v2` trata la pauta de reglas como **suelo de urgencia**: el LLM puede subir la urgencia, pero para bajarla tiene que citar el criterio del protocolo que lo permite.
5. **La política de combinación se elige con los datos guardados.** Hay dos políticas:
   - `llm`: el nivel del LLM tal cual.
   - `min_critico`: si las reglas detectan un nivel I–II, prevalece el más urgente de los dos.

   Ambas se comparan con `--summarize-only` sobre los checkpoints de *dev*. La elegida se fija en producción con `TRIAGE_COMBINE_POLICY`.

## 3. Pasos y comandos

Todos se ejecutan desde `backend/` (en Docker: `docker compose exec backend python manage.py ...`).

```bash
# 0. Línea base del motor de reglas (sin red)
python manage.py evaluate_extraction --engine reglas --split dev --output triage/benchmark/resultados/dev_reglas_lotes.json

# 1. Piloto de 10 casos para medir los tokens reales y estimar el costo
python manage.py evaluate_extraction --engine hibrido --model gemini-2.5-flash --split dev --limit 10 --tag piloto

# 2. dev con el prompt v1 (plan gratuito: --rpm 5 y --max-calls según la cuota diaria; se reanuda con el mismo comando)
python manage.py evaluate_extraction --engine hibrido --model gemini-2.5-flash --split dev --rpm 5 --tier gratuito \
    --output triage/benchmark/resultados/dev_hibrido_gemini-2.5-flash_pv1.json

# 3. Análisis de errores en dev (triage.critical_undertriage y triage.by_tipo del JSON) y, si hace falta, v2
python manage.py evaluate_extraction --engine hibrido --model gemini-2.5-flash --split dev --prompt-version v2 \
    --output triage/benchmark/resultados/dev_hibrido_gemini-2.5-flash_pv2.json

# 4. Política de combinación, sin nuevas llamadas
python manage.py evaluate_extraction --engine hibrido --model gemini-2.5-flash --split dev --prompt-version v2 \
    --summarize-only --policy min_critico --output triage/benchmark/resultados/dev_hibrido_gemini-2.5-flash_pv2_min.json

# 5. Ablación y repetibilidad (dev)
python manage.py evaluate_extraction --engine gemini --model gemini-2.5-flash --split dev --no-rule-hint --no-rag \
    --output triage/benchmark/resultados/dev_gemini_gemini-2.5-flash_sin-pauta.json
python manage.py evaluate_extraction --engine hibrido --model gemini-2.5-flash --split dev --limit 30 --tag r2 \
    --output triage/benchmark/resultados/dev_hibrido_r2.json

# 6. Congelar (commit con TRIAGE_PROMPT_VERSION, TRIAGE_COMBINE_POLICY y el modelo) y revisar las etiquetas de test

# 7. test, una sola vez, con la configuración congelada
python manage.py evaluate_extraction --engine reglas --split test --output triage/benchmark/resultados/test_reglas.json
python manage.py evaluate_extraction --engine hibrido --model gemini-2.5-flash --split test --prompt-version v2 \
    --policy min_critico --tier pago --output triage/benchmark/resultados/test_hibrido_gemini-2.5-flash.json

# 8. Tablas comparativas (sección 8 de este documento y panel «Resultados de Evaluación»)
python manage.py compare_engines --split dev --only dev_reglas_lotes dev_hibrido_gemini-2.5-flash_pv1 ...
python manage.py compare_engines --split dev --only ... --repeatability triage/benchmark/resultados/dev_hibrido_gemini-2.5-flash_pv1.json triage/benchmark/resultados/dev_hibrido_r2.json
python manage.py compare_engines --split test
```

La repetibilidad compara solo los casos comunes: los 30 primeros de *dev*. El sexo y el grupo de edad de cada caso (`backend/triage/benchmark/demografia.json`) se generan con `python manage.py derive_demographics`. `evaluate_extraction` los desglosa en `triage.by_sexo` y `triage.by_grupo_edad`.

## 4. Cuota y costo de Gemini

**Plan gratuito.** `gemini-2.5-flash` permite 5 peticiones por minuto y **20 al día por modelo**. Es la cuota `GenerateRequestsPerDayPerProjectPerModel-FreeTier` que devolvió la API el 18-10-2026. Una pasada de *dev* (150 casos) necesita unos 8 días y el programa completo más de un mes, así que el plan gratuito no alcanza para el plazo de la tesis. El corredor tiene tres protecciones:
- respeta `--rpm`;
- corta la tanda con `--max-calls`;
- si el proveedor informa la cuota diaria agotada (`PerDay` en el 429) o el 429 persiste tras los reintentos, se detiene sin perder casos.

Al día siguiente se repite el mismo comando.

**Plan de pago.** Las tarifas son de 0,30 USD por millón de tokens de entrada y 2,50 USD por millón de salida, razonamiento incluido, tanto en 2.5 Flash como en 3.5 Flash-Lite ([precios oficiales](https://ai.google.dev/gemini-api/docs/pricing), consultados el 18-10-2026 y guardados en `evaluation_runner.PRICES`).

Piloto medido el 18-10-2026: 10 casos de *dev*, motor `gemini` (sin NER), prompt `v1`, plan gratuito.

| Concepto | Medido en el piloto |
| :--- | :--- |
| Tokens por caso | 476 de entrada, 282 de salida y 815 de razonamiento, de media |
| Costo por caso | ≈ 0,0029 USD (2,89 USD por 1.000 triajes). El razonamiento supone el 70 % del costo. |
| Latencia | p50 de 6,0 s y p95 de 9,8 s |
| Programa completo (3 versiones × 150 de *dev* + ablación + repetibilidad + 100 de *test*, ≈ 700 llamadas) | **≈ 2 USD** |
| Corrida adicional con Flash-Lite | + ≈ 0,5 USD |

En el piloto hubo un 503 por alta demanda, que el corredor reintentó: hubo 11 llamadas para 10 casos. `performance.cost_usd` recalcula el costo con los tokens reales de cada corrida.

**Recomendación: activar la facturación para estas corridas.** El costo es despreciable, se elimina el riesgo de plazo y, con el plan de pago, Google no usa el contenido para mejorar sus productos. Eso es relevante para la sección de privacidad aunque el corpus sea sintético. La Batch API cuesta la mitad y no tiene límite por minuto, pero tarda hasta 24 h y no está integrada.

## 5. LLM local

El adaptador está en `backend/triage/local_llm.py`. Funciona así:
- Llama a `POST {LOCAL_LLM_BASE_URL}/v1/chat/completions` con `response_format: json_schema` y el mismo `TriageOutputSchema`.
- El texto se seudonimiza igual que con Gemini y la salida se valida con Pydantic.
- **Si falla, clasifica el motor de reglas y nunca se recurre a Gemini.** Quien elige el motor local lo hace para que los datos no salgan del servidor.

| Equipo | Uso | Tiempo |
| :--- | :--- | :--- |
| Junior (GPU NVIDIA) | Operativo. La latencia que se reporta como operativa es la de este equipo. | Segundos por caso |
| Kevin (CPU AMD) | Solo evaluación por lotes. La latencia se reporta con el hardware anotado (`--hardware`). | 1–2 minutos por caso; 150 casos son una noche |

```bash
docker compose --profile llm-local up -d
docker compose exec llm-local ollama pull qwen2.5:7b-instruct-q4_K_M
python manage.py evaluate_extraction --engine hibrido --model local:qwen2.5:7b-instruct-q4_K_M --split dev \
    --tier local --hardware "RTX ... / Ryzen ..." --output triage/benchmark/resultados/dev_hibrido_local-qwen.json
```

**Modelo principal:** Qwen2.5-7B-Instruct en Q4_K_M (licencia Apache-2.0, buen desempeño en español). **Alternativa:** Llama-3.1-8B-Instruct en Q4_K_M (licencia Llama Community, que hay que citar).

El LLM local usa el prompt y la política congelados con Gemini, sin ajuste propio, para que la comparación sea justa.

Ollama impone la estructura del esquema, pero no sus límites numéricos. En la corrida de *dev* del 18-10-2026, Qwen devolvió la confianza en porcentaje (`95` en vez de `0.95`) en 40 de 150 casos. `_coerce_llm_output` la divide entre 100 antes de validar y lo deja anotado en `output_coerced` y en `performance.coerced_cases`. El nivel de triaje nunca se modifica, y una confianza mayor que 100 sigue siendo inválida. Fuera de Docker se arranca Ollama nativo con `LOCAL_LLM_BASE_URL=http://localhost:11434`.

Para usarlo desde la interfaz, se elige «LLM local» en Configuración. En CPU hay que subir `LLM_TASK_TIMEOUT` por encima de `LOCAL_LLM_TIMEOUT_SECONDS`.

## 6. Validación clínica ciega

1. **Importar la muestra.** Con el motor congelado ya evaluado sobre *test*:

   ```bash
   python manage.py import_blind_review --run triage/benchmark/resultados/test_hibrido_gemini-2.5-flash.json
   ```

   El comando carga en la Validación ciega 50 casos de *test*, 10 por nivel, elegidos por hash. Usa el nivel y la justificación ya guardados, sin nuevas llamadas al LLM.
2. **Adjudicar.** El clínico entra en «Validación ciega» y asigna su nivel viendo solo el relato. Después valora la justificación de la IA con Likert 1–5 (claridad, pertinencia y fidelidad al protocolo). No debe abrir el corpus ni los resultados antes de terminar.
3. **Exportar.** `python manage.py export_blind_review --run ...` calcula:
   - Kappa ponderado clínico–IA, clínico–reglas y clínico–equipo, este último como **techo humano**;
   - las medias Likert con IC95.

   El resultado se guarda en `resultados/validacion_clinica_test.json`, que muestra el panel.
4. **Limpiar.** `python manage.py import_blind_review --purge` borra los pacientes `CORPUS-`. Mientras existen, `evaluation_metrics` los excluye.

## 7. Análisis de errores y sesgo

- **Infratriaje crítico.** Cada resumen trae `triage.critical_undertriage`: los casos de referencia I–II clasificados como III–V, ordenados por la distancia del error y con el nivel de reglas y la justificación. `compare_engines` lista los ids por motor.
  - En *dev* sirve para decidir la versión del prompt y la política.
  - En *test* solo se reporta.
- **Por tipo de caso y por lote.** `triage.by_tipo` (típico, coloquial, negación, signos vitales) y `triage.by_lote`. El lote 2 se redactó sin ver el catálogo y mide mejor la generalización.
- **Sexo y edad.** `triage.by_sexo` y `triage.by_grupo_edad` son solo descriptivos, sin pruebas de hipótesis. La mayoría de relatos en primera persona no dicen el sexo ni la edad: unos 40 de 250 casos traen sexo y unos 30 traen grupo de edad. Por eso los grupos son pequeños, y así se declara en la sección 7.5. Las entradas de `demografia.json` revisadas a mano se marcan con `"fuente": "revisado"`.

## 8. Resultados

Las tablas las genera `compare_engines` entre los marcadores. Las de *test* solo existen después del paso 7.

### Desarrollo (*dev*)

<!-- comparativa:dev:inicio -->
Split **dev**. Intervalos de confianza al 95 % por bootstrap (1.000 remuestreos).

| Motor | n | Exactitud | Kappa ponderado | Sensibilidad I–II | Infratriaje | Sobretriaje | Latencia p50 / p95 | Costo por 1.000 | Privacidad |
| :--- | ---: | :--- | :--- | :--- | :--- | ---: | :--- | ---: | :--- |
| LLM local (gemma4:e4b-it-qat) + reglas (prompt v1, NER) | 150 | 65,3 % [57,3–72,7] | 0,766 [0,667–0,846] | 75,0 % [62,9–85,9] | 30,0 % [23,3–38,0] | 4,7 % | 114941 / 178835 ms (CPU AMD Ryzen (12 hilos, Docker 8 GB), Ollama 0.34.4, razonamiento activado; solo por lotes) | 0,00 USD | local (los datos no salen del servidor) |
| LLM local (gemma4:e4b-it-qat) + reglas (prompt v1, política min_critico, NER) | 150 | 65,3 % [57,3–72,7] | 0,766 [0,667–0,846] | 75,0 % [62,9–85,9] | 30,0 % [23,3–38,0] | 4,7 % | 114941 / 178835 ms (CPU AMD Ryzen (12 hilos, Docker 8 GB), Ollama 0.34.4, razonamiento activado; solo por lotes) | 0,00 USD | local (los datos no salen del servidor) |
| LLM local (qwen2.5:7b-instruct-q4_K_M) + reglas (prompt v1, NER) | 150 | 50,0 % [41,3–58,0] | 0,487 [0,357–0,609] | 50,0 % [36,8–62,5] | 46,7 % [38,0–54,7] | 3,3 % | 45150 / 55070 ms (CPU AMD Ryzen (12 hilos, Docker 8 GB), solo por lotes) | 0,00 USD | local (los datos no salen del servidor) |
| LLM local (qwen2.5:7b-instruct-q4_K_M) + reglas (prompt v1, política min_critico, NER) | 150 | 51,3 % [42,7–59,3] | 0,497 [0,365–0,619] | 51,7 % [39,0–64,0] | 44,7 % [36,7–53,3] | 4,0 % | 45150 / 55070 ms (CPU AMD Ryzen (12 hilos, Docker 8 GB), solo por lotes) | 0,00 USD | local (los datos no salen del servidor) |
| Reglas (Christus Sinergia / Res. 5596) | 150 | 43,3 % [35,3–51,3] | 0,255 [0,134–0,373] | 30,0 % [18,3–41,5] | 54,0 % [46,0–62,0] | 2,7 % | 3 / 6 ms (AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD) | 0,00 USD | local (los datos no salen del servidor) |
| Reglas (Christus Sinergia / Res. 5596) | 70 | 41,4 % | 0,130 [-0,005–0,303] | 21,4 % [6,7–37,9] | 54,3 % | 4,3 % | 2 / 4 ms | 0,00 USD | local (los datos no salen del servidor) |
| Reglas (Christus Sinergia / Res. 5596) | 70 | 47,1 % | 0,331 [0,147–0,532] | 39,3 % [20,7–57,7] | 48,6 % | 4,3 % | 5 / 6 ms | 0,00 USD | local (los datos no salen del servidor) |
| Reglas (Christus Sinergia / Res. 5596) | 70 | 47,1 % | 0,331 [0,147–0,532] | 39,3 % [20,7–57,7] | 48,6 % | 4,3 % | 3 / 4 ms | 0,00 USD | local (los datos no salen del servidor) |
| Reglas (Christus Sinergia / Res. 5596) | 70 | 38,6 % | 0,107 [-0,033–0,288] | 21,4 % [6,7–37,9] | 54,3 % | 7,1 % | 2 / 3 ms | 0,00 USD | local (los datos no salen del servidor) |

Diferencias pareadas frente a «Reglas (Christus Sinergia / Res. 5596)» (motor − referencia, IC95):

| Motor | n | Exactitud (pp) | Kappa | Sensibilidad I–II (pp) | Infratriaje (pp) |
| :--- | ---: | :--- | :--- | :--- | :--- |
| LLM local (gemma4:e4b-it-qat) + reglas (prompt v1, NER) | 150 | 22,0 [16,0–28,7] | 0,511 [0,395–0,630] | 45,0 [32,4–58,2] | -24,0 [-30,7–-17,3] |
| LLM local (gemma4:e4b-it-qat) + reglas (prompt v1, política min_critico, NER) | 150 | 22,0 [16,0–28,7] | 0,511 [0,395–0,630] | 45,0 [32,4–58,2] | -24,0 [-30,7–-17,3] |
| LLM local (qwen2.5:7b-instruct-q4_K_M) + reglas (prompt v1, NER) | 150 | 6,7 [2,0–11,4] | 0,232 [0,125–0,344] | 20,0 [8,4–31,5] | -7,3 [-12,6–-2,0] |
| LLM local (qwen2.5:7b-instruct-q4_K_M) + reglas (prompt v1, política min_critico, NER) | 150 | 8,0 [4,0–12,7] | 0,242 [0,137–0,355] | 21,7 [11,7–32,7] | -9,3 [-14,0–-5,3] |
| Reglas (Christus Sinergia / Res. 5596) | 70 | -5,7 [-11,4–-1,4] | -0,201 [-0,367–-0,051] | -17,9 [-33,4–-4,3] | 5,7 [1,4–11,4] |
| Reglas (Christus Sinergia / Res. 5596) | 70 | 0,0 [0,0–0,0] | 0,000 [0,000–0,000] | 0,0 [0,0–0,0] | 0,0 [0,0–0,0] |
| Reglas (Christus Sinergia / Res. 5596) | 70 | 0,0 [0,0–0,0] | 0,000 [0,000–0,000] | 0,0 [0,0–0,0] | 0,0 [0,0–0,0] |
| Reglas (Christus Sinergia / Res. 5596) | 70 | -8,5 [-15,7–-2,8] | -0,224 [-0,401–-0,072] | -17,9 [-33,4–-4,3] | 5,7 [1,4–11,4] |

Infratriaje crítico (referencia I–II clasificada como III–V), por motor:

- LLM local (gemma4:e4b-it-qat) + reglas (prompt v1, NER): 15 casos: N061 (coloquial; ref. 1, pred. 5), N076 (negacion; ref. 1, pred. 5), B026 (tipico; ref. 2, pred. 5), N087 (coloquial; ref. 2, pred. 5), N101 (negacion; ref. 2, pred. 5), N107 (signos_vitales; ref. 2, pred. 5), B006 (coloquial; ref. 1, pred. 3), N017 (coloquial; ref. 2, pred. 4), N071 (tipico; ref. 1, pred. 3), N093 (coloquial; ref. 2, pred. 4), B024 (coloquial; ref. 2, pred. 3), N085 (coloquial; ref. 2, pred. 3), N095 (tipico; ref. 2, pred. 3), N100 (negacion; ref. 2, pred. 3), N102 (negacion; ref. 2, pred. 3)
- LLM local (gemma4:e4b-it-qat) + reglas (prompt v1, política min_critico, NER): 15 casos: N061 (coloquial; ref. 1, pred. 5), N076 (negacion; ref. 1, pred. 5), B026 (tipico; ref. 2, pred. 5), N087 (coloquial; ref. 2, pred. 5), N101 (negacion; ref. 2, pred. 5), N107 (signos_vitales; ref. 2, pred. 5), B006 (coloquial; ref. 1, pred. 3), N017 (coloquial; ref. 2, pred. 4), N071 (tipico; ref. 1, pred. 3), N093 (coloquial; ref. 2, pred. 4), B024 (coloquial; ref. 2, pred. 3), N085 (coloquial; ref. 2, pred. 3), N095 (tipico; ref. 2, pred. 3), N100 (negacion; ref. 2, pred. 3), N102 (negacion; ref. 2, pred. 3)
- LLM local (qwen2.5:7b-instruct-q4_K_M) + reglas (prompt v1, NER): 30 casos: B005 (coloquial; ref. 1, pred. 5), B006 (coloquial; ref. 1, pred. 5), N002 (coloquial; ref. 1, pred. 5), N057 (coloquial; ref. 1, pred. 5), N059 (coloquial; ref. 1, pred. 5), N061 (coloquial; ref. 1, pred. 5), N065 (coloquial; ref. 1, pred. 5), N072 (tipico; ref. 1, pred. 5), N076 (negacion; ref. 1, pred. 5), N077 (negacion; ref. 1, pred. 5), B020 (coloquial; ref. 2, pred. 5), B026 (tipico; ref. 2, pred. 5), N087 (coloquial; ref. 2, pred. 5), N088 (coloquial; ref. 2, pred. 5), N101 (negacion; ref. 2, pred. 5) y 15 más
- LLM local (qwen2.5:7b-instruct-q4_K_M) + reglas (prompt v1, política min_critico, NER): 29 casos: B005 (coloquial; ref. 1, pred. 5), B006 (coloquial; ref. 1, pred. 5), N002 (coloquial; ref. 1, pred. 5), N057 (coloquial; ref. 1, pred. 5), N059 (coloquial; ref. 1, pred. 5), N061 (coloquial; ref. 1, pred. 5), N065 (coloquial; ref. 1, pred. 5), N072 (tipico; ref. 1, pred. 5), N076 (negacion; ref. 1, pred. 5), N077 (negacion; ref. 1, pred. 5), B020 (coloquial; ref. 2, pred. 5), B026 (tipico; ref. 2, pred. 5), N087 (coloquial; ref. 2, pred. 5), N088 (coloquial; ref. 2, pred. 5), N101 (negacion; ref. 2, pred. 5) y 14 más
- Reglas (Christus Sinergia / Res. 5596): 42 casos: B004 (coloquial; ref. 1, pred. 5), B005 (coloquial; ref. 1, pred. 5), B006 (coloquial; ref. 1, pred. 5), B007 (coloquial; ref. 1, pred. 5), N002 (coloquial; ref. 1, pred. 5), N007 (coloquial; ref. 1, pred. 5), N011 (negacion; ref. 1, pred. 5), N057 (coloquial; ref. 1, pred. 5), N059 (coloquial; ref. 1, pred. 5), N060 (coloquial; ref. 1, pred. 5), N061 (coloquial; ref. 1, pred. 5), N065 (coloquial; ref. 1, pred. 5), N067 (coloquial; ref. 1, pred. 5), N068 (tipico; ref. 1, pred. 5), N070 (tipico; ref. 1, pred. 5) y 27 más
- Reglas (Christus Sinergia / Res. 5596): 22 casos: B004 (coloquial; ref. 1, pred. 5), B005 (coloquial; ref. 1, pred. 5), B006 (coloquial; ref. 1, pred. 5), B007 (coloquial; ref. 1, pred. 5), B009 (signos_vitales; ref. 1, pred. 5), B017 (signos_vitales; ref. 2, pred. 5), B020 (coloquial; ref. 2, pred. 5), B023 (coloquial; ref. 2, pred. 5), B024 (coloquial; ref. 2, pred. 5), B026 (tipico; ref. 2, pred. 5), N001 (signos_vitales; ref. 1, pred. 5), N002 (coloquial; ref. 1, pred. 5), N004 (signos_vitales; ref. 1, pred. 5), N007 (coloquial; ref. 1, pred. 5), N009 (signos_vitales; ref. 1, pred. 5) y 7 más
- Reglas (Christus Sinergia / Res. 5596): 17 casos: B004 (coloquial; ref. 1, pred. 5), B005 (coloquial; ref. 1, pred. 5), B006 (coloquial; ref. 1, pred. 5), B007 (coloquial; ref. 1, pred. 5), B020 (coloquial; ref. 2, pred. 5), B023 (coloquial; ref. 2, pred. 5), B024 (coloquial; ref. 2, pred. 5), B026 (tipico; ref. 2, pred. 5), N002 (coloquial; ref. 1, pred. 5), N007 (coloquial; ref. 1, pred. 5), N011 (negacion; ref. 1, pred. 5), N013 (coloquial; ref. 2, pred. 5), N014 (signos_vitales; ref. 2, pred. 4), N015 (coloquial; ref. 2, pred. 5), N017 (coloquial; ref. 2, pred. 4) y 2 más
- Reglas (Christus Sinergia / Res. 5596): 17 casos: B004 (coloquial; ref. 1, pred. 5), B005 (coloquial; ref. 1, pred. 5), B006 (coloquial; ref. 1, pred. 5), B007 (coloquial; ref. 1, pred. 5), B020 (coloquial; ref. 2, pred. 5), B023 (coloquial; ref. 2, pred. 5), B024 (coloquial; ref. 2, pred. 5), B026 (tipico; ref. 2, pred. 5), N002 (coloquial; ref. 1, pred. 5), N007 (coloquial; ref. 1, pred. 5), N011 (negacion; ref. 1, pred. 5), N013 (coloquial; ref. 2, pred. 5), N014 (signos_vitales; ref. 2, pred. 4), N015 (coloquial; ref. 2, pred. 5), N017 (coloquial; ref. 2, pred. 4) y 2 más
- Reglas (Christus Sinergia / Res. 5596): 22 casos: B004 (coloquial; ref. 1, pred. 5), B005 (coloquial; ref. 1, pred. 5), B006 (coloquial; ref. 1, pred. 5), B007 (coloquial; ref. 1, pred. 5), B009 (signos_vitales; ref. 1, pred. 5), B017 (signos_vitales; ref. 2, pred. 5), B020 (coloquial; ref. 2, pred. 5), B023 (coloquial; ref. 2, pred. 5), B024 (coloquial; ref. 2, pred. 5), B026 (tipico; ref. 2, pred. 5), N001 (signos_vitales; ref. 1, pred. 5), N002 (coloquial; ref. 1, pred. 5), N004 (signos_vitales; ref. 1, pred. 5), N007 (coloquial; ref. 1, pred. 5), N009 (signos_vitales; ref. 1, pred. 5) y 7 más
<!-- comparativa:dev:fin -->

### Evaluación final (*test*)

<!-- comparativa:test:inicio -->
Pendiente de la evaluación final.
<!-- comparativa:test:fin -->

## 9. Texto para la tesis

### 9.1 Cambios frente al anteproyecto

**Resolución 5596 / Christus Sinergia en lugar de ESI.** El anteproyecto mencionaba el Emergency Severity Index (ESI) como referencia de clasificación. El sistema implementa la Resolución 5596 de 2015 del Ministerio de Salud y Protección Social, en la versión institucional de Christus Sinergia Salud, por tres razones:
- es la norma de obligatorio cumplimiento para los servicios de urgencias en Colombia;
- es el protocolo que usa la institución de referencia;
- conserva la misma escala ordinal de cinco niveles, de modo que las métricas previstas (exactitud, Kappa ponderado, infratriaje) se aplican sin cambios.

Las diferencias con ESI (tiempos de atención y criterios de recursos) se documentan en el capítulo del protocolo.

**Un LLM guiado por reglas en lugar de un modelo de decisión entrenado.** El anteproyecto preveía entrenar un modelo de clasificación del nivel de triaje. Para entrenarlo hacen falta miles de consultas reales etiquetadas por expertos, y el proyecto no tiene acceso a historias clínicas reales ni al volumen necesario. Un clasificador entrenado con 250 casos sintéticos sobreajustaría y no sería defendible.

En su lugar se diseñó un motor híbrido:
- **un motor de reglas determinista** que codifica los criterios del protocolo y los umbrales de signos vitales y es explicable y auditable;
- **un LLM** que recibe esas reglas como pauta, junto con los criterios recuperados por RAG, y aporta la comprensión del lenguaje coloquial y de las paráfrasis que un motor léxico no reconoce.

La salida del LLM está restringida a un esquema validado. La evaluación compara el motor híbrido con las reglas solas y con el LLM sin pauta (ablación), lo que cuantifica lo que aporta cada componente.

**Las reglas como respaldo de seguridad.** El motor de reglas cumple dos funciones de seguridad:
- **Continuidad asistencial.** Si el LLM no responde (cuota, red, error de esquema), clasifica el motor de reglas y el clínico nunca queda sin clasificación.
- **Red de seguridad frente al infratriaje**, si se adopta la política `min_critico`. Cuando las reglas detectan un criterio de nivel I–II, el nivel final no puede ser menos urgente.

Se eligió esta política porque el infratriaje de casos críticos es el error con mayor impacto clínico. La elección se tomó con los datos de *dev* y se congeló antes de *test*.

### 9.2 Privacidad

- Antes de enviar texto a un LLM externo, el sistema reemplaza el nombre, el documento y el teléfono por marcadores (Ley 1581 de 2012). Los valores se reinyectan en el servidor.
- La evaluación con Gemini se hizo en el plan de pago, en el que el proveedor no usa el contenido para mejorar sus productos.
- El motor local ofrece una alternativa en la que ningún dato sale del servidor, al costo de mayor latencia en hardware sin GPU. La tabla comparativa reporta la privacidad de cada motor junto a su exactitud y su costo (pregunta de investigación 3).

### 9.3 Amenazas a la validez

- **Corpus sintético.** Los 250 casos los redactó el equipo con asistencia de IA a partir de los criterios del protocolo. No son consultas reales y el habla transcrita real puede diferir.
- **Etiquetas del equipo.** El nivel de referencia es del equipo. La validación ciega la hizo un único clínico sobre 50 casos. No se puede medir el acuerdo entre varios clínicos, y el Kappa clínico–equipo es una cota aproximada del techo humano.
- **Tamaño de muestra.** Con n = 100 en *test*, los IC95 son anchos (±10 puntos en exactitud). Las diferencias entre motores se reportan con IC pareados y no se afirman cuando el intervalo incluye el cero.
- **Sesgo de autoría.** El catálogo y las reglas se ajustaron mirando *dev*, y el lote 1 está más cerca del catálogo que el lote 2. Por eso se reporta el desglose por lote.
- **No determinismo del LLM.** Con temperatura 0,1 la salida puede variar entre corridas. Se reporta la repetibilidad (Kappa entre dos corridas sobre 30 casos) y se registra la versión exacta del modelo.
- **Sesgo demográfico.** La mayoría de los casos no indican el sexo ni la edad. El desglose es descriptivo y no permite conclusiones sobre equidad.
