# Individual RAG app: the same tested App Studio code, packaged for the server.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    APP_MODE=production \
    APP_DATABASE=/data/studio.sqlite3

WORKDIR /srv/app
COPY requirements.txt requirements-rag.txt ./
RUN pip install -r requirements.txt -r requirements-rag.txt

# Download the embedding model at build time so the running app never fetches code.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

COPY app ./app
COPY studio_tools ./studio_tools

RUN useradd --uid 10001 --no-create-home app \
    && mkdir /data && chown app /data && chmod 700 /data \
    && chmod -R a+rX /opt/fastembed
USER app
VOLUME /data
EXPOSE 8000

# The app only answers its own hostname, so the check sends that Host header.
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.parse as p, urllib.request as u; host = p.urlsplit(os.environ['APP_ORIGIN']).hostname; u.urlopen(u.Request('http://127.0.0.1:8000/health', headers={'Host': host}), timeout=4)"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
