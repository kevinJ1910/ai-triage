# Informe Técnico de Implementación, Arquitectura y Brechas del Sistema

**Fecha:** 2026-10-05  
**Proyecto:** AI-Triage Hospitalario (Trabajo de Grado / Sistema de Soporte a la Decisión Clínica)  
**Rama base:** `develop`  
**Versión anterior del informe:** 2026-09-10

---

## 1. Resumen Ejecutivo

AI-Triage es una plataforma de apoyo al triaje de urgencias por voz. Transcribe la consulta con Faster-Whisper, propone un nivel de triaje (1–5) según el protocolo Christus Sinergia Salud / Resolución 5596 de Minsalud, combinando un motor determinista de reglas con Google Gemini, y deja la decisión final al profesional, que puede ratificar o ajustar el nivel.

Desde la versión anterior de este informe, los cambios principales son:

- **Métricas honestas y validación ciega.** La concordancia IA–médico deja de presentarse como validación: el médico ve la sugerencia de la IA antes de decidir (sesgo de anclaje). Se añadió un flujo de **nivel de referencia ciego**, asignado por un clínico distinto del autor que solo ve la transcripción, y métricas contra esa referencia (Kappa ponderado, infratriaje, sensibilidad en niveles 1–2).
- **Benchmark reproducible.** El comando `evaluate_benchmark` y un conjunto de 65 casos sintéticos permiten medir el motor de reglas y el pipeline completo. La medición destapó fallos en los patrones del motor de reglas, ya corregidos, y cuantifica sus límites: sensibilidad del 28,6 % en casos críticos sobre el conjunto sintético.
- **Seguridad.** HTTPS con TLS en nginx, cabeceras de seguridad y CSP; refresh token en cookie httpOnly y access token solo en memoria; permisos aplicados en el servidor en todos los endpoints clínicos; límites de intentos en login, OTP y confirmación de contraseña.
- **Arquitectura de inferencia.** Whisper y Gemini se ejecutan en workers Celery con Redis (colas `asr` y `llm`). El estado compartido (caché clínica, contexto ASR, throttling) vive en Redis. Por defecto la plataforma corre en CPU; un override de Compose activa la GPU NVIDIA.
- **Calidad.** 253 pruebas de backend y 67 de frontend, y CI en GitHub Actions (tests, lint y build).

---

## 2. Arquitectura

### 2.1. Servicios

| Servicio | Función |
| :--- | :--- |
| `nginx` | Entrada única: TLS en 443 (80 redirige, salvo `/health`), cabeceras de seguridad y CSP, proxy a frontend y backend. |
| `frontend` | Next.js 15 (App Router, React 19) en modo standalone. Llama siempre a rutas relativas `/api/...`. |
| `backend` | Django 5 + DRF sobre Gunicorn (2 procesos × 8 hilos). API, RBAC, persistencia y auditoría; encola la inferencia y espera el resultado. |
| `worker-asr` | Celery, cola `asr`, pool `solo`: Faster-Whisper cargado una sola vez al arrancar. CPU `int8` / modelo `small` por defecto; GPU `float16` / `large-v3-turbo` con `docker-compose.gpu.yml`. |
| `worker-llm` | Celery, cola `llm`, pool de hilos: triaje con Gemini y normalización clínica. |
| `postgres` | PostgreSQL 16 (sin puerto expuesto al host). |
| `redis` | Broker de Celery (db 0) y caché de Django (db 1): caché clínica, contexto ASR por sesión, estado del motor ASR y contadores de throttling. |
| `mailpit` | SMTP local y visor web de los correos OTP. |

### 2.2. Flujo de una consulta

