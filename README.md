# AI-Triage: Asistente Inteligente de Voz para la Clasificación Médica Automatizada

**AI-Triage** es una plataforma web inteligente de procesamiento de voz en tiempo real y soporte a la decisión clínica diseñada para optimizar y automatizar el triaje en servicios de urgencias hospitalarias. Mediante la integración de Inteligencia Artificial (IA) multimodal, Reconocimiento Automático del Habla (ASR) clínico y Procesamiento de Lenguaje Natural (NLP), el sistema asiste a médicos y enfermeros transcribiendo la consulta, normalizando terminología a estándares médicos (SNOMED-CT / CIE-10), extrayendo entidades críticas (NER), cuantificando la concordancia clínico-algorítmica y clasificando el nivel de prioridad bajo escalas internacionales (ESI / Manchester).

---

## Características Clave

* **ASR Clínico en Tiempo Real (Faster-Whisper):** Transcripción continua y segmentada en español con prompts especializados para terminología médica y manejo de buffers de audio con control de concurrencia y limpieza TTL.
* **Compatibilidad de Cómputo (GPU NVIDIA CUDA / Fallback CPU):** Aceleración por hardware en entornos con GPU y fallback transparente en CPU (int8/float16).
* **Motor de Triaje Multimodal con Inferencia Adaptativa:** Inferencia de nivel de prioridad (1 al 5) mediante Google Gemini Flash con justificación clínica estructurada en JSON y soporte para timeout resiliente.
* **Ajuste y Ratificación Médica de Nivel (Human-in-the-Loop):** Control stepper interactivo para que el profesional ratifique o modifique el nivel sugerido, registrando discrepancias y motivos clínicos.
* **Telemetría y Métricas de Concordancia (Cohen's Kappa):** Monitor de concordancia porcentual entre la IA y el criterio médico, cálculo de Cohen's Kappa, tasa de modificación y deriva temporal de discrepancias.
* **Normalización Ontológica en Vivo (SNOMED-CT / CIE-10):** Traducción de relatos coloquiales ("le aprieta el pecho", "falta el aire") a conceptos y códigos médicos formales con resaltado interactivo y tabla ontológica filtrable.
* **Simulador HCE / EMR con Asignación de Box Persistente:** Módulo de admisión y gestión de pacientes en espera con asignación persistente de box y registro de auditoría.
* **Interoperabilidad FHIR R4:** Generación, validación semántica e historial transaccional de Bundles HL7 FHIR Release 4 (`Patient`, `Encounter`, `Condition`, `Observation`).
* **Bóveda de Credenciales Cifradas (AES-256 Fernet):** Gestión dinámica de claves API (`gemini`, `openai`, `anthropic`, `deepseek`) con cifrado simétrico en base de datos y exposición exclusivamente enmascarada.
* **Seguridad Hospitalaria, RBAC y Auditoría Inmutable:** Control de acceso por roles (`admin`, `medico`, `enfermero`), matriz granular de permisos por usuario, pistas de auditoría forense (`AuditLog`) y protección `IsAuthenticatedOrReadOnly` en triaje.
* **Defensa de Autenticación y Rate Limiting:** Verificación OTP de 6 dígitos vía correo SMTP local (Mailpit), rotación e invalidación de JWT con lista negra (`token_blacklist`), limitación de tasa contra ataques de fuerza bruta (`AuthThrottle` 10/min, `OTPThrottle` 5/min) y renovación silenciosa automática en cliente frontend.
* **Diseño Responsivo Clínico:** Soporte adaptativo para terminales de escritorio y dispositivos móviles de urgencias mediante Drawer flotante y visualizaciones alternadas lista/detalle.
* **Suites de Pruebas Automatizadas:** Cobertura integral fullstack con 56 pruebas en Pytest (Backend) y 47 pruebas en Vitest / React Testing Library (Frontend).

---

## Arquitectura del Proyecto

```
ai-triage/
├── backend/                              # Backend API en Django 5 + Django REST Framework
│   ├── config/                           # Configuración global
│   │   ├── settings.py                   # Ajustes (JWT, Blacklist, Throttles, Logging, DB)
│   │   ├── urls.py                       # Enrutamiento maestro
│   │   ├── wsgi.py / asgi.py             # Entry points de servidor
│   │   └── crypto.py                     # Criptografía simétrica AES-256 Fernet
│   ├── accounts/                         # Autenticación, Usuarios, RBAC y Auditoría
│   │   ├── models.py                     # User, AuthVerificationCode, UserPermission, AuditLog
│   │   ├── views.py                      # Login, Registro, OTP, Reset, Usuarios, Auditoría
│   │   ├── throttles.py                  # Rate limiting (AuthThrottle, OTPThrottle)
│   │   ├── emails.py                     # Plantillas HTML de correo transaccional
│   │   └── tests/                        # Pruebas de autenticación, OTP, RBAC y auditoría
│   ├── patients/                         # Entidad de Pacientes
│   │   ├── models.py                     # Modelo Patient y restricciones documentales
│   │   └── tests/                        # Pruebas de modelos y unicidad
│   ├── triage/                           # Motor de Triaje, Métricas y FHIR
│   │   ├── models.py                     # TriageSession, FHIRRecord, FHIRMessageLog
│   │   ├── views.py                      # Analyze, Override, Assign Box, Metrics, EMR, FHIR
│   │   ├── ai_analyzer.py                # Cliente Gemini con control de timeouts y resiliencia
│   │   └── tests/                        # Pruebas de sesiones, métricas, FHIR y seguridad
│   ├── system_settings/                  # Parámetros y Bóveda Cifrada
│   │   ├── models.py                     # SystemConfiguration, APIKeyCredential
│   │   └── tests/                        # Pruebas de cifrado y administración de llaves
│   ├── transcription/                    # Transcripción ASR y Normalización
│   │   ├── views.py                      # Transcribe chunk, Reset, Health check, Normalize
│   │   ├── whisper_engine.py             # Singleton Faster-Whisper con threading.Lock
│   │   ├── medical_prompts.py            # Prompts léxicos para ASR clínico
│   │   └── tests/                        # Pruebas de motor ASR, poda TTL y normalización
│   ├── core/                             # Capa Transversal de Validación
│   │   ├── validation.py                 # Esquemas de contrato en Pydantic v2
│   │   └── tests/                        # Pruebas unitarias de esquemas Pydantic
│   ├── Dockerfile                        # Imagen de producción multi-etapa Python 3.12-slim
│   ├── requirements.txt                  # Dependencias optimizadas de backend
│   └── pytest.ini                        # Configuración de pruebas Django con SQLite en memoria
│
├── frontend/                             # Frontend SPA/SSR en Next.js 15 (React 19)
│   ├── app/                              # Next.js App Router
│   │   ├── page.tsx                      # Vista clínica principal protegida
│   │   ├── login/page.tsx                # Portal de inicio de sesión y validación
│   │   ├── layout.tsx                    # Layout corporativo oscuro
│   │   └── globals.css                   # Tokens de diseño Tailwind CSS
│   ├── components/                       # Componentes de interfaz de usuario
│   │   ├── TriageDashboard.tsx           # Panel interactivo de triaje, stepper y entidades
│   │   ├── AppNavigation.tsx             # Barra lateral colapsable y Drawer móvil
│   │   ├── EMRSimulator.tsx              # Admisiones hospitalarias y asignación de boxes
│   │   ├── FHIRMonitor.tsx               # Monitor e inspección de bundles FHIR R4
│   │   ├── MetricsDashboard.tsx          # Panel analítico de concordancia y Kappa
│   │   ├── NormalizationMonitor.tsx      # Traductor de lenguaje coloquial a SNOMED-CT
│   │   ├── SecurityPanel.tsx             # Administración RBAC y registro de auditoría
│   │   └── ConfigPanel.tsx               # Bóveda de credenciales cifradas y modelos
│   ├── lib/                              # Utilidades y contratos de cliente
│   │   ├── api.ts                        # Wrapper fetch con inyección JWT y auto-refresh silencioso
│   │   └── validation.tsx                # Validadores de formulario en cliente
│   ├── tests/                            # Suite de pruebas automatizadas en Vitest
│   ├── Dockerfile                        # Imagen multi-etapa Node 20 Alpine Standalone
│   ├── vitest.config.mts                 # Configuración de testing con jsdom
│   └── package.json                      # Dependencias de cliente y scripts pnpm/npm
│
├── nginx/                                # Gateway / Proxy Inverso
│   ├── nginx.conf                        # Enrutamiento unificado de puertos y encabezados
│   └── Dockerfile
│
├── docs/                                 # Documentación técnica y memorias de ingeniería
│   ├── INFORME_IMPLEMENTACION_Y_BRECHAS.md # Informe técnico integral y brechas del sistema
│   └── AUDIT_TECNICO.md                  # Auditoría técnica, matriz de riesgos y resolución
│
├── docker-compose.yml                    # Orquestación de infraestructura multi-contenedor
├── .env                                  # Variables de entorno locales
├── .env.example                          # Plantilla documentada de variables
└── README.md                             # Documento principal del repositorio
```

---

## Flujo de Integración y Servicios

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NAVEGADOR / TERMINAL CLÍNICO                    │
│                      http://localhost (Puerto 80)                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                              NGINX (Puerto 80)                         │
│                           API Gateway / Proxy Inverso                  │
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
     │  FRONTEND CONTAINER  │              │  BACKEND CONTAINER   │
     │   (Node 20 Alpine)   │              │ (Python 3.12-slim)   │
     │                      │              │                      │
     │  • Next.js App       │              │  • Faster-Whisper    │
     │  • fetchWithAuth     │              │  • Pydantic v2       │
     │  • Auto-refresh JWT  │              │  • SimpleJWT + Auth  │
     │  • Reactive UI       │              │  • AES-256 Vault     │
     └──────────────────────┘              └──────────┬───────────┘
                                                      │
         ┌──────────────────┬─────────────────────────┼──────────────────┐
         │                  │                         │                  │
         ▼                  ▼                         ▼                  ▼
┌─────────────────┐┌─────────────────┐       ┌─────────────────┐┌─────────────────┐
│   POSTGRESQL    ││   REDIS 7       │       │    MAILPIT      ││  GOOGLE GEMINI  │
│  (Persistencia) ││  (Cache / ASR)  │       │  (SMTP 1025 /   ││  (Inferencia    │
│  Puerto interno ││  Puerto interno │       │   Web UI 8025)  ││   IA Externa)   │
└─────────────────┘└─────────────────┘       └─────────────────┘└─────────────────┘
```

---

## Servicios Docker Orquestados

El archivo `docker-compose.yml` aprovisiona los siguientes contenedores interconectados mediante la red bridge `ai_triage_network`:

| Servicio | Imagen / Contenedor | Puerto Expuesto | Propósito |
| :--- | :--- | :--- | :--- |
| `nginx` | `ai_triage_nginx` | `80:80` | Punto único de entrada HTTP y proxy inverso |
| `frontend` | `ai_triage_frontend` | `3000` (interno) | Interfaz web de usuario Next.js 15 en modo standalone |
| `backend` | `ai_triage_backend` | `8000` (interno) | Servidor Gunicorn Django REST con migraciones y ASR |
| `postgres` | `ai_triage_postgres` | `5432` (interno aislado) | Base de datos relacional PostgreSQL 16 Alpine |
| `redis` | `ai_triage_redis` | `6379` (interno) | Cache en memoria y gestión temporal de sesiones |
| `mailpit` | `ai_triage_mailpit` | `8025:8025` (Web) | Servidor SMTP local y visualizador web de correos OTP |

---

## Requisitos del Sistema

* **Docker Engine** 24.0+ y **Docker Compose** v2.20+
* **Memoria RAM:** Mínimo 8 GB (16 GB recomendado para modelos Whisper `small` o superiores).
* **Almacenamiento:** Mínimo 10 GB libres de espacio en disco.
* **NVIDIA GPU (Opcional):** Driver NVIDIA compatible y `nvidia-container-toolkit` configurado para aceleración CUDA en Whisper.
* **Entorno de Desarrollo Local (Sin Docker):**
  * Python 3.12 o 3.13 con entorno virtual `.venv`.
  * Node.js 20+ y administrador de paquetes `pnpm`.

---

## Inicio Rápido con Docker

### 1. Clonar el repositorio y configurar variables de entorno

```bash
git clone https://github.com/kevinJ1910/ai-triage.git
cd ai-triage
cp .env.example .env
```

Configurar las variables requeridas en `.env`:

```bash
# Clave criptografica principal (Requerida - sin fallback)
SECRET_KEY=clave-secreta-para-firmas-jwt-y-cifrado-aes-generar-una-segura

# Clave de API para Google Gemini (Triaje e inferencia clínica)
GEMINI_API_KEY=tu-api-key-de-gemini

# Configuracion de Whisper ASR
WHISPER_MODEL_SIZE=large-v3-turbo   # tiny, base, small, medium, large-v3-turbo
WHISPER_DEVICE=auto                 # auto, cpu, cuda
WHISPER_COMPUTE_TYPE=default        # int8 (CPU), float16 (GPU), default
```

### 2. Desplegar los servicios

```bash
docker compose up --build -d
```

### 3. Verificar el estado de salud de la plataforma

```bash
# Verificar estado de contenedores
docker compose ps

# Verificar health check del backend a traves del proxy
curl http://localhost/api/health_check/

# Visualizar logs del backend
docker compose logs -f backend
```

Acceder a las interfaces en el navegador:
* **Aplicación Clínica:** `http://localhost/`
* **Visor de Correos OTP (Mailpit):** `http://localhost:8025/`
* **Django Admin:** `http://localhost/admin/`

---

## Matriz de Endpoints de la API

| Método | Endpoint | Descripción | Validación | Control de Acceso |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login/` | Autenticación de usuarios con JWT | `LoginSchema` | Público (Rate Limit: 10/min) |
| `POST` | `/api/auth/register/` | Registro de personal y despacho de OTP | `RegisterSchema` | Público (Rate Limit: 10/min) |
| `POST` | `/api/auth/verify/` | Validación de código OTP de 6 dígitos | `VerifyCodeSchema` | Público (Rate Limit: 5/min) |
| `POST` | `/api/auth/password-reset/` | Solicitud y confirmación de restablecimiento | `PasswordResetSchema` | Público (Rate Limit: 10/min) |
| `POST` | `/api/auth/token/refresh/` | Renovación de access tokens JWT | SimpleJWT | Público / Refresh Token (Blacklist) |
| `GET` | `/api/auth/me/` | Perfil y permisos del usuario activo | N/A | Bearer JWT Requerido |
| `GET` | `/api/security/users/` | Directorio institucional de usuarios | N/A | Bearer JWT Requerido |
| `PATCH`| `/api/security/users/<id>/permissions/` | Modificación de matriz de permisos | `UserPermissionUpdateSchema` | Bearer JWT (Solo Admin) |
| `GET` | `/api/security/audit/` | Consulta de pistas de auditoría inmutables | N/A | Bearer JWT Requerido |
| `GET` | `/api/config/` | Configuración y modelos de IA activos | N/A | Bearer JWT Requerido |
| `PATCH`| `/api/config/` | Actualización de parámetros del sistema | `SystemConfigUpdateSchema` | Bearer JWT (Solo Admin) |
| `POST` | `/api/config/keys/` | Registro y cifrado de claves API en bóveda AES | `APIKeyCreateSchema` | Bearer JWT Requerido |
| `DELETE`| `/api/config/keys/<id>/` | Revocación de clave API en bóveda | N/A | Bearer JWT Requerido |
| `POST` | `/api/transcribe/` | Transcripción de fragmentos de audio ASR | FormData | Público / Libre |
| `POST` | `/api/transcribe/reset/` | Reinicio de sesión acustica en memoria | N/A | Público / Libre |
| `POST` | `/api/transcribe/normalize/` | Normalización clínica a SNOMED-CT / CIE-10 | `NormalizeTextSchema` | Público / Bearer JWT |
| `POST` | `/api/triage/sessions/analyze/` | Inferencia clínica de triaje y extracción NER | N/A | Bearer JWT Requerido |
| `PATCH`| `/api/triage/sessions/<id>/override_level/` | Ratificación o ajuste de nivel de triaje | `TriageOverrideSchema` | Bearer JWT Requerido |
| `POST` | `/api/triage/sessions/<id>/assign_box/` | Asignación persistente de box hospitalario | `EMRBoxAssignSchema` | Bearer JWT Requerido |
| `GET` | `/api/triage/sessions/evaluation_metrics/` | Métricas de concordancia y Cohen's Kappa | N/A | IsAuthenticatedOrReadOnly |
| `GET` | `/api/triage/sessions/emr_patients/` | Lista de admisiones para simulador HCE | N/A | IsAuthenticatedOrReadOnly |
| `GET` | `/api/triage/sessions/fhir_logs/` | Registro de transacciones FHIR R4 | N/A | IsAuthenticatedOrReadOnly |
| `POST` | `/api/fhir/` | Ingestión y validación de Bundles FHIR R4 | `FHIRSyncSchema` | Público / Validación Esquema |
| `GET` | `/api/health_check/` | Telemetría del motor ASR y hardware | N/A | Público / Libre |

---

## Ejecución de Pruebas Automatizadas

El proyecto implementa un estándar estricto de pruebas automatizadas con aislamiento de hardware y bases de datos en memoria para garantizar que ninguna regresión afecte la operación clínica:

### Suite de Backend (Django + Pytest)

Ejecuta 56 pruebas unitarias y de integración que cubren autenticación, OTP, RBAC, criptografía AES-256, modelos de pacientes, sesiones de triaje, interoperabilidad FHIR y validación de esquemas Pydantic:

```bash
# Ejecutar toda la suite de pruebas del backend
backend/.venv/Scripts/python.exe -m pytest backend

# Ejecutar con detalle de cada caso de prueba
backend/.venv/Scripts/python.exe -m pytest backend -v
```

### Suite de Frontend (Next.js + Vitest + Testing Library)

Ejecuta 47 pruebas unitarias y de componentes que validan el comportamiento reactivo de paneles, validación de tipos en cliente, monitor FHIR, simulador EMR, normalizador SNOMED-CT y manejo de tokens JWT:

```bash
# Ejecutar todas las pruebas del frontend
pnpm --dir frontend test

# Validar compilacion limpia de produccion en Next.js
pnpm --dir frontend run build
```

---

## Autores y Créditos Institucionales

* **Kevin Jordan Alzate** - [kevin.jordan@correounivalle.edu.co](mailto:kevin.jordan@correounivalle.edu.co)
* **Junior Orlando Cantor Arevalo** - [junior.cantor@correounivalle.edu.co](mailto:junior.cantor@correounivalle.edu.co)
* **Director de Proyecto:** Carlos Mauricio Gaona Cuevas

*Trabajo de Grado desarrollado en la Escuela de Ingeniería de Sistemas y Computación de la **Universidad del Valle**, Cali, Colombia (2026).*