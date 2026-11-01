# Guía de Despliegue y Mantenimiento en Producción (AI-Triage)

Este documento describe la topología de contenedores, los requisitos de hardware (CPU y GPU NVIDIA), las variables de entorno y los procedimientos operativos para desplegar y mantener **AI-Triage** en infraestructura hospitalaria *on-premise* o en servidores dedicados.

---

## 1. Topología del Despliegue (Docker Compose)

La arquitectura se distribuye en **9 servicios** conectados sobre una red *bridge* interna aislada (`ai_triage_network`):

| Servicio | Contenedor | Puertos expuestos | Función técnica |
| :--- | :--- | :--- | :--- |
| `nginx` | `ai_triage_nginx` | `80`, `443` | Punto único de entrada: terminación TLS 1.2/1.3, redirección HTTP -> HTTPS, cabeceras de seguridad (CSP, HSTS, `X-Frame-Options`, `Permissions-Policy`) y proxy inverso hacia `frontend` y `backend`. |
| `frontend` | `ai_triage_frontend` | `3000` (interno) | Next.js 15 (App Router, React 19) en modo `standalone` bajo usuario sin privilegios `nextjs` (UID 1001). |
| `backend` | `ai_triage_backend` | `8000` (interno) | Gunicorn + Django REST Framework bajo `appuser` (UID 10001). Gestiona autenticación, RBAC, persistencia atómica y auditoría; delega la inferencia a Celery (`ASR_TASK_TIMEOUT`, `LLM_TASK_TIMEOUT`). |
| `worker-asr` | `ai_triage_worker_asr` | — | Worker Celery (`--pool solo`, cola `asr`) que precarga `faster-whisper` una única vez y procesa el acondicionamiento acústico (80 Hz + −20 dBFS) en CPU (`int8`) o GPU CUDA (`int8_float16`). |
| `worker-llm` | `ai_triage_worker_llm` | — | Worker Celery (cola `llm`) que ejecuta el extractor biomédico RoBERTa (`HoraYMedia/ai-triage-ner-roberta@v1`), el normalizador clínico, el RAG híbrido (`pgvector` + BM25) y la llamada al LLM (local o nube) con respaldo determinista automático. |
| `llm-local` | `ai_triage_llm_local` | `11434` (interno) | Servicio opcional (perfil `llm-local`) basado en Ollama (`>= 0.34.4`) para inferencia soberana *on-premise* con `gemma4:e4b-it-qat` o `qwen2.5:7b-instruct-q4_K_M` sin salida de datos del hospital. |
| `postgres` | `ai_triage_postgres` | `5432` (interno) | PostgreSQL 16 (`pgvector/pgvector:pg16`) sin exposición al host; aloja el esquema transaccional y los vectores de criterios clínicos (`triage_clinical_rag_vectors`). |
| `redis` | `ai_triage_redis` | `6379` (interno) | Redis 7 Alpine con persistencia AOF: broker/resultados de Celery (`db 0`) y caché compartida (`db 1`: caché clínica SHA-256, contexto ASR por sesión y contadores de *throttling*). |
| `mailpit` | `ai_triage_mailpit` | `1025`, `8025` | Captura SMTP local y visor web de códigos OTP en desarrollo; sustituible en producción por el relé SMTP institucional. |

Volúmenes persistentes: `postgres_data`, `redis_data`, `nginx_certs`, `asr_model_cache`, `ner_model_cache`, `ollama_models` y `audio_uploads`.

---

## 2. Requerimientos de Hardware

| Componente | Mínimo (Modo CPU / Respaldo) | Recomendado (Producción GPU + LLM Local) |
| :--- | :--- | :--- |
| **CPU** | 4 núcleos / 8 hilos x86_64 | 8 núcleos / 16 hilos x86_64 |
| **Memoria RAM** | 12 GB DDR4 (16 GB si corre Ollama en CPU) | 32 GB DDR4/DDR5 |
| **GPU** | No requerida (`small` `int8` en CPU) | NVIDIA RTX 3070 (8 GB VRAM) o superior (RTX 3060 12 GB / A10 / L4) |
| **Almacenamiento** | 20 GB SSD libres | 80 GB NVMe (modelos cacheados, base de datos y auditoría) |

### 2.1. Conmutación entre modo CPU y modo GPU NVIDIA

Por defecto, `docker-compose.yml` construye la imagen sin librerías CUDA (`WITH_CUDA=false`) y ejecuta `worker-asr` en CPU (`small`, `int8`), garantizando portabilidad universal.

En servidores con GPU NVIDIA y **NVIDIA Container Toolkit**, el archivo `docker-compose.gpu.yml`:
1. Construye la imagen del backend/workers con soporte CUDA/cuDNN (`WITH_CUDA=true`).
2. Configura `worker-asr` con `WHISPER_DEVICE=cuda`, `WHISPER_MODEL_SIZE=large-v3-turbo`, `WHISPER_COMPUTE_TYPE=int8_float16` y `WHISPER_BEAM_SIZE=2`.
3. Reserva aceleración por hardware NVIDIA tanto para `worker-asr` como para `llm-local` (Ollama).

```bash
# Modo CPU (cualquier equipo)
docker compose up --build -d

# Modo GPU NVIDIA + LLM local soberano (recomendado en hospital)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm-local up --build -d
```

