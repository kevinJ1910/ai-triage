# Auditoría Técnica Integral — AI-Triage

**Fecha de esta revisión:** 2026-10-26 (revisión 3)  
**Auditoría inicial:** 2026-09-10  
**Rama auditada:** `develop`  
**Alcance:** backend (Django/Python), frontend (Next.js/TypeScript), infraestructura Docker y nginx, modelo de datos, seguridad, validez de las métricas clínicas y deuda técnica.

Esta revisión actualiza el estado de los hallazgos de la auditoría inicial, contrastado con el código actual (no con el informe anterior), y añade los hallazgos posteriores. Dos hallazgos que el informe anterior daba por resueltos no lo estaban del todo (A-02 y A-11); se señalan como **corrección de estado**.

---

## 1. Severidades

| Nivel | Descripción |
|:------|:------------|
| **CRÍTICO** | Fallo de seguridad o de corrección con impacto directo en datos clínicos o en la decisión de triaje |
| **ALTO** | Deuda técnica o defecto que degrada de forma significativa la confiabilidad, la seguridad o la validez de los resultados |
| **MEDIO** | Inconsistencia de diseño, cobertura faltante o patrón subóptimo |
| **BAJO** | Mejora menor de calidad, legibilidad o consistencia |

---

## 2. Resumen

| | Resueltos | Pendientes |
| :--- | ---: | ---: |
| Auditoría inicial (A-01 … A-34) | 33 | 1 |
| Hallazgos posteriores (N-01 … N-22) | 22 | 0 |
| Riesgos abiertos de esta revisión (P-01 … P-08) | 1 | 7 |

Lo más importante de esta revisión:

1. **Validez de las métricas (N-01, N-02).** La concordancia IA–médico se presentaba como validación del sistema. Como el médico ve la sugerencia de la IA antes de decidir, esa cifra está inflada por el sesgo de anclaje. Ahora existe un nivel de referencia ciego y un benchmark reproducible.
2. **Motor de reglas (N-19).** El benchmark destapó patrones que nunca casaban; ya están corregidos. Sigue siendo un riesgo abierto (P-01) que el motor detecte solo el 28,6 % de los casos críticos del conjunto sintético cuando Gemini no está disponible.
3. **Timeout de Gemini inefectivo en Docker (N-20).** La imagen instalaba `google-genai 0.3.0`, que ignora el timeout configurado. Se actualizó a la versión 2.28.0 y se verificó con una llamada real.

---

## 3. Hallazgos de la Auditoría Inicial

