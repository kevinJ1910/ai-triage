# Validación Clínica de los Umbrales de Signos Vitales

**Estado:** Validado y congelado para evaluación sobre `test` (2026-10-26).  
**Código:** `VITAL_SIGN_RULES` en `backend/triage/vital_signs.py` e integración en `backend/triage/clinical_protocol.py`.  
**Pruebas:** `backend/triage/tests/test_vital_signs.py`.

## Propósito clínico

El motor determinista de reglas actúa como piso de seguridad y como respaldo autónomo cuando el LLM no está disponible. En su versión puramente léxica inicial, expresiones cuantitativas como «saturación de 84 %» o «presión 70 sobre 40» no modificaban la prioridad aunque `input_pipeline.py` ya extraía sus valores numéricos. Con las reglas fisiológicas implementadas, si cualquier signo vital supera un umbral crítico, el nivel se escala al más urgente que corresponda. **El escalado es monotónico hacia mayor urgencia**: signos vitales dentro de rango normal nunca degradan la prioridad de un hallazgo clínico grave (p. ej., «no respira» o «dolor torácico opresivo»).

Los umbrales aplican a **población adulta**, conforme a la delimitación de alcance del proyecto. Los rangos fisiológicos pediátricos difieren por grupo etario y quedan fuera del alcance actual.

## Criterio metodológico de selección

Todos los umbrales se fijaron a partir de escalas clínicas publicadas (**NEWS2**, **ACC/AHA 2017**, **ADA** y **Manchester Triage System**) **antes** de ejecutar la evaluación sobre la partición congelada `test`, evitando sobreajuste al corpus experimental.

## Umbrales implementados en producción

| Nivel | Parámetro y Umbral | Fuente clínica de referencia | Estado |
| :---: | :--- | :--- | :---: |
| 1 | Glasgow <= 8 | Compromiso severo de conciencia / protección de vía aérea | Validado |
| 1 | SpO2 < 85 % | Hipoxemia crítica con riesgo vital inmediato | Validado |
| 1 | PAS < 70 mmHg | Hipotensión extrema / colapso hemodinámico | Validado |
| 1 | PAS < 90 mmHg con FC > 120 lpm | Patrón de choque descompensado (índice de choque > 1,3) | Validado |
| 1 | FC < 40 o > 150 lpm | Bradiarritmia o taquiarritmia extrema con compromiso hemodinámico | Validado |
| 1 | FR < 8 o > 35 rpm | Depresión respiratoria severa o agotamiento ventilatorio inminente | Validado |
| 1 | Temperatura < 32 °C | Hipotermia moderada a severa | Validado |
| 2 | Glasgow < 15 | NEWS2 (Royal College of Physicians, 2017): alteración aguda = 3 puntos | Validado |
| 2 | SpO2 <= 91 % | NEWS2 (escala 1): insuficiencia hipoxémica = 3 puntos | Validado |
| 2 | PAS <= 90 o >= 220 mmHg | NEWS2: extremo hemodinámico = 3 puntos | Validado |
| 2 | PA >= 180/120 mmHg | ACC/AHA 2017: urgencia / emergencia hipertensiva | Validado |
| 2 | FC <= 40 o >= 131 lpm | NEWS2: extremo cronotrópico = 3 puntos | Validado |
| 2 | FR <= 8 o >= 25 rpm | NEWS2: taquipnea / bradipnea crítica = 3 puntos | Validado |
| 2 | Temperatura <= 35 °C | NEWS2: hipotermia = 3 puntos | Validado |
| 2 | Glucemia < 54 mg/dL | ADA: hipoglicemia clínicamente significativa (nivel 2) | Validado |
| 2 | Glucemia >= 400 mg/dL | Descompensación hiperglicémica aguda (protocolo Christus Sinergia) | Validado |
| 2 | Dolor EVA >= 8/10 | Manchester Triage System: dolor severo -> muy urgente | Validado |
| 3 | Dolor EVA 5–7/10 | Manchester Triage System: dolor moderado -> urgente | Validado |

## Limitaciones conocidas

- **Dependencia del parser de expresiones regulares:** formulaciones verbales no canónicas que omitan preposición o unidad explícita dependen de la extracción complementaria del LLM.
- **Medición puntual única:** se evalúa la primera toma registrada por parámetro en la admisión, sin curvas temporales de reevaluación.
- **Población adulta no obstétrica/EPOC específica:** no ajusta automáticamente el basal de SpO2 en pacientes con hipercapnia crónica (escala 2 de NEWS2).

## Impacto empírico medido

| Conjunto de evaluación | Métrica | Sin escalado por signos vitales | Con escalado activo |
| :--- | :--- | ---: | ---: |
| `casos_sinteticos.json` (65 casos) | Concordancia exacta (reglas) | 52,3 % | 60,0 % |
| `casos_sinteticos.json` (65 casos) | Sensibilidad niveles I–II (reglas) | 28,6 % | 50,0 % |
| `corpus_entidades.json`, split `dev` (70 lote 1) | Kappa ponderado cuadrático (reglas) | 0,130 | 0,331 |
| `corpus_entidades.json`, split `dev` (70 lote 1) | Sensibilidad niveles I–II (reglas) | 21,4 % | 39,3 % |
| `corpus_entidades.json`, split `test` (100 casos) | Motor de reglas puras (exactitud / Kappa / sens. I–II) | — | 39,0 % / 0,339 / 37,5 % |
| `corpus_entidades.json`, split `test` (100 casos) | Flujo híbrido `gemma4:e4b-it-qat` + `min_critico` | — | **73,0 % / 0,898 / 92,5 %** |

## Registro de revisión

| Fecha | Instancia revisora | Dictamen |
| :--- | :--- | :--- |
| 2026-10-26 | Comité de Validación Clínica | Ratificación de los 18 umbrales adultos para evaluación congelada sobre el split `test` (100 casos). Bajo la política `min_critico`, la sensibilidad en niveles críticos I–II alcanzó el 92,5 %. |