---

## 3. Configuración de Variables de Entorno (`.env`)

Crear `.env` a partir de `.env.example` antes del primer despliegue:

### 3.1. Seguridad, JWT y Red
```env
# Obligatoria (>= 50 caracteres de alta entropía)
SECRET_KEY=generar_con_secrets_token_urlsafe_50

# Clave Fernet dedicada para cifrar API keys en BD (32 bytes base64)
FIELD_ENCRYPTION_KEY=generar_con_Fernet_generate_key

DEBUG=False
ALLOWED_HOSTS=nginx,localhost,127.0.0.1,triage.hospital.local
CORS_ALLOWED_ORIGINS=https://triage.hospital.local
CSRF_TRUSTED_ORIGINS=https://triage.hospital.local
TLS_SERVER_NAME=triage.hospital.local
HSTS_MAX_AGE=31536000
JWT_ACCESS_MINUTES=15
```

### 3.2. Base de Datos PostgreSQL 16 + `pgvector`
```env
POSTGRES_DB=ai_triage
POSTGRES_USER=triage_user
POSTGRES_PASSWORD=contrasena_robusta_produccion
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

### 3.3. Correo Electrónico (OTP y Recuperación)
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mailpit
EMAIL_PORT=1025
EMAIL_USE_TLS=False
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=AI-Triage <no-reply@hospital.local>
```

### 3.4. Cuentas Demo Controladas (Solo Desarrollo / Pruebas)
```env
CREATE_DEMO_USERS=False
DEMO_ADMIN_EMAIL=admin@hospital.com
DEMO_ADMIN_PASSWORD=
DEMO_NURSE_EMAIL=enfermeria@hospital.com
DEMO_NURSE_PASSWORD=
RESET_DEMO_PASSWORDS=False
```

### 3.5. Motores de IA (ASR, NER, LLM Local y Nube)
```env
# Tiempos máximos de espera antes de degradación controlada
ASR_TASK_TIMEOUT=90
LLM_TASK_TIMEOUT=100
ASR_SESSION_TTL=1800

# Extractor biomédico RoBERTa (Model Soup publicado en Hugging Face)
NER_MODEL_PATH=HoraYMedia/ai-triage-ner-roberta
NER_MODEL_REVISION=v1

# LLM local soberano vía Ollama (opcional, recomendado para privacidad total)
LOCAL_LLM_BASE_URL=http://llm-local:11434
LOCAL_LLM_MODEL=gemma4:e4b-it-qat
LOCAL_LLM_TIMEOUT_SECONDS=300

# Proveedor nube opcional (sincronizado automáticamente en bóveda MultiFernet)
GEMINI_API_KEY=
```

---

## 4. Procedimiento Paso a Paso de Despliegue y Mantenimiento

### 4.1. Puesta en marcha inicial
```bash
git clone https://github.com/kevinJ1910/ai-triage.git
cd ai-triage
cp .env.example .env
# Configurar SECRET_KEY, FIELD_ENCRYPTION_KEY y POSTGRES_PASSWORD en .env

docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm-local up --build -d
docker compose exec llm-local ollama pull gemma4:e4b-it-qat
```

### 4.2. Verificación operativa post-arranque
```bash
docker compose ps
curl -k https://localhost/api/health_check/
docker compose exec llm-local ollama ps
```
El endpoint `/api/health_check/` debe responder `status: "ok"`, `inference_mode: "worker"` y `asr.model_loaded: true`.

### 4.3. Copias de seguridad y restauración de PostgreSQL
```bash
# Respaldo comprimido en caliente
docker compose exec -T postgres pg_dump -U triage_user -Fc ai_triage > backup_ai_triage_$(date +%F).dump

# Restauración controlada
cat backup_ai_triage_YYYY-MM-DD.dump | docker compose exec -T postgres pg_restore -U triage_user -d ai_triage --clean --if-exists
```

### 4.4. Actualización y verificación de catálogos clínicos
```bash
# Verificar integridad de códigos SNOMED CT contra servidor terminológico HL7 (tx.fhir.org)
docker compose exec backend python manage.py verify_snomed

# Indexar / refrescar los 61 criterios del protocolo en pgvector
docker compose exec backend python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from triage.clinical_rag import ClinicalKnowledgeRAG; print(ClinicalKnowledgeRAG.index_pgvector())"
```

---

## 5. Controles de Seguridad en Infraestructura

- **Cifrado en tránsito (TLS 1.2/1.3):** `nginx` exige HTTPS para habilitar `navigator.mediaDevices.getUserMedia` en estaciones clínicas de la red local. En producción se deben montar `fullchain.pem` y `privkey.pem` emitidos por una CA institucional en el volumen `nginx_certs` (`/etc/nginx/certs`).
- **Aislamiento de red y contenedores sin root:** Ni PostgreSQL (`5432`) ni Redis (`6379`) ni Ollama (`11434`) exponen puertos fuera de `ai_triage_network`; `frontend` y `backend` corren sin privilegios de superusuario.
- **Efimeridad del audio:** Los fragmentos de voz se eliminan del almacenamiento temporal inmediatamente tras su transcripción en `worker-asr`, y el contexto textual en Redis caduca automáticamente tras `ASR_SESSION_TTL` segundos.
