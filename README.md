# AI-Triage: Asistente Inteligente de Voz para la Clasificación Médica Automatizada en Entornos Hospitalarios y de Telemedicina

**AI-Triage** es una aplicación inteligente basada en voz que aprovecha la inteligencia artificial (IA) y las tecnologías de procesamiento de lenguaje natural (NLP) para automatizar el triaje médico utilizando el análisis de voz en tiempo real. El sistema busca reducir la carga administrativa del personal de salud y mejorar la precisión en la clasificación de pacientes en servicios de urgencias y atención primaria.

## 🚀 Características Principales

*   **Reconocimiento Automático de Voz (ASR) Médico:** Transcripción en tiempo real adaptada al vocabulario clínico en español utilizando tecnologías como OpenAI Whisper.
*   **Procesamiento de Lenguaje Natural (NLP) Clínico:** Identificación y extracción automática de entidades como síntomas, diagnósticos, medicamentos y signos vitales mediante modelos NER (Named Entity Recognition).
*   **Triaje Inteligente:** Clasificación de la gravedad del paciente basada en modelos de decisión de IA y criterios médicos estandarizados como ESI o el Sistema Manchester.
*   **Interoperabilidad:** Generación de fichas clínicas estructuradas sincronizables con sistemas de Historia Clínica Electrónica (HCE) mediante estándares FHIR R4 y HL7 v3.
*   **Explicabilidad:** Generación de justificaciones en lenguaje natural sobre las decisiones de triaje para facilitar la validación por parte del personal médico.

## 🛠️ Stack Tecnológico

*   **Lenguaje y Backend:** Python con el framework Django.
*   **Inteligencia Artificial:**
    *   **ASR:** OpenAI Whisper.
    *   **NLP/NER:** Transformers (Hugging Face), modelos BERT (ClinicalBERT, BioBERT).
    *   **Modelos de Lenguaje:** OpenAI API para fine-tuning de modelos médicos.
*   **Bases de Datos:** PostgreSQL para datos estructurados y Redis para caché.
*   **Infraestructura:** Docker para despliegue y contenedores.
*   **Hardware Sugerido:** Estación de trabajo con GPU (NVIDIA RTX 4070 o superior) para entrenamiento e inferencia eficiente.

## 📂 Estructura Modular del Proyecto

El sistema está diseñado bajo una arquitectura de microservicios dividida en los siguientes módulos:

1.  **Módulo de Transcripción:** Captura audio y lo convierte en texto clínico estructurado.
2.  **Módulo de Normalización:** Limpieza de texto, corrección de errores fonéticos y mapeo a vocabularios controlados (SNOMED CT, ICD-10).
3.  **Módulo de Extracción NER:** Identificación automática de entidades clínicas críticas.
4.  **Módulo de Triaje Inteligente:** Evaluación de la gravedad y asignación de prioridad preliminar.
5.  **Módulo de Sincronización:** Conexión segura con sistemas HCE/HIS mediante APIs FHIR/HL7.

## 🔒 Seguridad y Ética

El desarrollo de AI-Triage se rige por la **Ley de Protección de Datos Personales de Colombia**, asegurando el cifrado de información y el uso de datos sintéticos o anonimizados durante las fases de prueba para proteger la privacidad del paciente.

## 👥 Autores y Créditos

*   **Kevin Jordan Alzate** - [kevin.jordan@correounivalle.edu.co](mailto:kevin.jordan@correounivalle.edu.co)
*   **Junior Orlando Cantor Arevalo** - [junior.cantor@correounivalle.edu.co](mailto:junior.cantor@correounivalle.edu.co)
*   **Director de Proyecto:** Carlos Mauricio Gaona Cuevas

---
*Proyecto desarrollado en la Escuela de Ingeniería de Sistemas y Computación de la **Universidad del Valle**, Cali, Colombia (2026)*.
