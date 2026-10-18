---
language:
  - es
license: apache-2.0
library_name: transformers
pipeline_tag: token-classification
base_model: PlanTL-GOB-ES/roberta-base-biomedical-clinical-es
tags:
  - ner
  - clinical
  - biomedical
  - spanish
  - triage
  - emergency-medicine
metrics:
  - f1
  - precision
  - recall
---

# AI-Triage NER: RoBERTa clínico para transcripciones de triaje (v1)

Modelo de reconocimiento de entidades (NER) que detecta **síntomas, enfermedades y fármacos** en relatos de consultas de urgencias en español, tal como llegan de un reconocedor de voz. Es un componente del prototipo **AI-Triage**, una plataforma de apoyo al triaje por voz desarrollada como trabajo de grado en la Universidad del Valle (Colombia).

> **Aviso:** es un prototipo de investigación. **No es un dispositivo médico** ni está validado clínicamente, y no debe usarse para tomar decisiones asistenciales. En AI-Triage sus menciones son una entrada más de un pipeline (catálogo terminológico, reglas del protocolo y un LLM) cuyo resultado revisa siempre un profesional.

## Etiquetas

Esquema BIO con tres tipos de entidad:

| Etiqueta | Qué marca | Ejemplos |
| --- | --- | --- |
| `SINTOMA` | Síntomas y signos referidos u observados | «dolor en el pecho», «vomitó», «no puede respirar» |
| `ENFERMEDAD` | Diagnósticos, enfermedades y lesiones | «diabetes», «hipertensión», «fractura de muñeca» |
| `FARMACO` | Medicamentos y alergias a fármacos | «losartán», «metformina», «alérgico a la penicilina» |

Etiquetas del modelo: `O`, `B-SINTOMA`, `I-SINTOMA`, `B-ENFERMEDAD`, `I-ENFERMEDAD`, `B-FARMACO`, `I-FARMACO`.

## Entrenamiento

Parte de [`PlanTL-GOB-ES/roberta-base-biomedical-clinical-es`](https://huggingface.co/PlanTL-GOB-ES/roberta-base-biomedical-clinical-es) y se ajusta en dos etapas:

1. **Etapa 1, corpus clínicos públicos.** 1.000 documentos de casos clínicos (900 de entrenamiento y 100 de validación) que fusionan tres corpus anotados del Barcelona Supercomputing Center: SympTEMIST (`SINTOMA`), DisTEMIST (`ENFERMEDAD`) y DrugTEMIST (`FARMACO`). Cuando dos anotaciones se solapan se conserva una sola. 10 épocas, lr 5e-5, lote 16, 512 tokens con *stride* 128.
2. **Etapa 2, adaptación al habla de urgencias.** 150 relatos de triaje transcritos (split *dev* del corpus propio del proyecto, anotado por el equipo con una guía de límites). 20 épocas, lr 3e-5, lote 8. La configuración se eligió por validación cruzada de 5 particiones entre 10, 20 y 30 épocas.

Semilla 42. Entrenado el 2026-10-17 en una GPU T4 con `transformers` 5.18 y `torch` 2.11.

## Resultados

Métricas por *span*: la **exacta** exige los mismos límites y etiqueta; la **parcial** acepta solapamiento con la misma etiqueta.

**Validación cruzada de 5 particiones sobre los 150 relatos de triaje (etapa 2), media ± desviación:**

| Entidad | F1 exacta | F1 parcial |
| --- | --- | --- |
| SINTOMA | 0,807 ± 0,052 | 0,935 ± 0,014 |
| ENFERMEDAD | 0,585 ± 0,190 | 0,833 ± 0,113 |
| FARMACO | 0,945 ± 0,050 | 0,945 ± 0,050 |
| **Micro** | **0,777 ± 0,055** | **0,917 ± 0,032** |

Como referencia, el modelo de la etapa 1 sin adaptar obtiene 0,482 de F1 micro exacta (0,818 parcial) sobre esos mismos relatos. En la validación de la etapa 1, sobre casos clínicos escritos, la F1 micro exacta es 0,693 (0,828 parcial).

Cómo leer estas cifras:

- La mayoría de los errores restantes son de **límites** de la mención, no de detección. Por eso la métrica parcial es mucho más alta.
- `ENFERMEDAD` es la clase menos estable porque hay pocos ejemplos por partición.
- El split *test* del corpus propio está reservado para la evaluación final de la tesis y **no se usó** para entrenar ni para elegir la configuración.

## Uso

```python
from transformers import pipeline

ner = pipeline(
    "token-classification",
    model="HoraYMedia/ai-triage-ner-roberta",
    revision="v1",
    aggregation_strategy="simple",
)
ner("Refiere dolor en el pecho desde hace una hora, toma losartán y es alérgico a la penicilina.")
```

Algunos detalles de uso:

- **`tokenizer.json`:** lo generó `transformers` 5. Con versiones 4.x puede no cargar; en ese caso, construye `RobertaTokenizerFast` desde `vocab.json` y `merges.txt` con las opciones de `tokenizer_config.json` (así lo hace AI-Triage).
- **Ajuste de spans:** el modelo trabaja con subpalabras y a veces corta una palabra. AI-Triage extiende cada mención a palabras completas y descarta las formadas solo por palabras funcionales.
- **Negación:** el modelo no la detecta. «Niega fiebre» se etiqueta como `SINTOMA`, y es una regla aparte (tipo NegEx) la que la marca como negada.

## Limitaciones

- **Corpus sintético y pequeño.** Los relatos de la etapa 2 los escribió el equipo imitando consultas reales, no son transcripciones de pacientes. Lo anotaron personas del propio equipo y el acuerdo entre anotadores aún no está medido.
- **Desfase de dominio.** El habla real de urgencias (ruido, interrupciones, errores del reconocedor de voz, coloquialismos regionales) puede rendir peor que estos relatos.
- **Límites de mención.** Algunos casos todavía se están revisando con una guía de límites: intensidad («muy fuerte»), duración («desde ayer»), verbos de marco («está con…») o el mecanismo de un trauma.
- **Español de Colombia.** Los coloquialismos del corpus propio son colombianos; en otras variantes del español el rendimiento puede ser distinto.

## Licencia y atribución

- **Modelo:** Apache-2.0, la misma licencia del modelo base de PlanTL / BSC.
- **Datos de la etapa 1:** se usaron corpus publicados bajo **CC BY 4.0**, que exige citarlos:
  - **SympTEMIST**: Lima-López et al., *Overview of SympTEMIST at BioCreative VIII*, 2023. Zenodo [10.5281/zenodo.10635215](https://doi.org/10.5281/zenodo.10635215).
  - **DisTEMIST**: Miranda-Escalada et al., *Overview of DisTEMIST at BioASQ*, CLEF 2022. Zenodo [10.5281/zenodo.7614764](https://doi.org/10.5281/zenodo.7614764).
  - **DrugTEMIST** (en MultiCardioNER): Lima-López et al., *Overview of MultiCardioNER at BioASQ*, CLEF 2024. Zenodo [10.5281/zenodo.11368861](https://doi.org/10.5281/zenodo.11368861).
- **Modelo base:** Carrino et al., *Pretrained Biomedical Language Models for Clinical NLP in Spanish*, BioNLP 2022.
- **Corpus propio:** no se publica con el modelo.

## Cita

Si usas este modelo, cita el trabajo de grado *AI-Triage: plataforma de apoyo al triaje de urgencias por voz* (Universidad del Valle, 2026) y los corpus y el modelo base indicados arriba.
