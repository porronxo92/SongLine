# HitsterCasero: servidor

FastAPI + WebSocket, motor de juego puro en `app/game/`. Contrato para el frontend: `docs/PROTOCOL.md`.

## Entorno

```powershell
cd apps/server
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Desarrollo (sin Spotify ni Postgres)

```powershell
$env:AUTH_MODE="fake"; $env:CATALOG_SOURCE="csv"; $env:PERSISTENCE="none"
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Una sola réplica de uvicorn (el estado de las salas vive en memoria). Variables: `AUTH_MODE` (`spotify`|`fake`), `CATALOG_SOURCE` (`postgres`|`csv`), `CATALOG_CSV_PATH` (por defecto `catalog/songs.csv`), `PERSISTENCE` (`postgres`|`none`), `DATABASE_URL`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_REDIRECT_URI`, `TOKEN_ENC_KEY` (clave Fernet), `PUBLIC_ORIGIN`, `ADMIN_TOKEN`.

Migraciones (solo con Postgres): `.venv\Scripts\alembic upgrade head`.

## Tests

```powershell
.venv\Scripts\python -m pytest                       # todo
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy --strict app/game
.venv\Scripts\python tests/sim/run_bots.py 300      # simulador de bots (N partidas); --leaks activa el antitrampas en cada paso
```