| # | Sev. | Hallazgo | Estado | Resolución |
|:--|:-----|:---------|:-------|:-----------|
| A-01 | CRÍTICO | `TriageSessionViewSet` con `AllowAny` | **Resuelto** | `012d8a6`, endurecido en `184dda0`: todas las acciones exigen JWT y un permiso granular (`core/permissions.py`); las rutas CRUD genéricas ya no se exponen. |
| A-02 | CRÍTICO | Sin rate limiting en autenticación | **Resuelto** (corrección de estado) | `012d8a6` añadió los throttles `auth` (10/min) y `otp` (5/min), pero **el login y la confirmación de contraseña quedaron sin throttle propio**. Corregido en `92deeb3`. Los contadores se comparten vía Redis. |
| A-03 | ALTO | Refresh token sin lista negra ni logout | **Resuelto** | `012d8a6`: `token_blacklist`, `BLACKLIST_AFTER_ROTATION` y `POST /api/auth/logout/`. |
| A-04 | ALTO | Tokens JWT en `localStorage` | **Resuelto** | `c400bed`: refresh token en cookie `httpOnly` y access token solo en memoria; se purgan las claves heredadas. |
| A-05 | ALTO | `SECRET_KEY` con valor por defecto inseguro | **Resuelto** | `012d8a6`: obligatoria salvo en pytest. |
| A-06 | MEDIO | `ALLOWED_HOSTS = ['*']` | **Resuelto** | Lista desde variable de entorno, sin comodín. |
| A-07 | MEDIO | Endpoint FHIR público | **Resuelto** | `184dda0`: `POST /api/fhir/` exige JWT y `fhir_logs` exige `can_view_fhir`. |
| A-08 | ALTO | Historial de triajes solo en `localStorage` | **Resuelto** | `04a29c7`: `GET /api/triage/sessions/history/`; se purga el historial heredado. |
| A-09 | ALTO | `time.sleep(0.5)` en el endpoint FHIR | **Resuelto** | `012d8a6`. |
| A-10 | ALTO | Variable global `engine` en las vistas de transcripción | **Resuelto** | `9267476`: singleton `WhisperEngine`; desde `7e10125` el modelo solo se carga en el worker `asr`. |
| A-11 | ALTO | Llamada a Gemini sin timeout | **Resuelto** (corrección de estado) | `9267476` añadió el timeout en `ai_analyzer`, pero la imagen Docker instalaba `google-genai==0.3.0`, que lo ignora (`requests` sin timeout), y la normalización tampoco lo aplicaba. Corregido en `dae83f4` (normalización) y `e79dbfa` (SDK 2.28.0). Además, `run_task` limita la espera del backend con `LLM_TASK_TIMEOUT`. |
| A-12 | ALTO | `TriageSession.save()` recalcula en guardados parciales | **Resuelto** | `9267476`. |
| A-13 | MEDIO | `AuditLog` con `except Exception: pass` | **Resuelto** | Los fallos se registran con `logger.error(..., exc_info=True)`. |
| A-14 | MEDIO | `evaluation_metrics` carga todas las sesiones | **Resuelto** | `131c74e`: matrices con `GROUP BY` (como máximo 25 filas), totales con `aggregate()` y retención de síntomas recorrida por lotes. El número de consultas no crece con las sesiones (test dedicado). |
| A-15 | MEDIO | Valores inventados en `emr_patients` (box, fecha de nacimiento, EPS) | **Resuelto** | `63a62fa`: se devuelve `null` y la UI muestra «No registrado». |
| A-16 | MEDIO | `SystemConfigUpdateSchema` desalineado con el modelo | **Resuelto** | El esquema coincide con `SystemConfiguration`, rechaza campos extra y se aplica en la vista. |
| A-17 | MEDIO | `db.sqlite3` versionado | **Resuelto** | Excluido en `.gitignore`. |
| A-18 | BAJO | Logging duplicado con `FileHandler` manual | **Resuelto** | `LOGGING` centralizado en `settings.py`. |
| A-19 | ALTO | `useState<any>` en datos clínicos | **Resuelto** | `4e31c14`: interfaces tipadas. |
| A-20 | ALTO | `TriageDashboard.tsx` monolítico | **Pendiente** | Ha crecido de 1.451 a 1.731 líneas. Ver P-06. |
| A-21 | MEDIO | `fetchWithAuth` sin renovación automática | **Resuelto** | `4e31c14` y `c400bed`: una renovación compartida por las peticiones concurrentes. |
| A-22 | MEDIO | Perfil leído de `localStorage` sin validar | **Mitigado** | El shell obtiene el perfil de `/api/auth/me/`; `TriageDashboard` aún lee la copia cacheada, pero solo para mostrar u ocultar controles, porque la autorización ocurre en el servidor. Ver P-08. |
| A-23 | MEDIO | Validación de frontend no centralizada | **Parcial** | `lib/validation.tsx` (Zod) se usa en login y triaje; `ConfigPanel` y `SecurityPanel` siguen validando por su cuenta (BAJO). |
| A-24 | MEDIO | `GEMINI_API_KEY` en el contenedor del frontend | **Resuelto** | La clave solo está en el entorno compartido de backend y workers. |
| A-25 | BAJO | Puerto 5432 expuesto | **Resuelto** | `012d8a6`. |
| A-26 | BAJO | Nombre de acción de auditoría inconsistente (`ASSIGN_EMR_BOX`) | **Resuelto** | Ahora `EMR_BOX_ASSIGNED`. |
| A-27 | BAJO | `google-genai` en versión alfa | **Resuelto** | `e79dbfa`: 2.28.0 (ver A-11). |
| A-28 | MEDIO | Dependencias no usadas (`boto3`, `sendgrid`) | **Resuelto** | `9267476`. |
| A-29 | CRÍTICO | Detalles internos de excepción en respuestas del ASR | **Resuelto** | `3547a8a`. |
| A-30 | ALTO | `makemigrations` en el build de Docker | **Resuelto** | `3547a8a`: `entrypoint.sh` solo ejecuta `migrate`. |
| A-31 | ALTO | Usuario demo inseguro en producción | **Resuelto** | `3547a8a` y `e342c92` (ver N-17). |
| A-32 | MEDIO | Endpoints de cuentas y de administración mezclados | **Resuelto** | `3547a8a`: `/api/security/`. |
| A-33 | MEDIO | Validación de teléfonos inconsistente | **Resuelto** | `3547a8a`. |
| A-34 | MEDIO | Variables `.env` desconectadas de la bóveda | **Resuelto** | `16e74c5`. |

