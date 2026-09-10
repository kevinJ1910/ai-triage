# Informe Tecnico de Implementacion, Arquitectura y Brechas del Sistema

**Fecha:** 2026-09-10  
**Proyecto:** AI-Triage Hospitalario (Tesis de Grado / Sistema de Soporte Clinico)  
**Rama Base:** `develop`  
**Autor:** Ingenieria de Software y Arquitectura Clinica  

---

## 1. Resumen Ejecutivo

El sistema AI-Triage ha sido transformado de una arquitectura con componentes prototipales y simulaciones estaticas a una plataforma hospitalaria integral, atestada en base de datos relacional con control de acceso basado en roles (RBAC), auditoria inmutable, cifrado simetrico de credenciales, motor semantico de triaje y telemetria matematica de concordancia Humano-IA.

Todos los modulos mock fueron eliminados o sustituidos por capas de negocio persistentes que se comunican a traves de contratos REST tipados en el frontend (Next.js 15) y Django REST Framework en el backend.

---

## 2. Componentes y Funcionalidades Implementadas

### 2.1. Autenticacion Institucional y Servicio SMTP Local (Mailpit)
- **Servicio Mailpit**: Desplegado en `docker-compose.yml` (puerto SMTP 1025, Web UI 8025) para captura local y trazabilidad de trafico de correos transaccionales sin requerir proveedores de pago en desarrollo.
- **Modelo de Usuario Extendido (`accounts.User`)**: Incorpora campos de identificacion clinica (`document_type`, `document_number`, `phone_number`, `role`, `is_verified`).
- **Verificacion OTP y Restablecimiento**:
  - Generacion criptografica segura de tokens OTP de 6 digitos (`AuthVerificationCode`) con validez de 15 minutos e invalidacion tras un unico uso.
  - Correos HTML corporativos con la paleta clinica oscura institucional generados mediante plantillas en `accounts/emails.py`.
- **Proteccion de Rutas y Sesion Real**:
  - Enrutamiento protegido en la raiz `/` que valida el token JWT contra `/api/auth/me/`.
  - Reemplazo dinamico del nombre estatico ("Dr. Rodriguez") por el perfil autenticado en la barra lateral y en los encabezados de triaje.

### 2.2. Boveda de Credenciales Cifradas y Seleccion de Modelos
- **App `system_settings`**:
  - Modelo `APIKeyCredential` con cifrado AES-256 (Fernet) derivado de la `SECRET_KEY` del entorno (`crypto.py`).
  - Deteccion automatica del proveedor (`gemini`, `openai`, `anthropic`, `deepseek`) basada en prefijos de clave (`AIza...`, `sk-...`, `sk-ant-...`).
  - Politica estricta de seguridad: las llaves nunca se devuelven en texto plano; unicamente se exponen enmascaradas (`••••••••Wxyz`) y solo se permite crear o revocar.
- **Inferencia Dinamica (`ai_analyzer.py`)**:
  - Consulta en tiempo de ejecucion de la llave activa en base de datos con respaldo transparente en variables de entorno `.env`.

### 2.3. Seguridad Basada en Roles (RBAC) y Auditoria Inmutable
- **Matriz de Permisos Granulares (`accounts.UserPermission`)**:
  - Conmutadores independientes por usuario: `can_use_transcriber`, `can_edit_symptoms`, `can_register_patients`, `can_view_emr`, `can_view_fhir`, `can_manage_config`.
  - Endpoint de actualizacion administrativa: `PATCH /api/security/users/<id>/permissions/`.
- **Bloqueo Fisico en UI**:
  - Bloqueo de botones de grabacion ASR y edicion de sintomas si el usuario carece de permisos, acompanado de advertencias visuales y notificaciones toast.
- **Trazabilidad Inmutable (`accounts.AuditLog`)**:
  - Registro de eventos criticos (`LOGIN`, `TRIAGE_CREATED`, `TRIAGE_OVERRIDE`, `PERMISSIONS_UPDATED`, `KEY_REGISTERED`, `CONFIG_UPDATED`) con direccion IP y marca temporal inalterable.

### 2.4. Motor de Normalizacion Clinica (SNOMED-CT / CIE-10)
- **Servicio `POST /api/transcribe/normalize/`**:
  - Analisis con LLM (Gemini) estructurado en JSON y motor de respaldo de reglas clinicas para traduccion de lenguaje coloquial ("le aprieta el pecho", "falta el aire", "posartan", "presion alta") a conceptos estandarizados (opresion toracica, disnea, losartan, hipertension arterial).
