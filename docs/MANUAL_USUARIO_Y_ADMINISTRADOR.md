# Manual de Usuario Clínico y Administrador del Sistema — AI-Triage

**Versión:** 1.0 (2026-10-27)  
**Sistema:** AI-Triage — Asistente Inteligente de Voz para la Clasificación Médica Automatizada  
**Normativa clínica de referencia:** Protocolo de Urgencias Christus Sinergia Salud / Resolución 5596 de 2015 (Ministerio de Salud y Protección Social de Colombia)  
**Población objetivo:** Pacientes adultos en admisión de urgencias hospitalarias y telemedicina asistida

---

## Parte I — Manual del Usuario Clínico

### 1. Acceso Seguro y Gestión de Sesión

1. **Requisitos del navegador:** Ingresar desde Google Chrome, Microsoft Edge o Mozilla Firefox actualizados a través de la URL institucional segura (`https://<dominio-hospital>/` o `https://localhost/`). El protocolo **HTTPS** es obligatorio para que el navegador autorice la captura del micrófono (`getUserMedia`).
2. **Registro e inicio de sesión:**
   - En el primer registro, el profesional ingresa correo institucional, nombre completo, documento de identidad, teléfono, rol solicitado y contraseña robusta.
   - El sistema envía un **código OTP de 6 dígitos** al correo electrónico registrado (con vigencia de 15 minutos y un único uso). Una vez verificado en pantalla, la cuenta queda activa con los permisos base de su rol.
   - Durante el inicio de sesión ordinario, la plataforma mantiene el token de acceso únicamente en la memoria volátil de la pestaña y renueva la sesión de forma transparente mediante una cookie segura `httpOnly`.
3. **Recuperación de contraseña y cierre de sesión:**
   - En caso de olvido, la opción *«¿Olvidó su contraseña?»* envía un código OTP al correo verificado para definir una nueva clave.
   - Al finalizar el turno, el botón **Cerrar sesión** de la barra lateral invalida inmediatamente la sesión en el servidor y limpia la memoria local.

---

### 2. Roles Asistenciales y Módulos Disponibles

La barra lateral adapta automáticamente las vistas visibles según los permisos otorgados por el servidor:

| Módulo en interfaz | Permiso requerido | Enfermero (`enfermero`) | Médico (`medico`) | Administrador (`admin`) |
| :--- | :--- | :---: | :---: | :---: |
| **Módulo de Triaje** | `can_register_patients` / `can_use_transcriber` | Sí | Sí | Sí |
| **Simulador HCE** | `can_view_emr` | Según asignación | Sí | Sí |
| **Validación Ciega** | `can_edit_symptoms` | Según asignación | Sí | Sí |
| **Telemetría Operativa** | Autenticado (identidad HCE protegida) | Agregado | Completo | Completo |
| **Benchmarks de Investigación** | Autenticado | Sí | Sí | Sí |
| **Monitor Normalización** | `can_use_transcriber` | Sí | Sí | Sí |
| **Monitor FHIR / HL7** | `can_view_fhir` | Según asignación | Sí | Sí |
| **Seguridad y RBAC** | Rol `admin` | No | No | Sí |
| **Configuración** | `can_manage_config` / `admin` | No | No | Sí |

En la esquina inferior de la barra lateral se visualiza de forma permanente el indicador **Estado de Motores** (`EngineStatus`), que informa en tiempo real qué motor ASR (`CUDA` o `CPU`), qué extractor NER (`RoBERTa v1` o `Catálogo`) y qué motor LLM (`LLM local Ollama`, `Google Gemini` o `Motor de Reglas`) están activos.

---

### 3. Estación de Triaje por Voz (`Módulo de Triaje`)

> **Aviso clínico:** AI-Triage es una herramienta de soporte a la decisión clínica (*human-in-the-loop*). Nunca reemplaza el criterio profesional: el clínico responsable debe verificar los hallazgos y ratificar o ajustar el nivel antes de derivar al paciente.

