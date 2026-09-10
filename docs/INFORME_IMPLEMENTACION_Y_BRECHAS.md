# Informe Tecnico de Implementacion, Arquitectura y Brechas del Sistema

**Fecha:** 2026-09-10  
**Proyecto:** AI-Triage Hospitalario (Tesis de Grado / Sistema de Soporte Clinico)  
**Rama Base:** `develop`  
**Autor:** Ingenieria de Software y Arquitectura Clinica  

---

## 1. Resumen Ejecutivo

El sistema AI-Triage ha sido transformado de una arquitectura con componentes prototipales y simulaciones estaticas a una plataforma hospitalaria integral, atestada en base de datos relacional con control de acceso basado en roles (RBAC), auditoria inmutable, cifrado simetrico de credenciales, motor semantico de triaje, telemetria matematica de concordancia Humano-IA, suites automatizadas de pruebas fullstack y despliegue orquestado multi-contenedor.

Todos los modulos mock y asignaciones simuladas fueron eliminados y sustituidos por capas de negocio persistentes que se comunican a traves de contratos REST tipados y validados (Pydantic v2 en backend y validadores de asercion en frontend Next.js 15). La interfaz de usuario fue refactorizada para ofrecer navegacion fluida y responsiva en entornos de escritorio y dispositivos moviles de urgencias.

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
  - Registro de eventos criticos (`LOGIN`, `TRIAGE_CREATED`, `TRIAGE_OVERRIDE`, `PERMISSIONS_UPDATED`, `KEY_REGISTERED`, `CONFIG_UPDATED`, `EMR_BOX_ASSIGNED`) con direccion IP y marca temporal inalterable.

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

### 2.7. Simulador HCE / HIS con Persistencia Real de Boxes
- **Rediseno Visual (`EMRSimulator.tsx`)**:
  - Reemplazo de la interfaz clara por la paleta oscura clinica unificada (`bg-slate-900`/`bg-slate-950`).
- **Consulta Real (`GET /api/triage/sessions/emr_patients/`)**:
  - Carga dinamica de sesiones de triaje y admisiones desde PostgreSQL.
  - Detalle demografico, signos vitales y entidades clinicas estructuradas.
- **Asignacion de Box Persistente (`POST /api/triage/sessions/<id>/assign_box/`)**:
  - Eliminacion total del `setTimeout` simulado.
  - Asignacion real y persistente del Box clinico (`REAN-01`, `BOX-01` a `BOX-06`, `SALA-OBSERVACION`) almacenada en `clinical_entities` de `TriageSession`.
  - Trazabilidad y auditoria de la accion en `AuditLog`.

### 2.8. Monitor de Interoperabilidad FHIR R4
- **Persistencia de Transacciones (`triage.FHIRMessageLog`)**:
  - Almacenamiento de cada mensaje entrante/saliente con codigo de estado HTTP, tipo de recurso, identificador FHIR y resultado de validacion.
- **Visor Estructurado (`FHIRMonitor.tsx`)**:
  - Lista cronologica de transacciones con filtros de estado.
  - Inspector de payloads JSON R4 con resaltado sintactico.
  - Resumen de recursos anidados (`Patient`, `Encounter`, `Observation`).
  - Transmision de bundles de prueba en tiempo real hacia `/api/fhir/`.

### 2.9. Capa de Validacion de Tipos y Resiliencia en Runtime
- **Backend (Pydantic v2 en `backend/core/validation.py`)**:
  - Esquemas tipados para autenticacion, registro, verificacion OTP, override de triaje, configuracion del sistema y asignacion de box EMR (`EMRBoxAssignSchema`).
  - Validacion estricta en campos criticos (emails RFC, enteros delimitados, booleanos, enums de proveedores de IA).
  - Flexibilidad controlada para estructuras polimorficas de salud (cargas FHIR JSON, sintomas en lista libre, metadatos clinicos).
  - Utilidad centralizada `validate_payload` con conversion transparente a excepciones estandar DRF (`ValidationError` con codigo HTTP 400).