- **Monitor Reactivo (`NormalizationMonitor.tsx`)**:
  - Entrada editable con selector de casos predefinidos de urgencias.
  - Visualizacion paralela crudo vs estandarizado con resaltado semantico.
  - Tabla ontologica interactiva con codigos numericos y filtrado por categorias (Sintoma, Signo, Medicamento, Antecedente).

### 2.5. Motor de Triaje Interactivo con Nivel Editable
- **Persistencia Desacoplada (`triage.TriageSession`)**:
  - Campos `ai_level` (nivel propuesto por el modelo), `final_level` (nivel ratificado por el medico), `is_level_modified` (booleano) y `agreement_score` (escala 0.0 a 1.0).
- **Control Stepper en UI (`TriageDashboard.tsx`)**:
  - Botones interactivos `+` y `-` para navegacion entre los 5 niveles (I al V).
  - Transicion visual de gradientes y bordes segun escala estandar:
    - Nivel I: Rojo (`#ef4444` / Resucitacion inmediata)
    - Nivel II: Naranja (`#f97316` / Emergencia)
    - Nivel III: Amarillo/Ambar (`#eab308` / Urgencia)
    - Nivel IV: Verde (`#22c55e` / Urgencia Menor)
    - Nivel V: Azul (`#3b82f6` / No Urgente)
  - Badge de estado ("IA Concordante" vs "Ajustado por Medico").
  - Sobreescritura persistente mediante `PATCH /api/triage/sessions/<id>/override_level/`.

### 2.6. Telemetria y Metricas de Evaluacion Humano-IA
- **Endpoint Analitico `GET /api/triage/sessions/evaluation_metrics/`**:
  - Tasa de concordancia global (% de casos identicos).
  - Indice Kappa de Cohen ponderado con interpretacion clinica cualitativa.
  - Deriva de severidad (desviacion neta promedio: positiva indica sobreclasificacion medica hacia menor gravedad, negativa indica aumento de urgencia).
  - Tasa de retencion de entidades sintomaticas.
- **Panel Reactivo (`MetricsDashboard.tsx`)**:
  - Tarjetas KPI con umbrales y metas hospitalarias.
  - Grafico comparativo de distribucion de niveles (Volumen IA vs Medico).
  - Tabla de auditoria de sesiones recientes con fecha y score de concordancia.

### 2.7. Simulador HCE / HIS en Estetica Oscura
- **Rediseno Visual (`EMRSimulator.tsx`)**:
  - Reemplazo de la interfaz clara por la paleta oscura clinica unificada (`bg-slate-900`/`bg-slate-950`).
- **Conexion a Datos Reales (`GET /api/triage/sessions/emr_patients/`)**:
  - Consulta directa de admisiones en base de datos.
  - Detalle demografico, signos vitales y sintomas extraidos.
  - Selector y asignacion de Boxes hospitalarios (`REAN-01`, `BOX-01` a `BOX-06`, `SALA-OBSERVACION`) con actualizacion de estado clinico.

### 2.8. Monitor de Interoperabilidad FHIR R4
- **Persistencia de Transacciones (`triage.FHIRMessageLog`)**:
  - Almacenamiento de cada mensaje entrante/saliente con codigo de estado HTTP, tipo de recurso, identificador FHIR y resultado de validacion.
- **Visor Estructurado (`FHIRMonitor.tsx`)**:
  - Lista cronologica de transacciones.
  - Inspector de payloads JSON R4 con resaltado sintactico.
  - Resumen de recursos anidados (`Patient`, `Encounter`, `Observation`).
  - Transmision de bundles de prueba en tiempo real hacia `/api/fhir/`.

---

## 3. Brechas Identificadas y Limitaciones Actuales

A pesar de que el sistema cumple a cabalidad con la funcionalidad logica y la persistencia en base de datos, se documentan las siguientes brechas tecnicas y dependencias operativas:

### 3.1. Procesamiento ASR (Whisper) en Host de Desarrollo vs Docker
- **Brecha**: La libreria `faster-whisper` requiere dependencias nativas de CUDA y cuDNN para aceleracion por hardware en Windows.
- **Mecanismo de Mitigacion Implementado**: Se implemento un bloqueo `try/except` con fallback seguro en `whisper_engine.py` para permitir la ejecucion de comandos administrativos de Django y tests de integracion en entornos host sin GPU dedicada.
- **Impacto**: La transcripcion acustica en tiempo real con latencia minima depende de la ejecucion del contenedor Docker `backend` con runtime NVIDIA configurado, o de la utilizacion del modo de transcripcion asistida/pregrabada en el host.