1. El navegador graba el audio por fragmentos (`hooks/useWhisperASR.ts`) y los envía a `POST /api/transcribe/`.
2. El backend encola `transcribe_audio_chunk` en la cola `asr` (`core.task_runner.run_task`, timeout `ASR_TASK_TIMEOUT`). El worker transcribe con el contexto previo de la sesión, guardado en Redis. Si el worker no responde, el backend devuelve 503.
3. Al pedir el análisis (`POST /api/triage/sessions/analyze/`), el backend encola `analyze_transcript` en la cola `llm` (timeout `LLM_TASK_TIMEOUT`). Si el worker no responde, se aplica el motor de reglas en línea (`allow_llm=False`) y la respuesta lleva un aviso: el análisis nunca falla por el LLM.
4. El resultado se guarda de forma atómica (`Patient`, `Transcription`, `TriageSession` y `AuditLog`) y se muestra al profesional, que ratifica o ajusta el nivel.

Sin `REDIS_HOST`, y siempre en pytest, las tareas se ejecutan en línea (`CELERY_TASK_ALWAYS_EAGER`) y la caché es local al proceso.

---

## 3. Componentes Implementados

### 3.1. Autenticación y sesión
- `accounts.User` con roles `admin`, `medico` y `enfermero`, datos de identificación clínica y verificación por correo con código OTP de 6 dígitos (15 minutos de validez, un solo uso). Los correos se capturan en Mailpit durante el desarrollo.
- **Tokens:** el access token vive solo en memoria del navegador; el refresh token va en una cookie `httpOnly` (`ai_triage_refresh`, ruta `/api/auth/`, `Secure` con `SECURE_COOKIES=True`) que gestiona `accounts/jwt_cookies.py`. La renovación rota el refresh token y el anterior pasa a la lista negra (`token_blacklist`). `POST /api/auth/logout/` lo invalida.
- `fetchWithAuth` (`frontend/lib/api.ts`) renueva el token una sola vez ante un 401 (con un refresh compartido entre peticiones concurrentes) y, si falla, redirige a `/login`. Al iniciar se purgan las claves que versiones anteriores guardaban en `localStorage`.
- **Límites de intentos** (`accounts/throttles.py`, compartidos vía Redis): 10/min en login, registro y solicitud de recuperación (`AuthThrottle`); 5/min en verificación OTP, reenvío de código y confirmación de nueva contraseña (`OTPThrottle`).
- **Usuarios demo:** solo se crean si `CREATE_DEMO_USERS=True` y su contraseña está definida (`DEMO_ADMIN_PASSWORD`, `DEMO_NURSE_PASSWORD`). Nunca se generan contraseñas aleatorias que nadie conoce, y en `ENVIRONMENT=production` se omiten.

### 3.2. RBAC y auditoría
- `UserPermission` es una matriz granular por usuario: `can_use_transcriber`, `can_edit_symptoms`, `can_register_patients`, `can_view_emr`, `can_view_fhir` y `can_manage_config`.
- Los permisos se aplican **en el servidor** con las clases de `core/permissions.py` en cada acción. La interfaz solo oculta controles; no es una barrera de seguridad.
- `AuditLog` registra con IP y fecha: `LOGIN`, `USER_REGISTER_REQUEST`, `EMAIL_VERIFIED`, `PASSWORD_RESET_REQUEST`, `PASSWORD_RESET_SUCCESS`, `TRIAGE_CREATED`, `TRIAGE_OVERRIDE`, `TRIAGE_REFERENCE`, `EMR_BOX_ASSIGNED`, `RBAC_PERMISSION_CHANGE`, `MODEL_CONFIG_CHANGE`, `API_KEY_ADDED`, `API_KEY_DELETED` y `UPDATE_VOCABULARY`. Los fallos al escribir la auditoría se registran en el log, no se silencian.

