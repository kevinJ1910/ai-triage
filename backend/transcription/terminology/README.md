# Catálogos terminológicos de la normalización

**Estado:** borrador pendiente de revisión clínica (`estado: "borrador"` en cada archivo).
**Código:** `transcription/terminology/__init__.py` (búsqueda y validación) y `transcription/normalizer.py` (pipeline).
**Pruebas:** `transcription/tests/test_terminology.py` y `triage/tests/test_normalization_pipeline.py`.

## Para qué sirve

Antes, la normalización era una llamada a Gemini sin validar más un respaldo de 12 términos con códigos SNOMED CT que nadie había verificado. Además, el triaje no la usaba, y había otros dos mapas de sinónimos sueltos: uno en el RAG y otro en la caché.

Ahora hay una sola fuente terminológica, versionada en este directorio, que usan cuatro consumidores:

| Consumidor | Uso |
| :--- | :--- |
| `/api/transcribe/normalize/` (`NormalizationMonitor`) | Pipeline completo, con el LLM para los términos que el catálogo no cubre. |
| `analyze_triage_transcript` | Capas deterministas como paso previo del NER: se pasan a Gemini como pistas y alimentan las entidades del motor de reglas. El resultado incluye `normalized_terms`. |
| `ClinicalKnowledgeRAG` | Expande la consulta con el término clínico de cada coloquialismo o sigla. |
| `ClinicalQueryCache` | Unifica sinónimos en la huella («dolor de cabeza» y «cefalea» dan la misma clave). |

## Capas

1. **Correcciones ASR** (`correcciones_asr.json`): errores fonéticos plausibles de Whisper («posartan» → losartán). Cada corrección apunta a un término que ya existe en los otros catálogos.
2. **Abreviaturas** (`abreviaturas.json`): siglas clínicas (HTA, DM2, EPOC, IAM, ACV…). Se excluyen las que chocan con palabras del español o entre sí: IRA, FA, LES, AR, ASA y TA.
3. **Diccionario** (`coloquialismos.json`): unos 300 conceptos y más de 1.000 formas de superficie del español de urgencias en Colombia, con categoría y código.
4. **LLM residual**: Gemini Flash-Lite (`NORMALIZER_LLM_MODEL`, por defecto `gemini-3.5-flash-lite`) recibe el relato seudonimizado y la lista de lo ya resuelto, y solo propone términos nuevos. **No se usa dentro del triaje**, para no gastar una segunda llamada por consulta con la cuota gratuita.
5. **Validación**: cada código se comprueba contra `cie10.json`. Un código mal formado se marca como `valid: false` y no se corrige. Un término del LLM que no aparece literalmente en el relato se descarta.

La búsqueda elige la coincidencia más larga, sin solapes y respetando los límites de palabra, sobre el texto sin tildes ni mayúsculas. Las posiciones se refieren al texto original, de modo que la negación (`triage/negation.py`) se evalúa sobre el span exacto. Un fármaco o alérgeno precedido de «alérgico a…» se marca como alergia, y un alérgeno fuera de ese contexto («polvo») se ignora.

## Salida de cada término

```json
{"raw_term": "posartan", "medical_term": "losartán", "code": "C09CA01", "code_system": "ATC",
 "category": "Medicamento", "source": "correccion_asr", "valid": true, "negated": false, "allergy": false}
```

`valid` toma tres valores:

- `true`: el código está en el catálogo local.
- `false`: el código está mal formado, o falta en un catálogo marcado como completo.
- `null`: no hay código, o el código está bien formado pero no se puede verificar porque el catálogo es parcial.

## Sistemas de codificación

- **CIE-10.** `cie10.json` es un **subconjunto** (`"completo": false`) con los 188 códigos que usan los catálogos y su título de la CIE-10 de la OMS/OPS. Para validar cualquier código que proponga el LLM hay que importar la tabla completa de Minsalud/SISPRO:

  ```bash
  python manage.py import_cie10 TablaReferencia_CIE10.csv --code-column Codigo --name-column Nombre
  ```

  El comando acepta tanto el formato con punto (`R06.0`) como el colombiano con relleno (`R060`, `R51X`). Después de importar, el archivo queda con `"completo": true`.
- **ATC** (OMS), solo para medicamentos. La validación es de formato, y de pertenencia a los códigos del catálogo.
- **SNOMED CT** no se usa, porque su uso requiere licencia de SNOMED International. Hasta confirmar con el director si la universidad o el hospital tienen una, se declara como limitación (anteproyecto, objetivo 4).

Un concepto sin código verificado lleva `null`. **Nunca se pone un código de memoria si no hay certeza.**

## Cómo ampliar los catálogos

1. Añade la variante al concepto existente o crea un concepto nuevo, con su `categoria` y su `cie10` o `atc`.
2. Si el código es nuevo, regenera `cie10.json` o importa la tabla oficial.
3. Ejecuta `pytest backend/transcription/tests/test_terminology.py`. `validate_catalogs()` falla si una forma pertenece a dos conceptos, si hay una categoría inválida o si un código no está en el catálogo.
4. **No amplíes el catálogo mirando los casos del split `test`** de `triage/benchmark/corpus_entidades.json`: invalidaría la evaluación final.

## Efecto medido sobre `dev` (motor de reglas)

| Métrica | Antes | Después |
| :--- | ---: | ---: |
| Micro-F1 de entidades (relajado) | 0,241 | 0,876 |
| RAG: algún criterio del nivel de referencia entre los 4 recuperados (70 casos) | 41 | 46 |
| RAG: el primer criterio es del nivel de referencia | 26 | 35 |
| RAG en `casos_sinteticos.json` (65 casos): algún criterio del nivel | 45 | 53 |

**Estas cifras de `dev` están infladas.** El catálogo se escribió después de ver las entidades anotadas de `dev`, y el corpus es un borrador anotado con asistencia de IA. La cifra que se reporta en la tesis es la de `test`, en la evaluación final (paso 4.1).