#### Paso 1. Identificación del paciente
1. Completar los campos del formulario de admisión: **Nombre completo**, **Documento de identidad**, **Fecha de nacimiento**, **Sexo biológico/administrativo**, **Teléfono** y **EPS / Aseguradora**.
2. El validador en tiempo real advierte formatos atípicos sin bloquear la atención de emergencias vitales (si un paciente ingresa inconsciente o sin documentos, el sistema asigna un identificador temporal trazable `anon-<uuid>`).

#### Paso 2. Captura por voz o ingreso de relato clínico
1. Pulsar **Iniciar grabación** y dictar o permitir la narración del motivo de consulta, tiempo de evolución, signos vitales tomados en admisión, antecedentes, medicamentos actuales, alergias y negaciones pertinentes (p. ej., *«niega dolor torácico, niega disnea»*).
2. El indicador acústico muestra el nivel de entrada del micrófono y envía fragmentos cada **4 segundos** al worker `faster-whisper`, acumulando el texto transcrito en pantalla con corrección fonética de terminología médica.
3. Pulsar **Detener grabación** al concluir. El profesional puede corregir o complementar manualmente cualquier palabra en el área de transcripción antes de solicitar el análisis.

#### Paso 3. Análisis híbrido e interpretación explicable
1. Pulsar **Analizar Triaje**. El sistema ejecuta la cadena completa (reglas Christus Sinergia + umbrales de signos vitales + NegEx + recuperación RAG de criterios + extracción RoBERTa NER + inferencia LLM con política `min_critico`) y persiste la sesión de forma atómica.
2. En el panel de resultados se presentan:
   - **Nivel sugerido (1 a 5)** con código cromático normativo (**Nivel 1 Rojo — Reanimación**, **Nivel 2 Naranja — Emergencia**, **Nivel 3 Amarillo — Urgencia**, **Nivel 4 Verde — Consulta Prioritaria**, **Nivel 5 Azul — Consulta Externa**) y tiempo máximo de atención institucional.
   - **Siete tarjetas de entidades clínicas estructuradas:** *Síntomas*, *Diagnósticos / Lesiones*, *Antecedentes*, *Medicamentos*, *Alergias*, *Signos Vitales* y *Hallazgos Negados* (estos últimos separados explícitamente para impedir falsas alarmas). El personal con permiso `can_edit_symptoms` puede añadir, editar o depurar etiquetas directamente.
   - **Panel de Explicabilidad (`¿En qué se basa este resultado?`):** detalla la justificación clínica redactada, el motor exacto que resolvió el caso, los signos vitales escalados y los criterios textuales de la Resolución 5596 / Christus Sinergia recuperados por el módulo RAG. Si el servicio LLM estuvo no disponible, se muestra un banner explícito advirtiendo que la clasificación provino del respaldo determinista de reglas.

#### Paso 4. Ratificación o ajuste médico (*Override*) y exportación
1. Si el profesional concuerda con la prioridad propuesta, el nivel queda ratificado como `final_level`.
2. Si el juicio clínico determina un nivel distinto, pulsar **Modificar nivel**, seleccionar la prioridad definitiva (`1` a `5`), registrar obligatoriamente la **justificación clínica del ajuste** y confirmar. El cambio actualiza el índice de concordancia y escribe un registro inmutable `TRIAGE_OVERRIDE` en la auditoría.
3. Desde la barra de acciones del resultado o desde el **Historial de Sesiones**, el clínico puede:
   - Descargar el **informe clínico en PDF**.
   - Descargar el **Bundle HL7 FHIR R4 (`.json`)** o enviarlo directamente al receptor HCE (`Sincronizar FHIR`).
   - Descargar la trama **HL7 v2.5.1 ER7 `ADT^A08` (`.hl7`)** compatible con sistemas HIS hospitalarios clásicos.

---

### 4. Simulador HCE (`Simulador HCE`) y Monitor FHIR (`Monitor FHIR/HL7`)

