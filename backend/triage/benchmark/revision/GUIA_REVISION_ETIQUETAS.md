# Guía de revisión de las etiquetas del corpus

Todos los casos de `corpus_entidades.json` están en `estado: "borrador"`. Los redactó el equipo con asistencia de IA y nadie los ha revisado todavía. Antes de evaluar el split *test*, alguien del equipo tiene que revisar sus 100 casos: el nivel de triaje, el criterio y las entidades. La evaluación final se reporta frente a estas etiquetas, así que tienen que ser defendibles.

La planilla es `revision_test.csv`. Se abre con Excel o Google Sheets; en Google Sheets, importa con separador «punto y coma».

## Antes de empezar: reglas de ciego

1. **No mires ningún resultado del sistema sobre *test*.** No abras `../resultados/`, el panel «Resultados de Evaluación» ni la tabla de `docs/EVALUACION_TRIAJE.md`. Por ahora no existe ninguna corrida sobre *test*, y así debe seguir hasta terminar la revisión. La planilla no trae ninguna predicción.
2. **Decide con el relato y el protocolo, no con lo que crees que haría el sistema.** El objetivo es la etiqueta correcta, no una etiqueta «fácil» ni «difícil».
3. **Quién revisa.** Lo ideal es Kevin o Junior. **El clínico que hará la validación ciega no debe revisar esta planilla.** Esa validación usa 50 casos de este mismo *test*: si el clínico ve antes las etiquetas del equipo, su juicio deja de ser independiente y el Kappa clínico–equipo pierde valor.
4. Si dos personas revisan, repartan los casos sin solaparse, o revisen por separado y discutan los desacuerdos. En la columna `revisado_por` va quien firma la decisión final.

## Cómo llenar cada fila

| Columna | Qué poner |
| :--- | :--- |
| `nivel_revisado` | Vacío si estás de acuerdo con `nivel_actual`. Un número del 1 al 5 si debe cambiar. |
| `criterio_revisado` | Vacío si el criterio actual sirve. **Obligatorio si cambias el nivel:** el criterio del protocolo que justifica el nuevo nivel (ver la tabla de abajo). |
| `entidades_ok` | `si` si las entidades de la columna `entidades` están bien. `no` si alguna sobra, falta o está mal: span, forma normalizada, negación o código CIE-10. |
| `comentario` | Qué hay que corregir en las entidades, o por qué cambiaste el nivel. Breve. |
| `revisado_por` | Tus iniciales. **Las filas sin iniciales no se aplican**, así que se puede revisar en varias sesiones. |

No edites las columnas `id`, `transcript`, `nivel_actual`, `criterio_actual` ni `entidades`. El comando comprueba que el transcript coincida con el corpus.

**Entidades.** En la columna `entidades`, `«texto»` es el span literal del transcript y lo que va después de `→` es la forma normalizada. Entre corchetes va el código CIE-10, si lo hay, y `(NEGADO)` marca un hallazgo negado. Las reglas están en `../README.md` (sección «Guía de anotación») y en `../GUIA_LIMITES.md`. Recuerda que «no respira», «no responde» o «no puede mover el brazo» son hallazgos **presentes**, no negados.

**Códigos CIE-10.** Los que hay se rellenaron automáticamente desde el catálogo. Compruébalos con la tabla oficial, no con el catálogo del proyecto. Si uno está mal, pon `entidades_ok = no` y anótalo en el comentario.

## Niveles del protocolo (Resolución 5596 / Christus Sinergia)

| Nivel | Nombre | Atención | Definición resumida | Criterios de ejemplo |
| :---: | :--- | :--- | :--- | :--- |
| 1 | Reanimación | Inmediata | Riesgo vital que necesita maniobras de reanimación por compromiso ventilatorio, respiratorio, hemodinámico o neurológico. | Ausencia de signos vitales, inconsciencia, dificultad respiratoria severa, hemorragia masiva, trabajo de parto expulsivo, abuso sexual de menos de 72 h |
| 2 | Emergencia | Dentro de los siguientes 30 minutos | Puede evolucionar hacia un deterioro rápido, la muerte o la pérdida de un miembro u órgano. | Alteración aguda de signos vitales, estado convulsivo, dificultad respiratoria moderada, crisis hipertensiva, dolor torácico con signos de alarma, fractura expuesta, sangrado vaginal en embarazada |
| 3 | Urgencia | Hasta 120 minutos | Fisiológicamente estable, pero requiere estudios o tratamiento rápido en urgencias. | Vértigo severo, dificultad respiratoria leve, vómito y diarrea con deshidratación, trauma moderado, reacción alérgica generalizada, valoración médico-legal |
| 4 | Consulta Prioritaria | Direccionamiento a su EPS | No compromete el estado general, pero hay riesgo de complicación si no se atiende. | Tos y congestión, faringitis, vómito y diarrea sin deshidratación, dolor leve a moderado de más de 24 h, trauma leve, ardor al orinar |
| 5 | Consulta Externa | Direccionamiento a su EPS | Problema agudo o crónico sin deterioro ni riesgo evidente. | Dolor de cabeza crónico, tos crónica, estreñimiento, dermatitis, enfermedades crónicas, formulación de medicamentos |

Los umbrales de signos vitales que elevan el nivel están en `docs/VALIDACION_UMBRALES_SIGNOS_VITALES.md`.

## Cómo se aplica la revisión

Desde `backend/`:

```bash
python manage.py apply_corpus_review triage/benchmark/revision/revision_test.csv --dry-run
python manage.py apply_corpus_review triage/benchmark/revision/revision_test.csv
```

- `--dry-run` muestra los cambios sin tocar el corpus: niveles cambiados (`viejo -> nuevo`), criterios y casos que quedan con entidades por corregir.
- Si cambia un nivel, el nivel original se guarda en `nivel_particion`. Así **ningún caso cambia de dev a test ni al revés**: la partición por hash se calcula con ese nivel.
- Con `entidades_ok = si`, el caso pasa a `estado: "revisado"`. Con `no` queda en `borrador`, y sus entidades se corrigen a mano en `corpus_entidades.json`, con spans literales. Después, el caso se marca como `revisado`.
- El comando valida el corpus antes de escribirlo y rechaza la planilla entera si encuentra un error, por ejemplo un nivel fuera de 1–5, un nivel cambiado sin criterio o un transcript que no coincide.
- Revisa el diff con git y haz commit, por ejemplo: `fix(corpus): revisar las etiquetas del split test`.

Cuando los 100 casos de *test* estén en `revisado`, se congela la configuración (prompt, política y modelos) con los resultados de *dev* y se evalúa *test* una sola vez (ver `docs/EVALUACION_TRIAJE.md`).
