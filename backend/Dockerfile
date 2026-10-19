# PonyArchive — backend (FastAPI + agente RAG LangGraph)
#
#   docker build -t ponyarchive-backend ./backend
#
# Ollama queda FUERA del contenedor (el modelo corre en local, en el portátil),
# así que en el arranque hay que apuntar a él:
#   OLLAMA_BASE_URL=http://host.docker.internal:11434   (Windows / Docker Desktop)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache

WORKDIR /app

# Torch solo en CPU: evita ~4 GB de dependencias CUDA que no usamos en el contenedor.
# (El índice de PyTorch va primero; PyPI queda como red de seguridad para el resto.)
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
                --extra-index-url https://pypi.org/simple \
                torch

COPY requirements.txt .
RUN pip install -r requirements.txt

# Modelo de embeddings precargado en la imagen: el primer arranque no necesita red
# para los embeddings (solo para la semilla inicial de Pony API).
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('intfloat/multilingual-e5-small')"

COPY app ./app
COPY scripts ./scripts
# fichas narrativas propias y notas de contexto del curso:
# se copian a /app/seed, FUERA de /app/data, porque docker-compose monta un volumen
# en /app/data y ocultaría lo que hubiera dentro de la imagen.
COPY data/seed ./seed
ENV PONYARCHIVE_SEED_DIR=/app/seed

# Usuario sin privilegios + directorios de persistencia (volumen de compose)
RUN useradd -m pony \
    && mkdir -p /app/data /app/vectorstore \
    && chown -R pony:pony /app /opt/hf-cache
USER pony

EXPOSE 8000

# /health responde en cuanto el servidor y la base están listos
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