1. **Cola asistencial (`Simulador HCE`):** Lista las admisiones activas ordenadas por prioridad clínica y hora de ingreso, indicando si el encuentro ya cuenta con sincronización FHIR válida (`Recibido en HCE`).
2. **Gestión de estado y evolución:** Al seleccionar un paciente, el médico visualiza su ficha consolidada (signos vitales, entidades, justificación, payload FHIR asociado), actualiza el **estado asistencial** (p. ej., *Pendiente de Recepción*, *En Atención Médica*, *Observación*, *Alta / Remisión*) y registra **notas de evolución clínica**, persistidas mediante `update_care_status`.
3. **Auditoría de interoperabilidad (`Monitor FHIR/HL7`):** Permite inspeccionar cada transacción `OUTBOUND`/`INBOUND` enviada a `/api/fhir/`, verificando el código HTTP (`201` válido vs. `422` rechazado por esquema R4), el identificador `fhir-enc-<uuid>` y el detalle estructural de los seis recursos (`Patient`, `Encounter`, `Observation`, `Condition`, `AllergyIntolerance`, `MedicationStatement`).

---

### 5. Validación Clínica Ciega (`Validación Ciega`) y Monitores de Calidad

1. **Adjudicación sin sesgo de anclaje (`Validación Ciega`):**
   - Presenta al médico evaluador una cola de casos pendientes mostrando **únicamente** edad, sexo y transcripción clínica cruda (ocultando el nivel sugerido por la IA, el nivel del médico tratante y la justificación, y excluyendo automáticamente cualquier caso atendido por el propio evaluador).
   - El evaluador selecciona el nivel de referencia (`1` a `5`) según el protocolo institucional y confirma. Esta adjudicación es **inmutable** (`TRIAGE_REFERENCE`).
   - Solo **después** de fijar el nivel ciego, la interfaz revela la justificación generada por la IA para que el mismo evaluador la califique por única vez en tres dimensiones Likert (`1` a `5`): **Claridad**, **Pertinencia clínica** y **Fidelidad al protocolo**.
2. **Métricas operativas y científicas (`Telemetría Operativa` y `Benchmarks de Investigación`):**
   - `Telemetría Operativa` calcula en vivo la matriz de confusión 5x5, el Kappa de Cohen con ponderación cuadrática, las tasas de infratriaje/sobretriaje, la sensibilidad en niveles críticos I–II, el ahorro de tokens por caché clínica SHA-256 y la comparación separada entre acuerdo en vivo y validación contra referencia ciega.
   - `Benchmarks de Investigación` expone las corridas experimentales reproducibles del corpus (`dev` y `test`) en ASR, extracción NER y clasificación de triaje.
3. **Monitor de Normalización (`Monitor Normalización`):** Permite introducir cualquier texto clínico libre y contrastar la extracción y codificación estandarizada en **SNOMED CT**, **CIE-10** y **ATC**.

---

## Parte II — Manual del Administrador del Sistema

### 6. Administración de Usuarios, Permisos RBAC y Auditoría (`Seguridad y RBAC`)

1. **Gestión granular de permisos:** En la pestaña **Directorio de Usuarios**, el administrador localiza cualquier profesional registrado y activa o revoca en caliente sus seis permisos individuales (`Usar transcriptor`, `Editar síntomas / Override`, `Registrar pacientes`, `Ver HCE`, `Ver FHIR`, `Gestionar configuración`). Todo cambio se aplica de inmediato en el servidor (`PATCH /api/security/users/<id>/permissions/`) sin requerir reinicio de contenedores.
2. **Inspección de bitácora (`Registro de Auditoría`):** Permite auditar cronológicamente los eventos de seguridad y trazabilidad médico-legal (`LOGIN`, `TRIAGE_CREATED`, `TRIAGE_OVERRIDE`, `TRIAGE_REFERENCE`, `TRIAGE_JUSTIFICATION_RATING`, `EMR_CARE_STATUS_UPDATED`, `FHIR_HCE_SYNC`, `RBAC_PERMISSION_CHANGE`, `MODEL_CONFIG_CHANGE`, `API_KEY_ADDED`, `API_KEY_DELETED`), incluyendo usuario actor, dirección IP de origen, recurso afectado y marca temporal.

---

### 7. Configuración de Motores de IA y Bóveda Criptográfica (`Configuración`)

