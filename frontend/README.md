# PonyArchive · Frontend (React + Vite + TypeScript)

Interfaz de PonyArchive: chat con fuentes, gestión de documentos e historial.

## Arranque

```powershell
npm install
npm run dev        # http://localhost:5173
```

La URL de la API se configura en `frontend/.env` con `VITE_API_URL`
(por defecto `http://127.0.0.1:8000`). Build de producción: `npm run build` (tsc + vite).

## Páginas

| Archivo | Función |
|---|---|
| `src/pages/ChatPage.tsx` | Preguntas al agente, respuesta con fuentes (título, tipo, similitud), rechazo destacado, historial lateral |
| `src/pages/DocumentsPage.tsx` | Subida (.txt/.md), listado con filtros, borrado propio |
| `src/pages/LoginPage.tsx` | Registro e inicio de sesión |
| `src/api.ts` | Cliente HTTP con Bearer y renovación automática del token (401 → refresh) |
| `src/auth.tsx` | Contexto de sesión (JWT en `localStorage`) |
| `src/components/Answer.tsx` | Formato de la respuesta y listado de fuentes |

Sin librerías de UI: CSS propio en `src/index.css`.

Más información: `README.md` de la raíz.
