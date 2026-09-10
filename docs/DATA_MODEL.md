# Modelo de Datos Propuesto

## 1. Diagrama de Entidad-Relación (Mermaid)

```mermaid
erDiagram
    USER {
        int id PK
        string email UK "username o email"
        string role "admin, medico, enfermero"
        string password
        boolean is_active
        datetime date_joined
    }
    
    PATIENT {
        int id PK
        string document_id UK "Cédula, 6-10 dígitos"
        string full_name
        date birth_date
        string gender "male, female, other, unknown"
        string phone
        string insurance
        datetime created_at
    }

    TRIAGESESSION {
        int id PK
        int patient_id FK
        int user_id FK
        int level "1 al 5"
        text justification
        jsonb clinical_entities "Síntomas, vitals, etc."
        datetime created_at
    }

    TRANSCRIPTION {
        int id PK
        int triage_session_id FK
        string session_uuid "ID para logs y chunks"
        text full_text
        string model_used
        datetime created_at
    }

    FHIRRECORD {
        int id PK
        int triage_session_id FK
        string fhir_resource_id "ID devuelto por server FHIR"
        jsonb payload_sent
        datetime created_at
    }

    AUDITLOG {
        int id PK
        int user_id FK
        string action
        string resource_type
        int resource_id
        datetime timestamp
    }

    USER ||--o{ TRIAGESESSION : "realiza"
    USER ||--o{ AUDITLOG : "genera"
    PATIENT ||--o{ TRIAGESESSION : "tiene"
    TRIAGESESSION ||--o| TRANSCRIPTION : "contiene"
    TRIAGESESSION ||--o| FHIRRECORD : "exportado_a"
```

## 2. Descripción y Justificación de las Relaciones

1. **User (Usuario del Sistema)**:
   - Representa al personal médico. Se usa email/cédula como llave principal de acceso. Reemplaza al `User` por defecto de Django para poder tener un rol (`role`).
2. **Patient (Paciente)**:
   - Contiene la información demográfica. `document_id` es único para evitar duplicados en la base de datos (restricción explícita solicitada).
3. **TriageSession (Sesión de Triaje)**:
   - Entidad central. 
   - *FK a User*: Para saber quién realizó el triaje.
   - *FK a Patient*: Para vincular el triaje a un paciente específico.
   - Contiene el nivel (1-5) y el JSON de `clinical_entities` arrojado por Gemini.
4. **Transcription (Transcripción)**:
   - *FK a TriageSession*: Todo triaje se basa en una transcripción. Permite guardar la transcripción y el UUID usado en `whisper_engine.py`.
5. **FHIRRecord (Registro FHIR)**:
   - *FK a TriageSession*: Registra el mapeo exitoso de la sesión hacia el estándar HL7/FHIR, guardando el ID remoto para trazabilidad clínica.
6. **AuditLog (Log de Auditoría)**:
   - *FK a User*: Para registrar quién hizo una consulta sensible (ej. acceder a un paciente crítico, modificar un resultado). Requisito para sistemas de salud.
