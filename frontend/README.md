# AI-Triage: Frontend Web App (Next.js 15)

Aplicación cliente en **Next.js 15** (App Router), **React 19**, **Tailwind CSS 4** y **TypeScript** para la asistencia de triaje clínico en tiempo real.

## Características Principales

* **Triaje clínico interactivo:** Transcripción ASR en vivo, entidades clínicas, nivel sugerido (I a V) con ratificación o ajuste médico y justificación editable.
* **Priorización Christus Sinergia Salud:** Escala con tiempos máximos de espera según la Resolución 5596 de Minsalud.
* **Validación ciega (`BlindReview`):** Cola de casos para que un clínico distinto al tratante asigne el nivel de referencia viendo solo la transcripción, sin el nivel de la IA ni el del médico.
* **Métricas:** Concordancia, Kappa ponderado, infratriaje / sobretriaje, sensibilidad en niveles I–II, comparación contra la referencia ciega y gobernanza de tokens.
* **Simulador HCE:** Cola de pacientes clasificados y asignación persistente de box.
* **Normalización ontológica:** Mapeo de términos coloquiales a SNOMED-CT y CIE-10.
* **Monitor FHIR:** Inspección y descarga de Bundles HL7 FHIR R4 y mensajes HL7 v2.5.1.
* **Configuración:** Modelos de IA, dispositivo real del motor ASR (CPU o GPU) y bóveda de claves API.
* **Diseño responsivo:** Escritorio y móvil con drawer de navegación.

## Comunicación con el Backend

* El cliente llama siempre a rutas relativas `/api/...`; en Docker, nginx las dirige a Django. `pnpm dev` por sí solo no alcanza el backend: hace falta el stack de Docker (o un proxy equivalente).
* Todas las llamadas autenticadas pasan por `fetchWithAuth` (`lib/api.ts`): el access token vive solo en memoria y el refresh token en una cookie httpOnly que gestiona el backend; ante un 401 se renueva una vez y, si falla, se redirige a `/login`.
* En producción la app se sirve por HTTPS con una CSP estricta (`connect-src 'self'`): no se deben añadir llamadas a dominios externos desde el navegador.

## Ejecución y Pruebas

```bash
pnpm install          # dependencias
pnpm dev              # servidor de desarrollo (requiere el backend detrás de nginx)
pnpm test             # Vitest + Testing Library (67 pruebas)
pnpm lint             # ESLint
pnpm build            # compilación de producción y validación de tipos
```

## Estructura de Componentes

* `components/AppNavigation.tsx`: Shell de la app; verifica la sesión con `/api/auth/me/` y conmuta entre paneles.
* `components/TriageDashboard.tsx`: Triaje interactivo, ASR en tiempo real, modales y exportaciones.
* `components/BlindReview.tsx`: Adjudicación ciega del nivel de referencia.
* `components/MetricsDashboard.tsx`: Concordancia clínica, seguridad, referencia ciega y gobernanza de tokens.
* `components/EMRSimulator.tsx`: Simulador de Historia Clínica Electrónica y asignación de box.
* `components/NormalizationMonitor.tsx`: Ontologías SNOMED-CT / CIE-10.
* `components/FHIRMonitor.tsx`: Historial e inspección de interoperabilidad FHIR R4.
* `components/ConfigPanel.tsx`: Motores de IA, estado del ASR y bóveda de credenciales.
* `components/SecurityPanel.tsx`: Usuarios, roles, permisos y auditoría.
* `hooks/useWhisperASR.ts`: Captura de micrófono por fragmentos y envío a `/api/transcribe/`.