1. **Motor de Reconocimiento de Voz (ASR — `Faster-Whisper`):**
   - Seleccionar **`Según entorno (auto)`** (recomendado: emplea `large-v3-turbo` `int8_float16` en servidores con GPU NVIDIA y `small` `int8` en equipos solo CPU) o fijar explícitamente una variante (`tiny`, `base`, `small`, `medium`, `large-v3-turbo`, `large-v3`).
   - Tras cambiar manualmente el tamaño del modelo ASR, aplicar en el servidor con `docker compose restart worker-asr` para recargar los pesos en memoria.
2. **Motor de Triaje y Explicabilidad (LLM):**
   - **Modo soberano local (recomendado para privacidad hospitalaria):** elegir **LLM local (Ollama / servidor propio)** y seleccionar el modelo descargado (`gemma4:e4b-it-qat` para máxima precisión clínica o `qwen2.5:7b-instruct-q4_K_M` para menor consumo de memoria). Ningún dato abandona la red interna; si el contenedor local no responde a tiempo, el sistema degrada exclusivamente al motor determinista de reglas.
   - **Modo nube con seudonimización:** elegir **Google Gemini (`gemini-2.5-flash`)** cuando exista clave activa en la bóveda y acuerdo institucional de tratamiento de datos. Los identificadores directos (nombre, documento, teléfono) se reemplazan por marcadores antes del envío.
   - **Modo determinista puro:** elegir **Solo Motor de Reglas** en contingencias o entornos desconectados de baja capacidad.
3. **Extractor de Entidades Clínicas (NER) y Vocabularios:**
   - Alternar entre el modelo neuronal **`HoraYMedia/ai-triage-ner-roberta` (`v1`)** combinado con el catálogo y el modo rápido basado únicamente en el catálogo determinista.
   - El botón **Sincronizar / Validar Vocabularios** verifica la integridad de los catálogos locales SNOMED CT (`302` conceptos / `299` códigos únicos), CIE-10 (`208` conceptos / `188` códigos únicos) y ATC (`76` fármacos) y registra la versión activa.
4. **Bóveda de Credenciales API (`MultiFernet`):**
   - Permite añadir nuevas llaves de proveedores (`Gemini`, `OpenAI`, `Anthropic`, `DeepSeek`, `Servidor local`) cifradas en reposo con AES-128-CBC + HMAC-SHA256 (`FIELD_ENCRYPTION_KEY`).
   - Una vez guardada, la interfaz solo expone una máscara truncada (`AIza...9xQ`) y permite revocarla (`Eliminar`) con registro en `AuditLog`.

---

### 8. Operación Técnica, Monitoreo y Resolución de Incidentes

| Tarea administrativa | Comando en servidor anfitrión | Resultado esperado |
| :--- | :--- | :--- |
| Verificar estado de contenedores | `docker compose ps` | Todos los servicios activos en estado `Up` / `healthy`. |
| Comprobar salud de API y ASR | `curl -k https://localhost/api/health_check/` | JSON con `"status": "ok"`, `"inference_mode": "worker"` y `"model_loaded": true`. |
| Verificar aceleración GPU en LLM local | `docker compose exec llm-local ollama ps` | Columna `PROCESSOR` reporta `100% GPU` tras el primer triaje. |
| Inspeccionar logs de inferencia | `docker compose logs -f backend worker-asr worker-llm` | Trazas sin errores `TaskUnavailable` ni `Out of memory`. |
| Respaldar base de datos PostgreSQL | `docker compose exec -T postgres pg_dump -U triage_user -Fc ai_triage > backup.dump` | Archivo `.dump` íntegro con pacientes, sesiones y bitácoras. |
| Rotar `FIELD_ENCRYPTION_KEY` | Definir `< clave_nueva >,< clave_anterior >` en `FIELD_ENCRYPTION_KEY` (`MultiFernet`) y reiniciar `backend` y `worker-llm` | Lectura continua de llaves existentes y cifrado de nuevas llaves con la clave primaria. |
| Importar / limpiar muestra de validación ciega | `docker compose exec backend python manage.py import_blind_review --run ...` / `--purge` | Carga los 50 casos `CORPUS-` para adjudicación médica o los depura al finalizar el estudio. |

Para detalles de aprovisionamiento inicial de servidores, certificados TLS institucionales y variables `.env`, consultar [`docs/DEPLOYMENT.md`](DEPLOYMENT.md).