### 3.2. Servidor FHIR Externo (HAPI-FHIR / Firely)
- **Brecha**: El endpoint `/api/fhir/` valida la conformidad semantica del esquema R4 y persiste los registros en la base de datos local (`FHIRRecord` y `FHIRMessageLog`), pero no existe un relay HTTP saliente hacia un servidor HAPI-FHIR externo en la nube.
- **Impacto**: Para una interoperabilidad institucional federada fuera del entorno hospitalario simulado, se requiere anadir una tarea en segundo plano (Celery/Redis) que retransmita el bundle JSON al endpoint FHIR externo configurado en `SystemConfiguration`.

### 3.3. Servidor Ontologico Integral (Ontoserver / RF2 Release)
- **Brecha**: El motor de normalizacion utiliza una combinacion de LLM (Gemini) y un catalogo relacional de reglas clinicas SNOMED-CT de alta frecuencia de urgencias.
- **Impacto**: No contiene el volcado completo de la ontologia SNOMED-CT (archivos RF2 de mas de 350.000 conceptos activos), el cual demandaria un motor de busqueda ontologica dedicado (e.g., Elasticsearch o servidor Snowstorm/Ontoserver) con varios gigabytes de memoria. La aproximacion actual con LLM y catalogo rapido cubre los escenarios de urgencias con precision aceptable para triaje.

### 3.4. Gestion de Sesiones Abiertas de Transcripcion
- **Brecha**: El almacenamiento de buffers de audio en `whisper_engine.py` opera mediante diccionarios en memoria protegidos con `threading.Lock`.
- **Impacto**: En una arquitectura con balanceo de carga horizontal (multiples pods o instancias de backend), las sesiones de grabacion en streaming requeririan persistencia compartida en Redis o comunicacion via WebSockets/WebRTC en lugar de HTTP polling tradicional.

---

## 4. Matriz de Endpoints y Servicios

| Metodo | Endpoint | Descripcion | Autenticacion |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login/` | Autenticacion JWT con verificacion de cuenta | No |
| `POST` | `/api/auth/register/` | Registro de personal con envio de OTP | No |
| `POST` | `/api/auth/verify/` | Validacion de codigo OTP de 6 digitos | No |
| `POST` | `/api/auth/password-reset/` | Solicitud y confirmacion de clave | No |
| `GET` | `/api/auth/me/` | Perfil del usuario autenticado y roles | Bearer JWT |
| `GET` | `/api/security/users/` | Directorio de usuarios y permisos | Bearer JWT |
| `PATCH`| `/api/security/users/<id>/permissions/` | Modificacion de matriz RBAC | Bearer JWT |
| `GET` | `/api/security/audit/` | Pistas de auditoria inmutables | Bearer JWT |
| `GET` | `/api/config/` | Parametros y modelos de IA activos | Bearer JWT |
| `POST` | `/api/config/keys/` | Registro y cifrado de llaves en boveda | Bearer JWT |
| `POST` | `/api/transcribe/normalize/` | Normalizacion SNOMED-CT / CIE-10 | Permisivo / JWT |
| `POST` | `/api/triage/sessions/analyze/` | Inferencia clinica y creacion de triaje | Permisivo / JWT |
| `PATCH`| `/api/triage/sessions/<id>/override_level/` | Ajuste manual de nivel y sintomas | Permisivo / JWT |
| `GET` | `/api/triage/sessions/evaluation_metrics/` | Calculo de Kappa, concordancia y deriva | Permisivo / JWT |
| `GET` | `/api/triage/sessions/emr_patients/` | Lista de admisiones para HCE | Permisivo / JWT |
| `GET` | `/api/triage/sessions/fhir_logs/` | Historial de transacciones FHIR R4 | Permisivo / JWT |
| `POST` | `/api/fhir/` | Ingestion e interoperabilidad FHIR R4 | Libre / Publico |

---

## 5. Recomendaciones para Despliegue en Produccion

1. **Persistencia en Postgres**: Migrar de SQLite a PostgreSQL en produccion actualizando `DATABASE_URL` en variables de entorno.
2. **Workers de Fondo**: Incorporar Celery con Redis para la sincronizacion asincrona de bundles FHIR y generacion de reportes en segundo plano.
3. **Contenedor GPU**: Levantar el servicio `backend` en Docker con soporte `nvidia-container-toolkit` para transcripcion ASR sub-segundo con faster-whisper.
4. **Rotacion de Clave AES**: Establecer politicas semestrales de re-cifrado de credenciales en caso de modificacion de `SECRET_KEY`.