- **Frontend (Aserciones y Validadores en `frontend/lib/validation.ts`)**:
  - Validaciones reactivas para correos electronicos, cadenas numericas (OTP de 6 digitos, identificadores de documento), telefonos, fechas ISO y rangos de niveles de urgencia (1 a 5).
  - Sanitizacion de entradas y emision visual de advertencias (badges ambar y bordes de alerta) en tiempo de edicion sin interrumpir el flujo clinico.

### 2.10. Suites de Pruebas Automatizadas Fullstack
- **Frontend (Vitest + React Testing Library)**:
  - 10 archivos de prueba y 47 tests unitarios/componentes ejecutandose al 100% de exito (~3.3s).
  - Cobertura: navegacion de la app, apertura y conmutacion del drawer movil, asignacion EMR y vistas adaptativas, monitores FHIR y Normalizacion, paneles de Seguridad y Metricas, y logica de validaciones tipadas.
- **Backend (Pytest + pytest-django)**:
  - 54 tests unitarios y de integracion ejecutandose al 100% de exito (~26s).
  - Cobertura: ciclo de vida de autenticacion y verificacion OTP, seguridad RBAC y registros de auditoria, modelos criptograficos de credenciales, motor Whisper y limpieza TTL, endpoints FHIR R4, calculo matematico de concordancia de triaje y esquemas de validacion Pydantic.

### 2.11. Responsividad Movil Integral y Adaptabilidad de Interfaz
- **Encabezado Superior Movil y Drawer Deslizante (`AppNavigation.tsx`)**:
  - Barra superior compacta visible unicamente en pantallas reducidas (`md:hidden`) con boton de accion rapida y logotipo del sistema.
  - Drawer flotante tipo Sheet con fondo desenfocado (`backdrop-blur-sm`), control de cierre táctil y badges de usuario autenticado.
  - Barra lateral colapsable preservada sin regresiones para pantallas de escritorio (`hidden md:flex`).
- **Navegacion Adaptativa por Vistas**:
  - `EMRSimulator.tsx` y `FHIRMonitor.tsx`: Conmutacion condicional entre vista de lista y vista de detalle (`mobileView: 'list' | 'detail'`) con boton de retorno, evitando el colapso horizontal de tablas y visualizadores JSON en pantallas moviles.
  - `TriageDashboard.tsx`: Alturas minimas adaptativas y ocultamiento de manijas de redimensionamiento tactiles en dispositivos moviles.

### 2.12. Orquestacion Contenerizada con Docker Compose
- **Despliegue Multi-Contenedor Saludable**:
  - `ai_triage_nginx`: Proxy inverso unificado en puerto 80 con reescritura de URLs hacia API y Frontend.
  - `ai_triage_backend`: Imagen multi-etapa basada en Python 3.12-slim, servidor Gunicorn en puerto 8000, scripts de entrypoint con migraciones automaticas y healthcheck activo contra `/api/health_check/`.
  - `ai_triage_frontend`: Imagen multi-etapa optimizada basada en Node 20 Alpine y Next.js Standalone en puerto 3000.
  - `ai_triage_postgres`: Base de datos PostgreSQL 16 Alpine persistente.
  - `ai_triage_redis`: Cola y almacenamiento temporal Redis 7 Alpine.
  - `ai_triage_mailpit`: Servidor SMTP y visor web de correos transaccionales.

---

## 3. Brechas Identificadas y Limitaciones Actuales

A pesar de que el sistema cumple a cabalidad con la funcionalidad logica, validacion tipada y persistencia en base de datos, se documentan las siguientes brechas tecnicas y dependencias operativas:

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
- **Brecha**: El almacenamiento de buffers de audio en `whisper_engine.py` opera mediante diccionarios en memoria protegidos con `threading.Lock` y limpieza TTL automatica.
- **Impacto**: En una arquitectura con balanceo de carga horizontal (multiples pods o instancias de backend), las sesiones de grabacion en streaming requeririan persistencia compartida en Redis o comunicacion via WebSockets/WebRTC en lugar de HTTP polling tradicional.

