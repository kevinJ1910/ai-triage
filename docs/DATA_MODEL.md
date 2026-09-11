# Modelo de Datos Implementado (AI-Triage)

**Fecha de Actualización:** 2026-09-10  
**Motor de Persistencia:** PostgreSQL 16 (Producción) / SQLite (Test Suite)  
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
        string action "LOGIN, TRIAGE_CREATED, TRIAGE_OVERRIDE, etc."
        string resource "Nombre del recurso o endpoint"
        string status "SUCCESS, FAILED, WARNING"
        string ip_address "IP cliente remota"
        jsonb details "Contexto y payload estructurado"
        datetime timestamp
    }

    PATIENT {
        int id PK
        string document_id UK "Documento de identidad"
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
        string active_asr_model "Whisper model tag"
        string active_llm_engine "Gemini model engine"
        string active_ner_model "Modelo extractor NER"
        string snomed_version "Versión ontológica activa"
        datetime snomed_updated_at
        string icd10_version "Versión CIE-10 activa"
        datetime icd10_updated_at
        datetime updated_at
    }

    APIKEYCREDENTIAL {
        int id PK
        string provider "gemini, openai, anthropic, deepseek, etc."
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
   - Registro inmutable de eventos críticos de seguridad y auditoría clínica (`LOGIN`, `TRIAGE_CREATED`, `TRIAGE_OVERRIDE`, `PERMISSIONS_UPDATED`, `KEY_REGISTERED`, `CONFIG_UPDATED`, `EMR_BOX_ASSIGNED`) con persistencia de IP cliente y metadatos JSON.

### 2.2. Dominio de Pacientes (`patients`)
1. **`Patient`**:
   - Contiene la información demográfica fundamental. El campo `document_id` posee restricción de unicidad estricta para evitar duplicidad de historias clínicas en urgencias.

### 2.3. Dominio Clínico de Triaje (`triage`)
1. **`TriageSession`**:
   - Entidad núcleo del flujo clínico. Desacopla la sugerencia del modelo (`ai_level`, `ai_symptoms`) del dictamen humano (`final_level`, `final_symptoms`), registrando si existió override (`is_level_modified`) y computando el índice matemático de concordancia (`agreement_score`). En `clinical_entities` se almacenan signos vitales normalizados y asignación física de box de urgencias (`box_assigned`).
2. **`Transcription`**:
   - Vinculada a la sesión de triaje. Guarda el texto consolidado y el `session_uuid` utilizado por el motor acústico ASR (`faster-whisper`) para streaming y reensamblado de audio.
3. **`FHIRRecord`**:
   - Registro del recurso HL7/FHIR exportado hacia el servidor de interoperabilidad clínica.
4. **`FHIRMessageLog`**:
   - Bitácora de transacciones FHIR R4 entrantes y salientes con trazabilidad de código de estado HTTP, validez estructural del payload y detalle de fallos de conformidad.

### 2.4. Dominio de Configuración del Sistema (`system_settings`)
1. **`SystemConfiguration`**:
   - Parámetros dinámicos del sistema: motores de inferencia activos (ASR, LLM, NER) y versiones de las terminologías clínicas (SNOMED-CT y CIE-10).
2. **`APIKeyCredential`**:
   - Bóveda de credenciales de proveedores de IA (`gemini`, `openai`, `anthropic`, `deepseek`, `groq`, `cohere`, `mistral`). Las claves se cifran en reposo con AES-256 (Fernet) derivado de la clave secreta del sistema; nunca se devuelven en texto plano y se sincronizan automáticamente con variables de entorno `.env`.

---

## 3. Índices Compuestos y Optimización

Para garantizar rendimiento hospitalario en escenarios de alta concurrencia, el modelo implementa los siguientes índices relacionales:

- `accounts.User`: Índices únicos sobre `email` y `document_id`.
- `accounts.AuditLog`: Índice compuesto sobre `('user', '-timestamp')` y sobre `('action', '-timestamp')`.
- `patients.Patient`: Índice único en `document_id` e índice sobre `full_name`.
- `triage.TriageSession`: Índice compuesto sobre `('patient', '-created_at')` e índice sobre `('-created_at', 'level')`.
- `triage.FHIRMessageLog`: Índice compuesto sobre `('session', '-created_at')` y sobre `('validation_status', '-created_at')`.
