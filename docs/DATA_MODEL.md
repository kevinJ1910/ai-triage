# Modelo de Datos Implementado (AI-Triage)

**Fecha de Actualización:** 2026-10-26  
**Motor de Persistencia:** PostgreSQL 16 con extensión `pgvector` (Producción) / SQLite (Test Suite)  
**ORM:** Django 5.2.8 / Django REST Framework  

---

## 1. Diagrama de Entidad-Relación (Mermaid)

```mermaid
erDiagram
    USER {
        int id PK
        string email UK "Correo institucional"
        string first_name
        string last_name
        string document_id UK "Cédula o documento"
        string phone
        string role "admin, medico, enfermero"
        boolean is_verified "Verificado por OTP"
        boolean is_active
        boolean is_staff
        datetime date_joined
    }

    AUTHVERIFICATIONCODE {
        int id PK
        int user_id FK
        string code "OTP criptográfico de 6 dígitos"
        string code_type "VERIFY_EMAIL, PASSWORD_RESET"
        datetime created_at
        datetime expires_at "TTL 15 minutos"
        boolean is_used
    }

    USERPERMISSION {
        int id PK
        int user_id FK "1 a 1 estricto"
        boolean can_use_transcriber
        boolean can_edit_symptoms
        boolean can_register_patients
        boolean can_view_emr
        boolean can_view_fhir
        boolean can_manage_config
    }

    AUDITLOG {
        int id PK
        int user_id FK
        string action "LOGIN, TRIAGE_CREATED, TRIAGE_OVERRIDE, TRIAGE_REFERENCE, etc."
        string resource "Nombre del recurso o endpoint"
        string status "SUCCESS, FAILED, WARNING"
        string ip_address "IP cliente remota"
        jsonb details "Contexto y payload estructurado"
        datetime timestamp
    }

    PATIENT {
        int id PK
        string document_id UK "Documento de identidad (prefijo CORPUS- para evaluación)"
        string full_name
        date birth_date
        string gender "male, female, other, unknown"
        string phone
        string insurance "EPS / Aseguradora"
        datetime created_at
    }

    TRIAGESESSION {
        int id PK
        int patient_id FK
        int user_id FK
        int level "Nivel de triaje vigente (1 al 5)"
        int ai_level "Nivel sugerido por modelo IA"
        int final_level "Nivel ratificado por médico"
        boolean is_level_modified "Indica si hubo override clínico"
        text justification "Justificación clínica estructurada"
        jsonb clinical_entities "Entidades NER, signos vitales, box EMR"
        jsonb ai_symptoms "Síntomas extraídos por IA"
        jsonb final_symptoms "Síntomas validados por personal"
        float confidence_score "Confianza del modelo (0.0 a 1.0)"
        float agreement_score "Concordancia matemática (0.0 a 1.0)"
        int reference_level "Nivel adjudicado ciego por segundo médico (1 al 5)"
        int reference_by_id FK "Médico que adjudica la referencia ciega"
        datetime reference_at "Momento del dictamen ciego"
        int justification_clarity "Likert claridad (1-5)"
        int justification_relevance "Likert pertinencia clínica (1-5)"
        int justification_fidelity "Likert fidelidad al protocolo (1-5)"
        datetime justification_rated_at "Momento de calificación Likert"
        datetime created_at
    }

    CLINICALKNOWLEDGEVECTOR {
        int id PK
        string criterion_id UK "ID criterio protocolo (p. ej. CS-CV-01)"
        int level "Nivel de triaje asignado (1 al 5)"
        string category "cardiovascular, respiratorio, neurologico, etc."
        text description "Texto del criterio clínico institucional"
        vector embedding "Embedding denso vector(768) para búsqueda semántica"
        jsonb metadata "CIE-10, banderas rojas, palabras clave"
        datetime created_at
    }

    TRANSCRIPTION {
        int id PK
        int triage_session_id FK
        string session_uuid UK "UUID de sesión para audio streaming"
        text full_text "Transcripción acumulada"
        string model_used "large-v3-turbo, etc."
        datetime created_at
    }

    FHIRRECORD {
        int id PK
        int triage_session_id FK
        string fhir_resource_id "ID devuelto o asignado FHIR"
        jsonb payload_sent "Bundle JSON transmitido"
        datetime created_at
    }

    FHIRMESSAGELOG {
        int id PK
        int session_id FK
        string resource_type "Bundle, Encounter, Observation, Patient"
        string direction "INBOUND, OUTBOUND"
        int status_code "Código HTTP (200, 201, 400, etc.)"
        string fhir_resource_id "Identificador único FHIR"
        string validation_status "VALID, INVALID, ERROR"
        jsonb validation_details "Detalles de errores de esquema"
        jsonb payload "Contenido JSON completo"
        datetime created_at
    }

    SYSTEMCONFIGURATION {
        int id PK
        string active_asr_model "Whisper model tag (large-v3-turbo, small, etc.)"
        string active_llm_engine "Gemini model engine (gemini-2.5-flash)"
        string local_llm_model "Modelo local Ollama (gemma4:e4b-it-qat, qwen2.5:7b)"
        string active_ner_model "Modelo extractor NER (HoraYMedia/ai-triage-ner-roberta)"
        string snomed_version "Versión ontológica activa"
        datetime snomed_updated_at
        string icd10_version "Versión CIE-10 activa"
        datetime icd10_updated_at
        datetime updated_at
    }

    APIKEYCREDENTIAL {
        int id PK
        string provider "gemini, openai, anthropic, custom, etc."
        string name "Etiqueta identificadora"
        string encrypted_key "Cifrado simétrico AES-256 Fernet"
        string masked_key "Muestra pública segura"
        boolean is_active
        datetime created_at
    }

    USER ||--o{ AUTHVERIFICATIONCODE : "valida_con"
    USER ||--|| USERPERMISSION : "posee_rbac"
    USER ||--o{ AUDITLOG : "origina"
    USER ||--o{ TRIAGESESSION : "ejecuta_clinicamente"
    USER ||--o{ TRIAGESESSION : "adjudica_referencia_ciega"
    PATIENT ||--o{ TRIAGESESSION : "es_clasificado_en"
    TRIAGESESSION ||--o| TRANSCRIPTION : "respaldado_por"
    TRIAGESESSION ||--o| FHIRRECORD : "exportado_como"
    TRIAGESESSION ||--o{ FHIRMESSAGELOG : "traza_interoperabilidad"
```

