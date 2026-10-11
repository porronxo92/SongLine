# API: FastAPI + uvicorn con 1 worker (el estado de partida vive en memoria).
# Contexto de build: raíz del repo.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 app

WORKDIR /opt/hitster
COPY apps/server /opt/hitster/apps/server
RUN pip install /opt/hitster/apps/server

COPY catalog/songs.csv catalog/packs.json /opt/hitster/catalog/
COPY catalog/packs/ /opt/hitster/catalog/packs/

WORKDIR /opt/hitster/apps/server
USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3     CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/healthz', timeout=2)"]

# --no-access-log: nothing about requests is logged (no URLs, no tokens).
# --ws-max-size: 16 KiB per WebSocket message.
# --proxy-headers: the real client IP comes from X-Forwarded-For, but only when the peer is Caddy
# (the fixed subnet declared in docker-compose.yml); anyone else cannot spoof it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1",      "--no-access-log", "--ws-max-size", "16384",      "--proxy-headers", "--forwarded-allow-ips=172.28.0.0/24"]