---

## 4. Hallazgos Posteriores a la Auditoría Inicial (todos resueltos)

### Validez clínica y de las métricas

**N-01 [CRÍTICO] La concordancia IA–médico se presentaba como validación.** El médico ve el nivel propuesto antes de ratificarlo, así que el acuerdo mide en parte el anclaje y no la exactitud. Además, sin sesiones el endpoint devolvía cifras fijas (concordancia del 100 % y Kappa de 0,88). *Resolución:* `ec87bec` sustituye las métricas por funciones puras y probadas (Kappa ponderado cuadrático, infratriaje, sobretriaje, sensibilidad en niveles 1–2, matriz de confusión) que devuelven `null` sin datos. `9db4069` y `4be8039` añaden el nivel de referencia ciego (asignado por un clínico distinto del autor, inmutable y auditado) con sus métricas y la interfaz `BlindReview`.

**N-02 [ALTO] Sin forma reproducible de medir el motor de triaje.** *Resolución:* `2a26532` añade el comando `evaluate_benchmark`, y `ff149fb` el conjunto de 65 casos sintéticos con una línea base de regresión. Ver P-02 sobre sus límites.

**N-03 [MEDIO] Las métricas exponían la identidad del paciente** a usuarios sin permiso de HCE. *Resolución:* `a98eba0`.

### Seguridad y privacidad

**N-04 [CRÍTICO] La caché clínica podía devolver datos de otro paciente.** La huella no preservaba negaciones ni orden, asumía vitales normales si faltaban y guardaba `patientInfo`. *Resolución:* `184dda0`, con pruebas de no filtración entre pacientes.

**N-05 [CRÍTICO] Endpoints ASR y FHIR sin autenticación ni permisos granulares.** *Resolución:* `184dda0`.

**N-06 [ALTO] Identificadores del paciente enviados en claro a Gemini.** *Resolución:* `ec87bec`: seudonimización de nombre, documento y teléfono antes de la llamada y restauración local. Los fallos del LLM no se guardan en caché.

**N-07 [ALTO] Bóveda dependiente de `SECRET_KEY`.** *Resolución:* `ec87bec`: `MultiFernet` con `FIELD_ENCRYPTION_KEY`, manteniendo la lectura de los cifrados heredados.

**N-08 [ALTO] Sin HTTPS ni cabeceras de seguridad.** Además, el micrófono no funcionaba fuera de `localhost`. *Resolución:* `a63dafc`: TLS en nginx, redirección 80→443, HSTS, CSP y demás cabeceras, más `SECURE_PROXY_SSL_HEADER`, cookies seguras y `CSRF_TRUSTED_ORIGINS` en Django.

**N-09 [MEDIO] Identificadores de encuentro FHIR predecibles.** *Resolución:* `401cde7` (`uuid4`).

**N-10 [MEDIO] Cualquier usuario autenticado podía sincronizar vocabularios.** *Resolución:* `2437455`: solo administradores o `can_manage_config`.

### Corrección funcional

