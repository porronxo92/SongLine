# HitsterCasero: atajos de desarrollo y pruebas.
# Funciona con GNU make desde Git Bash o PowerShell (mingw32-make). Python del venv:
# apps/server/.venv/Scripts/python.exe (Windows) con fallback a apps/server/.venv/bin/python.

PY := $(if $(wildcard apps/server/.venv/Scripts/python.exe),apps/server/.venv/Scripts/python.exe,apps/server/.venv/bin/python)
NPM_WEB := npm --prefix apps/web
ENV_FILE := $(if $(wildcard .env),--env-file .env,)
COMPOSE_DEV := docker compose $(ENV_FILE) -f infra/docker-compose.dev.yml
COMPOSE := docker compose $(ENV_FILE) -f infra/docker-compose.yml

.PHONY: help dev-api dev-web db test sim e2e import-catalog up down

help:
	@echo "Targets: dev-api dev-web db test sim e2e import-catalog up down"

# API en local con recarga automática (lee .env de la raíz). Requiere `make db`.
dev-api:
	$(PY) -m uvicorn app.main:app --app-dir apps/server --reload --host 127.0.0.1 --port 8000 --no-access-log --ws-max-size 16384

# Vite en :5173 con proxy de /api y /ws hacia :8000.
dev-web:
	$(NPM_WEB) run dev

# Postgres de desarrollo en localhost:5432.
db:
	$(COMPOSE_DEV) up -d --wait

# Pytest de servidor y catálogo, y comprobaciones de la web.
test:
	$(PY) -m pytest apps/server catalog -q
	$(NPM_WEB) run typecheck
	$(NPM_WEB) run lint

# Simulaciones de partidas (apps/server/tests/sim).
sim:
	$(PY) -m pytest apps/server/tests/sim -q

# Playwright. Requiere la API en marcha con AUTH_MODE=fake (make dev-api).
e2e:
	$(NPM_WEB) run test:e2e

# Importa el banco de canciones (DISENO §6 bis). Pasa argumentos con ARGS="...".
import-catalog:
	$(PY) catalog/import_spotify.py $(ARGS)

# Stack de producción en segundo plano (construye imágenes).
up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down
