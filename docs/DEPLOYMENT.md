# Guía Exhaustiva de Despliegue en Producción (AI-Triage)

Este documento detalla los requerimientos, consideraciones arquitectónicas y configuraciones de variables de entorno necesarias para desplegar de forma exitosa y segura el ecosistema AI-Triage en un entorno de producción hospitalaria u *on-premise*.

---

## 1. Topología del Despliegue (Docker Compose)

El sistema se distribuye en 4 componentes interconectados mediante una red *bridge* aislada de Docker:

*   **`nginx` (Proxy Inverso):** Puerta de enlace que expone el puerto 80 (y 443 en caso de configurar SSL). Dirige el tráfico a React o Django según la ruta.
*   **`frontend` (Next.js):** Sirve la aplicación React. 
*   **`backend` (Django 5.1):** Procesamiento pesado. Contiene la inferencia de *faster-whisper* (ASR) y la conexión a Gemini (NLP).
*   **`postgres` (PostgreSQL 16):** Persistencia ACID de datos (usuarios, pacientes, historiales de triaje).
*   **`redis` (Redis 7):** Gestión de caché y estados intermedios.

## 2. Requerimientos de Hardware

Dado que el procesamiento acústico de transcripción requiere inferencias neuronales, se exigen los siguientes recursos para el servidor anfitrión (*Host*):

| Componente | Requerimiento Mínimo | Requerimiento Recomendado |
| :--- | :--- | :--- |
| **CPU** | 4 Cores / 8 Hilos | 8 Cores / 16 Hilos |
| **RAM (Sistema)** | 16 GB DDR4 | 32 GB DDR4 o superior |
| **Almacenamiento** | 50 GB SSD | 100 GB NVMe (logs y audios) |
| **GPU (NVIDIA)** | No requerida (Caída a CPU) | RTX 3060 (12GB VRAM) o superior |

> **Passthrough de GPU:** Si se cuenta con una GPU NVIDIA, el host debe tener instalados los drivers oficiales y el **NVIDIA Container Toolkit** para que Docker pueda delegar el hardware al contenedor del backend. La configuración ya se encuentra parametrizada en el `docker-compose.yml`.

## 3. Variables de Entorno y Secretos

Es obligatorio crear un archivo `.env` en la raíz del proyecto antes de levantar los contenedores. A continuación, el análisis exhaustivo de cada variable necesaria.

### 3.1. Configuración de Base de Datos (PostgreSQL)
Estas variables sincronizan la inicialización de Postgres con la conexión del ORM en Django.
```env
POSTGRES_DB=ai_triage_prod
POSTGRES_USER=triage_admin
POSTGRES_PASSWORD=una_contraseña_muy_segura_123
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

### 3.2. Configuración de Seguridad y Red (Django)
```env
SECRET_KEY=clave_criptografica_aleatoria_larga_sin_espacios
DEBUG=False
# ALLOWED_HOSTS debe incluir la IP del servidor, localhost y el proxy interno
ALLOWED_HOSTS=nginx,localhost,127.0.0.1,192.168.X.X
# Orígenes CORS aceptados (importante para producción)
CORS_ALLOWED_ORIGINS=http://localhost,http://192.168.X.X
```

### 3.3. Configuración de Inteligencia Artificial
```env
# Claves de APIs de Google (Obligatorias para NLP)
GEMINI_API_KEY=tu_clave_gemini_aqui

# Configuración del Motor ASR (Faster-Whisper)
WHISPER_MODEL_SIZE=large-v3-turbo # Opciones: base, small, medium, large-v3-turbo
WHISPER_DEVICE=auto # 'cuda' para forzar GPU, 'cpu' para forzar procesador
WHISPER_COMPUTE_TYPE=float16 # 'int8' para ahorrar VRAM, 'float16' para mayor precisión
```

### 3.4. Configuración del Frontend
```env
# URL pública donde el frontend encuentra el backend (a través de Nginx)
NEXT_PUBLIC_API_URL=http://tu_dominio_o_ip/api
# URL del servidor FHIR externo (Si aplica)
NEXT_PUBLIC_FHIR_URL=http://servidor_fhir_hospital/fhir
```

## 4. Pasos para el Despliegue

1. **Clonar repositorio y preparar secretos:**
   ```bash
   git clone <repo>
   cd ai-triage
   # Copiar archivo .env y rellenar con datos de producción
   cp .env.example .env
   ```

2. **Otorgar permisos de ejecución:**
   ```bash
   chmod +x backend/scripts/entrypoint.sh
   ```

3. **Construir y Desplegar:**
   Se recomienda usar el *flag* de desacople (`-d`) para que los procesos corran en segundo plano.
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

4. **Verificación Post-Despliegue:**
   El backend creará automáticamente el usuario administrador. Se debe revisar que no existan errores de inicialización del modelo:
   ```bash
   docker logs ai_triage_backend --tail 50
   ```

## 5. Consideraciones Finales de Seguridad

*   **Certificados SSL/TLS:** Actualmente el proxy `nginx.conf` está configurado para tráfico HTTP (Puerto 80). En un entorno hospitalario de producción real, **es obligatorio** interceptar este tráfico con certificados SSL. Se recomienda modificar el `Dockerfile` de Nginx para incluir `Certbot` o desplegar el proyecto detrás de un balanceador de carga que termine el SSL.
*   **Retención de Audios:** Por defecto, los audios (`/app/media`) persisten en el volumen `audio_uploads`. De acuerdo con leyes de privacidad sanitaria, se debe implementar un *cronjob* o tarea automatizada que purgue periódicamente los archivos de audio tras ser procesados por la API.
