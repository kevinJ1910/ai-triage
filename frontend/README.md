# AI-Triage: Frontend Web App (Next.js 15)

Aplicación web cliente desarrollada con **Next.js 15**, **React 19**, **TailwindCSS** y **TypeScript** para la asistencia interactiva de triaje clínico hospitalario en tiempo real.

## Características Principales del Frontend

* **Triaje Clínico Interactivo:** Panel visual con transcripción ASR en vivo, extracción NER, asignación de nivel (I a V), justificación médica editable y telemetría de confianza.
* **Priorización Institucional Christus Sinergia Salud:** Escala oficial con tiempos máximos de espera según la Resolución 5596 del Ministerio de Salud de Colombia.
* **Gobernanza y UX Hospitalaria:**
  - Modales de confirmación para inicio de nueva consulta y discrepancias clínicas en ajuste manual de nivel.
  - Tooltips interactivos con ventanas terapéuticas de espera y estados operativos.
  - Banner minimizable/colapsable para avisos de respaldo asistencial determinista.
* **Simulador EMR Hospitalario:** Cola de espera de pacientes clasificados y asignación persistente de boxes de atención médica.
* **Monitor Ontológico y Normalización:** Mapeo de quejas coloquiales a conceptos formales de SNOMED-CT y CIE-10.
* **Monitor de Interoperabilidad FHIR:** Inspección y descarga de Bundles HL7 FHIR Release 4 y mensajes HL7 v2.5.1 ER7.
* **Dashboard de Métricas y Gobernanza de Tokens:** Monitoreo de tasa de concordancia clínica, índice Kappa de Cohen, y telemetría de tokens LLM consumidos y ahorrados por caché semántico.
* **Diseño Responsivo:** Soporte adaptativo para terminales desktop de urgencias y dispositivos móviles mediante Drawer deslizante.

## Ejecución y Pruebas

```bash
# Instalación de dependencias
pnpm install

# Servidor de desarrollo
pnpm dev

# Suite de pruebas automatizadas (Vitest)
pnpm test

# Verificación de tipos TypeScript
pnpm tsc --noEmit

# Linting de código
pnpm lint

# Compilación de producción
pnpm build
```

## Estructura de Componentes

* `components/TriageDashboard.tsx`: Motor de triaje clínico interactivo, ASR en tiempo real, modales y exportaciones.
* `components/EMRSimulator.tsx`: Simulador de Historia Clínica Electrónica y asignación de box persistente.
* `components/MetricsDashboard.tsx`: Monitor de concordancia clínica y gobernanza de tokens LLM.
* `components/NormalizationMonitor.tsx`: Tabla y filtros de ontologías SNOMED-CT / CIE-10.
* `components/FHIRMonitor.tsx`: Visor e historial transaccional de interoperabilidad FHIR R4.
* `components/ConfigPanel.tsx`: Gestión de motores de IA y bóveda cifrada de credenciales API.
* `components/SecurityPanel.tsx`: Administración de usuarios, roles hospitalarios y auditoría forense.
* `components/AppNavigation.tsx`: Barra superior, navegación adaptativa y drawer móvil.
