# AI-Triage: Asistente Inteligente de Voz para la Clasificación Médica Automatizada

**AI-Triage** es una plataforma web inteligente de procesamiento de voz en tiempo real diseñada para optimizar y automatizar el triaje médico. Mediante el uso de Inteligencia Artificial (IA) avanzada y Procesamiento de Lenguaje Natural (NLP), el sistema asiste a los profesionales de la salud transcribiendo, editando, extrayendo entidades críticas y clasificando el nivel de urgencia de los pacientes, reduciendo sustancialmente los tiempos administrativos y de consulta.

---

## 🚀 Características Clave

*   **ASR Clínico en Tiempo Real (Faster-Whisper):** Transcripción continua y fragmentada de voz adaptada al idioma español, optimizada para capturar conversaciones entre médico y paciente.
*   **Compatibilidad con GPU y Fallback Automático a CPU:**
    *   Ejecución acelerada por hardware usando **NVIDIA CUDA** cuando está disponible.
    *   **Fallback automático a CPU** cuando no hay GPU, garantizando compatibilidad con cualquier sistema.
*   **Paso Intermedio de Verificación y Edición:**
    *   Al finalizar la grabación, el sistema entra en un **modo de revisión interactivo**.
    *   Permite modificar manualmente la conversación transcrita (corregir errores, cambiar speakers, etc.) antes de enviar al motor de IA.
*   **Extracción de Entidades Clínicas (NER):** Extracción automatizada mediante IA de:
    *   *Síntomas*, *Antecedentes Médicos*, *Medicamentos* y *Signos Vitales*.
    *   Edición dinámica directamente desde el Dashboard.
*   **Motor de Triaje Inteligente & Justificación:** Clasificación del 1 al 5 con base en escalas internacionales (ESI/Manchester), con justificación clínica generada por IA.
*   **Interoperabilidad FHIR R4:** Generación de Bundles JSON compatibles con FHIR R4 (`Patient`, `Encounter`, `Condition`, `Observation`).
*   **Generación de Reportes PDF:** Descarga de reportes clínicos detallados.
*   **Interfaz Premium:** Diseño oscuro moderno con animaciones fluidas mediante Framer Motion.

---

## 🏗️ Arquitectura del Proyecto

```
ai-triage/
├── backend/                      # Django REST API (Python 3.12)
│   ├── config/                    # Configuración Django
│   │   ├── settings.py            # Settings principales (Whisper, DB, Redis)
│   │   ├── urls.py                 # Enrutamiento principal
│   │   ├── wsgi.py                 # WSGI entry point
│   │   └── asgi.py                # ASGI entry point
│   ├── transcription/              # App Django de transcripción
│   │   ├── views.py                # Vistas REST (transcribe, reset, health)
│   │   ├── urls.py                 # Rutas de la app
│   │   ├── whisper_engine.py       # Motor singleton de Faster-Whisper
│   │   └── medical_prompts.py      # Prompts clínicos para Whisper
│   ├── Dockerfile
│   ├── requirements.txt
│   └── manage.py
│
├── frontend/                      # Next.js 15 (React 19)
│   ├── app/                       # App Router de Next.js
│   │   ├── page.tsx               # Página principal
│   │   ├── layout.tsx             # Layout raíz
│   │   ├── AppNavigation.tsx      # Navegación principal
│   │   ├── globals.css            # Estilos globales (Tailwind)
│   │   └── api/                   # API Routes (Next.js)
│   │       ├── transcribe/        # Proxy a backend Django
│   │       │   ├── route.ts       # POST /api/transcribe → backend
│   │       │   └── reset/route.ts # POST /api/transcribe/reset → backend
│   │       ├── triage/
│   │       │   └── analyze/route.ts # POST /api/triage/analyze → Gemini
│   │       └── fhir/route.ts     # Generación FHIR R4
│   ├── components/                 # Componentes React
│   │   ├── TriageDashboard.tsx    # Dashboard principal de triaje
│   │   ├── ConfigPanel.tsx        # Panel de configuración
│   │   ├── SecurityPanel.tsx      # Panel de seguridad
│   │   ├── MetricsDashboard.tsx   # Métricas visuales
│   │   ├── FHIRMonitor.tsx       # Monitor FHIR
│   │   ├── NormalizationMonitor.tsx
│   │   └── EMRSimulator.tsx       # Simulador de HCE
│   ├── hooks/                     # Custom React Hooks
│   │   ├── useWhisperASR.ts      # Hook de grabación/transcripción
│   │   └── use-mobile.ts         # Detección de dispositivo móvil
│   ├── lib/                       # Utilidades
│   │   └── utils.ts               # Funciones helper (cn, etc.)
│   ├── Dockerfile
│   ├── next.config.ts             # Configuración Next.js
│   ├── package.json
│   └── tailwind/postcss config
│
├── nginx/                         # Reverse Proxy (nginx alpine)
│   ├── nginx.conf                 # Configuración de rutas
│   └── Dockerfile
│
├── scripts/                       # Scripts de utilidad
│   └── entrypoint.sh              # Script de inicio
│
├── docker-compose.yml             # Orquestación de servicios
├── .env                           # Variables de entorno (producción)
├── .env.example                   # Template de variables
└── README.md
```

---

## 🔌 Flujo de Datos entre Servicios

