---
name: fullstack-testing
description: >-
  Estandar y guia de ejecucion de pruebas automatizadas para el proyecto AI-Triage,
  abarcando la suite de Frontend en Next.js con Vitest y React Testing Library,
  y la suite de Backend en Django con pytest-django.
---

# Estandar de Testing — AI-Triage Fullstack Suite

Esta skill documenta y estandariza los procedimientos de testing automatizado para garantizar
la robustez clinica, la integridad de datos, la seguridad RBAC y la reactividad del sistema.

## 1. Arquitectura de Testing

### Frontend (npm / Next.js)
- **Motor:** `vitest` (ejecutor de pruebas veloz, ESM nativo, compatible con Vite y Next.js).
- **Entorno DOM:** `jsdom`.
- **Librerias:** `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`.
- **Ubicacion de Pruebas:** `frontend/tests/**/*.test.{ts,tsx}`.
- **Configuracion:** `frontend/vitest.config.ts`, inicializado con `frontend/tests/setup.ts`.

### Backend (Python / Django)
- **Motor:** `pytest` con extension `pytest-django`.
- **Aislamiento de Base de Datos:** Base de datos en memoria SQLite para ejecucion instantanea en pruebas unitarias (`--reuse-db`).
- **Ubicacion de Pruebas:** `backend/<app>/tests/test_*.py`.
- **Configuracion:** `backend/pytest.ini`.

---

## 2. Comandos de Ejecucion

### Frontend
```bash
# Ejecutar toda la suite de frontend
pnpm --dir frontend run test

# Ejecutar con reporte de cobertura
pnpm --dir frontend run test:coverage

# Ejecutar un archivo especifico
pnpm --dir frontend run test tests/components/ConfigPanel.test.tsx
```

### Backend
```bash
# Ejecutar toda la suite de backend localmente
backend/.venv/Scripts/python.exe -m pytest backend

# Ejecutar con verbosidad y salida detallada
backend/.venv/Scripts/python.exe -m pytest backend -v

# Ejecutar en contenedor Docker
docker compose exec backend pytest
```

---

## 3. Principios y Convenciones de Mocking

1. **Aislamiento de Hardware Acustico (Whisper ASR):**
   - Nunca cargar el modelo Whisper de 3GB en pruebas unitarias.
   - Mockear la clase `WhisperEngine` y las llamadas a `ctranslate2.models.Whisper`.
   - Probar directamente la logica de gestion de sesiones y poda TTL (`_prune_inactive_sessions`).

2. **Inferencia Externa LLM (Google Gemini):**
   - Simular las respuestas del SDK `@google/genai` devolviendo estructuras JSON deterministicas
     con niveles de triaje del 1 al 5 y entidades clinicas estructuradas.

3. **Autenticacion y Tokens JWT:**
   - En frontend: simular respuestas de `/api/auth/me/` y metodos de almacenamiento local (`localStorage`).
   - En backend: utilizar `APIClient` de Django REST Framework con `client.force_authenticate(user=...)`
     o inyeccion de cabecera `HTTP_AUTHORIZATION="Bearer ..."`.

4. **Entorno de Correo (SMTP):**
   - En backend: usar el backend de email en memoria de Django (`locmem`) durante tests para inspeccionar
     codigos OTP sin requerir conexion viva con Mailpit.
