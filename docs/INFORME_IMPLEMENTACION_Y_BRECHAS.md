# Informe Técnico de Implementación, Arquitectura y Estado del Sistema

**Fecha:** 2026-10-27 (Versión 4 — Cierre Experimental)  
**Proyecto:** AI-Triage Hospitalario (Sistema de Soporte a la Decisión Clínica por Voz)  
**Rama:** `feat/optimizacion-rag-asr-metricas` (convergente a `develop`)  
**Versión anterior del informe:** 2026-10-26 (Versión 3)

---

## 1. Resumen Ejecutivo

**AI-Triage** es una plataforma web de apoyo a la clasificación de urgencias por voz para población adulta bajo el protocolo institucional de **Christus Sinergia Salud** y la **Resolución 5596 de 2015** del Ministerio de Salud y Protección Social de Colombia. El sistema transcribe el relato clínico con `faster-whisper`, extrae entidades biomédicas mediante un modelo RoBERTa ajustado (`HoraYMedia/ai-triage-ner-roberta@v1`, consolidado con *Model Soup*) en conjunto con un catálogo terminológico determinista (SNOMED CT, CIE-10 y ATC), recupera criterios institucionales mediante un motor RAG híbrido (`pgvector` + Okapi BM25) y propone un nivel de prioridad (1 a 5) combinando un motor determinista de reglas (con escalado por signos vitales y detección de negación NegEx) con inferencia LLM local soberana (Ollama GPU `gemma4:e4b-it-qat`) o en nube (Google Gemini), manteniendo siempre la decisión final en el profesional (*human-in-the-loop*).

Principales hitos cerrados en esta versión definitiva:

- **Evaluación acústica sobre hardware GPU real:** Sobre 40 grabaciones clínicas reales (20 en silencio y 20 con ruido hospitalario a 12 dB SNR / 60–65 dB), `faster-whisper` (`large-v3-turbo` en NVIDIA RTX 3070) alcanzó un **WER global de 2,39 %** (`1,87 %` en silencio, `2,90 %` en ruido), un error en términos clínicos de **3,33 %** y un **RTF de 0,044** (latencia media `1,26 s`), frente a **7,53 % de WER** (`RTF 0,142`) en CPU (`small`, `int8`).
- **Extracción biomédica y normalización auditada:** El flujo híbrido alcanzó un **micro-F1 de 0,888** en `dev` (150 casos) y **0,789** IC95 `[0,750, 0,828]` en `test` (100 casos, con `0,963` en medicamentos y `97,2 %` de exactitud en negación), respaldado por doble anotación ciega inter-anotador de **0,979 micro-F1** y validación externa sobre **CodiEsp** (`73,3 %` de precisión a 3 caracteres CIE-10). El catálogo local reúne **315 conceptos** (`1.337` variantes, `302` mapeados a `299` códigos SNOMED CT únicos verificados contra `tx.fhir.org`, `208` a `188` códigos CIE-10 únicos y `76` a códigos ATC).
- **Soberanía de datos con LLM local en GPU y política `min_critico`:** En la corrida única sobre el split congelado `test` (100 casos), el flujo local `gemma4:e4b-it-qat` en GPU NVIDIA RTX 3070 (prompt `v2`, política `min_critico`) obtuvo **73,0 % de exactitud** IC95 `[64,0, 81,0]`, **Kappa ponderado cuadrático de 0,898** IC95 `[0,828, 0,945]`, **sensibilidad crítica en niveles I–II del 92,5 %** IC95 `[83,0, 100,0]` e **infratriaje de 12,0 %** (`-44,0 pp` respecto al motor de reglas aisladas), con latencia mediana de **15,2 s** y sin salida de datos del servidor hospitalario.
- **Validación clínica ciega (`BlindReview`):** Un médico independiente evaluó a ciegas 50 casos estratificados de `test` (10 por nivel), registrando **80,0 % de exactitud clínico-IA**, **Kappa ponderado de 0,911** IC95 `[0,793, 0,975]` y calificaciones medias Likert (1–5) de **4,80** en claridad, **4,58** en pertinencia clínica y **4,58** en fidelidad al protocolo.
- **Calidad de software e integración continua:** **731 pruebas automatizadas** en verde (`597` en `backend` + `43` en `ml` bajo Pytest, más `1 xfail` documentado, y `91` en `14` suites bajo Vitest en `frontend`), ejecutadas automáticamente en GitHub Actions (`.github/workflows/ci.yml`).