### 3.3. Bóveda de credenciales y configuración
- `APIKeyCredential` cifra las claves con `MultiFernet`: usa `FIELD_ENCRYPTION_KEY` si está definida y, por compatibilidad, también descifra con la clave histórica derivada de `SECRET_KEY`. Las claves nunca se devuelven en claro (solo enmascaradas), y `sync_environment_api_keys()` importa a la bóveda cualquier variable `*_API_KEY` del entorno.
- `SystemConfiguration` guarda el modelo LLM activo y el modelo ASR. Con `active_asr_model='auto'` (valor por defecto) se respeta `WHISPER_MODEL_SIZE` del entorno, que difiere entre CPU y GPU; cualquier otro valor lo impone. El panel de configuración muestra el dispositivo real del motor ASR (GPU CUDA o CPU INT8) y el modelo en uso, según el estado que publica el worker.
- La sincronización de vocabularios está restringida a administradores o a quien tenga `can_manage_config`.

### 3.4. Pipeline de triaje (`backend/triage/`)
1. `clinical_protocol.evaluate_christus_sinergia_triage`: motor determinista de reglas léxicas (niveles 1–5). Se calcula siempre y se pasa al LLM como pauta prioritaria.
2. `input_pipeline.ClinicalTranscriptCompressor`: elimina muletillas, extrae signos vitales por regex y detecta banderas rojas.
3. `clinical_cache.ClinicalQueryCache`: caché sobre la caché de Django (Redis), compartida por web y workers. Usa una huella SHA-256 del texto normalizado más los vitales, con TTL de 24 h, y nunca guarda `patientInfo`.
4. `clinical_rag.ClinicalKnowledgeRAG`: recuperación léxica top-K de criterios del protocolo.
5. Gemini (`google-genai` 2.28) con `response_schema` derivado de los modelos Pydantic (sanitizado para la API) y validación con `TriageOutputSchema.model_validate`. Prueba el modelo activo y luego modelos de respaldo, con un timeout por petición de `GEMINI_TIMEOUT_SECONDS`.
6. Si no hay clave, fallan todos los modelos o el worker no responde: motor de reglas, con un aviso explícito para el clínico.

**Privacidad:** antes de llamar a Gemini, `_pseudonymize` reemplaza nombre, documento y teléfono por marcadores; `_restore_identifiers` los reinyecta localmente.

**Respuestas de error:** 400 si la transcripción está vacía, 422 si el audio no contiene voz y 503 si el worker de transcripción no está disponible.

### 3.5. Métricas de evaluación
- `triage/metrics.py` contiene funciones puras: matriz de confusión, Kappa de Cohen con ponderación cuadrática, tasas de infratriaje y sobretriaje, y sensibilidad en niveles críticos (1–2). Devuelven `null` cuando no hay datos, en lugar de cifras inventadas.
- `GET /api/triage/sessions/evaluation_metrics/` informa la concordancia IA–médico (descrita como acuerdo, no como validación), las métricas contra la referencia ciega y la telemetría de tokens. La identidad del paciente solo se muestra a quien tenga `can_view_emr`.

### 3.6. Validación ciega del nivel de referencia
- Campos `reference_level`, `reference_by` y `reference_at` en `TriageSession` (migración `0005`).
- `GET /api/triage/sessions/blind_review_queue/` devuelve los casos pendientes con solo fecha, sexo, edad y transcripción: sin el nivel de la IA ni el del médico, y excluye las sesiones creadas por quien revisa.
- `POST /api/triage/sessions/<id>/reference_level/` registra el nivel. Es inmutable: 409 si ya existe, 403 si quien lo envía es el autor de la sesión. Usa `select_for_update` y queda en la auditoría como `TRIAGE_REFERENCE`.
- En el frontend, el panel `BlindReview` es la cola de adjudicación, y `MetricsDashboard` muestra la sección «Validación contra referencia ciega» para la IA y para el médico.

### 3.7. Benchmark reproducible
- `python manage.py evaluate_benchmark <casos.json|csv> --engine reglas|pipeline [--output detalle.json]` calcula concordancia exacta, Kappa ponderado, infratriaje, sobretriaje y sensibilidad en niveles 1–2, y lista los casos críticos infratriados. Con `--engine pipeline` ejecuta el análisis completo sin caché e informa qué motor resolvió cada caso.
- `backend/triage/benchmark/casos_sinteticos.json`: 65 casos (entre 11 y 15 por nivel) en lenguaje clínico y coloquial colombiano. Cada caso indica su tipo (`tipico`, `coloquial`, `negacion`, `signos_vitales`) y el criterio del protocolo que justifica su nivel de referencia. El conjunto se describe en `backend/triage/benchmark/README.md`.
- **Resultados del motor de reglas sobre el conjunto sintético:**

