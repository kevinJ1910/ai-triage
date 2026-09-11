# Guía Exhaustiva de Despliegue en Producción (AI-Triage)

Este documento detalla los requerimientos, consideraciones arquitectónicas y configuraciones de variables de entorno necesarias para desplegar de forma exitosa y segura el ecosistema AI-Triage en un entorno de producción hospitalaria u *on-premise*.

---

## 1. Topología del Despliegue (Docker Compose)

El sistema se distribuye en 6 componentes interconectados mediante una red *bridge* aislada de Docker (`ai_triage_network`):

*   **`nginx` (Proxy Inverso):** Puerta de enlace unificada que expone el puerto 80 (y 443 en despliegues con terminación SSL/TLS). Dirige el tráfico a Next.js o Django según el prefijo de la ruta.
*   **`frontend` (Next.js 15 Standalone):** Servidor Node.js 20 Alpine ejecutado con usuario sin privilegios `nextjs` (UID 1001), sirviendo la interfaz reactiva optimizada.
*   **`backend` (Django 5.2.8 / DRF):** Procesamiento clínico central ejecutado bajo usuario no-root `appuser` (UID 10001). Contiene la inferencia acústica de *faster-whisper* (ASR), análisis semántico con LLM (Gemini), validación Pydantic v2 y bóveda de claves AES-256.
*   **`postgres` (PostgreSQL 16 Alpine):** Persistencia ACID relacional con esquemas optimizados e índices compuestos.
*   **`redis` (Redis 7 Alpine):** Gestión de caché, colas y control de estado volátil.
*   **`mailpit` (Servidor SMTP Transaccional):** Servidor SMTP (puerto 1025) y panel web de inspección de correos (puerto 8025) para captura local de OTPs y alertas; reemplazable en producción por relé SMTP corporativo o SendGrid/SES.

---

## 2. Requerimientos de Hardware

Dado que el procesamiento acústico de transcripción requiere inferencias neuronales y la inferencia clínica opera con modelos densos, se recomiendan los siguientes recursos para el servidor anfitrión (*Host*):

| Componente | Requerimiento Mínimo | Requerimiento Recomendado |
| :--- | :--- | :--- |
| **CPU** | 4 Cores / 8 Hilos | 8 Cores / 16 Hilos |
| **RAM (Sistema)** | 16 GB DDR4 | 32 GB DDR4 o superior |
| **Almacenamiento** | 50 GB SSD | 100 GB NVMe (logs y audios) |
| **GPU (NVIDIA)** | No requerida (Fallback CPU) | NVIDIA RTX 3060 (12GB VRAM) o superior |

> **Passthrough de GPU:** Si se cuenta con una GPU NVIDIA, el host debe tener instalados los controladores oficiales y el **NVIDIA Container Toolkit** para que Docker pueda delegar el acelerador al contenedor del backend. La configuración de reserva de GPU se encuentra parametrizada en el bloque `deploy.resources.reservations.devices` de `docker-compose.yml`.

---

## 3. Variables de Entorno y Secretos

Es obligatorio crear un archivo `.env` en la raíz del proyecto antes de levantar los contenedores. A continuación, el detalle exhaustivo de cada bloque de configuración sincronizado con `.env.example`.

### 3.1. Configuración de Base de Datos (PostgreSQL)
```env
POSTGRES_DB=ai_triage_prod
POSTGRES_USER=triage_admin
POSTGRES_PASSWORD=contrasena_robusta_para_postgres_123
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

### 3.2. Configuración de Seguridad y Red (Django)
```env
# Clave criptográfica para firmas JWT y cifrado de bóveda AES-256 (OBLIGATORIA, sin fallbacks inseguros)
SECRET_KEY=clave_secreta_de_alta_entropia_sin_espacios_de_al_menos_50_caracteres
DEBUG=False
ENVIRONMENT=production # Opciones: production, development, staging