```
┌─────────────────────────────────────────────────────────────────────┐
│                         NAVEGADOR (Cliente)                         │
│                    http://localhost (puerto 80)                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                           NGINX (Puerto 80)                            │
│                        Reverse Proxy / API Gateway                     │
├───────────────────────────────────────────────────────────────────────┤
│  /              → frontend:3000  (Next.js App)                        │
│  /api/transcribe → backend:8000  (Django + Faster-Whisper)           │
│  /api/triage/    → frontend:3000  (Next.js → Gemini API)              │
│  /api/fhir/      → frontend:3000  (Next.js → FHIR R4)                 │
│  /admin/         → backend:8000  (Django Admin)                       │
└────────┬────────────────────┬──────────────────────┬───────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    FRONTEND     │  │    BACKEND       │  │   EXTERNAL      │
│  (Next.js 3000) │  │ (Django 8000)    │  │   APIs          │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ TriageDashboard │  │ Faster-Whisper  │  │ Google Gemini   │
│ useWhisperASR   │  │ (ASR Engine)    │  │ (Triaje IA)     │
│ FHIRMonitor     │  │ PostgreSQL      │  │                 │
│ PDF Generator   │  │ Redis (Cache)   │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## 📋 Requisitos

- **Docker Engine** 24.0+
- **Docker Compose** v2.20+
- **8GB+ RAM** mínimo (16GB recomendado para modelos grandes)
- **NVIDIA GPU** (opcional, para aceleración GPU)

---

## 🚀 Inicio Rápido

### 1. Clonar y configurar

```bash
git clone <repo-url>
cd ai-triage
cp .env.example .env
```

### 2. Configurar variables de entorno

Edita `.env` con tus credenciales:

```bash
# Gemini API Key (necesaria para triaje)
GEMINI_API_KEY=tu-api-key-de-gemini

# Whisper (opcional, para cambiar modelo)
WHISPER_MODEL_SIZE=base           # Modelos: tiny, base, small, medium, large-v3-turbo
WHISPER_DEVICE=cpu                # cpu o cuda (para GPU)
WHISPER_COMPUTE_TYPE=int8         # int8 para CPU, float16 para GPU
```

### 3. Levantar servicios

```bash
docker compose up --build -d
```

### 4. Verificar funcionamiento

```bash
# Estado de servicios
docker compose ps

# Health check del backend
curl http://localhost/api/transcribe/health

# Ver logs
docker compose logs -f backend
```

---

## 🌐 Endpoints API

| Método | Endpoint | Descripción | Servicio |
|--------|----------|-------------|----------|
| GET | `/api/transcribe/health` | Health check del motor ASR | Backend |
| POST | `/api/transcribe` | Transcribir audio (FormData) | Backend |
| POST | `/api/transcribe/reset` | Resetear sesión de transcripción | Backend |
| POST | `/api/triage/analyze` | Análisis de triaje con Gemini | Frontend |
| POST | `/api/fhir` | Generar Bundle FHIR R4 | Frontend |
| GET | `/health` | Health check general | Nginx |

---

## ⚙️ Configuración de Modelos Whisper

Edita las variables en `.env`:

```bash
# Modelo Whisper (disponibles: tiny, base, small, medium, large-v3-turbo)
WHISPER_MODEL_SIZE=base

# Dispositivo de cómputo
# - cpu: Usa CPU (funciona en cualquier máquina)
# - cuda: Usa GPU NVIDIA (requiere CUDA Toolkit)
# - auto: Detecta automáticamente (GPU si disponible, si no CPU)
WHISPER_DEVICE=cpu

# Tipo de cómputo
# - int8: Recomendado para CPU (más rápido, menos RAM)
# - float16: Recomendado para GPU
# - default: Automático según dispositivo
WHISPER_COMPUTE_TYPE=int8
```

### Requisitos de RAM según modelo:

| Modelo | RAM mínima | RAM recomendada |
|--------|-----------|-----------------|
| tiny | 1GB | 2GB |
| base | 1GB | 3GB |
| small | 2GB | 4GB |
| medium | 3GB | 6GB |
| large-v3-turbo | 4GB | 8GB |

---

## 🛠️ Desarrollo

### Solo backend (sin frontend)

```bash
docker compose up backend postgres redis -d
```

### Recargar después de cambios en backend

```bash
docker compose up --build backend
```

### Ver logs de un servicio específico

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f nginx
```

---

## 🛑 Detener Servicios

```bash
# Detener sin eliminar datos
docker compose stop

# Detener y eliminar contenedores
docker compose down

# Detener y eliminar volúmenes (⚠️ elimina datos)
docker compose down -v
```

---

## 📁 Estructura de Volumes Docker

Los datos persistentes se almacenan en volúmenes Docker:

| Volumen | Descripción |
|---------|-------------|
| `postgres_data` | Datos de PostgreSQL |
| `redis_data` | Cache de Redis |
| `audio_uploads` | Archivos de audio subidos |

---

## 👥 Autores

- **Kevin Jordan Alzate** - [kevin.jordan@correounivalle.edu.co](mailto:kevin.jordan@correounivalle.edu.co)
- **Junior Orlando Cantor Arevalo** - [junior.cantor@correounivalle.edu.co](mailto:junior.cantor@correounivalle.edu.co)
- **Director de Proyecto:** Carlos Mauricio Gaona Cuevas

*Desarrollado en la Escuela de Ingeniería de Sistemas y Computación de la **Universidad del Valle**, Cali, Colombia (2026).*