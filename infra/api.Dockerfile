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

# PORT lo fija el proveedor (Render pone uno propio); 8000 por defecto (Docker Compose).
ENV PORT=8000     FORWARDED_ALLOW_IPS=172.28.0.0/24

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3     CMD ["sh", "-c", "python -c \"import urllib.request as u; u.urlopen('http://127.0.0.1:${PORT}/api/healthz', timeout=2)\""]

# --no-access-log: nothing about requests is logged (no URLs, no tokens).
# --ws-max-size: 16 KiB per WebSocket message.
# --proxy-headers: the real client IP comes from X-Forwarded-For, but only from the peers listed in
# FORWARDED_ALLOW_IPS. Docker Compose: the fixed subnet of Caddy. Render: its own proxy ("*"),
# since Render does not publish a fixed range (see docs/DESPLIEGUE.md for the trade-off).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT}\" --workers 1 --no-access-log --ws-max-size 16384 --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS}\""]
