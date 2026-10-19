# Despliegue en nube (M8) — estado y pasos

## Hecho y verificado (2026-10-18)

- [x] Flags dual local/nube por variable de entorno (config.py + .env.example):
      `EMBEDDINGS_PROVIDER=local|openai`, `LLM_PROVIDER=ollama|openai`,
      `VECTOR_PROVIDER=chroma|qdrant`; los defaults preservan la pila local.
- [x] Qdrant Cloud activo (free tier, región sa-east-1, sin tarjeta).
- [x] Corpus indexado en la nube: **1.001 documentos → 3.086 fragmentos** con
      embeddings `text-embedding-3-small` (1536 dimensiones, ~$0.02).
- [x] Índices de payload `user_id` (entero) y `doc_type` (cadena): Qdrant Cloud
      rechaza con 400 los filtros sobre campos sin índice; ahora se crean al
      asegurar la colección.
- [x] IDs de punto UUIDv5 deterministas (`doc{N}_chunk{i}` no es un ID válido
      para Qdrant; el borrado sigue siendo por filtro `doc_id`).
- [x] Umbral E1 calibrado por proveedor de embeddings (config.py):
      0.62 con e5 local, 0.50 con OpenAI (relevante ≥0.59, sin evidencia ~0.46,
      fuera de dominio ~0.21; calibrado con T01/T05/T11 del smoke).
- [x] Smoke contra backend en modo nube (EMBEDDINGS=openai, LLM=openai,
      VECTOR=qdrant en :8001): **12/12**, incluido T11 "Duvan Gomez".
- [x] Smoke local (Chroma + Ollama + e5): **12/12** sin regresiones.
- [x] `requirements-nube.txt` (sin torch/chromadb/Ollama) y `render.yaml`
      corregido: build ligero, `SECRET_KEY` generado por Render (antes
      `JWT_SECRET`, que el código no lee) y `OPENAI_EMBEDDING_MODEL` con el
      nombre real.
- [x] La semilla corre en un hilo al arrancar (main.py): en un despliegue
      nuevo indexa en segundo plano y `/health` responde ya, para que el
      health check de Render no agote el tiempo.

## Medido (no estimado)

- Backend sin torch: 204 MB RAM → cabe en Render free (512 MB).
- Backend con torch: 570 MB → NO cabe; por eso existe `requirements-nube.txt`.
- deps openai+qdrant: 137 MB disco → caben.
- Qdrant Cloud free: 1 GB RAM / 0.5 vCPU / 4 GB disco, sin tarjeta; el clúster
  se suspende a la semana sin uso y se borra al mes.
- Embeddings OpenAI: ~$0.02 por reindexar todo el corpus.

## Estado del despliegue

- **Backend (Render, plan free): https://ponyarchive-api.onrender.com** — Live.
  Smoke 12/12 contra la URL pública (2026-10-18). `/health`:
  `{"env":"prod","model":"gpt-4o-mini","chunks_indexados":3086}`.
- Primer arranque: un fallo transitorio de red mató el hilo de la semilla y
  dejó una fila en error que bloqueaba el reintento. Arreglado (commit
  `3d743f5`): la siembra contiene fallos por documento, descarta filas en
  error y si la base relacional está vacía pero el índice de la nube tiene la
  biblioteca, **hidrata el catálogo desde los payloads del índice** sin
  re-embeber ni reimportar (segundos, 0 USD). Verificado: DB nueva → 1.001
  documentos reconstruidos.

## Pasos que faltan (requieren cuenta de la usuaria)

### 1. Render (backend) — HECHO

1. ~~Crear cuenta en render.com~~ ✓
2. ~~New → Blueprint → repo → deploy (`ponyarchive-api`, plan free)~~ ✓
3. Variables completadas: `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`,
   `CORS_ORIGINS` (placeholder pendiente de la URL de Vercel).
4. ~~Primer deploy + semilla~~ ✓ Catálogo hidratado (1.001 docs).
5. ~~Verificar `https://ponyarchive-api.onrender.com/health`~~ ✓

### 2. Vercel (frontend) — HECHO

1. ~~Crear cuenta en vercel.com con GitHub~~ ✓
2. ~~Importar repo con Root Directory `frontend`, preset Vite~~ ✓
3. ~~`VITE_API_URL=https://ponyarchive-api.onrender.com` en Production and
   Preview~~ ✓
4. ~~Desplegar → **https://pony-archive.vercel.app**~~ ✓
5. ~~`frontend/vercel.json` con rewrite SPA (`/(.*) → /index.html`): con
   `BrowserRouter`, las rutas directas (`/login`) devolvían 404~~ ✓
6. ~~`CORS_ORIGINS=https://pony-archive.vercel.app` en Render → Environment →
   Save (redespliegue automático)~~ ✓ (verificado: `Access-Control-Allow-Origin`
   correcto y preflight OPTIONS 200 en la E2E del navegador)

### 3. Verificación end-to-end en nube

```bash
SMOKE_BASE_URL=https://ponyarchive-api.onrender.com python scripts/smoke_test.py
```

Debe dar 12/12 (usa la API pública; crea usuarios de prueba efímeros).

### 4. Cierre del documento

- Anotar las dos URLs en este archivo y en el §12 del documento técnico
  (`docs/documento-tecnico.md` → regenerar el PDF).
- Enlazar la imagen principal del README raíz a la URL del frontend.
