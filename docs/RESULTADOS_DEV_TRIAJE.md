# Resultados de desarrollo del triaje inteligente (split *dev*)

> **Registro histórico de la fase de desarrollo (*dev*).** Este documento conserva intactas las mediciones intermedias del split *dev* (150 casos, 21-10-2026) empleadas para elegir el modelo, el prompt (`v2`) y la política de combinación (`min_critico`) antes de congelar el sistema. **La evaluación definitiva sobre el split congelado *test* (100 casos en GPU NVIDIA RTX 3070: exactitud 73,0 %, Kappa 0,898, sensibilidad I–II 92,5 %) y la validación clínica ciega independiente (`BlindReview`, 50 casos: exactitud 80,0 %, Kappa 0,911) ya fueron ejecutadas y se documentan en [`EVALUACION_TRIAJE.md`](EVALUACION_TRIAJE.md).**

> **Gemini 2.5 Flash en *dev* ya está completo (150 de 150):** 78,7 % de exactitud [72,0–85,3], Kappa ponderado 0,923 [0,877–0,956] y sensibilidad I–II de 91,7 % [83,9–98,2]. Lo que este documento dice de Gemini (66 casos, «en curso») es el avance intermedio; la tabla completa está en [`EVALUACION_TRIAJE.md`](EVALUACION_TRIAJE.md).

Datos al 21-10-2026. Todas las cifras se pueden regenerar desde `backend/triage/benchmark/resultados/`: los JSON de resumen y los checkpoints `crudos/*.jsonl` con la salida cruda de cada modelo. Los intervalos son IC95 por bootstrap (1.000 remuestreos, semilla 0).

## 1. Qué se comparó

Todos los motores con LLM usan la misma configuración:
- el mismo pipeline (reglas Christus Sinergia / Res. 5596, umbrales de signos vitales y NegEx, RAG léxico y NER RoBERTa `HoraYMedia/ai-triage-ner-roberta@v1`);
- el mismo prompt, `v1` (SHA-256 `06e56653b71e…`), con temperatura 0,1;
- el mismo esquema de salida validado con Pydantic.

Solo cambia el LLM.

| Motor | Modelo exacto | Dónde corre | Razonamiento | Casos |
| :--- | :--- | :--- | :--- | :---: |
| Reglas | Motor determinista | CPU | No aplica | 150 |
| Qwen2.5-7B | `qwen2.5:7b-instruct-q4_K_M` (Ollama 0.12.6) | CPU AMD Ryzen, 12 hilos, Docker con 8 GB | No tiene | 150 |
| Gemma 4 E4B | `gemma4:e4b-it-qat` (Ollama 0.34.4) | La misma CPU | Activado (por defecto) | 150 |
| Gemini 2.5 Flash | `gemini-2.5-flash` (API, plan gratuito) | Nube | Activado (por defecto) | **66 de 150, en curso** |

Gemini avanza a 20 llamadas al día por la cuota gratuita. Sus cifras son **parciales**: los 66 casos evaluados cubren la mayor parte del lote 1, así que no se pueden comparar directamente con los 150 de los demás. En la sección 3 se comparan los cuatro motores sobre esos mismos 32 casos.

## 2. Triaje sobre los 150 casos de *dev*

| Motor | Exactitud | Kappa ponderado | Sensibilidad I–II | Infratriaje | Sobretriaje | Críticos infratriados |
| :--- | :--- | :--- | :--- | :--- | ---: | ---: |
| Reglas | 43,3 % [35,3–51,3] | 0,255 [0,134–0,373] | 30,0 % [18,3–41,5] | 54,0 % [46,0–62,0] | 2,7 % | 42 de 60 |
| Qwen2.5-7B | 50,0 % [41,3–58,0] | 0,487 [0,357–0,609] | 50,0 % [36,8–62,5] | 46,7 % [38,0–54,7] | 3,3 % | 30 de 60 |
| Qwen2.5-7B + `min_critico` | 51,3 % [42,7–59,3] | 0,497 [0,365–0,619] | 51,7 % [39,0–64,0] | 44,7 % [36,7–53,3] | 4,0 % | 29 de 60 |
| **Gemma 4 E4B** | **65,3 % [57,3–72,7]** | **0,766 [0,667–0,846]** | **75,0 % [62,9–85,9]** | **30,0 % [23,3–38,0]** | 4,7 % | 15 de 60 |
| Gemma 4 E4B + `min_critico` | Igual que sin la política | | | | | |