---

## 2. Arquitectura de Servicios

| Servicio | Función técnica |
| :--- | :--- |
| `nginx` | Terminación TLS 1.2/1.3 en puerto 443 (redirección desde 80), cabeceras de seguridad (CSP, HSTS, COOP, `Permissions-Policy`) y enrutamiento inverso hacia `frontend` y `backend`. |
| `frontend` | Next.js 15 (App Router, React 19, TypeScript) en modo `standalone` sin privilegios de root. |
| `backend` | Django 5.2+ / DRF sobre Gunicorn: autenticación JWT + OTP, RBAC en servidor, persistencia atómica, auditoría y encolamiento Celery. |
| `worker-asr` | Celery (`--pool solo`, cola `asr`): `WhisperEngine` con acondicionamiento acústico (pasa-altos 80 Hz + RMS −20 dBFS), *hotwords* médicas y soporte CPU (`small`, `int8`) o GPU CUDA (`large-v3-turbo`, `int8_float16`). |
| `worker-llm` | Celery (cola `llm`): inferencia RoBERTa NER (`HoraYMedia/ai-triage-ner-roberta@v1`), normalización clínica, RAG híbrido (`pgvector` + BM25) y clasificación con Gemini o LLM local, con degradación garantizada a reglas. |
| `llm-local` | Contenedor Ollama (perfil `llm-local`, CPU o GPU NVIDIA) para ejecución *on-premise* de `gemma4:e4b-it-qat` y `qwen2.5:7b-instruct-q4_K_M`. |
| `postgres` | PostgreSQL 16 + `pgvector` (aislado sin puerto expuesto al host): persistencia relacional y tabla vectorial `triage_clinical_rag_vectors` (61 criterios). |
| `redis` | Redis 7 Alpine: broker Celery (`db 0`), caché clínica canónica SHA-256, contexto ASR por sesión y contadores de *throttling* (`db 1`). |
| `mailpit` | Servidor SMTP local y visor web para códigos OTP de verificación y recuperación. |

---

## 3. Componentes Técnicos Verificados

1. **Seguridad, autenticación y RBAC (`backend/accounts/`, `backend/core/permissions.py`):** Registro con verificación OTP de 6 dígitos (TTL 15 min), access token exclusivamente en memoria del navegador, refresh token rotativo en cookie `httpOnly` con invalidación en lista negra (`POST /api/auth/logout/`), limitación de tasa en Redis (`10/min` en `auth`, `5/min` en `otp`), seis permisos granulares verificados en servidor y registro inmutable en `AuditLog`.
2. **Bóveda criptográfica (`backend/system_settings/`):** Cifrado simétrico `MultiFernet` con `FIELD_ENCRYPTION_KEY` independiente de `SECRET_KEY`, enmascaramiento estricto en respuestas API y conmutación dinámica de motores ASR, NER y LLM desde `ConfigPanel`.
3. **Pipeline híbrido de triaje (`backend/triage/`):**
   - Motor determinista `clinical_protocol.py` + `vital_signs.py` (18 umbrales fisiológicos adultos basados en NEWS2, ACC/AHA, ADA y MTS) + detector de negación en español `negation.py` (NegEx).
   - Compresor clínico `input_pipeline.py` y seudonimizador reversible de identificadores personales (Ley 1581 de 2012) previo a cualquier llamada externa.
   - Caché canónica `clinical_cache.py` (huella SHA-256 de texto normalizado + signos vitales, sin almacenar datos identificativos del paciente).
   - Recuperador `clinical_rag.py` sobre **61 criterios institucionales** combinando similitud coseno en `pgvector` (`triage_clinical_rag_vectors`) con puntuación léxica Okapi BM25 y expansión ontológica.
   - Extractor `ner_model.py` (`HoraYMedia/ai-triage-ner-roberta@v1`, consolidado mediante *Uniform Model Soup* en `ml/ner/model_soup.py`) fusionado con el catálogo determinista (`backend/transcription/terminology/`).
   - Clasificador estructurado en `ai_analyzer.py` / `local_llm.py` validado con Pydantic v2 (`TriageOutputSchema`) bajo la política `min_critico` (cuando las reglas detectan un criterio de nivel I–II, el nivel final nunca puede ser menos urgente).