# Dominios y orígenes autorizados
ALLOWED_HOSTS=nginx,localhost,127.0.0.1,hospital.triage.salud.gov.co
CORS_ALLOWED_ORIGINS=http://localhost,https://hospital.triage.salud.gov.co
```

### 3.3. Configuración de Correo Transaccional (OTP y Recuperación)
```env
# En desarrollo local se utiliza Mailpit; en producción configurar relé SMTP institucional
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mailpit # o smtp.hospital.gov.co
EMAIL_PORT=1025    # o 587 con TLS
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=False
DEFAULT_FROM_EMAIL=notificaciones@ai-triage.hospital.gov.co
```

### 3.4. Inicialización Controlada de Cuentas Demo
> [!IMPORTANT]
> En entornos de producción (`ENVIRONMENT=production`), la creación del usuario demo es **omitida automáticamente** por seguridad en el script de arranque. Si se requiere en `development`, debe especificarse obligatoriamente una contraseña robusta.
```env
DJANGO_DEMO_EMAIL=admin@hospital.com
DJANGO_DEMO_PASSWORD=AdminHospital2026!
```

### 3.5. Configuración de Inteligencia Artificial y Proveedores de LLM
Las claves especificadas aquí se sincronizan automáticamente al inicio en la bóveda de credenciales cifradas (`APIKeyCredential`):
```env
# Proveedor principal de análisis clínico estructurado
GEMINI_API_KEY=AIzaSy...

# Proveedores alternativos opcionales (sincronizados automáticamente)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
GROQ_API_KEY=
COHERE_API_KEY=
MISTRAL_API_KEY=

# Configuración del Motor ASR (Faster-Whisper)
WHISPER_MODEL_SIZE=large-v3-turbo # Opciones: base, small, medium, large-v3-turbo
WHISPER_DEVICE=auto               # 'auto', 'cuda' o 'cpu'
WHISPER_COMPUTE_TYPE=float16      # 'int8' (menor VRAM) o 'float16' (mayor fidelidad)
```

### 3.6. Configuración del Frontend
```env
# URL pública donde el frontend encuentra el backend (a través de Nginx)
NEXT_PUBLIC_API_URL=http://localhost/api
# URL del servidor FHIR externo (si aplica)
NEXT_PUBLIC_FHIR_URL=http://servidor_fhir_hospital/fhir
```

---

## 4. Pasos para el Despliegue

1. **Clonar repositorio y preparar secretos:**
   ```bash
   git clone <repo>
   cd ai-triage
   cp .env.example .env
   # Editar .env con contraseñas seguras y API keys de producción
   ```

2. **Otorgar permisos de ejecución al entrypoint:**
   ```bash
   chmod +x backend/scripts/entrypoint.sh
   ```

3. **Construir y levantar el ecosistema:**
   Se utiliza Docker Compose v2 (`docker compose`):
   ```bash
   docker compose down
   docker compose build
   docker compose up -d
   ```

4. **Verificación Post-Despliegue:**
   Comprobar que todos los servicios estén saludables (`healthy`) y que las migraciones runtime se hayan aplicado:
   ```bash
   docker compose ps
   docker compose logs backend --tail 50
   ```

---

## 5. Consideraciones Finales de Seguridad

*   **Certificados SSL/TLS:** En producción hospitalaria, es mandatario terminar el tráfico HTTPS con certificados válidos (vía Certbot, proxy perimetral o balanceador de carga institucional).
*   **Usuarios No-Root:** Tanto el frontend (`nextjs:nodejs`, UID 1001) como el backend (`appuser:appgroup`, UID 10001) corren bajo cuentas de sistema aisladas sin permisos de root dentro de los contenedores.
*   **Aislamiento de PostgreSQL:** El puerto 5432 de la base de datos no se expone al host en `docker-compose.yml`, garantizando que únicamente los contenedores internos de `ai_triage_network` puedan conectarse.
*   **Depuración de Audios:** Las grabaciones de audio cargadas se procesan en streaming y buffer de memoria con algoritmo de poda automática por TTL (1800s); los archivos temporales en disco deben ser depurados periódicamente mediante políticas institucionales de cumplimiento HIPAA/RGPD.