**Diferencias pareadas frente a las reglas** (los mismos 150 casos; motor menos reglas):

| Motor | Exactitud (pp) | Kappa | Sensibilidad I–II (pp) | Infratriaje (pp) |
| :--- | :--- | :--- | :--- | :--- |
| Qwen2.5-7B | +6,7 [2,0–11,4] | +0,232 [0,125–0,344] | +20,0 [8,4–31,5] | −7,3 [−12,6 a −2,0] |
| Qwen2.5-7B + `min_critico` | +8,0 [4,0–12,7] | +0,242 [0,137–0,355] | +21,7 [11,7–32,7] | −9,3 [−14,0 a −5,3] |
| Gemma 4 E4B | **+22,0 [16,0–28,7]** | **+0,511 [0,395–0,630]** | **+45,0 [32,4–58,2]** | **−24,0 [−30,7 a −17,3]** |

Ningún intervalo incluye el cero. Ambos LLM locales mejoran a las reglas en todas las métricas, y Gemma lo hace con un margen grande.

Matrices de confusión (filas: nivel predicho 1–5; columnas: nivel de referencia 1–5):

```
Reglas            Qwen2.5-7B         Gemma 4 E4B
 9  1  0  0  0     12  1  0  0  0     22  3  0  0  0
 2  6  1  0  0      6 11  1  0  0      4 16  2  0  0
 1  0  4  0  0      2  4  6  1  0      2  5 10  1  0
 0  7  9 18  2      0  6 10 18  2      0  2  8 21  1
18 16 16 12 28     10  8 13 11 28      2  4 10  8 29
```

El error dominante de las reglas es enviar a nivel 5 los casos que no reconocen: 62 casos de niveles 1–4 terminan en la fila 5. Es el comportamiento esperado de un motor léxico, que no entiende paráfrasis. Qwen reduce ese error a 42 casos y Gemma a 24.

## 3. Los cuatro motores sobre los mismos 66 casos evaluados con Gemini

| Motor | Exactitud | Kappa | Sensibilidad I–II | Infratriaje |
| :--- | :--- | :--- | :---: | :---: |
| Reglas | 37,9 % [26,5–49,2] | 0,098 [−0,075–0,278] | 21,4 % | 57,6 % |
| Qwen2.5-7B + min_critico | 54,5 % [42,4–66,7] | 0,598 [0,432–0,753] | 60,7 % | 40,9 % |
| Gemma 4 E4B + min_critico | 69,7 % [58,5–80,3] | 0,852 [0,735–0,942] | 85,7 % | 24,2 % |
| Gemini 2.5 Flash | 74,2 % [63,6–84,8] | 0,896 [0,803–0,954] | 92,9 % | 18,2 % |

Al ampliar la muestra evaluada de Gemini a 66 casos, la progresión entre arquitecturas se mantiene sólida y estadísticamente clara (reglas < Qwen < Gemma < Gemini). Gemini 2.5 Flash alcanza un Kappa ponderado de 0,896 (concordancia casi perfecta) y una sensibilidad del 92,9 % en casos críticos (26 de 28 casos nivel I–II detectados correctamente). Por su parte, Gemma 4 E4B local con política min_critico se sitúa muy próximo a Gemini (Kappa 0,852 y sensibilidad del 85,7 %) ejecutándose íntegramente de manera local y privada en el servidor hospitalario.

## 4. Dónde falla cada motor

**Por tipo de caso** (exactitud / sensibilidad I–II):

| Tipo (n) | Reglas | Qwen2.5-7B | Gemma 4 E4B |
| :--- | :--- | :--- | :--- |
| Coloquial (83) | 36,1 % / 10,7 % | 48,2 % / 50,0 % | 65,1 % / 75,0 % |
| Negación (22) | 40,9 % / 25,0 % | 40,9 % / 25,0 % | 54,5 % / 50,0 % |
| Signos vitales (20) | 55,0 % / 73,3 % | 50,0 % / 66,7 % | 70,0 % / 93,3 % |
| Típico (25) | 60,0 % / 22,2 % | 64,0 % / 44,4 % | 72,0 % / 66,7 % |

- Los relatos **coloquiales** son donde más aporta un LLM: la sensibilidad en casos críticos pasa del 10,7 % de las reglas al 75 % de Gemma.
- La **negación** sigue siendo el punto débil de los tres. Qwen no mejora a las reglas en estos casos.