4. **Interoperabilidad dual y Simulador HCE (`frontend/lib/hl7.ts`, `backend/triage/fhir_validation.py`):** Exportación de Bundles **HL7 FHIR R4** (`Patient`, `Encounter`, `Observation` LOINC/UCUM, `Condition` con `refuted` para negaciones, `AllergyIntolerance` y `MedicationStatement`) y tramas **HL7 v2.5.1 ER7 (`ADT^A08`)** con segmentos `MSH`, `EVN`, `PID`, `PV1`, `PV2`, `OBX`, `AL1` y `DG1`. El endpoint `POST /api/fhir/` valida la conformidad estructural R4 (`201` / `422`), persiste `FHIRRecord` + `FHIRMessageLog` y sincroniza el estado en `EMRSimulator` (`update_care_status`).

---

## 4. Limitaciones Conocidas y Trabajo Futuro

Las brechas críticas de iteraciones previas (ausencia de umbrales de signos vitales, falta de NegEx, dependencia exclusiva de nube, falta de pruebas en GPU NVIDIA real y ausencia de adjudicación médica ciega) quedaron resueltas. Las limitaciones residuales que delimitan la transferencia a operación asistencial real son:

1. **Piloto prospectivo multicéntrico con pacientes reales:** El corpus de 250 casos y los 40 audios se construyeron sobre relatos sintéticos para cumplir estrictamente con la Ley 1581 de 2012 sin exponer historias clínicas reales, y la validación ciega contó con un médico adjudicador independiente sobre 50 casos. Antes de cualquier uso asistencial directo se requiere un estudio prospectivo multicéntrico aprobado por comité de ética institucional, con panel de múltiples evaluadores, cronometraje asistencial y aplicación presencial de la escala SUS.
2. **Codificación semántica dentro de recursos FHIR y transporte externo:** Aunque el normalizador resuelve códigos SNOMED CT, CIE-10 y ATC verificados y los signos vitales ya se exportan con códigos LOINC y unidades UCUM, los recursos `Condition`, `AllergyIntolerance` y `MedicationStatement` del Bundle FHIR exportan actualmente la descripción textual clínica sin inyectar aún los códigos en `coding[].code`, y `/api/fhir/` opera como receptor validador local sin retransmisión automática SMART on FHIR o MLLP hacia un HIS externo.
3. **Servidor terminológico SNOMED CT RF2 completo:** El catálogo local cubre los 315 conceptos más frecuentes de urgencias adultas (verificados contra `tx.fhir.org`), pero no embebe la edición completa SNOMED CT RF2 (>350.000 conceptos) mediante Snowstorm u Ontoserver.
4. **Población pediátrica y obstétrica especializada:** Los umbrales de signos vitales implementados en `vital_signs.py` aplican exclusivamente a adultos; su extensión a pediatría requiere tablas fisiológicas estratificadas por edad.
5. **Deuda técnica menor de frontend e infraestructura:** `TriageDashboard.tsx` concentra múltiples subpaneles en un único componente (~1.890 líneas); la cabecera CSP mantiene `'unsafe-inline'` en `script-src` por los scripts de hidratación sin *nonce* de Next.js; y la clave `asr:engine_status` en Redis se limpia en apagados ordenados pero carece aún de *heartbeat* con TTL ante caídas abruptas del proceso.

---

## 5. Matriz Consolidada de Endpoints REST

