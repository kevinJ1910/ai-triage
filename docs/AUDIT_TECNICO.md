# Auditoría Técnica Integral — AI-Triage

**Fecha de esta revisión:** 2026-10-27 (revisión 4 — cierre experimental y verificación en GPU/CI)  
**Auditoría inicial:** 2026-09-10  
**Rama auditada:** `feat/optimizacion-rag-asr-metricas` / `develop`  
**Alcance:** backend (`Django/Python`), modelos ML (`ml/ner`), frontend (`Next.js/TypeScript`), infraestructura (`Docker Compose`, `CUDA`, `Ollama`, `nginx`), modelo de datos (`PostgreSQL 16 + pgvector`), seguridad, validez metodológica y deuda técnica.

---

## 1. Severidades

| Nivel | Descripción |
|:------|:------------|
| **CRÍTICO** | Fallo de seguridad o de corrección con impacto directo en datos clínicos o en la decisión de triaje |
| **ALTO** | Deuda técnica o defecto que degrada de forma significativa la confiabilidad, la seguridad o la validez de los resultados |
| **MEDIO** | Inconsistencia de diseño, cobertura faltante o patrón subóptimo |
| **BAJO** | Mejora menor de calidad, legibilidad o consistencia |

---

## 2. Resumen Ejecutivo de Estado

| Categoría de hallazgos | Resueltos / Mitigados | Pendientes (Deuda menor) |
| :--- | ---: | ---: |
| Auditoría inicial (`A-01 … A-34`) | 33 | 1 (`A-20`) |
| Hallazgos de iteraciones intermedias (`N-01 … N-22`) | 22 | 0 |
| Riesgos de seguimiento (`P-01 … P-08`) | 5 | 3 (`P-04`, `P-05`, `P-06`) |

Hitos técnicos verificados en la revisión 4:

1. **Mitigación de infratriaje y reglas fisiológicas (`P-01` -> Resuelto):** Se incorporaron 18 reglas cuantitativas de signos vitales adultos (`backend/triage/vital_signs.py`), detección determinista de negaciones en español (`backend/triage/negation.py`), recuperación híbrida `pgvector` + Okapi BM25 sobre 61 criterios (`backend/triage/clinical_rag.py`) y la política de piso de seguridad `min_critico`, elevando la sensibilidad en niveles críticos I–II al **92,5 %** en la partición congelada `test`.
2. **Evaluación congelada y adjudicación médica ciega (`P-02` -> Mitigado):** Se consolidó el corpus de 250 relatos (`150 dev` + `100 test` con doble anotación ciega e IAA `0,865` en triaje / `0,979` en NER) y se completó la revisión ciega independiente sobre 50 casos estratificados de `test` (`80,0 %` de exactitud clínico-IA, `Kappa = 0,911`, Likert `4,80 / 4,58 / 4,58`).
3. **Soberanía de datos con LLM local en GPU (`P-03` -> Resuelto):** Se integró `backend/triage/local_llm.py` y el servicio `llm-local` (Ollama GPU con `gemma4:e4b-it-qat`), garantizando operación 100 % *on-premise* sin transferencia externa de relatos clínicos y sin degradar jamás a nube cuando se selecciona el modo local.
4. **Verificación empírica en GPU NVIDIA real y CI en GitHub (`P-07` -> Resuelto):** Tanto `faster-whisper` (`large-v3-turbo`, `WER 2,39 %`, `RTF 0,044`) como `gemma4:e4b-it-qat` (`15,2 s` p50) fueron medidos sobre GPU NVIDIA GeForce RTX 3070 real, y el flujo `.github/workflows/ci.yml` ejecuta y aprueba las suites de `backend` y `frontend` en GitHub Actions.

---

## 3. Hallazgos de la Auditoría Inicial (`A-01 … A-34`)