**Por lote** (exactitud / Kappa). El lote 2 se redactó sin ver el catálogo y mide mejor la generalización:

| Lote | Reglas | Qwen2.5-7B | Gemma 4 E4B |
| :--- | :--- | :--- | :--- |
| 1 (70 casos) | 47,1 % / 0,331 | 52,9 % / 0,607 | 70,0 % / 0,862 |
| 2 (80 casos) | 40,0 % / 0,194 | 47,5 % / 0,394 | 61,3 % / 0,688 |

**Casos críticos infratriados** (referencia I–II clasificada como III–V):
- Las reglas fallan 42 de 60.
- Qwen rescata 13 de esos 42 y falla 1 que las reglas acertaban.
- Gemma rescata 27 de los 42 y no falla ninguno que las reglas acertaran.
- 14 casos los fallan los tres motores: 6 coloquiales, 4 de negación, 3 típicos y 1 de signos vitales. Son los candidatos para el análisis de errores cualitativo, que debe hacerse en *dev*.

**Política `min_critico`.** Con esta política, si las reglas detectan un nivel I–II, prevalece el nivel más urgente de los dos. En Qwen mejora 1–2 puntos el infratriaje: rescata los casos críticos que el LLM bajaba. En Gemma no cambia nada, porque Gemma nunca dejó por debajo de I–II un caso que las reglas marcaran como crítico. Como no empeora ninguna métrica en ningún modelo y actúa como red de seguridad, **se recomienda congelar `min_critico`** para test.

## 5. Extracción de entidades

| Motor | Precisión | Sensibilidad | F1 micro | Macro-F1 | Exactitud de negación | CIE-10 | F1 lote 1 | F1 lote 2 |
| :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| Reglas | 0,805 | 0,705 | 0,751 [0,700–0,796] | 0,818 | 1,000 | 0,839 | 0,876 | 0,614 |
| Qwen2.5-7B | 0,836 | 0,948 | 0,888 [0,864–0,912] | 0,870 | 0,839 | 0,839 | 0,876 | 0,901 |
| Gemma 4 E4B | 0,828 | 0,959 | 0,888 [0,863–0,914] | 0,862 | 0,839 | 0,839 | 0,895 | 0,882 |

F1 por tipo:

| Motor | Síntomas | Diagnósticos | Medicamentos | Alergias | Signos vitales | Antecedentes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Reglas | 0,705 | 0,744 | 0,960 | 0,750 | 0,825 | 0,927 |
| Qwen2.5-7B | 0,882 | 0,951 | 0,962 | 0,706 | 0,812 | 0,909 |
| Gemma 4 E4B | 0,902 | 0,899 | 0,926 | 0,750 | 0,765 | 0,930 |

- **El LLM sube mucho la sensibilidad** (de 0,70 a 0,95) sobre todo en síntomas y diagnósticos. Además, cierra la brecha entre lotes: el lote 2 pasa de 0,614 a cerca de 0,90.
- **La negación es el contrapunto.** Con reglas y NegEx ningún hallazgo negado se reporta como presente (1,000). En los híbridos, 9 de 56 negados sí se reportan como presentes (0,839). La fusión deja pasar algunos hallazgos negados que el LLM incluye como síntomas, y hay que revisarla en *dev*.
- El CIE-10 es igual en los tres porque lo aporta la capa del catálogo, no el LLM. La cifra todavía mide **cobertura** del catálogo, no exactitud clínica, mientras los códigos no se revisen a mano.

## 6. Latencia, costo y privacidad

| Motor | Latencia p50 / p95 | Tokens por caso (entrada / salida) | Costo por 1.000 triajes | Los datos salen del servidor |
| :--- | :--- | :--- | :---: | :--- |
| Reglas | 3 / 6 ms | No aplica | 0 | No |
| Qwen2.5-7B (CPU) | 45 / 55 s | 584 / 205 | 0 (hardware propio) | No |
| Gemma 4 E4B (CPU) | 115 / 179 s | 514 / 1.066 (incluye el razonamiento) | 0 (hardware propio) | No |
| Gemini 2.5 Flash | 5,4 / 9,1 s | 493 / 257, más 904 de razonamiento | 3,05 USD | Sí, con el texto seudonimizado |

