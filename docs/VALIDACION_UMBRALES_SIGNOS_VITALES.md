# Validación clínica de los umbrales de signos vitales

**Estado:** propuesta pendiente de revisión por el equipo clínico.
**Código:** `VITAL_SIGN_RULES` en `backend/triage/clinical_protocol.py`.
**Pruebas:** `backend/triage/tests/test_vital_signs.py`.

## Para qué sirve

El motor de reglas, que es el respaldo cuando el LLM no responde, clasificaba solo por palabras. «Saturación de 84 %» o «presión 70 sobre 40» no subían el nivel aunque `input_pipeline` ya extraía esos valores. Ahora, si un signo vital cumple un criterio, el nivel sube al más urgente que corresponda. **El escalado nunca baja un nivel**: unos signos vitales normales no restan urgencia a un hallazgo como «no respira».

Las reglas aplican a **adultos**, la población del proyecto según el anteproyecto (§5.2). Los umbrales pediátricos son distintos y no están implementados.

## Cómo se eligieron

Los umbrales se fijaron **desde referencias publicadas y antes de medir**, sin ajustarlos al corpus de evaluación. Un umbral elegido mirando los casos de prueba no sería defendible. Si la revisión clínica cambia alguno, el cambio se registra en este documento, con la fecha y la razón, antes de la evaluación final sobre el split `test`.

## Criterios propuestos

| Nivel | Criterio | Referencia | Revisión clínica |
| :---: | :--- | :--- | :--- |
| 1 | Glasgow ≤ 8 | Umbral clásico de compromiso grave de la conciencia / protección de vía aérea | ☐ De acuerdo ☐ Ajustar: ___ |
| 1 | SpO2 < 85 % | Criterio del equipo: hipoxemia grave | ☐ De acuerdo ☐ Ajustar: ___ |
| 1 | PAS < 70 mmHg | Criterio del equipo: hipotensión grave | ☐ De acuerdo ☐ Ajustar: ___ |
| 1 | PAS < 90 mmHg con FC > 120 lpm | Patrón de choque (índice de choque elevado) | ☐ De acuerdo ☐ Ajustar: ___ |
| 1 | FC < 40 o > 150 lpm | Criterio del equipo: bradi/taquiarritmia con riesgo vital | ☐ De acuerdo ☐ Ajustar: ___ |
| 1 | FR < 8 o > 35 rpm | Criterio del equipo: falla respiratoria inminente | ☐ De acuerdo ☐ Ajustar: ___ |
| 1 | Temperatura < 32 °C | Hipotermia moderada a grave | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | Glasgow < 15 | NEWS2: alteración de la conciencia = 3 puntos | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | SpO2 ≤ 91 % | NEWS2 (escala 1): 3 puntos | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | PAS ≤ 90 o ≥ 220 mmHg | NEWS2: 3 puntos | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | PA ≥ 180/120 mmHg | ACC/AHA 2017: crisis hipertensiva | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | FC ≤ 40 o ≥ 131 lpm | NEWS2: 3 puntos | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | FR ≤ 8 o ≥ 25 rpm | NEWS2: 3 puntos | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | Temperatura ≤ 35 °C | NEWS2: 3 puntos | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | Glucemia < 54 mg/dL | ADA: hipoglicemia nivel 2 | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | Glucemia ≥ 400 mg/dL | Criterio ya presente en el protocolo («glucosa > 400») | ☐ De acuerdo ☐ Ajustar: ___ |
| 2 | Dolor EVA ≥ 8/10 | Manchester: dolor intenso → muy urgente | ☐ De acuerdo ☐ Ajustar: ___ |
| 3 | Dolor EVA 5–7/10 | Manchester: dolor moderado → urgente | ☐ De acuerdo ☐ Ajustar: ___ |

En NEWS2 (Royal College of Physicians, 2017), un único parámetro con 3 puntos exige una respuesta clínica urgente. Por eso esos criterios se asignan a nivel 2. Los criterios de nivel 1 marcados como «criterio del equipo» no salen de una escala publicada: son los que más necesitan la revisión clínica.

## Limitaciones conocidas

- **Extracción por regex.** Si `input_pipeline` no reconoce cómo se dijo el valor, no hay escalado. Por ejemplo, «la tensión está en 80 sobre 50» no se reconoce, mientras que «tensión de 80 sobre 50» sí. Esos casos dependen del LLM.
- **Un solo valor por tipo.** Se toma la primera medición de cada signo; no hay tendencia ni reevaluación.
- **Sin ajuste por contexto.** No se tienen en cuenta la edad, el embarazo, las enfermedades crónicas (p. ej., la SpO2 basal en la EPOC) ni el uso de oxígeno.

## Efecto medido (motor de reglas, sin LLM)

| Conjunto | Métrica | Sin escalado | Con escalado |
| :--- | :--- | ---: | ---: |
| `corpus_entidades.json`, split `dev` (70) | Kappa ponderado | 0,130 | 0,331 |
| | Sensibilidad niveles 1–2 | 21,4 % | 39,3 % |
| `casos_sinteticos.json` (65) | Concordancia exacta | 52,3 % | 60,0 % |
| | Sensibilidad niveles 1–2 | 28,6 % | 50,0 % |
| | Sobretriaje | 0,0 % | 1,5 % |

El split `test` no se ha usado. La cifra que se reporta en la tesis es la de `test` en la evaluación final.

## Registro de revisión

| Fecha | Revisor | Cambios |
| :--- | :--- | :--- |
| | | |
