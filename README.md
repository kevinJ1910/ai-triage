# AI-Triage: Asistente Inteligente de Voz para la Clasificación Médica Automatizada

**AI-Triage** es una plataforma web inteligente de procesamiento de voz en tiempo real diseñada para optimizar y automatizar el triaje médico. Mediante el uso de Inteligencia Artificial (IA) avanzada y Procesamiento de Lenguaje Natural (NLP), el sistema asiste a los profesionales de la salud transcribiendo, editando, extrayendo entidades críticas y clasificando el nivel de urgencia de los pacientes, reduciendo sustancialmente los tiempos administrativos y de consulta.

---

## 🚀 Características Clave y Últimas Funcionalidades

*   **ASR Clínico en Tiempo Real (Faster-Whisper):** Transcripción continua y fragmentada de voz adaptada al idioma español, optimizada para capturar conversaciones entre médico y paciente.
*   **Compatibilidad y Autodetección de GPU (Fallback Automático):** 
    *   Ejecución acelerada por hardware usando **NVIDIA CUDA** cuando está disponible en la máquina.
    *   **Detección inteligente y fallback automático a CPU** en caso de no encontrarse una tarjeta gráfica compatible (NVIDIA) o librerías CUDA/cuDNN instaladas. Esto garantiza compatibilidad universal con ordenadores de bajos recursos, procesadores Intel/AMD y sistemas sin gráficas dedicadas.
*   **Paso Intermedio de Verificación y Edición (¡Nuevo!):**
    *   Al finalizar la grabación, el sistema detiene el audio y entra en un **modo de revisión interactivo**.
    *   Permite a los profesionales médicos modificar manualmente la conversación transcrita (cambiar speakers, corregir errores ortográficos/fonéticos, agregar nuevas líneas o eliminar entradas incorrectas) antes de enviar los datos al motor de IA.
*   **Extracción de Entidades Clínicas (NER):** Extracción automatizada y estructurada mediante IA de datos críticos:
    *   *Síntomas*, *Antecedentes Médicos*, *Medicamentos* y *Signos Vitales*.
    *   Permite la edición dinámica (adición y eliminación de entidades) directamente desde el Dashboard.
*   **Motor de Triaje Inteligente & Justificación:** Clasificación de la prioridad preliminar del paciente (Niveles del 1 al 5) con base en escalas internacionales (como ESI o Manchester), acompañada de una justificación clínica detallada redactada en lenguaje natural por la IA.
*   **Interoperabilidad Estándar FHIR R4 & HL7:** Generación automatizada de Bundles estructurados en formato JSON compatibles con FHIR R4 (recursos `Patient`, `Encounter`, `Condition` y `Observation`), listos para sincronizarse con sistemas de Historia Clínica Electrónica (HCE).
*   **Generación de Reportes PDF:** Descarga de reportes clínicos detallados con un solo clic.
*   **Interfaz de Usuario Premium:**
    *   Diseño moderno, fluido y oscuro con paleta de colores HSL armoniosa.
    *   **Sidebar Colapsable (¡Nuevo!)** con transiciones y micro-animaciones fluidas animadas mediante Framer Motion.
    *   Panel adaptable y redimensionable interactivamente (tanto vertical como horizontalmente) para un espacio de trabajo óptimo.

---

## 📂 Estructura del Proyecto

El repositorio está organizado en una arquitectura desacoplada de dos módulos principales:

```
ai-triage/                    (Raíz del repositorio)
├── .gitignore                (Configuración global de exclusiones de Git)
├── README.md                 (Documentación principal del proyecto)
│
├── ai-triage/                (Módulo del Frontend - Next.js)
│   ├── app/                  (Enrutamiento del lado del cliente, páginas y APIs)
│   │   ├── api/              (Rutas de API locales para proxy/transmisión de datos)
│   │   └── layout.tsx / AppNavigation.tsx
│   ├── components/           (Componentes reutilizables, incluyendo TriageDashboard.tsx)
│   ├── hooks/                (Hooks de React, incluyendo el controlador ASR useWhisperASR.ts)
│   ├── public/               (Archivos estáticos y favicons)
│   ├── package.json          (Dependencias de node)
│   └── .env                  (Variables de entorno del cliente - Gemini API Key)
│
└── ai-triage-backend/        (Módulo del Backend - Django)
    ├── config/               (Configuración base del proyecto Django)
    │   ├── settings.py       (Ajustes de CORS, Whisper y variables globales)
    │   └── urls.py           (Rutas del backend)
    ├── transcription/        (Aplicación de transcripción)
    │   ├── views.py          (Endpoints de chunking de audio)
    │   └── whisper_engine.py (Inicializador y motor del modelo Faster-Whisper)
    ├── manage.py             (Orquestador de comandos de Django)
    └── requirements.txt      (Dependencias de Python)
```