- La latencia de los modelos locales es la de un **portátil sin GPU, solo para evaluación por lotes**. No es la latencia operativa: en la GPU NVIDIA del equipo de Junior se espera que respondan en segundos, y conviene medirlo antes de la sustentación.
- El razonamiento de Gemma explica que tarde 2,5 veces más que Qwen. También explica, probablemente, buena parte de su ventaja en exactitud. Gemini también razona por defecto: unos 900 tokens de razonamiento por caso, el 70 % de su costo.
- Costo de Gemini: 0,0031 USD por triaje con el plan de pago (0,30 USD por millón de tokens de entrada y 2,50 USD por millón de salida). Un servicio de urgencias con 1.000 triajes al mes gastaría unos 3 USD.

## 7. Observaciones para la tesis

1. **Qwen devolvía la confianza en porcentaje.** Ollama impone la estructura del esquema, pero no sus límites numéricos, y Qwen devolvió `confidence: 95` en vez de `0.95` en 40 de 150 casos. Se normaliza antes de validar (`_coerce_llm_output`) y queda registrado en `output_coerced`. El nivel de triaje nunca se modifica. Gemma no tuvo este problema.
2. **El plan gratuito de Gemini permite 20 peticiones al día por modelo.** La evaluación de *dev* (150 casos) lleva más de una semana con ese límite. El corredor es reanudable y nunca cuenta como resultado del modelo un caso resuelto por reglas.
3. **Versiones de Ollama.** Qwen se evaluó con Ollama 0.12.6 y Gemma con 0.34.4, porque 0.12.6 no soporta Gemma 4. Ambos usan el mismo prompt y el mismo esquema.
4. **Estabilidad en CPU.** En un equipo con 8 GB para Docker, Gemma 4 (unos 6,4 GB) llegó al límite de memoria y Docker Desktop se cayó dos veces. La corrida se reanudó sin perder casos: 5 casos necesitaron reintento o quedaron pendientes y se completaron después. En producción conviene la GPU o al menos 12 GB de memoria.
5. **Reproducibilidad.** Cada corrida guarda la salida cruda del modelo, el id exacto, la versión y el hash del prompt, los tokens, la latencia y el hardware. Las corridas dentro de Docker no registran el commit, porque el contenedor no tiene git: el código corresponde a la rama `feat/triaje-evaluacion-llm` en las fechas indicadas.

## 8. Lo que estos resultados permiten decir (y lo que no)

**Se puede decir:**
- Un LLM guiado por reglas supera al motor de reglas solo en todas las métricas de triaje, con diferencias pareadas significativas. La mejora se concentra en los relatos coloquiales y en los casos críticos.
- Un modelo abierto pequeño (Gemma 4 E4B, unos 4 B de parámetros efectivos) que corre en el propio servidor alcanza un Kappa sustancial (0,77) sin que los datos salgan del hospital. Esto responde a la pregunta de investigación 3: ¿se puede hacer sin la nube?
- La elección del modelo importa mucho: Gemma supera a Qwen en +15 puntos de exactitud y +0,28 de Kappa con el mismo prompt.

**Todavía no se puede decir:**
- Que se cumpla el criterio de más del 80 % de exactitud: en *dev*, ningún motor completo lo alcanza. Gemma llega al 65,3 %, y Gemini, sobre 32 casos fáciles, al 87,5 %.
- Cuál es el mejor motor entre Gemma y Gemini: faltan 118 casos de Gemini.
- Nada sobre test: no se ha evaluado, y así debe seguir hasta congelar.

## 9. Próximos pasos

1. Completar Gemini en *dev* (tarea diaria de 20 llamadas, unos 6 días más, o unos minutos con facturación).
2. Revisar los 100 casos de *test* con la planilla `backend/triage/benchmark/revision/revision_test.csv`, sin ver resultados.
3. Congelar la configuración. La propuesta es: prompt `v1`, política `min_critico` y motores reglas, Qwen2.5-7B, Gemma 4 E4B y Gemini 2.5 Flash.
4. Evaluar *test* una sola vez y generar la tabla con `compare_engines --split test`.
5. Hacer la validación ciega del clínico sobre 50 casos de *test* (`import_blind_review`).

## Limitaciones

- **Corpus.** Es sintético y redactado por el equipo con asistencia de IA. Sigue en estado «borrador» y sus etiquetas son del equipo.
- **Tamaño.** Con n = 150, las diferencias de 5 puntos no son concluyentes, y con n = 32 nada lo es.
- **Dev no es test.** Las decisiones se tomaron mirando *dev*, así que estas cifras pueden ser optimistas frente a *test*.
- **Latencia.** Medida en un portátil sin GPU, con Docker limitado a 8 GB.