| Métrica | Antes de corregir los patrones | Después |
| :--- | ---: | ---: |
| Concordancia exacta | 41,5 % | 46,2 % |
| Kappa ponderado cuadrático | 0,096 | 0,159 |
| Infratriaje | 52,3 % | 49,2 % |
| Sobretriaje | 6,2 % | 4,6 % |
| Sensibilidad niveles 1–2 (28 casos) | 25,0 % | 28,6 % |

  Patrones corregidos: el sangrado vaginal en embarazadas y la diarrea o el vómito «sin deshidratación» nunca casaban por un `\b` mal colocado; no se reconocían plurales («convulsiones», «sibilancias»); «paro» y «coma» sueltos clasificaban como reanimación frases como «cuando me paro» o «que coma»; «glucosa > 400» no casaba; faltaba «gripa». Los casos no reconocidos son sobre todo paráfrasis, valores de signos vitales y negaciones (§4.2).

- **Cómo leer estas cifras:** los casos y sus niveles los redactó el equipo a partir del protocolo, y las correcciones se hicieron después de ver los fallos. Son una **línea base de regresión** (`test_benchmark_dataset.py` falla si empeoran), no una estimación del rendimiento clínico. El pipeline con Gemini aún no se ha medido sobre este conjunto.

### 3.8. Normalización clínica (SNOMED-CT / CIE-10)
- `POST /api/transcribe/normalize/` encola `normalize_clinical_text_task` en la cola `llm`. Gemini devuelve JSON estructurado, con timeout; si no hay clave, la llamada falla o el worker no responde, se usa el catálogo determinista de términos de urgencias.
- `NormalizationMonitor` compara el texto crudo con el estandarizado y muestra una tabla de códigos filtrable por categoría.

### 3.9. Simulador HCE e interoperabilidad
- `GET /api/triage/sessions/emr_patients/` y `POST /api/triage/sessions/<id>/assign_box/` permiten la asignación persistente y auditada de box. No se inventan box, estado, fecha de nacimiento ni EPS cuando faltan los datos.
- `POST /api/fhir/` valida la estructura de Bundles FHIR R4 (`triage/fhir_validation.py`), responde 422 si el Bundle no es válido y registra cada transacción en `FHIRMessageLog`. Los identificadores de encuentro usan `uuid4`. El frontend exporta Bundles FHIR R4 y mensajes HL7 v2.5.1.

### 3.10. ASR (`backend/transcription/`)
- `WhisperEngine` es un singleton con lock dentro del worker `asr`, que precarga el modelo al arrancar (`WHISPER_PRELOAD`) y publica su estado en Redis (`asr:engine_status`). El contexto textual de cada sesión de grabación vive en Redis, con un TTL de `ASR_SESSION_TTL` y un máximo de 2.000 caracteres.
- El modo de ejecución depende de `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE` y `WHISPER_MODEL_SIZE`, con fallback a CPU `int8`. La imagen de CPU no instala las librerías CUDA (`WITH_CUDA=false`). PyAV se fija en la versión 18.1.0 por compatibilidad con faster-whisper.
- Rendimiento medido en CPU con el modelo `small`: unos 3 s por fragmento de 5 s de audio.