---

## 🛠️ Stack Tecnológico

### Frontend
- **Framework:** Next.js 15.4.9 (React 19, TypeScript)
- **Estilos:** Vanilla CSS y utilidades modernas
- **Animaciones:** Framer Motion (motion/react)
- **Iconografía:** Lucide React
- **Documentos:** jsPDF
- **Notificaciones:** Sonner (Toast system)
- **Gestor de Paquetes:** `pnpm`

### Backend
- **Framework:** Django 5.1
- **Motor de Transcripción ASR:** `faster-whisper`
- **NLP / Triage Engine:** Google Gemini API (modelos 1.5 Flash / 3.5 Flash)
- **Control de Variables:** `python-dotenv`
- **Interoperabilidad:** Mapeadores JSON a FHIR R4

---

## 🚀 Guía de Instalación y Ejecución

Sigue estos pasos para desplegar la aplicación localmente en modo de desarrollo:

### 1. Requisitos Previos
- **Node.js** v18 o superior.
- **Python** v3.10 o v3.11 (se recomienda v3.11 para compatibilidad óptima con `faster-whisper`).
- **Gestor de paquetes** `pnpm` (`npm install -g pnpm`).
- *(Opcional)* **NVIDIA CUDA Toolkit (12.x)** y librerías **cuDNN** configuradas en tu sistema si deseas habilitar aceleración por GPU.

---

### 2. Configurar y Ejecutar el Backend (Django)

1. Navega a la carpeta del backend:
   ```bash
   cd ai-triage-backend
   ```
2. Crea un entorno virtual de Python:
   ```bash
   python -m venv .venv
   ```
3. Activa el entorno virtual:
   - **En Windows:**
     ```bash
     .venv\Scripts\activate
     ```
   - **En macOS/Linux:**
     ```bash
     source .venv/bin/activate
     ```
4. Instala las dependencias requeridas:
   ```bash
   pip install -r requirements.txt
   ```
5. *(Opcional)* Configura las variables de entorno de Whisper en un archivo `.env` dentro de `ai-triage-backend`:
   ```ini
   WHISPER_MODEL_SIZE=large-v3-turbo
   WHISPER_DEVICE=cuda # O 'cpu', o dejar en 'auto'
   WHISPER_COMPUTE_TYPE=float16 # float16 para GPU, int8 para CPU
   ```
6. Inicia el servidor de desarrollo de Django:
   ```bash
   python manage.py runserver 8000
   ```
   El backend estará disponible en `http://localhost:8000`.

---

### 3. Configurar y Ejecutar el Frontend (Next.js)

1. Abre una nueva terminal y navega a la carpeta del frontend:
   ```bash
   cd ai-triage
   ```
2. Instala las dependencias del proyecto utilizando `pnpm`:
   ```bash
   pnpm install
   ```
3. Crea un archivo `.env` en la raíz de la carpeta `ai-triage`:
   ```bash
   touch .env
   ```
4. Añade tu API Key de Gemini y la URL del servidor al archivo `.env`:
   ```ini
   GEMINI_API_KEY="TU_API_KEY_AQUI"
   APP_URL="http://localhost:3000"
   ```
5. Ejecuta el servidor en modo de desarrollo:
   ```bash
   pnpm run dev
   ```
   Abre [http://localhost:3000](http://localhost:3000) en tu navegador para ver la aplicación web interactiva.

---

## ⚡ Aceleración por GPU (NVIDIA CUDA)
Para utilizar la aceleración por hardware de `faster-whisper`:
1. Asegúrate de tener una tarjeta gráfica NVIDIA y que los controladores estén actualizados.
2. Instala [CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit) compatible con tu sistema.
3. Descarga y añade a tus variables del sistema (PATH) los binarios de [cuDNN](https://developer.nvidia.com/cudnn).
4. El sistema cargará el modelo ASR en GPU de forma predeterminada reduciendo la latencia de procesamiento por bloque a pocos milisegundos. De lo contrario, registrará un aviso en la terminal del backend (`backend_debug.log`) e iniciará de manera transparente en la CPU.

---

## 👥 Autores y Créditos
- **Kevin Jordan Alzate** - [kevin.jordan@correounivalle.edu.co](mailto:kevin.jordan@correounivalle.edu.co)
- **Junior Orlando Cantor Arevalo** - [junior.cantor@correounivalle.edu.co](mailto:junior.cantor@correounivalle.edu.co)
- **Director de Proyecto:** Carlos Mauricio Gaona Cuevas

*Desarrollado en la Escuela de Ingeniería de Sistemas y Computación de la **Universidad del Valle**, Cali, Colombia (2026).*
