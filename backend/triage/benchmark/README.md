# Benchmark de triaje

`casos_sinteticos.json` contiene 65 casos de consulta (entre 10 y 15 por nivel) para medir de forma reproducible el motor de reglas y el pipeline completo con `evaluate_benchmark`.

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
