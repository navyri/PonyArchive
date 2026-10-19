<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=140&color=21182E&text=PONYARCHIVE%20%C2%B7%20FRONTEND&fontColor=B78ADC&fontSize=38&fontAlignY=34&desc=React%20%C2%B7%20Vite%20%C2%B7%20TypeScript&descColor=79D9CD&descAlignY=60"/>
</p>

<p align="center">
  <img src="https://64.media.tumblr.com/ca492f2e341e5f0d825c899842bd2ca3/f8c0a52918cf3b90-85/s500x750/044bc7e22b528a519ee7391eeb1533b5542503dc.gifv" alt="Twilight Sparkle" height="200"/>
</p>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&height=6&color=21182E"/>
</p>

Interfaz de PonyArchive: chat con fuentes, gestión de documentos e historial.

## Arranque

```powershell
npm install
npm run dev        # http://localhost:5173
```

La URL de la API se configura en `frontend/.env` con `VITE_API_URL`
(por defecto `http://127.0.0.1:8000`). Build de producción: `npm run build` (tsc + vite).
<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&height=6&color=21182E"/>
</p>

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

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=120&section=footer&color=21182E" alt=""/>
</p>