**N-11 [ALTO] Validación FHIR simulada.** *Resolución:* `ec87bec`: `fhir_validation.py` valida la estructura R4 y responde 422.

**N-12 [ALTO] Guardado del triaje no atómico.** Un fallo intermedio dejaba paciente, transcripción y sesión inconsistentes. *Resolución:* `840da45` (`transaction.atomic`) y fechas en hora de Colombia.

**N-13 [MEDIO] Una transcripción vacía o un audio sin voz producían errores 500.** *Resolución:* `93eab7b`: respuestas 400 y 422.

**N-14 [ALTO] Whisper y Gemini se ejecutaban dentro de los procesos web.** Cada worker de Gunicorn cargaba su propio modelo, una llamada lenta bloqueaba la API y el estado (caché, contexto ASR, throttling) era local a cada proceso. *Resolución:* `7e10125`: workers Celery `asr` y `llm` con Redis, estado compartido en la caché de Django, fallback en línea si el worker LLM no responde y 503 si no responde el ASR.

**N-15 [ALTO] La imagen exigía GPU NVIDIA y no arrancaba con GPU AMD o sin GPU.** *Resolución:* `edbc5dd`: CPU por defecto (`int8`, `small`, sin librerías CUDA) y override `docker-compose.gpu.yml`.

**N-16 [ALTO] La transcripción fallaba con PyAV 19** (`metadata_errors`). *Resolución:* `ff7b83e`: PyAV fijado en 18.1.0.

**N-17 [MEDIO] Usuarios demo con contraseñas aleatorias que nadie conocía.** Sin `DEBUG` el backend podía no arrancar. *Resolución:* `e342c92`: sin contraseña definida no se crea el usuario y el log indica qué variable falta.

**N-18 [MEDIO] El Django Admin se servía sin CSS (404 en `/static/`).** *Resolución:* `0c26ae8`: WhiteNoise y ruta `/static/` en nginx.

**N-19 [ALTO] Patrones del motor de reglas que nunca casaban o casaban mal.** Un `\b` final tras prefijos (`embarazada.*sangr`, `diarrea.*sin deshidrat`) impedía detectar el sangrado vaginal en embarazadas (nivel 2) y la diarrea sin deshidratación; no se reconocían plurales («convulsiones»); «paro» y «coma» sueltos llevaban a reanimación frases como «cuando me paro»; «glucosa > 400» no casaba. *Resolución:* `12e00a6`, con pruebas de regresión y un caso por criterio. Concordancia en el benchmark sintético: del 41,5 % al 46,2 %.

**N-20 [ALTO] El timeout de Gemini no se aplicaba en Docker.** Ver A-11. *Resolución:* `e79dbfa`, verificado con una llamada real desde `worker-llm` (respuesta 200, timeout de 30.000 ms aplicado).

### Mantenibilidad

**N-21 [MEDIO] El box y el estado asistencial se guardaban dentro de `clinical_entities`.** Mezclaban datos operativos con las entidades clínicas extraídas por la IA, no se podían filtrar ni indexar y se colaban en las respuestas que exponen las entidades. *Resolución:* `666b569`: columnas `assigned_box` y `care_status` en `TriageSession`, con una migración (`0006`) que traslada los datos existentes, los retira del JSON y es reversible. El contrato de la API (`assigned_box`, `status`) no cambia.

**N-22 [BAJO] Restos de la plantilla de AI Studio en el frontend.** `next.config.ts` permitía imágenes remotas de `picsum.photos` (no se usa `next/image`) y contenía un ajuste de HMR para AI Studio; además había dependencias sin uso (`@google/genai`, `firebase-tools`) y el paquete se llamaba `ai-studio-applet`. *Resolución:* `f2c1ac1`.

---

## 5. Riesgos Abiertos

