# Auditoria Tecnica Integral — AI-Triage

**Fecha:** 2026-09-10  
**Rama auditada:** `develop`  
**Alcance:** Backend (Django/Python), Frontend (Next.js/TypeScript), Infraestructura Docker, Esquemas de base de datos, Seguridad, Deuda tecnica.

---

## 1. Severidades Utilizadas

| Nivel | Descripcion |
|:------|:------------|
| **CRITICO** | Bug o gap de seguridad con impacto directo en produccion o datos clinicos |
| **ALTO** | Deuda tecnica significativa que degrada confiabilidad o escalabilidad |
| **MEDIO** | Inconsistencia de diseno, cobertura faltante o patron suboptimo |
| **BAJO** | Mejoras menores de calidad, legibilidad o consistencia |

---

## 2. Seguridad

### [CRITICO] Autenticacion de triaje completamente desactivada
**Archivo:** [`backend/triage/views.py#L23`](file:///d:/Datos/Estudio/Universidad%202/semestre%209/TG1/ai-triage/backend/triage/views.py#L23)

```python
permission_classes = [AllowAny]
```

Todo el `TriageSessionViewSet` — incluyendo creacion de triajes, override de niveles, asignacion de boxes y lectura de pacientes — es accesible sin autenticacion. Cualquier actor externo que conozca los endpoints puede crear o modificar sesiones clinicas, alterar el nivel de triaje de pacientes reales, o leer datos de admisiones sin tener sesion valida.

**Impacto:** Violacion RBAC; modificacion maliciosa de decisiones clinicas de IA; lectura no autorizada de datos de salud (HIPAA/RGPD). 

**Correccion sugerida:** Reemplazar `AllowAny` por `IsAuthenticatedOrReadOnly` minimo, o mejor `IsAuthenticated` con excepciones granulares en acciones especificas.

---

### [CRITICO] Ausencia total de rate limiting en endpoints de autenticacion
**Archivos:** `backend/config/settings.py`, `backend/accounts/views.py`

No existe ningun throttle de DRF (`DEFAULT_THROTTLE_CLASSES`) en endpoints de login, verificacion OTP, reenvio de codigo o reset de contrasena. Esto habilita:
- Ataques de fuerza bruta sobre OTPs (espacio de 10^6 con codigos de 6 digitos sin bloqueo).
- Enumeracion de usuarios registrados via respuestas diferenciadas.
- Denial of Service por saturacion del backend con peticiones concurrentes.

**Correccion sugerida:** Agregar en `settings.py`:
```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '10/minute'},
}
```
Con throttle especifico para auth y OTP de 5/minuto.

---

### [ALTO] JWT Refresh Token sin lista negra
**Archivo:** [`backend/config/settings.py#L144`](file:///d:/Datos/Estudio/Universidad%202/semestre%209/TG1/ai-triage/backend/config/settings.py#L144)

```python
'BLACKLIST_AFTER_ROTATION': False,
```

Con `ROTATE_REFRESH_TOKENS = True` pero `BLACKLIST_AFTER_ROTATION = False`, un refresh token robado puede seguir siendo utilizado indefinidamente incluso despues de que el usuario ha renovado su sesion. La app tampoco tiene endpoint de logout que invalide el token activo.

**Correccion sugerida:** Agregar `rest_framework_simplejwt.token_blacklist` a `INSTALLED_APPS` y habilitar `BLACKLIST_AFTER_ROTATION: True`. Implementar endpoint `POST /api/auth/logout/` que haga `refresh_token.blacklist()`.

---

### [ALTO] Tokens JWT almacenados en `localStorage` (XSS Vulnerable)
**Archivos:** `frontend/lib/api.ts`, `frontend/app/login/page.tsx`, `frontend/components/AppNavigation.tsx`

El token `access_token`, `refresh_token` y `user_profile` completo se persisten en `localStorage`. Este mecanismo es inherentemente vulnerable a XSS: cualquier script inyectado puede extraer las credenciales y suplantar al usuario medico. Para un sistema hospitalario con datos clinicos, esto representa un riesgo de cumplimiento significativo.

**Correccion sugerida:** Migrar a cookies `httpOnly; Secure; SameSite=Strict` manejadas por el backend, eliminando la exposicion de tokens al entorno JavaScript.

---

### [ALTO] `SECRET_KEY` y credenciales con fallback inseguros
**Archivo:** `backend/config/settings.py#L14`

```python
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-triage-prototype-key-3289139')
```

El fallback hardcodeado expone la clave criptografica en caso de que la variable de entorno no se configure. Cualquier deployment sin `.env` correcto expone las firmas JWT, las cookies de sesion y el cifrado de la boveda de llaves AES-256.

**Correccion sugerida:** Eliminar el fallback. Hacer que el modulo falle explicitamente en arranque si `SECRET_KEY` no esta configurada:
```python
SECRET_KEY = os.environ['SECRET_KEY']  # KeyError intencional si falta
```

---

### [MEDIO] `ALLOWED_HOSTS = ['*']` en settings base
**Archivo:** `backend/config/settings.py#L17`

Con `ALLOWED_HOSTS = ['*']`, el backend acepta peticiones HTTP con cualquier valor en el header `Host`, habilitando ataques de Host Header Injection que pueden derivar en CSRF o redireccionamientos maliciosos.

**Correccion sugerida:** Restringir a los dominios reales via variable de entorno, con validacion de startup que falle si `DEBUG=False` y `ALLOWED_HOSTS` contiene `'*'`.

---

### [MEDIO] Endpoint FHIR completamente publico sin autenticacion
**Archivo:** `backend/triage/views.py#L400-L465`

El endpoint `POST /api/fhir/` acepta y persiste bundles FHIR arbitrarios sin ningun mecanismo de autenticacion. Cualquier actor externo puede inyectar transacciones FHIR falsas en el log clinico del sistema.

---

## 3. Arquitectura y Deuda Tecnica Backend

### [ALTO] Historico de sesiones de triaje almacenado solo en `localStorage`
**Archivo:** `frontend/components/TriageDashboard.tsx#L218-L298`

El historial de sesiones clinicas del panel de triaje se lee y escribe exclusivamente en `localStorage` del navegador (clave `triage_sessions`). Esto implica:
- Datos clinicos perdidos al limpiar cache del navegador o cambiar de dispositivo.
- Sin sincronizacion cross-session entre multiples usuarios/terminales hospitalarias.
- Los datos no estan en base de datos ni son auditables.

La base de datos ya tiene la entidad `TriageSession` con persistencia completa. El historial deberia leerse desde `GET /api/triage/sessions/` en lugar de `localStorage`.

---

### [ALTO] `time.sleep(0.5)` sincronico en endpoint FHIR (worker bloqueado)
**Archivo:** `backend/triage/views.py#L410`

```python
time.sleep(0.5)
```

Este `sleep` bloquea el worker de Gunicorn durante 500ms por cada llamada al endpoint `/api/fhir/`. Con el modelo de workers sincronicos por defecto, esto limita a 2 peticiones/segundo por worker antes de saturar el pool. En un entorno hospitalario con multiples terminales, genera cuellos de botella inmediatos.

**Correccion sugerida:** Eliminar el `sleep`. Si se requiere simular latencia externa, hacerlo como tarea asincrona con Celery.

---

### [ALTO] Inicializacion global de `engine` con variable global mutable en `transcription/views.py`
**Archivo:** `backend/transcription/views.py#L22,27`

```python
engine = None
global engine
```

El uso de una variable global mutable `engine` en un modulo de Django expone condiciones de carrera en entornos multi-worker (multiples instancias Gunicorn). Si dos requests intentan inicializar el engine simultaneamente antes de que `engine` sea asignado, se pueden crear multiples instancias `WhisperModel` en memoria. El `WhisperEngine` ya implementa Singleton con lock; el patron global en la vista duplica responsabilidades.

**Correccion sugerida:** Eliminar la variable `engine` del modulo y llamar directamente `WhisperEngine()` en cada request (el Singleton garantiza una sola instancia).

---

### [ALTO] `TriageSession.save()` recomputa `agreement_score` en cada guardado completo
**Archivo:** `backend/triage/models.py#L28-L37`

El metodo `save()` sobreescrito recalcula `is_level_modified` y `agreement_score` en cada llamada, incluyendo `save(update_fields=['clinical_entities'])` del endpoint `assign_box`. Esto genera recalculos de campos criticos en operaciones que no los modifican, con riesgo de corromper valores si los campos `ai_level`/`final_level` no estan correctamente hidratados en el objeto en memoria.

**Correccion sugerida:** Aplicar el recalculo solo si los campos relevantes estan siendo modificados:
```python
def save(self, *args, **kwargs):
    update_fields = kwargs.get('update_fields')
    if update_fields is None or 'final_level' in update_fields or 'ai_level' in update_fields:
        # recalculo
```

---

### [MEDIO] Captura silenciosa de excepciones en AuditLog (`except Exception: pass`)
**Archivo:** `backend/triage/views.py#L119,176`

```python
try:
    AuditLog.objects.create(...)
except Exception:
    pass
```

Si la escritura en `AuditLog` falla (timeout de BD, constraint violation, disco lleno), la excepcion es absorbida en silencio. El sistema continua operando sin trazabilidad clinica, sin alertas, y sin ningun mecanismo de reintento.

**Correccion sugerida:** Loguear el error con `logger.error()` al menos:
```python
except Exception as audit_err:
    logger.error(f"AuditLog write failed for action TRIAGE_CREATED: {audit_err}", exc_info=True)
```

---

### [MEDIO] `evaluation_metrics` carga TODAS las sesiones en memoria sin paginacion
**Archivo:** `backend/triage/views.py#L198`

```python
sessions = TriageSession.objects.all().order_by('-created_at')
```

El calculo de metricas (drift, retencion de sintomas, Kappa) itera sobre el queryset completo cargado en memoria Python. Con miles de sesiones clinicas, esto genera un uso de RAM proporcional al volumen total de datos y degrada la respuesta del endpoint analitico.

**Correccion sugerida:** Usar agregaciones en SQL via `annotate()` y `aggregate()` para drift y conteos, reservando la iteracion Python solo para la lista de sesiones recientes (ya limitada a 10).

---

### [MEDIO] Valores hardcodeados en respuestas de `emr_patients`
**Archivo:** `backend/triage/views.py#L308,325,327`

```python
box_num = f"BOX-0{((s.id * 3) % 8) + 1}"  # Determinismo falso
"birth_date": pat.birth_date or "1985-05-12"  # Fecha ejemplo expuesta
"insurance": pat.insurance or "EPS Sanitas"   # EPS default hardcoded
```

Datos ficticios se mezclan con datos reales de pacientes en la respuesta del simulador HCE. En produccion, esto podria presentar informacion incorrecta como si fuera real.

**Correccion sugerida:** Retornar `null`/`None` para campos faltantes en lugar de valores ficticios. El frontend debe renderizar el campo como "No registrado".

---

### [MEDIO] `ai_analyzer.py` sin manejo de errores HTTP ni timeout para la API de Gemini
**Archivo:** `backend/triage/ai_analyzer.py#L77-L88`

La llamada a `client.models.generate_content()` no tiene timeout configurado ni manejo de errores de red (timeouts, rate limits `429`, errores de autenticacion `401`). Si la API de Gemini no responde, el worker de Gunicorn queda bloqueado indefinidamente hasta que el SO cierre la conexion.

**Correccion sugerida:** Configurar timeout en el cliente y capturar excepciones de red explicitamente:
```python
try:
    response = client.models.generate_content(...)
except Exception as api_err:
    logger.error(f"Gemini API call failed: {api_err}")
    return {"error": "AI service temporarily unavailable", "fallback": True}
```

---

### [MEDIO] Esquema `SystemConfigUpdateSchema` no utilizado en las vistas de `system_settings`
**Archivo:** `backend/core/validation.py#L144-L152`

El esquema `SystemConfigUpdateSchema` define campos (`active_nlp_provider`, `auto_snomed_normalization`, `auto_fhir_dispatch`, `session_timeout_seconds`, `max_daily_triages`) que no existen en el modelo `SystemConfiguration`. Hay un desacoplamiento entre el esquema de validacion y el modelo real, lo que significa que los campos adicionales del schema son ignorados silenciosamente sin error.

---

### [MEDIO] `db.sqlite3` commiteado en el repositorio
**Archivo:** `backend/db.sqlite3` (en `.gitignore` no excluido del repo)

La base de datos SQLite local con datos de desarrollo esta rastreada en git. Esto puede exponer:
- OTPs de verificacion de pruebas.
- Datos de pacientes ficticios usados en desarrollo.
- Credenciales cifradas de prueba.

**Correccion sugerida:** Agregar `backend/db.sqlite3` a `.gitignore` y ejecutar `git rm --cached backend/db.sqlite3`.

---

### [BAJO] Modulo de logging duplicado entre `whisper_engine.py` y `transcription/views.py`
**Archivos:** `backend/transcription/whisper_engine.py#L35-L41`, `backend/transcription/views.py#L12-L18`

Ambos modulos configuran manualmente un `FileHandler` hacia el mismo archivo `backend_debug.log`. Esto resulta en entradas duplicadas en el log y competencia por el file descriptor. La configuracion de logging deberia centralizarse en `settings.py` via `LOGGING`.

---

## 4. Arquitectura y Deuda Tecnica Frontend

### [ALTO] `useState<any>` en componentes clinicos criticos
**Archivo:** `frontend/components/TriageDashboard.tsx#L32,63,65`

```typescript
const [currentUser, setCurrentUser] = useState<any>(null);
const [analysisResult, setAnalysisResult] = useState<any>(null);
const [editedEntities, setEditedEntities] = useState<any>(null);
```

El uso de `any` elimina toda garantia del sistema de tipos en los datos mas criticos del sistema: el perfil del usuario autenticado (y por tanto sus permisos RBAC) y el resultado del analisis de triaje clinico. Un error de forma en la respuesta de la API no generaria error de TypeScript, pasaria silenciosamente y podria causar comportamientos inesperados en la UI clinica.

**Correccion sugerida:** Definir interfaces `UserProfile`, `AnalysisResult`, `TriageEntities` y tipar los estados correctamente.

---

### [ALTO] `TriageDashboard.tsx` tiene 1.451 lineas — componente monolitico
**Archivo:** `frontend/components/TriageDashboard.tsx`

Con mas de 1.400 lineas, el componente de dashboard de triaje combina: logica de grabacion ASR, manejo del transcript editable, analisis clinico, stepper de niveles, historial de sesiones, exportacion PDF/JSON, formulario de paciente, sincronizacion FHIR y visualizacion de entidades NER. Esto viola el principio de responsabilidad unica y hace el componente:
- Dificilmente testeable en aislamiento.
- Propenso a re-renders completos por cambios de estado locales.
- Imposible de mantener en paralelo por multiples desarrolladores.

**Correccion sugerida:** Descomponer en: `<ASRRecorder>`, `<TranscriptEditor>`, `<PatientForm>`, `<TriageLevelStepper>`, `<TriageResultPanel>`, `<SessionHistory>`.

---

### [MEDIO] `fetchWithAuth` no implementa renovacion automatica del access token
**Archivo:** `frontend/lib/api.ts#L30-L37`

Cuando el backend retorna `401`, el cliente elimina los tokens y redirige a `/login`, sin intentar renovar el `access_token` usando el `refresh_token`. Esto genera sesiones interrumpidas cada 8 horas (lifetime configurado) incluso si el usuario sigue activo.

**Correccion sugerida:** Implementar logica de refresh automatico con `POST /api/auth/refresh/` antes de redirigir al login, con control de loop para evitar refreshes infinitos.

---

### [MEDIO] Lectura de perfil de usuario desde `localStorage` sin validacion de esquema
**Archivo:** `frontend/components/TriageDashboard.tsx#L39-L44`

```typescript
const stored = localStorage.getItem('user_profile');
if (stored) { setCurrentUser(JSON.parse(stored)); }
catch (e) {}
```

El perfil del usuario (y sus permisos RBAC) se lee de `localStorage` y se parsea sin validacion de esquema. Si el objeto en `localStorage` esta corrupto, es de una version anterior o fue manipulado, los permisos podrian aplicarse incorrectamente (e.g., `can_edit_symptoms: undefined` evaluaria como `truthy` o `falsy` dependiendo del uso).

**Correccion sugerida:** Validar el perfil contra un esquema Zod antes de usarlo, o re-fetch del servidor en cada montaje del componente.

---

### [MEDIO] `validation.tsx` declara funciones de validacion pero los componentes principales no las usan consistentemente
**Archivo:** `frontend/lib/validation.tsx`, `frontend/components/ConfigPanel.tsx`, `frontend/components/SecurityPanel.tsx`

Las funciones `validateEmail`, `validateOtpCode`, `validatePhone` existen en `lib/validation.tsx`, pero los paneles de Configuracion y Seguridad realizan validacion inline ad-hoc sin usar el modulo centralizado. Falta consistencia en la experiencia de validacion entre secciones.

---

### [MEDIO] GEMINI_API_KEY expuesto en variables de entorno del contenedor frontend
**Archivo:** `docker-compose.yml#L114`

```yaml
- GEMINI_API_KEY=${GEMINI_API_KEY:-}
```

La clave de API de Gemini es inyectada en el contenedor frontend. En Next.js, las variables sin el prefijo `NEXT_PUBLIC_` no se exponen al cliente, pero su presencia en el contenedor expone la variable al filesystem del contenedor, que puede ser inspeccionado si el contenedor es comprometido. La API key de Gemini deberia residir exclusivamente en el backend.

---

### [BAJO] Puerto PostgreSQL `5432` expuesto directamente en Docker Compose
**Archivo:** `docker-compose.yml#L10-L11`

```yaml
ports:
  - "5432:5432"
```

El puerto de la base de datos esta expuesto al host. En produccion, esto permite conexiones directas a PostgreSQL desde la red del host o desde redes adyacentes si el firewall no esta correctamente configurado. PostgreSQL deberia ser accesible solo dentro de la red interna `ai_triage_network`.

---

## 5. Cobertura de Pruebas — Gaps Identificados

| Area | Estado | Gap |
|:-----|:-------|:----|
| `accounts` — autenticacion y OTP | Cubierto | Sin tests de brute-force sobre OTP |
| `accounts` — RBAC | Cubierto | Sin test de acceso a endpoint de triaje sin autenticacion |
| `triage` — `analyze` action | No cubierto | Sin test de creacion de sesion via transcript |
| `triage` — `evaluation_metrics` carga masiva | No cubierto | Sin test de rendimiento con N sesiones |
| `triage` — `emr_patients` fallback de box | No cubierto | Sin test del algoritmo deterministico de box |
| `fhir_sync` — inyeccion de payload malicioso | No cubierto | Sin test de rejection de bundles sin autenticacion |
| Frontend — `TriageDashboard` flujo completo | No cubierto | Sin test E2E o de integracion del flujo ASR → analisis → guardado |
| Frontend — `fetchWithAuth` refresh token | No cubierto | Sin test de renovacion automatica de token |
| Frontend — Permisos RBAC en UI | No cubierto | Sin test que verifique bloqueo visual de controles por permisos |

---

## 6. Inconsistencias de Diseno

### Action string no estandarizado en AuditLog
**Archivo:** `backend/triage/views.py#L363`

```python
action="ASSIGN_EMR_BOX"  # vs otros: 'TRIAGE_CREATED', 'TRIAGE_OVERRIDE'
```

La mayoria de acciones usan snake_case upper (`TRIAGE_CREATED`) pero `ASSIGN_EMR_BOX` usa un formato distinto al esperado `EMR_BOX_ASSIGNED`. Sin un enum centralizado para las acciones de auditoria, la inconsistencia se propagara y dificultara queries analiticos sobre el log.

---

### `google-genai==0.3.0` es una version muy antigua (actual: 1.x)
**Archivo:** `backend/requirements.txt#L7`

La libreria `google-genai` en version `0.3.0` es una version alpha antigua. La API publica cambio significativamente en versiones `1.x`. El codigo ya usa `client.models.generate_content()` que corresponde a la API de la version actual, lo que sugiere que puede haber incompatibilidades silenciosas o que la libreria es mas nueva de lo que el pin indica.

---

### `boto3==1.34.84` incluido sin uso identificado
**Archivo:** `backend/requirements.txt#L11`

`boto3` (SDK de AWS) esta como dependencia pero no existe ninguna referencia a servicios S3, SQS, SES u otros en el codigo. Esta dependencia aumenta el tiempo de build y la superficie de ataque del contenedor innecesariamente.

---

### `sendgrid==6.10.0` incluido sin uso identificado
**Archivo:** `backend/requirements.txt#L30`

Similar a `boto3`, `sendgrid` esta declarado como dependencia pero el sistema de correo usa SMTP local via Mailpit. No hay llamadas al SDK de Sendgrid en el codigo.

---

## 7. Resumen de Prioridades y Estado de Resolucion

| # | Severidad | Descripcion | Archivo | Estado |
|:--|:----------|:------------|:--------|:-------|
| 1 | CRITICO | Todo `TriageSessionViewSet` sin autenticacion (`AllowAny`) | `triage/views.py:23` | **RESUELTO** (`012d8a6`) — Aplicado `IsAuthenticatedOrReadOnly` |
| 2 | CRITICO | Sin rate limiting en endpoints de auth y OTP | `config/settings.py` | **RESUELTO** (`012d8a6`) — Throttles `auth` (10/min) y `otp` (5/min) |
| 3 | ALTO | JWT refresh tokens sin lista negra | `config/settings.py:144` | **RESUELTO** (`012d8a6`) — `token_blacklist` y rotacion activa |
| 4 | ALTO | Tokens en `localStorage` (XSS vulnerable) | `lib/api.ts`, `login/page.tsx` | **EN HOJA DE RUTA** — Requiere cookies httpOnly en proxima iteracion |
| 5 | ALTO | `SECRET_KEY` con fallback inseguro hardcodeado | `config/settings.py:14` | **RESUELTO** (`012d8a6`) — Fallback eliminado; error explicito |
| 6 | ALTO | Historial clinico solo en `localStorage` | `TriageDashboard.tsx:218` | **EN HOJA DE RUTA** — Persistencia completa en BD lista; migrar UI historico |
| 7 | ALTO | `time.sleep(0.5)` sincronico bloquea workers | `triage/views.py:410` | **RESUELTO** (`012d8a6`) — Bloqueo sincronico eliminado |
| 8 | ALTO | Variable global `engine` con condicion de carrera | `transcription/views.py:22` | **RESUELTO** (`9267476`) — Singleton `WhisperEngine` directo |
| 9 | ALTO | `TriageDashboard.tsx` monolitico de 1.451 lineas | `TriageDashboard.tsx` | **EN HOJA DE RUTA** — Refactor modular planeado |
| 10 | ALTO | `useState<any>` en datos clinicos criticos (sin tipado) | `TriageDashboard.tsx:32,63,65` | **RESUELTO** (`4e31c14`) — Interfaces `UserProfile`, `AnalysisResult`, etc. |
| 11 | ALTO | Sin manejo de timeout ni errores en llamadas a Gemini | `ai_analyzer.py:77` | **RESUELTO** (`9267476`) — Timeout 30s y try/except estructurado |
| 12 | MEDIO | `TriageSession.save()` recalcula en updates parciales | `triage/models.py:28` | **RESUELTO** (`9267476`) — Evaluacion condicional de campos |
| 13 | MEDIO | `db.sqlite3` rastreado en git | `backend/db.sqlite3` | **VERIFICADO** — Excluido en `.gitignore` y no rastreado |
| 14 | MEDIO | Puerto PostgreSQL 5432 expuesto al host en Docker | `docker-compose.yml:10` | **RESUELTO** (`012d8a6`) — Puerto aislado en red interna |
| 15 | MEDIO | Dependencias no utilizadas (`boto3`, `sendgrid`) | `requirements.txt:11,30` | **RESUELTO** (`9267476`) — Dependencias eliminadas |
