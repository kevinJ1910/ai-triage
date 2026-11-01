# AI-Triage: Asistente Inteligente de Voz para la Clasificación Médica Automatizada

**AI-Triage** es una plataforma web de procesamiento de voz en tiempo real y soporte a la decisión clínica para el triaje en servicios de urgencias hospitalarias. Transcribe la consulta con un ASR clínico adaptado acústicamente, extrae entidades biomédicas mediante modelos RoBERTa especializados (Model Soup), normaliza la terminología a estándares médicos internacionales (SNOMED CT / CIE-10 / ATC), recupera guías institucionales mediante un RAG híbrido (`pgvector` + Okapi BM25) y propone el nivel de prioridad (1 a 5) según el protocolo Christus Sinergia Salud (Resolución 5596 de Minsalud), bajo un flujo centrado en el profesional médico (*human-in-the-loop*) y con interoperabilidad dual HL7 v2.5.1 / FHIR R4.

---

## Características Clave

* **ASR clínico en tiempo real (Faster-Whisper):** Transcripción en español por fragmentos de 4 s con preprocesamiento acústico adaptativo (filtro pasa-altos a 80 Hz y normalización RMS a −20 dBFS), inyección dinámica de *hotwords* médicas y contexto de continuidad por sesión guardado en Redis con expiración (TTL). WER empírico de **2,39 %** (1,87 % en silencio y 2,90 % bajo ruido hospitalario de 60–65 dB) y RTF de **0,044** en GPU NVIDIA RTX 3070 (`large-v3-turbo`, `int8_float16`), frente a un WER de **7,53 %** y RTF de **0,142** en CPU (`small`, `int8`).
* **CPU por defecto, GPU NVIDIA opcional:** El stack corre en cualquier equipo con Whisper en CPU (`int8`, modelo `small`). Con GPU NVIDIA, un override activa CUDA (`int8_float16`, modelo `large-v3-turbo`) y reserva la GPU tanto para `worker-asr` como para `llm-local`. Ver [Ejecución con GPU NVIDIA](#ejecución-con-gpu-nvidia).
* **Inferencia en workers dedicados (Celery + Redis):** Whisper corre en `worker-asr` y los modelos de lenguaje en `worker-llm`; el proceso web solo valida, persiste y encola. Si el worker LLM no responde, el triaje se resuelve deterministamente con el motor de reglas: el clínico nunca recibe un error por un fallo de la IA.
* **Motor de triaje con prioridad Christus Sinergia Salud:** Motor determinista de reglas (niveles 1 a 5) que evalúa signos vitales críticos, banderas rojas y criterios clínicos de urgencia, sirviendo de respaldo garantizado a los modelos de lenguaje.
* **LLM local soberano (Ollama en GPU / CPU):** Soporte de modelos locales como Gemma 4 E4B (`gemma4:e4b-it-qat`) y Qwen 2.5 7B en el propio servidor hospitalario, con el mismo prompt y esquema JSON que Gemini, garantizando privacidad total y cumplimiento de soberanía de datos de salud. Ver [Ejecución con modelos locales](#ejecución-con-modelos-locales-ollama).
* **Extracción biomédica NER y Model Soup:** Modelo RoBERTa biomédico ajustado (`HoraYMedia/ai-triage-ner-roberta@v1`) ensamblado mediante técnicas de *Model Soup* (`ml/ner/model_soup.py`), complementado con normalizador multicapa determinista validado en CodiEsp (SNOMED CT, CIE-10 y ATC).
* **Pipeline de compresión, RAG híbrido y caché clínica:** Limpieza de la transcripción y extracción de signos vitales (`ClinicalTranscriptCompressor`), recuperación híbrida top-K de criterios del protocolo combinando similitud semántica con `pgvector` y ranking léxico Okapi BM25 (`ClinicalKnowledgeRAG`), y caché canónica SHA-256 (`ClinicalQueryCache`) con 0 tokens en consultas recurrentes.
* **Decodificación estructurada y gobernanza de tokens:** Salida guiada por esquema JSON y validada con Pydantic v2; telemetría de tokens, modelo y tiempo de razonamiento persistida por sesión.
* **Seudonimización antes del LLM:** Nombre, documento y teléfono se reemplazan por marcadores antes de enviar el texto al LLM y se restauran localmente tras la inferencia.
* **Ratificación médica del nivel (human-in-the-loop):** Control interactivo para confirmar o ajustar el nivel sugerido, con motivo clínico y auditoría inmutable.
* **Métricas de concordancia y seguridad clínica:** Kappa cuadrático de Cohen (0,898 en test con IA local), infratriaje / sobretriaje, sensibilidad crítica en niveles I–II (92,5 % en test) y matrices de confusión detalladas.
* **Validación ciega y evaluación metodológica:** Módulo de adjudicación ciega (`BlindReview`) donde un clínico independiente clasifica los casos sin conocer los niveles sugeridos ni el modelo, evaluando además la justificación con escalas Likert (claridad 4,80, pertinencia 4,58, fidelidad 4,58; Kappa clínico-IA de 0,911 en test).
* **Corpus y Benchmark reproducible:** Corpus de 250 casos clínicos anotados y auditados (150 en *dev*, 100 en *test* con doble anotación ciega y Kappa inter-anotador 0,865) ejecutable mediante `evaluate_benchmark` y `evaluate_extraction`.
* **Simulador HCE / EMR e interoperabilidad dual:** Cola de pacientes clasificados con gestión persistente de estado asistencial y notas de evolución, y receptor integrado compatible tanto con **HL7 FHIR Release 4** (JSON Bundles) como con **HL7 v2.5.1** (mensajes ER7 `ADT^A08`).
* **Bóveda de credenciales cifradas (Fernet):** Claves API cifradas en base de datos con `MultiFernet` (`FIELD_ENCRYPTION_KEY`) y exposición solo enmascarada.
* **Seguridad, RBAC y auditoría:** Roles `admin` / `medico` / `enfermero`, matriz granular de permisos aplicada en el servidor y `AuditLog` de acciones sensibles.
* **Autenticación endurecida:** OTP de 6 dígitos por correo (Mailpit en local), access token solo en memoria del cliente, refresh token en cookie httpOnly con rotación y lista negra, y limitación de tasa.
* **HTTPS y cabeceras de seguridad:** nginx termina TLS, redirige HTTP a HTTPS y añade CSP, HSTS configurable, `X-Frame-Options`, `Permissions-Policy` y más.
* **Pruebas automatizadas y CI:** 640 pruebas en Pytest (597 en `backend` + 43 en `ml`, con 1 `xfail` documentado) y 91 pruebas en 14 suites en Vitest (`frontend`) — **731 pruebas automatizadas** en total — ejecutadas en GitHub Actions (`ci.yml`) con comprobación de migraciones Django, linter ESLint y build de producción Next.js.

---

## Arquitectura del Proyecto

```
ai-triage/
├── backend/                              # API en Django 5.2 / 6.x + Django REST Framework
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
│   │   ├── ai_analyzer.py                # Pipeline: reglas → compresión → caché → RAG híbrido → LLM → respaldo
│   │   ├── clinical_rag.py               # RAG híbrido (pgvector + Okapi BM25 sobre 61 criterios)
│   │   ├── ner_model.py                  # Cliente e inferencia del extractor biomédico RoBERTa
│   │   ├── local_llm.py                  # Cliente del LLM local (Ollama u otro servidor compatible OpenAI)
│   │   ├── clinical_protocol.py          # Motor determinista Christus Sinergia / Resolución 5596
│   │   ├── clinical_cache.py             # Caché clínica sobre Redis (SHA-256 canónico)
│   │   ├── metrics.py                    # Kappa cuadrático, infratriaje, sensibilidad, bootstrap IC95
│   │   ├── benchmark/                    # Corpus clínico (250 casos dev/test, doble anotación y resultados)
│   │   └── management/commands/          # evaluate_benchmark, evaluate_extraction, compare_engines, ...
│   ├── transcription/
│   │   ├── whisper_engine.py             # Singleton Faster-Whisper, audio cleaner y contexto continuo Redis
│   │   ├── tasks.py                      # Tareas Celery de transcripción (cola 'asr') y normalización
│   │   ├── normalizer.py                 # Normalización SNOMED-CT / CIE-10 / ATC (Gemini + catálogo)
│   │   ├── terminology/                  # Catálogo clínico determinista indexado
│   │   └── views.py                      # Transcribe, reset, normalize, health check
│   ├── system_settings/                  # SystemConfiguration y bóveda de claves API
│   ├── scripts/entrypoint.sh             # Espera a Postgres/Redis, migra, crea demo y collectstatic
│   ├── Dockerfile                        # Python 3.12-slim; ARG WITH_CUDA para las librerías NVIDIA
│   └── requirements.txt / requirements-dev.txt
│
├── frontend/                             # Next.js 15 (App Router, React 19, Tailwind CSS, TypeScript)
│   ├── app/                              # page.tsx (shell protegido), login/
│   ├── components/                       # TriageDashboard, EMRSimulator, FHIRMonitor, MetricsDashboard,
│   │                                     # NormalizationMonitor, BlindReview, SecurityPanel, ConfigPanel
│   ├── hooks/useWhisperASR.ts            # Captura de audio por fragmentos con hotwords y VU meter
│   ├── lib/api.ts                        # fetchWithAuth: token en memoria y refresh por cookie
│   └── tests/                            # Vitest + Testing Library (14 suites, 93 tests)
│
├── ml/                                   # Modelos y scripts de Machine Learning
│   └── ner/
│       ├── model_soup.py                 # Ensamble por interpolación de pesos (Model Soup) para RoBERTa
│       ├── train_ner.py                  # Fine-tuning de RoBERTa biomédico sobre entidades clínicas
│       ├── revision_corpus.py            # Verificación de integridad de spans y consistencia del corpus
│       └── error_analysis.py             # Análisis de errores y métricas macro/micro F1
│
├── nginx/
│   ├── templates/                        # Configuración (TLS, proxy) y cabeceras de seguridad / CSP
│   ├── 10-generate-self-signed-cert.sh   # Certificado autofirmado si no se monta uno real
│   └── Dockerfile
│
├── docs/                                 # Despliegue, manual de usuario/admin, modelo de datos, auditoría y evaluación
├── .github/workflows/ci.yml              # Pipeline único de CI (backend + frontend) en push y PR
├── docker-compose.yml                    # Stack completo en modo CPU (funciona en cualquier equipo)
├── docker-compose.gpu.yml                # Override para GPU NVIDIA (worker-asr con CUDA y GPU para llm-local)
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
| `worker-asr` | `ai_triage_worker_asr` | — | Celery, cola `asr`: Faster-Whisper con hotwords y preprocesado (CPU o CUDA) |
| `worker-llm` | `ai_triage_worker_llm` | — | Celery, cola `llm`: triaje con Gemini o LLM local, normalización ontológica y RoBERTa NER |
| `llm-local` | `ai_triage_llm_local` | `11434` (interno) | Opcional, perfil `llm-local`: Ollama con Gemma 4 / Qwen 2.5 (CPU o GPU NVIDIA) |
| `postgres` | `ai_triage_postgres` | `5432` (interno) | PostgreSQL 16 + extensión `pgvector` para persistencia y RAG vectorial |
| `redis` | `ai_triage_redis` | `6379` (interno) | Broker de Celery, caché clínica SHA-256, contexto ASR y limitación de tasa |
| `mailpit` | `ai_triage_mailpit` | `1025`, `8025` | SMTP local y visor web de correos OTP |

Volúmenes persistentes: `postgres_data`, `redis_data`, `nginx_certs` (certificados TLS), `asr_model_cache` (modelos Whisper descargados), `ner_model_cache` (modelo RoBERTa biomédico), `ollama_models` (modelos del LLM local) y `audio_uploads`.

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

Solo para equipos con GPU NVIDIA. El modo GPU configura `worker-asr` con CUDA (`int8_float16`, modelo `large-v3-turbo`, `beam_size=2`), reserva la GPU tanto para `worker-asr` como para `llm-local` (Ollama) y construye la imagen con las librerías CUDA/cuDNN (`WITH_CUDA=true`).

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
docker compose logs worker-asr | grep "Modelo cargado"     # debe decir: en 'cuda' (int8_float16)
curl -k https://localhost/api/health_check/                # "device": "cuda"
```

El Panel de Configuración muestra también el dispositivo y el modelo en uso. Si CUDA no se puede inicializar, el motor cae automáticamente a CPU `int8` y lo indica en el log de `worker-asr`.

### Selección del modelo ASR

El modelo se decide por equipo con `WHISPER_MODEL_SIZE` (`tiny`, `base`, `small`, `medium`, `large-v3-turbo`, `large-v3`). En el Panel de Configuración, la opción **"Según entorno"** (por defecto) respeta ese valor; elegir un modelo concreto lo impone en esa instalación y se aplica al reiniciar `worker-asr` (`docker compose restart worker-asr`).

---

## Ejecución con modelos locales (Ollama)

El triaje puede usar un LLM que corre **en el propio servidor** en vez de Gemini. Así ningún dato del paciente sale del hospital y no hace falta clave de API. El servicio `llm-local` (Ollama) está en `docker-compose.yml` bajo un perfil, así que no arranca salvo que se pida.

- El modelo local recibe **el mismo prompt, la misma pauta de reglas y el mismo esquema** que Gemini.
- Si no responde a tiempo, clasifica el motor de reglas. **Nunca se recurre a Gemini**: quien elige el motor local lo hace por privacidad.

| Modelo | Descarga | Razonamiento | Resultado en *dev* (exactitud / Kappa) | Latencia en CPU (portátil) | Memoria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gemma4:e4b-it-qat` (Gemma 4 E4B) | 6,1 GB | Sí | 65,3 % / 0,766 | 2–3 min por triaje | ~7 GB de RAM o VRAM |
| `qwen2.5:7b-instruct-q4_K_M` (Qwen2.5-7B) | 4,7 GB | No | 50,0 % / 0,487 | 45–55 s por triaje | ~5 GB de RAM o VRAM |

Las cifras completas están en [`docs/RESULTADOS_DEV_TRIAJE.md`](docs/RESULTADOS_DEV_TRIAJE.md). Con GPU NVIDIA, los dos modelos responden en segundos.

### Rendimiento Clínico Comparativo (Splits Dev y Test)

Evaluación experimental rigurosa sobre el corpus clínico estratificado (250 casos validados; 150 en *dev* y 100 en *test* congelado):

| Modelo / Pipeline | Exactitud (*test*) | Kappa Cuadrático (*test*) | Sensibilidad Crítica (*test*) | Infratriaje (*test*) | Latencia GPU (RTX 3070) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Gemma 4 E4B (`gemma4:e4b-it-qat`) + RoBERTa** | **73,0 %** [64,0–81,0] | **0,898** [0,828–0,945] | **92,5 %** [83,0–100,0] | **12,0 %** | **15,5 s** |
| Reglas puras (Línea base determinista) | 39,0 % [30,0–49,0] | 0,339 [0,199–0,477] | 37,5 % [22,5–52,5] | 56,0 % | < 1 ms |
| Mejora pareada (Δ IA vs. Reglas) | **+34,0 pp** | **+0,559** | **+55,0 pp** | **-44,0 pp** | — |

En la validación clínica ciega sobre el split *test* (50 casos evaluados a ciegas por personal médico independiente), el sistema demostró:
- **Concordancia Kappa clínico-IA:** `0,911` IC95 [0,793, 0,975] (concordancia casi perfecta).
- **Exactitud clínica:** `80,0 %`.
- **Evaluación de explicabilidad Likert (1–5):** Claridad `4,80`, Pertinencia `4,58`, Fidelidad `4,58`.

Las métricas detalladas y comparativas completas se encuentran en [`docs/EVALUACION_TRIAJE.md`](docs/EVALUACION_TRIAJE.md) y [`docs/RESULTADOS_DEV_TRIAJE.md`](docs/RESULTADOS_DEV_TRIAJE.md).

### 1. Requisitos

* **Con GPU NVIDIA (recomendado):** los mismos requisitos que en [Ejecución con GPU NVIDIA](#ejecución-con-gpu-nvidia). El override `docker-compose.gpu.yml` le reserva la GPU también a `llm-local`.
* **Solo con CPU:** funciona, pero solo es práctico para pruebas o evaluaciones por lotes. Docker necesita **12 GB de memoria o más**. Con 8 GB, Gemma y el resto del stack agotan la memoria y Docker Desktop puede dejar de responder. En Windows se asigna creando `%UserProfile%\.wslconfig` y reiniciando Docker Desktop:

  ```ini
  [wsl2]
  memory=12GB
  ```

### 2. Variables en `.env`

```env
# Modelo NER de las evaluaciones (Hugging Face, versión v1)
NER_MODEL_PATH=HoraYMedia/ai-triage-ner-roberta
NER_MODEL_REVISION=v1

# LLM local. El modelo se puede cambiar después en Configuración; este es el valor por defecto.
LOCAL_LLM_BASE_URL=http://llm-local:11434
LOCAL_LLM_MODEL=gemma4:e4b-it-qat

# Solo en CPU: tiempo máximo de espera del LLM (por debajo de los 300 s de nginx).
# Con GPU no hace falta tocarlos.
LOCAL_LLM_TIMEOUT_SECONDS=240
LLM_TASK_TIMEOUT=280

# Con GPU NVIDIA (Windows ';' — Linux/macOS ':')
# COMPOSE_FILE=docker-compose.yml;docker-compose.gpu.yml
```

`GEMINI_API_KEY` es opcional en este modo: solo hace falta si también se quiere poder elegir Gemini.

### 3. Levantar el stack con el perfil `llm-local`

```bash
docker compose --profile llm-local up --build -d
```

`--build` es necesario la primera vez y tras actualizar el código, porque `worker-llm` y `frontend` no montan el código fuente. La migración de la base de datos se aplica sola al arrancar el backend.

### 4. Descargar los modelos (una sola vez)

```bash
docker compose exec llm-local ollama pull gemma4:e4b-it-qat
```

```bash
docker compose exec llm-local ollama pull qwen2.5:7b-instruct-q4_K_M
```

Quedan guardados en el volumen `ollama_models` y sobreviven a reinicios y reconstrucciones.

### 5. Elegir el motor en la aplicación

1. Entrar en `https://localhost/` con un usuario administrador → **Configuración**.
2. En «Motor de Explicabilidad y Triaje (LLM)», elegir **LLM local (Ollama / servidor propio)**.
3. En **Modelo local**, elegir `gemma4:e4b-it-qat` o `qwen2.5:7b-instruct-q4_K_M`. La lista muestra los modelos descargados en Ollama.
4. Guardar.

### 6. Verificar

* El estado de los motores (barra lateral) debe decir **«LLM: Local · gemma4:e4b-it-qat»**. Si dice «Local no disponible: reglas», Ollama no responde o el modelo no está descargado.
* Al hacer un triaje, «En qué se basa este resultado» debe mostrar **«LLM local (gemma4:e4b-it-qat) + Christus Sinergia»**.
* Con GPU, después del primer triaje, este comando debe mostrar `100% GPU` en la columna `PROCESSOR`:

  ```bash
  docker compose exec llm-local ollama ps
  ```

**Equipos con poca memoria.** Si no se va a usar la voz, se puede liberar memoria parando el ASR con `docker compose stop worker-asr`. Para volver a activarlo: `docker compose up -d worker-asr`.

**Ollama instalado fuera de Docker.** Basta con definir `LOCAL_LLM_BASE_URL=http://host.docker.internal:11434` y no activar el perfil `llm-local`. Funciona tal cual en Windows y macOS; en Linux hay que añadir `extra_hosts` a `backend` y `worker-llm`. También sirve cualquier servidor compatible con la API de OpenAI, como llama.cpp server o LM Studio.

Para evaluar los modelos locales contra el corpus (`evaluate_extraction --model local:<modelo>`), ver [`docs/EVALUACION_TRIAJE.md`](docs/EVALUACION_TRIAJE.md#5-llm-local).

---

## Solución de Problemas

| Síntoma | Causa y solución |
| :--- | :--- |
| `dependency failed to start: container ai_triage_backend is unhealthy` y en `docker compose logs backend` aparece `password authentication failed` | El volumen de Postgres se creó con otra contraseña (por ejemplo, de una versión anterior del proyecto); `POSTGRES_PASSWORD` solo se aplica al crear el volumen. Si no hay datos que conservar: `docker compose down`, `docker volume ls` para ver el nombre exacto y `docker volume rm <carpeta>_postgres_data`. **Esto borra la base de datos.** |
| `could not select device driver "nvidia"` | Docker no tiene acceso a la GPU: revisar los requisitos del modo GPU o arrancar en modo CPU (sin el override). |
| No se puede iniciar sesión con los usuarios demo | Si no existen, definir `CREATE_DEMO_USERS=True`, `DEMO_ADMIN_PASSWORD` y `DEMO_NURSE_PASSWORD` en `.env`; si ya existen con otra contraseña, añadir también `RESET_DEMO_PASSWORDS=True`. Luego `docker compose up -d backend`. |
| El navegador no permite el micrófono desde otro equipo de la red | Los navegadores solo permiten el micrófono en HTTPS o `localhost`: acceder por `https://` y aceptar el certificado. |
| `health_check` devuelve `"status": "degraded"` | `worker-asr` no ha terminado de cargar el modelo o está caído: `docker compose logs worker-asr`. |
| En Configuración no aparece «LLM local» o la lista «Modelo local» está vacía | El stack no se levantó con `--profile llm-local`, o no se descargó ningún modelo (`docker compose exec llm-local ollama list`). Tras actualizar el código hay que reconstruir con `--build`. |
| Con el LLM local, el triaje sale del «Motor de Reglas» | El modelo tardó más que `LLM_TASK_TIMEOUT`, cosa habitual en CPU. Subir `LOCAL_LLM_TIMEOUT_SECONDS` y `LLM_TASK_TIMEOUT` (por ejemplo 240 y 280) y reiniciar con `docker compose up -d backend worker-llm`, o usar GPU o Qwen. |
| `request returned 500 Internal Server Error ... dockerDesktopLinuxEngine` mientras corre Gemma | Docker Desktop se quedó sin memoria. Asignar 12 GB o más a WSL (`.wslconfig`), reiniciar Docker Desktop y parar los servicios que no se usen (`docker compose stop worker-asr`). |
| `ollama pull gemma4...` falla o el modelo no carga | La imagen de Ollama debe ser `0.34.4` o posterior (variable `OLLAMA_IMAGE_TAG`). Gemma 4 no funciona con versiones anteriores. |

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
| `POST` | `/api/auth/password-reset/` · `/confirm/` | Recuperación de contraseña | Público |
| `GET` | `/api/auth/me/` | Perfil y permisos del usuario | JWT |
| `GET` | `/api/security/users/` | Directorio de usuarios | Admin |
| `PATCH` | `/api/security/users/<id>/permissions/` | Matriz de permisos de un usuario | Admin |
| `GET` | `/api/security/audit/` | Registro de auditoría | Admin |
| `GET` / `POST` | `/api/config/` | Configuración de modelos y estado del motor ASR | JWT / Admin para modificar |
| `GET` / `POST` | `/api/config/keys/` | Listado y registro de claves API cifradas | JWT / Admin para registrar |
| `DELETE` | `/api/config/keys/<id>/` | Revocación de clave API | Admin |
| `GET` | `/api/config/engines/` | Estado de motores ASR, NER y modelos locales disponibles | JWT |
| `POST` | `/api/config/vocabulary/sync/` | Verificación y recarga de catálogos SNOMED CT / CIE-10 | `can_manage_config` / Admin |
| `POST` | `/api/transcribe/` | Transcripción de un fragmento de audio (worker `asr`) | `can_use_transcriber` |
| `POST` | `/api/transcribe/reset/` | Reinicio del contexto de una sesión ASR | `can_use_transcriber` |
| `POST` | `/api/transcribe/normalize/` | Normalización SNOMED-CT / CIE-10 (worker `llm`) | JWT |
| `POST` | `/api/triage/sessions/analyze/` | Análisis de triaje y creación de la sesión (worker `llm`) | `can_register_patients` |
| `GET` | `/api/triage/sessions/history/` | Historial de triajes (propios; el admin ve todos) | JWT |
| `PATCH` | `/api/triage/sessions/<id>/override_level/` | Ajuste médico del nivel y síntomas | `can_edit_symptoms` |
| `GET` | `/api/triage/sessions/emr_patients/` | Admisiones para el simulador HCE | `can_view_emr` |
| `GET` | `/api/triage/sessions/evaluation_metrics/` | Concordancia, Kappa, seguridad y validación ciega | JWT (identidad del paciente solo con `can_view_emr`) |
| `GET` | `/api/triage/sessions/blind_review_queue/` | Casos pendientes de adjudicación ciega (sin niveles) | `can_edit_symptoms` |
| `POST` | `/api/triage/sessions/<id>/reference_level/` | Registro del nivel de referencia ciego (inmutable) | `can_edit_symptoms`, distinto del autor |
| `POST` | `/api/triage/sessions/<id>/justification_rating/` | Evaluación Likert de justificación (claridad, pertinencia, fidelidad) | `can_edit_symptoms`, adjudicador independiente |
| `GET` | `/api/triage/sessions/benchmark_results/` | Consulta de métricas y resultados históricos de benchmark | JWT |
| `POST` / `PATCH` | `/api/triage/sessions/<id>/update_care_status/` | Actualización de estado asistencial y notas de evolución en simulador HCE | `can_view_emr` |
| `GET` | `/api/triage/sessions/fhir_logs/` | Historial de transacciones FHIR | `can_view_fhir` |
| `POST` | `/api/fhir/` | Validación e ingestión de Bundles FHIR R4 en receptor HCE | JWT |
| `GET` | `/api/health_check/` | Estado del backend y del motor ASR | Público |

---

## Ejecución de Pruebas Automatizadas

### Backend y ML (Django + Pytest): 645 pruebas (602 backend [601 pasadas + 1 xfail] + 43 ML)

El conjunto cubre exhaustivamente autenticación, OTP, RBAC, cifrado, pacientes, sesiones de triaje, protocolo clínico (un caso por criterio y regresiones), compresión, RAG híbrido (`pgvector` + BM25), caché SHA-256, métricas y validación ciega, interoperabilidad dual FHIR R4 / HL7 v2.5.1, tareas Celery (en modo en línea), motor ASR (con Whisper simulado), configuración de seguridad y comandos de benchmark.

```bash
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m pytest --create-db backend
backend/.venv/Scripts/python.exe -m pytest ml/ner/tests -p no:django
docker compose exec backend pytest --create-db
```

En pytest las tareas Celery se ejecutan en línea y la caché es local al proceso: no hace falta Redis.

### Frontend (Next.js + Vitest + Testing Library): 93 pruebas pasadas (14 suites)

```bash
pnpm --dir frontend test
pnpm --dir frontend run lint
pnpm --dir frontend run build
```

### Benchmark del motor de triaje y extracción biomédica

Mide el motor contra el corpus clínico de **250 casos anotados y auditados** (`id`, `transcript`, `reference_level`, entidades y negación en JSON) en [`backend/triage/benchmark/corpus_entidades.json`](backend/triage/benchmark/README.md), estratificado en 150 casos de desarrollo (*dev*) y 100 de prueba (*test* con doble anotación ciega y Kappa inter-anotador 0,865):

```bash
# Evaluación de la línea base determinista de reglas sobre el split de prueba (100 casos)
backend/.venv/Scripts/python.exe backend/manage.py evaluate_benchmark backend/triage/benchmark/corpus_entidades.json --engine reglas --split test

# Evaluación de extracción NER y clasificación con LLM local o nube
backend/.venv/Scripts/python.exe backend/manage.py evaluate_extraction --split test --model local:gemma4:e4b-it-qat --fusion

# Comparativa estadística pareada con bootstrap de 1.000 remuestreos
backend/.venv/Scripts/python.exe backend/manage.py compare_engines --test-rules backend/triage/benchmark/resultados/test_reglas.json --test-llm backend/triage/benchmark/resultados/test_ollama_gemma4_gpu.json
```

---

## Documentación Técnica (`docs/`)

* [`docs/MANUAL_USUARIO_Y_ADMINISTRADOR.md`](docs/MANUAL_USUARIO_Y_ADMINISTRADOR.md) — Manual operativo por rol clínico (`enfermero`, `medico`, `admin`) y administración del sistema.
* [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — Guía de despliegue y mantenimiento en producción (CPU, GPU NVIDIA y Ollama local).
* [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — Modelo entidad-relación, tablas vectoriales (`pgvector`) e índices.
* [`docs/EVALUACION_ASR.md`](docs/EVALUACION_ASR.md) — Evaluación empírica de `faster-whisper` sobre 40 grabaciones clínicas reales.
* [`docs/EVALUACION_TRIAJE.md`](docs/EVALUACION_TRIAJE.md) — Protocolo experimental y resultados consolidados en *dev* y *test* congelado.
* [`docs/RESULTADOS_DEV_TRIAJE.md`](docs/RESULTADOS_DEV_TRIAJE.md) — Registro histórico del análisis comparativo sobre la partición *dev*.
* [`docs/VALIDACION_UMBRALES_SIGNOS_VITALES.md`](docs/VALIDACION_UMBRALES_SIGNOS_VITALES.md) — Justificación clínica de umbrales fisiológicos adultos (NEWS2, ACC/AHA, ADA, MTS).
* [`docs/INFORME_IMPLEMENTACION_Y_BRECHAS.md`](docs/INFORME_IMPLEMENTACION_Y_BRECHAS.md) — Arquitectura consolidada, matriz de endpoints y limitaciones conocidas.
* [`docs/AUDIT_TECNICO.md`](docs/AUDIT_TECNICO.md) — Trazabilidad de hallazgos de seguridad, calidad y cobertura de pruebas.

---

## Autores y Créditos Institucionales

* **Kevin Jordan Alzate** - [kevin.jordan@correounivalle.edu.co](mailto:kevin.jordan@correounivalle.edu.co)
* **Junior Orlando Cantor Arevalo** - [junior.cantor@correounivalle.edu.co](mailto:junior.cantor@correounivalle.edu.co)
* **Director de Proyecto:** Carlos Mauricio Gaona Cuevas

*Trabajo de Grado desarrollado en la Escuela de Ingeniería de Sistemas y Computación de la **Universidad del Valle**, Cali, Colombia (2026).*