| # | Sev. | Hallazgo | Estado | Resolución verificada |
|:--|:-----|:---------|:-------|:-----------|
| A-01 | CRÍTICO | `TriageSessionViewSet` con `AllowAny` | **Resuelto** | `GenericViewSet` sin CRUD genérico; cada acción exige `IsAuthenticated` y permiso granular (`core/permissions.py`). |
| A-02 | CRÍTICO | Sin *rate limiting* en autenticación | **Resuelto** | Throttles compartidos en Redis (`AuthThrottle` 10/min y `OTPThrottle` 5/min) en login, registro, OTP y recuperación. |
| A-03 | ALTO | Refresh token sin lista negra ni logout | **Resuelto** | `token_blacklist`, rotación automática y `POST /api/auth/logout/`. |
| A-04 | ALTO | Tokens JWT en `localStorage` | **Resuelto** | Refresh token en cookie `httpOnly` (`ai_triage_refresh`) y access token solo en memoria RAM del cliente. |
| A-05 | ALTO | `SECRET_KEY` con valor por defecto inseguro | **Resuelto** | Obligatoria en entorno de ejecución (solo mockeada en `pytest`). |
| A-06 | MEDIO | `ALLOWED_HOSTS = ['*']` | **Resuelto** | Lista explícita controlada por variable de entorno. |
| A-07 | MEDIO | Endpoint FHIR público | **Resuelto** | `POST /api/fhir/` exige JWT y `fhir_logs` exige `can_view_fhir`. |
| A-08 | ALTO | Historial de triajes solo en `localStorage` | **Resuelto** | Persistido y consultado vía `GET /api/triage/sessions/history/` (excluyendo casos `CORPUS-`). |
| A-09 | ALTO | `time.sleep(0.5)` artificial en endpoint FHIR | **Resuelto** | Eliminado. |
| A-10 | ALTO | Variable global `engine` en vistas ASR | **Resuelto** | Singleton thread-safe `WhisperEngine` aislado en `worker-asr`. |
| A-11 | ALTO | Llamada a Gemini sin timeout efectivo | **Resuelto** | SDK `google-genai >= 2.28`, timeout explícito en triaje y normalización, y cota `LLM_TASK_TIMEOUT` en `run_task`. |
| A-12 | ALTO | `TriageSession.save()` recalcula en guardados parciales | **Resuelto** | Recálculo condicionado exclusivamente a cambios en `level_fields`. |
| A-13 | MEDIO | `AuditLog` silenciaba excepciones | **Resuelto** | Trazabilidad explícita mediante `logger.error(..., exc_info=True)`. |
| A-14 | MEDIO | `evaluation_metrics` cargaba todas las sesiones en RAM | **Resuelto** | Agregaciones SQL (`GROUP BY` 5x5 y `aggregate()`) con complejidad constante en consultas. |
| A-15 | MEDIO | Datos inventados en `emr_patients` | **Resuelto** | Retorna cadenas vacías / `null` cuando el dato demográfico no fue registrado. |
| A-16 | MEDIO | `SystemConfigUpdateSchema` desalineado | **Resuelto** | Sincronizado con `SystemConfiguration` y `extra='forbid'`. |
| A-17 | MEDIO | `db.sqlite3` versionado | **Resuelto** | Excluido en `.gitignore`. |
| A-18 | BAJO | Logging duplicado con `FileHandler` manual | **Resuelto** | Centralizado en `settings.LOGGING`. |
| A-19 | ALTO | `useState<any>` en datos clínicos | **Resuelto** | Interfaces TypeScript estrictas en componentes clínicos. |
| A-20 | MEDIO | `TriageDashboard.tsx` monolítico | **Pendiente** | Mantiene ~1.890 líneas; candidato a extracción en subcomponentes (ver `P-06`). |
| A-21 | MEDIO | `fetchWithAuth` sin renovación concurrente | **Resuelto** | Promesa única compartida de refresh ante respuestas `401`. |
| A-22 | BAJO | Perfil leído de `localStorage` | **Resuelto** | Verificado contra `/api/auth/me/` en `AppNavigation` e inyectado por props; autorización real en servidor. |
| A-23 | BAJO | Validación de frontend parcial | **Mitigado** | `frontend/lib/validation.ts` centraliza cédula, fecha y teléfono; el backend valida todos los payloads con Pydantic v2. |
| A-24 | MEDIO | `GEMINI_API_KEY` expuesta al contenedor frontend | **Resuelto** | Confinada exclusivamente a `backend` y `worker-llm`. |
| A-25 | BAJO | Puerto `5432` expuesto al host | **Resuelto** | Confinado a la red interna `ai_triage_network`. |
| A-26 | BAJO | Nombres inconsistentes en `AuditLog` | **Resuelto** | Taxonomía unificada de acciones auditables. |
| A-27 | BAJO | `google-genai` en versión alfa | **Resuelto** | Actualizado a versión estable `2.28+`. |
| A-28 | MEDIO | Dependencias huérfanas (`boto3`, `sendgrid`) | **Resuelto** | Depuradas de `requirements.txt`. |
| A-29 | CRÍTICO | Fuga de trazas internas en errores ASR | **Resuelto** | Respuestas HTTP sanitizadas (`400`, `422`, `500`, `503`). |
| A-30 | ALTO | `makemigrations` ejecutado en arranque Docker | **Resuelto** | `entrypoint.sh` ejecuta únicamente `migrate`; `ci.yml` verifica `makemigrations --check --dry-run`. |
| A-31 | ALTO | Usuario demo inseguro en producción | **Resuelto** | Opt-in explícito con `CREATE_DEMO_USERS` y contraseñas obligatorias; bloqueado en producción. |
| A-32 | MEDIO | Rutas de cuenta mezcladas con seguridad | **Resuelto** | Separadas en `/api/auth/` y `/api/security/`. |
| A-33 | MEDIO | Validación inconsistente de teléfonos | **Resuelto** | Normalizada en frontend y backend. |
| A-34 | MEDIO | Variables `*_API_KEY` desconectadas de la bóveda | **Resuelto** | Sincronizadas automáticamente al arranque mediante `sync_environment_api_keys()`. |