| Método | Endpoint | Descripción | Validación | Control de acceso |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login/` | Inicio de sesión (access en cuerpo, refresh en cookie `httpOnly`) | `LoginSchema` | Público (10/min) |
| `POST` | `/api/auth/refresh/` | Renovación con rotación del refresh token (cookie) | — | Público (cookie) |
| `POST` | `/api/auth/logout/` | Cierre de sesión e inclusión del refresh en lista negra | — | JWT |
| `POST` | `/api/auth/register/` | Registro de personal asistencial y envío de OTP | `RegisterSchema` | Público (10/min) |
| `POST` | `/api/auth/verify/` · `/api/auth/resend-code/` | Verificación y reenvío de código OTP | `VerifyCodeSchema` | Público (5/min) |
| `POST` | `/api/auth/password-reset/request/` · `/confirm/` | Solicitud y confirmación de restablecimiento de contraseña | Pydantic | Público (10/min · 5/min) |
| `GET` | `/api/auth/me/` | Perfil autenticado y matriz de permisos | — | JWT |
| `GET` | `/api/security/users/` | Directorio de usuarios registrados | — | Admin |
| `PATCH` | `/api/security/users/<id>/permissions/` | Actualización de matriz RBAC por usuario | `UserPermissionUpdateSchema` | Admin |
| `GET` | `/api/security/audit/` | Consulta de bitácora inmutable `AuditLog` | — | Admin |
| `GET` / `POST` | `/api/config/` | Configuración activa de motores ASR, NER y LLM | `SystemConfigUpdateSchema` | JWT / Admin (`can_manage_config`) |
| `GET` | `/api/config/engines/` | Estado operativo de motores y modelos locales disponibles | — | JWT |
| `POST` | `/api/config/vocabulary/sync/` | Verificación y recarga de catálogos SNOMED CT / CIE-10 | — | Admin / `can_manage_config` |
| `GET` / `POST` / `DELETE` | `/api/config/keys/[<id>/]` | Gestión de bóveda de claves API cifradas (`MultiFernet`) | `APIKeyCreateSchema` | JWT / Admin |
| `POST` | `/api/transcribe/` | Transcripción de fragmento de audio en cola `asr` | — | `can_use_transcriber` |
| `POST` | `/api/transcribe/reset/` | Reinicio de contexto acumulado de sesión ASR | — | `can_use_transcriber` |
| `POST` | `/api/transcribe/normalize/` | Normalización clínica SNOMED CT / CIE-10 / ATC | `NormalizeTextSchema` | JWT |
| `POST` | `/api/triage/sessions/analyze/` | Análisis híbrido y guardado atómico de sesión de triaje | — | `can_register_patients` |
| `GET` | `/api/triage/sessions/history/` | Historial de sesiones (propias; administrador consulta todas) | — | JWT |
| `PATCH` | `/api/triage/sessions/<id>/override_level/` | Ratificación o ajuste médico de nivel y síntomas | `TriageOverrideSchema` | `can_edit_symptoms` |
| `GET` | `/api/triage/sessions/emr_patients/` | Cola de admisiones clínicas para el simulador HCE | — | `can_view_emr` |
| `POST` / `PATCH` | `/api/triage/sessions/<id>/update_care_status/` | Actualización de estado asistencial y notas de evolución HCE | — | `can_view_emr` |
| `GET` | `/api/triage/sessions/evaluation_metrics/` | Concordancia, Kappa cuadrático, seguridad y referencia ciega | — | JWT (identidad solo con `can_view_emr`) |
| `GET` | `/api/triage/sessions/benchmark_results/` | Artefactos reproducibles de evaluación ASR, NER y triaje | — | JWT |
| `GET` | `/api/triage/sessions/blind_review_queue/` | Cola de casos pendientes para adjudicación doble ciego | — | `can_edit_symptoms` |
| `POST` | `/api/triage/sessions/<id>/reference_level/` | Adjudicación inmutable de nivel de referencia ciego | `TriageReferenceSchema` | `can_edit_symptoms` (distinto del autor) |
| `POST` | `/api/triage/sessions/<id>/justification_rating/` | Calificación Likert (1–5) de claridad, pertinencia y fidelidad | `JustificationRatingSchema` | Adjudicador de la sesión |
| `GET` | `/api/triage/sessions/fhir_logs/` | Bitácora auditada de mensajes HL7 FHIR R4 | — | `can_view_fhir` |
| `POST` | `/api/fhir/` | Validación estructural e ingestión de Bundles HL7 FHIR R4 | `FHIRSyncSchema` | JWT |
| `GET` | `/api/health_check/` | Estado integral del backend y del worker ASR | — | Público |
