# AI-Triage: Asistente Inteligente de Voz para la Clasificación Médica Automatizada

**AI-Triage** es una plataforma web de procesamiento de voz en tiempo real y soporte a la decisión clínica para el triaje en servicios de urgencias. Transcribe la consulta con un ASR clínico, normaliza la terminología a estándares médicos (SNOMED-CT / CIE-10), extrae entidades críticas y propone el nivel de prioridad (1 a 5) según el protocolo institucional Christus Sinergia Salud (Resolución 5596 de Minsalud), que el profesional ratifica o ajusta.

---

## Características Clave

* **ASR clínico en tiempo real (Faster-Whisper):** Transcripción en español por fragmentos de 4 s, con prompts de terminología médica y contexto de continuidad por sesión guardado en Redis con expiración (TTL).
* **CPU por defecto, GPU NVIDIA opcional:** El stack corre en cualquier equipo con Whisper en CPU (`int8`, modelo `small`). Con GPU NVIDIA, un override activa CUDA (`float16`, modelo `large-v3-turbo`). Ver [Ejecución con GPU NVIDIA](#ejecución-con-gpu-nvidia).
* **Inferencia en workers dedicados (Celery + Redis):** Whisper corre en `worker-asr` y Gemini en `worker-llm`; el proceso web solo valida, persiste y encola. Si el worker LLM no responde, el triaje se resuelve con el motor de reglas: el clínico nunca recibe un error por un fallo de la IA.
* **Motor de triaje con prioridad Christus Sinergia Salud:** Motor determinista de reglas (niveles 1 a 5) que se pasa como pauta prioritaria a Google Gemini y actúa como respaldo garantizado.
* **Pipeline de compresión, RAG y caché clínica:** Limpieza de la transcripción y extracción de signos vitales (`ClinicalTranscriptCompressor`), recuperación léxica top-K de criterios del protocolo (`ClinicalKnowledgeRAG`) y caché canónica SHA-256 compartida entre procesos (`ClinicalQueryCache`) con 0 tokens en consultas recurrentes.
* **Decodificación estructurada y gobernanza de tokens:** Salida guiada por esquema JSON y validada con Pydantic v2; telemetría de tokens persistida por sesión.
* **Seudonimización antes del LLM:** Nombre, documento y teléfono se reemplazan por marcadores antes de enviar el texto a Gemini y se restauran localmente.
* **Ratificación médica del nivel (human-in-the-loop):** Control para confirmar o ajustar el nivel sugerido, con motivo clínico y auditoría.
* **Métricas de concordancia y seguridad:** Kappa de Cohen ponderado cuadrático, infratriaje / sobretriaje, sensibilidad en niveles 1–2 y matriz de confusión.
* **Validación ciega contra nivel de referencia:** Un clínico distinto al tratante asigna el nivel viendo solo la transcripción; las métricas comparan IA y médico tratante contra esa referencia, sin el sesgo de anclaje de comparar contra el nivel final.
* **Benchmark reproducible:** Comando `evaluate_benchmark` para medir el motor de reglas o el pipeline completo contra un conjunto de casos con nivel de referencia (JSON o CSV).
* **Normalización ontológica (SNOMED-CT / CIE-10):** Traducción de relatos coloquiales a conceptos y códigos médicos con catálogo determinista de respaldo.
* **Simulador HCE / EMR:** Cola de pacientes clasificados con asignación persistente de box y auditoría.
* **Interoperabilidad FHIR R4:** Generación, validación estructural e historial de Bundles HL7 FHIR R4.
* **Bóveda de credenciales cifradas (Fernet):** Claves API cifradas en base de datos con `MultiFernet` (`FIELD_ENCRYPTION_KEY`) y exposición solo enmascarada.
* **Seguridad, RBAC y auditoría:** Roles `admin` / `medico` / `enfermero`, matriz granular de permisos aplicada en el servidor y `AuditLog` de acciones sensibles.
* **Autenticación endurecida:** OTP de 6 dígitos por correo (Mailpit en local), access token solo en memoria del cliente, refresh token en cookie httpOnly con rotación y lista negra, y limitación de tasa.
* **HTTPS y cabeceras de seguridad:** nginx termina TLS, redirige HTTP a HTTPS y añade CSP, HSTS configurable, `X-Frame-Options`, `Permissions-Policy` y más.
* **Pruebas automatizadas y CI:** 168 pruebas en Pytest (backend) y 67 en Vitest / Testing Library (frontend), ejecutadas en GitHub Actions junto con lint, build y comprobación de migraciones.

---

## Arquitectura del Proyecto

```
ai-triage/
├── backend/                              # API en Django 5 + Django REST Framework
│   ├── config/
│   │   ├── settings.py                   # Ajustes (JWT, HTTPS, Redis, Celery, throttles, logging, BD)
│   │   ├── celery.py                     # App Celery (colas 'asr' y 'llm')
│   │   └── urls.py                       # Enrutamiento maestro
│   ├── core/
│   │   ├── validation.py                 # Contratos de request en Pydantic v2
│   │   ├── permissions.py                # Permisos granulares (CanEditSymptoms, CanViewEMR, ...)
│   │   └── task_runner.py                # Encola en el worker y espera el resultado con timeout
│   ├── accounts/                         # Usuarios, OTP, JWT en cookie, RBAC y auditoría
│   ├── patients/                         # Modelo Patient
│   ├── triage/
│   │   ├── views.py                      # Analyze, historial, override, box, métricas, validación ciega, FHIR
│   │   ├── tasks.py                      # Tarea Celery de triaje (cola 'llm') y respaldo por reglas
│   │   ├── ai_analyzer.py                # Pipeline: reglas → compresión → caché → RAG → Gemini → respaldo
│   │   ├── clinical_protocol.py          # Motor determinista Christus Sinergia / Resolución 5596
│   │   ├── clinical_cache.py             # Caché clínica sobre Redis
│   │   ├── metrics.py                    # Kappa, infratriaje, sensibilidad, referencia ciega
│   │   └── management/commands/evaluate_benchmark.py
│   ├── transcription/
│   │   ├── whisper_engine.py             # Singleton Faster-Whisper; contexto por sesión en Redis
│   │   ├── tasks.py                      # Tareas Celery de transcripción (cola 'asr') y normalización
│   │   ├── normalizer.py                 # Normalización SNOMED-CT / CIE-10 (Gemini + catálogo)
│   │   └── views.py                      # Transcribe, reset, normalize, health check
│   ├── system_settings/                  # SystemConfiguration y bóveda de claves API
│   ├── scripts/entrypoint.sh             # Espera a Postgres/Redis, migra, crea demo y collectstatic
│   ├── Dockerfile                        # Python 3.12-slim; ARG WITH_CUDA para las librerías NVIDIA
│   └── requirements.txt / requirements-dev.txt
│
├── frontend/                             # Next.js 15 (App Router, React 19, Tailwind 4)
│   ├── app/                              # page.tsx (shell protegido), login/
│   ├── components/                       # TriageDashboard, EMRSimulator, FHIRMonitor, MetricsDashboard,
│   │                                     # NormalizationMonitor, BlindReview, SecurityPanel, ConfigPanel
│   ├── hooks/useWhisperASR.ts            # Captura de audio por fragmentos
│   ├── lib/api.ts                        # fetchWithAuth: token en memoria y refresh por cookie
│   └── tests/                            # Vitest + Testing Library
│
├── nginx/
│   ├── templates/                        # Configuración (TLS, proxy) y cabeceras de seguridad / CSP
│   ├── 10-generate-self-signed-cert.sh   # Certificado autofirmado si no se monta uno real
│   └── Dockerfile
│
├── docs/                                 # Despliegue, modelo de datos, auditoría e informe de brechas
├── .github/workflows/ci.yml              # Tests, lint, build y migraciones en cada push / PR
├── docker-compose.yml                    # Stack completo en modo CPU (funciona en cualquier equipo)
├── docker-compose.gpu.yml                # Override para GPU NVIDIA (worker-asr con CUDA)
└── .env.example                          # Plantilla documentada de variables
```

---

## Flujo de Integración y Servicios

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NAVEGADOR / TERMINAL CLÍNICO                    │
│              https://localhost (443; el 80 redirige a HTTPS)            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       NGINX (TLS 443 / redirección 80)                 │
│          Proxy inverso + cabeceras de seguridad (CSP, HSTS, ...)       │
├───────────────────────────────────┬────────────────────────────────────┤
│  /                                │ → frontend:3000 (Next.js 15)       │
│  /api/auth/, /api/security/       │ → backend:8000  (Django REST)      │
│  /api/triage/, /api/config/       │ → backend:8000  (Django REST)      │
│  /api/transcribe/, /api/fhir/     │ → backend:8000  (Django REST)      │
│  /admin/                          │ → backend:8000  (Django Admin)     │
└───────────────┬───────────────────┴─────────────────┬──────────────────┘
                │                                     │
                ▼                                     ▼
     ┌──────────────────────┐              ┌──────────────────────┐
     │  FRONTEND CONTAINER  │              │  BACKEND (Gunicorn)  │
     │   (Node 20 Alpine)   │              │ (Python 3.12-slim)   │
     │                      │              │                      │
     │  • Next.js App       │              │  • API REST + RBAC   │
     │  • fetchWithAuth     │              │  • Pydantic v2       │
     │  • Auto-refresh JWT  │              │  • SimpleJWT + Auth  │
     │  • Reactive UI       │              │  • Encola inferencia │
     └──────────────────────┘              └──────────┬───────────┘
                                                      │ Celery (Redis)
                          ┌───────────────────────────┼──────────────────────┐
                          ▼                           ▼                      ▼
               ┌─────────────────────┐    ┌─────────────────────┐  ┌─────────────────┐
               │ WORKER-ASR (asr)    │    │ WORKER-LLM (llm)    │  │    REDIS 7      │
               │ Faster-Whisper      │    │ Gemini: triaje y    │  │ Broker, caché   │
               │ CPU o GPU NVIDIA    │    │ normalización       │  │ clínica, ASR    │
               └─────────────────────┘    └──────────┬──────────┘  └─────────────────┘
                                                     ▼
┌─────────────────┐  ┌─────────────────┐   ┌─────────────────┐
│   POSTGRESQL    │  │    MAILPIT      │   │  GOOGLE GEMINI  │
│  (Persistencia) │  │  (SMTP 1025 /   │   │  (Inferencia    │
│  Puerto interno │  │   Web UI 8025)  │   │   IA Externa)   │
└─────────────────┘  └─────────────────┘   └─────────────────┘
```

---

## Servicios Docker Orquestados

| Servicio | Contenedor | Puertos | Propósito |
| :--- | :--- | :--- | :--- |
| `nginx` | `ai_triage_nginx` | `80`, `443` | Entrada única: TLS, redirección a HTTPS, cabeceras de seguridad y proxy |
| `frontend` | `ai_triage_frontend` | `3000` (interno) | Interfaz Next.js 15 en modo standalone |
| `backend` | `ai_triage_backend` | `8000` (interno) | Gunicorn + Django REST: API, RBAC, persistencia; encola la inferencia |
| `worker-asr` | `ai_triage_worker_asr` | — | Celery, cola `asr`: Faster-Whisper cargado una sola vez (CPU o GPU) |
| `worker-llm` | `ai_triage_worker_llm` | — | Celery, cola `llm`: llamadas a Gemini (triaje y normalización) |
| `postgres` | `ai_triage_postgres` | `5432` (interno) | PostgreSQL 16 |
| `redis` | `ai_triage_redis` | `6379` (interno) | Broker de Celery, caché clínica, contexto ASR y throttling |
| `mailpit` | `ai_triage_mailpit` | `1025`, `8025` | SMTP local y visor web de correos OTP |

Volúmenes persistentes: `postgres_data`, `redis_data`, `nginx_certs` (certificados TLS), `asr_model_cache` (modelos Whisper descargados) y `audio_uploads`.

---

## Requisitos del Sistema

* **Docker Engine** 24.0+ y **Docker Compose** v2.20+ (en Windows, Docker Desktop con backend WSL2).
* **Memoria RAM:** mínimo 8 GB; 16 GB recomendados.
* **Almacenamiento:** mínimo 10 GB libres (unos GB más en modo GPU por las librerías CUDA y el modelo grande).
* **GPU (opcional):** solo NVIDIA. Las GPU AMD no son compatibles con faster-whisper/CTranslate2 dentro de Docker; en esos equipos se usa el modo CPU.
* **Desarrollo sin Docker:** Python 3.12 con entorno virtual en `backend/.venv`, Node.js 20+ y `pnpm`.

---

## Inicio Rápido con Docker (modo CPU)

Funciona en cualquier equipo, con o sin GPU.

### 1. Clonar el repositorio y configurar el entorno

```bash
git clone https://github.com/kevinJ1910/ai-triage.git
cd ai-triage
cp .env.example .env
```

Variables mínimas en `.env`:

```env
# Obligatoria (sin valor por defecto). Generar con:
#   python -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY=...

# Clave de Google Gemini para triaje y normalización (sin ella se usa el motor de reglas)
GEMINI_API_KEY=...

# Usuarios demo: solo se crean los que tengan contraseña definida
CREATE_DEMO_USERS=True
DEMO_ADMIN_PASSWORD=una_contraseña_segura
DEMO_NURSE_PASSWORD=otra_contraseña_segura
```

Opcionales: `WHISPER_MODEL_SIZE` (por defecto `small` en CPU), `WHISPER_CPU_THREADS` (por defecto 4), `POSTGRES_PASSWORD`, `HSTS_MAX_AGE`. Todas están documentadas en `.env.example`.

### 2. Levantar los servicios

```bash
docker compose up --build -d
```

La primera vez `worker-asr` descarga el modelo Whisper (unos 500 MB para `small`); después queda en el volumen `asr_model_cache`.

### 3. Verificar

```bash
docker compose ps                                         # todos deben estar Up / healthy
curl -k https://localhost/api/health_check/               # inference_mode "worker", asr.model_loaded true
docker compose logs -f backend worker-asr worker-llm
```

Interfaces:
* **Aplicación clínica:** `https://localhost/` (certificado autofirmado en desarrollo: aceptar la advertencia del navegador)
* **Correos OTP (Mailpit):** `http://localhost:8025/`
* **Django Admin:** `https://localhost/admin/`

---

## Ejecución con GPU NVIDIA

Solo para equipos con GPU NVIDIA. El modo GPU cambia únicamente `worker-asr`: usa CUDA con `float16`, el modelo `large-v3-turbo`, reserva la GPU y construye la imagen con las librerías CUDA/cuDNN (`WITH_CUDA=true`).

### 1. Requisitos (una sola vez)

* Driver NVIDIA reciente con soporte CUDA 12.
* **Windows:** Docker Desktop con backend WSL2 (incluye el soporte de GPU).
* **Linux:** [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) instalado y configurado para Docker.

Comprobar que Docker ve la GPU:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Si aparece la tabla con la GPU, el equipo está listo.

### 2. Activar el modo GPU

Opción A, en cada arranque:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
```

Opción B, de forma permanente en el `.env` de ese equipo, para usar `docker compose` sin más:

```env
# Windows (separador ';')
COMPOSE_FILE=docker-compose.yml;docker-compose.gpu.yml
# Linux / macOS (separador ':')
# COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml
```

```bash
docker compose up --build -d
```

`--build` es necesario la primera vez y cada vez que se cambia entre CPU y GPU, porque la imagen es distinta. La primera ejecución descarga `large-v3-turbo` (unos 1,6 GB).

### 3. Verificar que usa la GPU

```bash
docker compose logs worker-asr | grep "Modelo cargado"     # debe decir: en 'cuda' (float16)
curl -k https://localhost/api/health_check/                # "device": "cuda"
```

El Panel de Configuración muestra también el dispositivo y el modelo en uso. Si CUDA no se puede inicializar, el motor cae automáticamente a CPU `int8` y lo indica en el log de `worker-asr`.

### Selección del modelo ASR

El modelo se decide por equipo con `WHISPER_MODEL_SIZE` (`tiny`, `base`, `small`, `medium`, `large-v3-turbo`, `large-v3`). En el Panel de Configuración, la opción **"Según entorno"** (por defecto) respeta ese valor; elegir un modelo concreto lo impone en esa instalación y se aplica al reiniciar `worker-asr` (`docker compose restart worker-asr`).

---

## Solución de Problemas

| Síntoma | Causa y solución |
| :--- | :--- |
| `dependency failed to start: container ai_triage_backend is unhealthy` y en `docker compose logs backend` aparece `password authentication failed` | El volumen de Postgres se creó con otra contraseña (por ejemplo, de una versión anterior del proyecto); `POSTGRES_PASSWORD` solo se aplica al crear el volumen. Si no hay datos que conservar: `docker compose down`, `docker volume ls` para ver el nombre exacto y `docker volume rm <carpeta>_postgres_data`. **Esto borra la base de datos.** |
| `could not select device driver "nvidia"` | Docker no tiene acceso a la GPU: revisar los requisitos del modo GPU o arrancar en modo CPU (sin el override). |
| No se puede iniciar sesión con los usuarios demo | Si no existen, definir `CREATE_DEMO_USERS=True`, `DEMO_ADMIN_PASSWORD` y `DEMO_NURSE_PASSWORD` en `.env`; si ya existen con otra contraseña, añadir también `RESET_DEMO_PASSWORDS=True`. Luego `docker compose up -d backend`. |
| El navegador no permite el micrófono desde otro equipo de la red | Los navegadores solo permiten el micrófono en HTTPS o `localhost`: acceder por `https://` y aceptar el certificado. |
| `health_check` devuelve `"status": "degraded"` | `worker-asr` no ha terminado de cargar el modelo o está caído: `docker compose logs worker-asr`. |

---

## Matriz de Endpoints de la API

Todas las rutas requieren `Authorization: Bearer <access token>` salvo las marcadas como públicas.

| Método | Endpoint | Descripción | Control de acceso |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login/` | Inicio de sesión: access token en el cuerpo, refresh en cookie httpOnly | Público |
| `POST` | `/api/auth/refresh/` | Renovación del access token con rotación del refresh (cookie) | Público (cookie) |
| `POST` | `/api/auth/logout/` | Cierre de sesión e invalidación del refresh | JWT |
| `POST` | `/api/auth/register/` | Registro de personal y envío de OTP | Público (10/min) |
| `POST` | `/api/auth/verify/` · `/api/auth/resend-code/` | Verificación y reenvío del código OTP | Público (5/min) |
| `POST` | `/api/auth/password-reset/request/` · `/confirm/` | Recuperación de contraseña | Público |
| `GET` | `/api/auth/me/` | Perfil y permisos del usuario | JWT |
| `GET` | `/api/security/users/` | Directorio de usuarios | Admin |
| `PATCH` | `/api/security/users/<id>/permissions/` | Matriz de permisos de un usuario | Admin |
| `GET` | `/api/security/audit/` | Registro de auditoría | Admin |
| `GET` / `POST` | `/api/config/` | Configuración de modelos y estado del motor ASR | JWT / Admin para modificar |
| `GET` / `POST` | `/api/config/keys/` | Listado y registro de claves API cifradas | JWT / Admin para registrar |
| `DELETE` | `/api/config/keys/<id>/` | Revocación de clave API | Admin |
| `POST` | `/api/transcribe/` | Transcripción de un fragmento de audio (worker `asr`) | `can_use_transcriber` |
| `POST` | `/api/transcribe/reset/` | Reinicio del contexto de una sesión ASR | `can_use_transcriber` |
| `POST` | `/api/transcribe/normalize/` | Normalización SNOMED-CT / CIE-10 (worker `llm`) | JWT |
| `POST` | `/api/triage/sessions/analyze/` | Análisis de triaje y creación de la sesión (worker `llm`) | `can_register_patients` |
| `GET` | `/api/triage/sessions/history/` | Historial de triajes (propios; el admin ve todos) | JWT |
| `PATCH` | `/api/triage/sessions/<id>/override_level/` | Ajuste médico del nivel y síntomas | `can_edit_symptoms` |
| `POST` | `/api/triage/sessions/<id>/assign_box/` | Asignación persistente de box | `can_view_emr` |
| `GET` | `/api/triage/sessions/emr_patients/` | Admisiones para el simulador HCE | `can_view_emr` |
| `GET` | `/api/triage/sessions/evaluation_metrics/` | Concordancia, Kappa, seguridad y validación ciega | JWT (identidad del paciente solo con `can_view_emr`) |
| `GET` | `/api/triage/sessions/blind_review_queue/` | Casos pendientes de adjudicación ciega (sin niveles) | `can_edit_symptoms` |
| `POST` | `/api/triage/sessions/<id>/reference_level/` | Registro del nivel de referencia ciego (inmutable) | `can_edit_symptoms`, distinto del autor |
| `GET` | `/api/triage/sessions/fhir_logs/` | Historial de transacciones FHIR | `can_view_fhir` |
| `POST` | `/api/fhir/` | Validación e ingestión de Bundles FHIR R4 | JWT |
| `GET` | `/api/health_check/` | Estado del backend y del motor ASR | Público |

---

## Ejecución de Pruebas Automatizadas

### Backend (Django + Pytest): 261 pruebas

Además hay 4 `xfail` estrictos que documentan limitaciones conocidas del motor de reglas. Cubren autenticación, OTP, RBAC, cifrado, pacientes, sesiones de triaje, protocolo clínico (un caso por criterio y regresiones), compresión, RAG, caché, métricas y validación ciega, FHIR, tareas Celery (en modo en línea), motor ASR (con Whisper simulado), configuración de seguridad y el comando de benchmark.

```bash
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m pytest backend
docker compose exec backend pytest            # dentro del contenedor
```

En pytest las tareas Celery se ejecutan en línea y la caché es local al proceso: no hace falta Redis.

### Frontend (Next.js + Vitest + Testing Library): 67 pruebas

```bash
pnpm --dir frontend test
pnpm --dir frontend run lint
pnpm --dir frontend run build
```

### Benchmark del motor de triaje

Mide el motor contra un conjunto de casos con nivel de referencia (`id`, `transcript`, `reference_level` en JSON o CSV). El repositorio incluye 65 casos sintéticos en [`backend/triage/benchmark/`](backend/triage/benchmark/README.md):

```bash
backend/.venv/Scripts/python.exe backend/manage.py evaluate_benchmark backend/triage/benchmark/casos_sinteticos.json --engine reglas
backend/.venv/Scripts/python.exe backend/manage.py evaluate_benchmark casos.csv --engine pipeline --output resultados.json
```

`--engine pipeline` usa el análisis completo (Gemini si hay clave) sin caché. Los casos sintéticos los redactó el equipo a partir del protocolo: sirven como línea base de regresión, no como validación clínica. Para eso hace falta un conjunto con nivel asignado por clínicos (por ejemplo, mediante la validación ciega de la aplicación).

---

## Autores y Créditos Institucionales

* **Kevin Jordan Alzate** - [kevin.jordan@correounivalle.edu.co](mailto:kevin.jordan@correounivalle.edu.co)
* **Junior Orlando Cantor Arevalo** - [junior.cantor@correounivalle.edu.co](mailto:junior.cantor@correounivalle.edu.co)
* **Director de Proyecto:** Carlos Mauricio Gaona Cuevas

*Trabajo de Grado desarrollado en la Escuela de Ingeniería de Sistemas y Computación de la **Universidad del Valle**, Cali, Colombia (2026).*