### 3.11. Infraestructura y seguridad de transporte
- **nginx:** TLS 1.2/1.3 con certificado autofirmado generado al arrancar si no se monta uno real. Envía HSTS (`HSTS_MAX_AGE`), `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP y CSP, y oculta las cabeceras equivalentes del upstream y `X-Powered-By`.
- **Django:** `SECURE_PROXY_SSL_HEADER` (la cabecera la fija siempre nginx), cookies seguras, `CSRF_TRUSTED_ORIGINS`, `ALLOWED_HOSTS` por variable de entorno (sin comodín) y `SECRET_KEY` obligatoria. WhiteNoise sirve los estáticos del Django Admin.
- **Docker:** usuario no root, healthchecks en todos los servicios con estado, volúmenes `postgres_data`, `asr_model_cache` y `nginx_certs`. Modo GPU mediante `docker-compose.gpu.yml` o `COMPOSE_FILE` en `.env`.

### 3.12. Validación de entrada
- **Backend:** esquemas Pydantic v2 en `core/validation.py`, aplicados con `validate_payload`; el de configuración del sistema rechaza campos desconocidos (`extra='forbid'`).
- **Frontend:** validadores equivalentes con `zod` en `lib/validation.tsx`, con avisos visuales que no interrumpen el flujo clínico.

### 3.13. Interfaz
- El shell (`AppNavigation`) verifica la sesión contra `/api/auth/me/` y conmuta entre los paneles según los permisos: Triaje, Validación ciega, Métricas, HCE, Normalización, FHIR, Seguridad y Configuración.
- Diseño responsivo con drawer móvil y vistas de lista o detalle; accesibilidad WCAG 2.1 AA en el formulario de paciente; modales de confirmación al iniciar una nueva consulta y al ajustar el nivel; banner regulatorio minimizable. Las métricas de Lighthouse se optimizaron (CLS, contraste, peso de recursos).

### 3.14. Pruebas e integración continua
- **Backend (pytest):** 253 pruebas que pasan y 4 marcadas `xfail` estrictas, que documentan limitaciones conocidas del motor de reglas. Cubren autenticación, OTP y throttling, RBAC, cifrado, pacientes, sesiones y guardado atómico, motor de reglas (un caso por criterio, prioridad entre niveles, contrato de salida y regresiones), compresión, RAG, caché, métricas, validación ciega, benchmark, FHIR, tareas Celery, ASR con Whisper simulado y configuración de seguridad.
- **Frontend (Vitest + Testing Library):** 67 pruebas.
- **CI** (`.github/workflows/ci.yml`): tests de backend y frontend, lint y build.

---

## 4. Brechas Identificadas y Limitaciones Actuales

### 4.1. Validación clínica pendiente
- **Brecha:** no existe todavía un conjunto de casos reales con un nivel de referencia adjudicado por clínicos. El benchmark actual es sintético y lo redactó el propio equipo.
- **Impacto:** no hay evidencia sobre la exactitud clínica del sistema. La concordancia IA–médico no sirve como validación por el sesgo de anclaje.
- **Camino:** usar el módulo de validación ciega en un piloto (al menos dos revisores por caso y resolución de discrepancias por consenso), o etiquetar a ciegas un conjunto de casos con el formato de `evaluate_benchmark`. Después, medir `--engine pipeline` y reportar Kappa ponderado y sensibilidad en niveles 1–2 con sus intervalos de confianza.

### 4.2. Motor de reglas léxico
- **Brecha:** el motor solo reconoce las expresiones literales de su catálogo. En el conjunto sintético detecta el 28,6 % de los casos críticos. No interpreta negaciones («niega dolor torácico» se clasifica como nivel 2), no evalúa los **valores** de signos vitales («saturación 84 %», «presión 70/40») aunque `input_pipeline` ya los extrae, y no reconoce paráfrasis («habla enredado», «se le hunden las costillas»). Las cuatro limitaciones están fijadas como `xfail` estrictos en `test_clinical_protocol.py`.
- **Impacto:** cuando Gemini no está disponible, el respaldo infratriaja con frecuencia. La interfaz lo avisa, pero el profesional debe saber que ese resultado es solo una red de seguridad mínima.
- **Camino:** añadir reglas de escalado por signos vitales con umbrales definidos y validados por el equipo clínico, y un manejo básico de negaciones (tipo NegEx). Ninguna regla se debe ajustar contra el mismo conjunto con el que se evalúa.

### 4.3. Dependencia de un proveedor LLM externo
- **Brecha:** el triaje completo y la normalización dependen de Gemini, un servicio en la nube. Los identificadores directos se seudonimizan, pero el relato clínico sí sale de la institución.
- **Impacto:** el uso con pacientes reales exige evaluar el tratamiento de datos de salud por un tercero (Ley 1581 de 2012 y políticas institucionales) y la disponibilidad del servicio. Ante fallos o timeouts, el sistema degrada al motor de reglas (§4.2).

### 4.4. Interoperabilidad FHIR externa
- **Brecha:** `/api/fhir/` valida y persiste Bundles R4 localmente, pero no los reenvía a un servidor FHIR externo (HAPI-FHIR, Firely).
- **Camino:** una tarea Celery que retransmita el Bundle a un endpoint configurable, con reintentos.

### 4.5. Ontología SNOMED-CT completa
- **Brecha:** la normalización combina Gemini con un catálogo reducido de términos de urgencias; no incluye la release RF2 de SNOMED-CT (más de 350.000 conceptos).
- **Impacto:** la cobertura es aceptable para el triaje, pero los códigos que propone el LLM no se verifican contra un servidor terminológico (Snowstorm u Ontoserver).

### 4.6. ASR y hardware
- El modo GPU solo admite NVIDIA (CTranslate2 usa CUDA); en equipos con GPU AMD se ejecuta en CPU. El modo GPU está configurado pero no se ha probado en esta iteración sobre hardware NVIDIA real.
- El estado del motor que publica el worker (`asr:engine_status`) no caduca: se borra al apagar el worker de forma ordenada, pero si el proceso muere de golpe, el panel de configuración puede mostrar un estado obsoleto. `health_check` sí refleja si el worker responde.

### 4.7. Escalabilidad y mantenibilidad
- `evaluation_metrics` carga todas las sesiones en memoria para calcular las métricas; con volúmenes grandes conviene agregar en SQL o precalcular.
- `TriageDashboard.tsx` tiene 1.731 líneas y combina grabación, transcripción, formulario, resultado, historial y exportaciones; está pendiente dividirlo en componentes.
- El frontend declara la dependencia `@google/genai` sin usarla.

### 4.8. Seguridad residual
- La CSP incluye `'unsafe-inline'` en `script-src`, porque Next.js inyecta scripts de hidratación sin nonce. Para eliminarlo hace falta un middleware que genere nonces.
- El certificado autofirmado sirve para desarrollo; en producción hay que montar uno emitido por una CA en el volumen `nginx_certs`.
- Sin `FIELD_ENCRYPTION_KEY`, cambiar `SECRET_KEY` invalida las claves API guardadas.
- `TriageDashboard` lee el perfil cacheado en `localStorage` solo para mostrar u ocultar controles; la autorización real ocurre en el servidor.

### 4.9. Integración continua
- El workflow de CI está definido, pero todavía no se ha ejecutado en GitHub sobre esta rama.

---

## 5. Matriz de Endpoints

| Método | Endpoint | Descripción | Validación | Control de acceso |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login/` | Inicio de sesión: access token en el cuerpo, refresh en cookie httpOnly | `LoginSchema` | Público (10/min) |
| `POST` | `/api/auth/refresh/` | Renovación con rotación del refresh (cookie) | — | Público (cookie) |
| `POST` | `/api/auth/logout/` | Cierre de sesión e invalidación del refresh | — | JWT |
| `POST` | `/api/auth/register/` | Registro de personal y envío de OTP | `RegisterSchema` | Público (10/min) |
| `POST` | `/api/auth/verify/` · `/api/auth/resend-code/` | Verificación y reenvío del OTP | `VerifyCodeSchema` | Público (5/min) |
| `POST` | `/api/auth/password-reset/request/` | Solicitud de recuperación | `PasswordResetRequestSchema` | Público (10/min) |
| `POST` | `/api/auth/password-reset/confirm/` | Nueva contraseña con OTP | `PasswordResetConfirmSchema` | Público (5/min) |
| `GET` | `/api/auth/me/` | Perfil y permisos | — | JWT |
| `GET` | `/api/security/users/` | Directorio de usuarios | — | Admin |
| `PATCH` | `/api/security/users/<id>/permissions/` | Matriz de permisos | `UserPermissionUpdateSchema` | Admin |
| `GET` | `/api/security/audit/` | Registro de auditoría | — | Admin |
| `GET` / `POST` | `/api/config/` | Configuración de modelos y estado del ASR | `SystemConfigUpdateSchema` | JWT / Admin para modificar |
| `GET` / `POST` | `/api/config/keys/` | Claves API cifradas | `APIKeyCreateSchema` | JWT / Admin para registrar |
| `DELETE` | `/api/config/keys/<id>/` | Revocación de clave | — | Admin |
| `POST` | `/api/transcribe/` | Transcripción de un fragmento (worker `asr`) | — | `can_use_transcriber` |
| `POST` | `/api/transcribe/reset/` | Reinicio del contexto ASR de la sesión | — | `can_use_transcriber` |
| `POST` | `/api/transcribe/normalize/` | Normalización SNOMED-CT / CIE-10 (worker `llm`) | `NormalizeTextSchema` | JWT |
| `POST` | `/api/triage/sessions/analyze/` | Análisis y creación de la sesión (worker `llm`) | — | `can_register_patients` |
| `GET` | `/api/triage/sessions/history/` | Historial (propio; el admin ve todo) | — | JWT |
| `PATCH` | `/api/triage/sessions/<id>/override_level/` | Ajuste médico de nivel y síntomas | `TriageOverrideSchema` | `can_edit_symptoms` |
| `POST` | `/api/triage/sessions/<id>/assign_box/` | Asignación persistente de box | `EMRBoxAssignSchema` | `can_view_emr` |
| `GET` | `/api/triage/sessions/emr_patients/` | Admisiones para el simulador HCE | — | `can_view_emr` |
| `GET` | `/api/triage/sessions/evaluation_metrics/` | Concordancia, Kappa, seguridad, referencia ciega | — | JWT (identidad solo con `can_view_emr`) |
| `GET` | `/api/triage/sessions/blind_review_queue/` | Casos pendientes de adjudicación ciega | — | `can_edit_symptoms` |
| `POST` | `/api/triage/sessions/<id>/reference_level/` | Nivel de referencia ciego (inmutable) | — | `can_edit_symptoms`, distinto del autor |
| `GET` | `/api/triage/sessions/fhir_logs/` | Historial de transacciones FHIR | — | `can_view_fhir` |
| `POST` | `/api/fhir/` | Validación e ingestión de Bundles FHIR R4 | `FHIRSyncSchema` | JWT |
| `GET` | `/api/health_check/` | Estado del backend y del motor ASR | — | Público |

---

## 6. Recomendaciones para Producción

1. **Validación clínica antes de cualquier uso asistencial** (§4.1): piloto con validación ciega y reporte de sensibilidad en niveles 1–2.
2. **Reglas de signos vitales** en el motor determinista, con umbrales aprobados por el equipo clínico (§4.2).
3. **Certificado TLS real**, `FIELD_ENCRYPTION_KEY` definida, `DEBUG=False`, `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` con el dominio real, y `HSTS_MAX_AGE` ampliado una vez verificado HTTPS.
4. **GPU NVIDIA** para el worker ASR (`docker-compose.gpu.yml`) si se necesita el modelo `large-v3-turbo` con baja latencia.
5. **Acuerdo de tratamiento de datos** con el proveedor LLM, o evaluación de un modelo desplegado on-premise (§4.3).
6. **Copias de seguridad** del volumen de PostgreSQL y rotación periódica de `FIELD_ENCRYPTION_KEY` con re-cifrado de la bóveda.