---

## 4. Seguimiento de Riesgos Posteriores (`P-01 … P-08`)

| # | Sev. | Descripción | Estado actual | Evidencia técnica |
|:--|:-----|:------------|:--------------|:------------------|
| P-01 | ALTO | Baja sensibilidad del motor léxico aislado ante signos vitales, paráfrasis y negaciones | **Resuelto** | `vital_signs.py` (18 umbrales), `negation.py` (NegEx, `97,2 %` exactitud en *test*), `ner_model.py` (`RoBERTa v1`) y política `min_critico` (`92,5 %` sensibilidad I–II en *test*). |
| P-02 | ALTO | Ausencia de partición congelada `test` y validación médica ciega | **Mitigado** | Corpus de 250 casos (`150 dev` / `100 test` congelado), doble anotación ciega y adjudicación médica independiente sobre 50 casos en `BlindReview` (`Kappa = 0,911`, exactitud `80,0 %`). Queda como trabajo futuro un piloto prospectivo con pacientes reales. |
| P-03 | MEDIO | Salida de relatos seudonimizados hacia API externa en nube | **Resuelto** | Integración de `llm-local` (Ollama GPU `gemma4:e4b-it-qat`) con aislamiento estricto: cero tráfico externo y respaldo local a reglas. |
| P-04 | MEDIO | Cabecera CSP con `'unsafe-inline'` en `script-src` | **Pendiente** | Requerido por los scripts de hidratación estáticos de Next.js 15; mitigable en el futuro mediante middleware de *nonces* por petición. |
| P-05 | BAJO | Clave `asr:engine_status` en Redis sin TTL ante muerte abrupta (`SIGKILL`) | **Pendiente** | `/api/health_check/` detecta indisponibilidad real de `worker-asr`; añadir *heartbeat* periódico es una mejora menor recomendada. |
| P-06 | BAJO | Tamaño de `frontend/components/TriageDashboard.tsx` (~1.890 líneas) | **Pendiente** | Funcional y cubierto por pruebas de regresión en Vitest; refactorización modular diferida para mantenimiento evolutivo. |
| P-07 | BAJO | Modo GPU NVIDIA y pipeline GitHub Actions pendientes de corrida real | **Resuelto** | Verificado empíricamente sobre NVIDIA GeForce RTX 3070 (`docker-compose.gpu.yml`) y con jobs `backend` + `frontend` en verde en GitHub Actions. |
| P-08 | BAJO | Perfil de usuario cacheado en `localStorage` | **Resuelto** | Hidratado desde `/api/auth/me/` en `AppNavigation` y pasado como prop tipada. |

---

## 5. Cobertura de Pruebas Automatizadas

| Suite | Comando de verificación | Alcance principal | Total |
| :--- | :--- | :--- | ---: |
| **Backend (`Django + DRF`)** | `pytest --create-db backend` | Autenticación, OTP, cookies JWT, throttling, RBAC, cifrado `MultiFernet`, motor Christus Sinergia (criterio por criterio), umbrales de signos vitales, NegEx, RAG híbrido (`pgvector` + BM25), caché SHA-256 sin fuga entre pacientes, LLM local/nube, métricas Kappa/bootstrap, `BlindReview`, validación FHIR R4, ASR simulado y comandos de benchmark. | **597** (`+ 1 xfail`) |
| **Machine Learning (`ml/ner`)** | `pytest ml` | Alineación BIO de subtokens RoBERTa, fusión de corpus públicos (SympTEMIST, DisTEMIST, DrugTEMIST), aumentación controlada, *Uniform/Greedy Model Soup* sobre `safetensors`, postprocesado y auditoría de spans. | **43** |
| **Frontend (`Next.js + Vitest`)** | `pnpm --dir frontend test` | Navegación por permisos, `TriageDashboard`, `BlindReview`, `MetricsDashboard`, `EvaluationResults`, `EMRSimulator`, `FHIRMonitor`, exportación dual FHIR R4 / HL7 v2.5.1, `NormalizationMonitor`, `SecurityPanel`, `ConfigPanel`, `fetchWithAuth` y validadores. | **91** (`14` suites) |
| **Total del repositorio** | `.github/workflows/ci.yml` | Verificación continua de migraciones, tests, linter ESLint y build de producción Next.js. | **731** |