---

## 4. Matriz de Endpoints y Servicios

| Metodo | Endpoint | Descripcion | Esquema de Validacion | Autenticacion |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login/` | Autenticacion JWT con verificacion de cuenta | `LoginSchema` (Pydantic) | No |
| `POST` | `/api/auth/register/` | Registro de personal clinico con envio de OTP | `RegisterSchema` (Pydantic) | No |
| `POST` | `/api/auth/verify/` | Validacion de codigo OTP de 6 digitos | `VerifyCodeSchema` (Pydantic) | No |
| `POST` | `/api/auth/password-reset/` | Solicitud y confirmacion de recuperacion | `PasswordResetRequest/Confirm` | No |
| `GET` | `/api/auth/me/` | Perfil del usuario autenticado y roles | N/A | Bearer JWT |
| `GET` | `/api/security/users/` | Directorio de usuarios y permisos | N/A | Bearer JWT |
| `PATCH`| `/api/security/users/<id>/permissions/` | Modificacion de matriz RBAC | `UserPermissionUpdateSchema` | Bearer JWT |
| `GET` | `/api/security/audit/` | Pistas de auditoria inmutables | N/A | Bearer JWT |
| `GET` | `/api/config/` | Parametros y modelos de IA activos | N/A | Bearer JWT |
| `PATCH`| `/api/config/` | Actualizacion de configuracion del sistema | `SystemConfigUpdateSchema` | Bearer JWT |
| `POST` | `/api/config/keys/` | Registro y cifrado de llaves en boveda AES | `APIKeyCreateSchema` (Pydantic) | Bearer JWT |
| `POST` | `/api/transcribe/normalize/` | Normalizacion SNOMED-CT / CIE-10 | `NormalizeTextSchema` (Pydantic) | Permisivo / JWT |
| `POST` | `/api/triage/sessions/analyze/` | Inferencia clinica y creacion de triaje | N/A | Permisivo / JWT |
| `PATCH`| `/api/triage/sessions/<id>/override_level/` | Ajuste manual de nivel y sintomas | `TriageOverrideSchema` (Pydantic) | Permisivo / JWT |
| `POST` | `/api/triage/sessions/<id>/assign_box/` | Asignacion persistente de Box hospitalario | `EMRBoxAssignSchema` (Pydantic) | Permisivo / JWT |
| `GET` | `/api/triage/sessions/evaluation_metrics/` | Calculo de Kappa, concordancia y deriva | N/A | Permisivo / JWT |
| `GET` | `/api/triage/sessions/emr_patients/` | Lista de admisiones para HCE | N/A | Permisivo / JWT |
| `GET` | `/api/triage/sessions/fhir_logs/` | Historial de transacciones FHIR R4 | N/A | Permisivo / JWT |
| `POST` | `/api/fhir/` | Ingestion e interoperabilidad FHIR R4 | `FHIRSyncSchema` (Pydantic) | Libre / Publico |
| `GET` | `/api/health_check/` | Estado y telemetria del motor Whisper ASR | N/A | Libre / Publico |

---

## 5. Recomendaciones para Despliegue en Produccion

1. **Persistencia en Postgres**: El entorno Docker ya cuenta con PostgreSQL 16 Alpine integrado como base de datos predeterminada con indices optimizados para busquedas de pacientes y auditoria.
2. **Workers Asincronos de Fondo**: Incorporar tareas Celery con Redis para la sincronizacion asincrona de bundles FHIR y generacion pesada de reportes analiticos.
3. **Contenedor GPU**: Levantar el servicio `backend` en Docker con soporte `nvidia-container-toolkit` para transcripcion ASR sub-segundo con faster-whisper.
4. **Rotacion de Clave AES**: Establecer politicas semestrales de re-cifrado de credenciales en caso de modificacion de `SECRET_KEY`.
