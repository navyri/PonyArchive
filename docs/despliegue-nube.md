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

## Pasos que faltan (requieren cuenta de la usuaria)

### 1. Render (backend)

1. Crear cuenta en render.com con el mismo GitHub del repo.
2. New → Web Service → elegir el repo → Render detecta `render.yaml`
   (Blueprint); revisar y desplegar.
3. En Environment del servicio, completar las variables con `sync: false`:
   `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY` (los mismos del `.env`
   local) y `CORS_ORIGINS=https://<app-front>.vercel.app` (se rellena tras el
   paso 2, o se guarda tras conocer la URL de Vercel).
4. Esperar el primer deploy: la semilla indexa el corpus en segundo plano
   (~3-6 min); el health check pasa de inmediato.
5. Verificar: `https://ponyarchive-api.onrender.com/health` →
   `{"status":"ok", "chunks_indexados": 3086}`.

### 2. Vercel (frontend)

1. Crear cuenta en vercel.com con GitHub.
2. New Project → repo → ajustes del proyecto:
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`
3. Environment variable: `VITE_API_URL=https://ponyarchive-api.onrender.com`.
4. Desplegar y copiar la URL pública (`https://<app>.vercel.app`).
5. Volver al paso 3 de Render y poner esa URL en `CORS_ORIGINS`.

### 3. Verificación end-to-end en nube

```bash
SMOKE_BASE_URL=https://ponyarchive-api.onrender.com python scripts/smoke_test.py
```

Debe dar 12/12 (usa la API pública; crea usuarios de prueba efímeros).

### 4. Cierre del documento

- Anotar las dos URLs en este archivo y en el §12 del documento técnico
  (`docs/documento-tecnico.md` → regenerar el PDF).
- Enlazar la imagen principal del README raíz a la URL del frontend.