| # | Sev. | Riesgo | Recomendación |
|:--|:-----|:-------|:--------------|
| P-01 | ALTO | **El motor de reglas de respaldo detecta pocos casos críticos:** 28,6 % de los niveles 1–2 del conjunto sintético. No interpreta negaciones ni valores de signos vitales, y no reconoce paráfrasis (fijado con 4 `xfail` estrictos). | Reglas de escalado por signos vitales con umbrales validados clínicamente y manejo de negaciones. Mantener el aviso de respaldo en la UI. |
| P-02 | ALTO | **Sin validación clínica.** El benchmark es sintético, lo redactó el equipo y las correcciones del motor se hicieron viendo sus fallos; el pipeline con Gemini aún no se ha medido sobre él. | Piloto con validación ciega por clínicos o un conjunto etiquetado por expertos; reportar sensibilidad en niveles 1–2 con intervalos de confianza. |
| P-03 | MEDIO | **Envío del relato clínico a un proveedor externo** (Gemini), aunque seudonimizado. | Acuerdo de tratamiento de datos (Ley 1581 de 2012) o un modelo desplegado localmente. |
| P-04 | MEDIO | **CSP con `'unsafe-inline'` en `script-src`** (scripts de hidratación de Next.js sin nonce). | Middleware de Next.js que genere nonces por petición. |
| P-05 | MEDIO | **El estado del motor ASR (`asr:engine_status`) no caduca**: si el worker muere de golpe, el panel de configuración muestra un estado obsoleto. | Publicar el estado con TTL y renovarlo periódicamente (heartbeat). |
| P-06 | MEDIO | **`TriageDashboard.tsx` monolítico** (1.731 líneas, A-20). | Dividirlo en grabador, editor de transcripción, formulario, resultado, historial y exportaciones. |
| P-07 | BAJO | **Sin verificar en entorno real**: el modo GPU no se ha probado en hardware NVIDIA y el CI no se ha ejecutado aún en GitHub. | Probar el modo GPU y ejecutar el CI tras el push. |
| P-08 | BAJO | **Perfil cacheado en `localStorage`** para la UI (A-22). | **Resuelto** (`a454b08`): Inyectado directamente como prop `userProfile` desde `AppNavigation` hacia `TriageDashboard`, manteniendo compatibilidad con fallback local. |

---

## 6. Cobertura de Pruebas

| Área | Pruebas destacadas |
|:-----|:-------------------|
| `accounts` | Login, registro, OTP, recuperación de contraseña, throttling de login y de confirmación, cookies JWT y rotación, usuarios demo, RBAC y auditoría. |
| `triage`: motor de reglas | Un caso por criterio de los 5 niveles, insensibilidad a mayúsculas y tildes, prioridad del nivel más grave, contrato de salida, fallbacks, regresiones de N-19 y 4 limitaciones como `xfail` estrictos. |
| `triage`: benchmark | Validez del conjunto sintético, representación de los 5 niveles, línea base de regresión, ningún caso no urgente escalado a reanimación y el comando `evaluate_benchmark` (JSON, CSV, pipeline y errores). |
| `triage`: sesiones y métricas | Guardado atómico, 400/422/503, historial, override, box, Kappa ponderado, infratriaje, validación ciega (cola, inmutabilidad, autor excluido) y ocultación de identidad. |
| `triage`: pipeline LLM | Compresión, RAG, caché sin filtración entre pacientes, seudonimización, fallback sin caché y timeout. |
| `triage`: FHIR | Validación R4, 422 y logs. |
| `transcription` | Motor Whisper simulado, contexto en caché, endpoints autenticados, tareas Celery en línea, health check y normalización con fallback. |
| `system_settings` | Cifrado `MultiFernet`, compatibilidad con cifrados heredados, detección de proveedor, permisos de configuración y de vocabulario, y modelo ASR `auto`. |
| `core` | Esquemas Pydantic y `run_task` (`TaskUnavailable`). |
| Frontend | Navegación y drawer, validación ciega, métricas y referencia ciega, configuración, HCE, FHIR, normalización, seguridad, `fetchWithAuth` y validadores Zod. |

**Totales actuales:** backend, 261 pruebas que pasan y 4 `xfail` estrictos; frontend, 67 pruebas. CI en `.github/workflows/ci.yml`.
