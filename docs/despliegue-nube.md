# Despliegue nube (M8) — checklist

## Listo y verificado
- [x] Flags dual local/nube por variable de entorno: config.py + .env.example
      - EMBEDDINGS_PROVIDER=local|openai, LLM_PROVIDER=ollama|openai, VECTOR_PROVIDER=chroma|qdrant
      - Defaults = pila local intacta (Ollama + Chroma + e5-small)
- [x] embeddings.py con despacho por provider (import perezoso de torch)
- [x] vectorstore.py con despacho chroma|qdrant (misma API pública)
- [x] llm.py con despacho ollama|openai (httpx directo, sin langchain-openai)
- [x] Smoke local: 12/12 OK tras refactorizar (pila local sin regresiones)

## Medido (no estimado)
- Backend sin torch: 204 MB RAM  -> cabe en Render free (512 MB)
- Backend con torch: 570 MB       -> NO cabe en Render free
- deps openai+qdrant: 137 MB disco -> caben
- Qdrant Cloud free: 1 GB RAM / 0.5 vCPU / 4 GB disco, permanente, sin tarjeta
- OpenAI embeddings: ~$0.02 por reindexar todo el corpus con el token del profesor

## Pendiente (necesito servicios)
- [ ] Cuenta Render (backend) -> URL pública + deploy
- [ ] Cuenta Vercel (frontend) -> URL pública
- [ ] Qdrant Cloud (cluster free) -> QDRANT_URL + QDRANT_API_KEY
- [ ] Token OpenAI del profesor -> OPENAI_API_KEY
- [ ] Reconstruir índice en Qdrant (import de Pony API con embeddings OpenAI)
- [ ] smoke_test apuntando a la nube (EMBEDDINGS_PROVIDER=openai, VECTOR_PROVIDER=qdrant, LLM_PROVIDER=openai)