---

## 2. Descripción y Justificación de las Entidades

### 2.1. Dominio de Cuentas y Seguridad (`accounts`)
1. **`User`**:
   - Reemplaza el modelo base de Django. Define el correo institucional y `document_id` como identificadores únicos. Añade el rol asistencial (`role`) y estado de verificación médica (`is_verified`).
2. **`AuthVerificationCode`**:
   - Almacena códigos OTP numéricos de 6 dígitos generados criptográficamente para activación de cuenta y reseteo de contraseñas. Controla expiración temporal (TTL de 15 minutos) y previene reuso mediante bandera `is_used`.
3. **`UserPermission`**:
   - Matriz de permisos RBAC granulares asociados a cada usuario en relación uno a uno. Controla de forma individual el acceso al transcriptor de voz, edición de síntomas, admisión de pacientes, EMR, monitor FHIR y panel de configuración.
4. **`AuditLog`**:
   - Registro inmutable de eventos críticos de seguridad y auditoría clínica (`LOGIN`, `TRIAGE_CREATED`, `TRIAGE_OVERRIDE`, `TRIAGE_REFERENCE`, `TRIAGE_JUSTIFICATION_RATING`, `PERMISSIONS_UPDATED`, `KEY_REGISTERED`, `CONFIG_UPDATED`) con persistencia de IP cliente y metadatos JSON.

### 2.2. Dominio de Pacientes (`patients`)
1. **`Patient`**:
   - Contiene la información demográfica fundamental. El campo `document_id` posee restricción de unicidad estricta para evitar duplicidad de historias clínicas en urgencias. En evaluaciones experimentales, utiliza el prefijo `CORPUS-` para desacoplar casos sintéticos de pacientes reales.

### 2.3. Dominio Clínico de Triaje (`triage`)
1. **`TriageSession`**:
   - Entidad núcleo del flujo clínico. Desacopla la sugerencia del modelo (`ai_level`, `ai_symptoms`) del dictamen humano (`final_level`, `final_symptoms`), registrando si existió override (`is_level_modified`) y computando el índice matemático de concordancia (`agreement_score`).
   - **Validación Ciega (Blind Review)**: Incorpora campos inmutables para la adjudicación por un segundo facultativo independiente: `reference_level`, `reference_by`, `reference_at`, y métricas en escala de Likert de 1 a 5 (`justification_clarity`, `justification_relevance`, `justification_fidelity`, `justification_rated_at`).
2. **`ClinicalKnowledgeVector`**:
   - Persistencia de criterios clínicos del protocolo institucional (Resolución 5596 / Christus Sinergia) en la tabla `triage_clinical_rag_vectors`. Emplea la extensión vectorial `pgvector` en PostgreSQL con columnas de tipo `vector(768)` para recuperación híbrida semántica (coseno) combinada con Okapi BM25 léxico.
3. **`Transcription`**:
   - Vinculada a la sesión de triaje. Guarda el texto consolidado y el `session_uuid` utilizado por el motor acústico ASR (`faster-whisper`) para streaming y reensamblado de audio.
4. **`FHIRRecord`**:
   - Registro del recurso HL7/FHIR exportado hacia el servidor de interoperabilidad clínica.
5. **`FHIRMessageLog`**:
   - Bitácora de transacciones FHIR R4 entrantes y salientes con trazabilidad de código de estado HTTP, validez estructural del payload y detalle de fallos de conformidad.

### 2.4. Dominio de Configuración del Sistema (`system_settings`)
1. **`SystemConfiguration`**:
   - Parámetros dinámicos del sistema: motores de inferencia activos (ASR, LLM en nube, LLM local vía Ollama, extractor NER RoBERTa) y versiones de las terminologías clínicas (SNOMED-CT y CIE-10).
2. **`APIKeyCredential`**:
   - Bóveda de credenciales de proveedores de IA (`gemini`, `openai`, `anthropic`, `custom`). Las claves se cifran en reposo con AES-256 (Fernet) derivado de la clave secreta del sistema; nunca se devuelven en texto plano y se sincronizan automáticamente con variables de entorno `.env`.

---

## 3. Índices Compuestos y Optimización

Para garantizar rendimiento hospitalario en escenarios de alta concurrencia, el modelo implementa los siguientes índices relacionales y vectoriales:

- `accounts.User`: Índices únicos sobre `email` y `document_id`.
- `accounts.AuditLog`: Índice compuesto sobre `('user', '-timestamp')` y sobre `('action', '-timestamp')`.
- `patients.Patient`: Índice único en `document_id` e índice sobre `full_name`.
- `triage.TriageSession`: Índice compuesto sobre `('patient', '-created_at')`, índice sobre `('-created_at', 'level')` e índice sobre `reference_level`.
- `triage.FHIRMessageLog`: Índice compuesto sobre `('session', '-created_at')` y sobre `('validation_status', '-created_at')`.
- `triage.ClinicalKnowledgeVector`: Índice HNSW o IVFFlat sobre la columna `embedding` para búsquedas vectoriales por distancia coseno en sub-milisegundos.
