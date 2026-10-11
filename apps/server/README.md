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

Una sola réplica de uvicorn (el estado de las salas vive en memoria). Variables: `AUTH_MODE` (`spotify`|`fake`), `CATALOG_SOURCE` (`postgres`|`csv`), `CATALOG_CSV_PATH` (por defecto `catalog/songs.csv`), `CATALOG_PACKS_DIR` (por defecto `catalog/packs`), `CATALOG_PACKS_JSON` (por defecto `catalog/packs.json`), `PERSISTENCE` (`postgres`|`none`), `DATABASE_URL`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_REDIRECT_URI`, `TOKEN_ENC_KEY` (clave Fernet), `PUBLIC_ORIGIN`, `ADMIN_TOKEN`.

## Base de datos (Postgres / Neon)

`DATABASE_URL` en el `.env` de la raíz admite la cadena tal como la da Neon
(`postgresql://...?sslmode=require&channel_binding=require`); el servidor la convierte a asyncpg.

```powershell
cd apps/server
.venv\Scripts\python -m alembic upgrade head                      # crea songs, room_snapshots, spotify_sessions, packs (0002)
$env:PYTHONPATH="."; .venv\Scripts\python scripts/seed_songs.py   # siembra packs.json, songs.csv (pack mix) y catalog/packs/*.csv (repetible; --dry-run para probar)
```

Para que la API use la base en vez del CSV: `CATALOG_SOURCE=postgres` y `PERSISTENCE=postgres` en el `.env`.
`enabled` es true solo para las canciones `verified`; el resto queda fuera del mazo.

### Packs de géneros

Cada sala elige uno o varios packs al crearse (`settings.packs`, por defecto `["mix"]`). `catalog/songs.csv` es el pack `mix`; cada `catalog/packs/<slug>.csv` es el pack `<slug>`, y `catalog/packs.json` lista nombre, descripción, icono y orden. Para añadir un pack nuevo: un CSV con la misma cabecera, una entrada en `packs.json` y volver a ejecutar `seed_songs.py`. Los IDs de los CSV deben ser únicos entre ficheros (prefijo propio por pack). Una canción repetida en dos packs solo sale una vez por partida. `GET /api/catalog/packs` devuelve los packs con su número de canciones habilitadas.

La migración `0002` ya admite años desde 1900. Si la base está en `0001`, ejecuta `alembic upgrade head` antes de sembrar. En el servidor, `catalog/packs.json` y `catalog/packs/` tienen que estar disponibles junto a `songs.csv` (la API lee `packs.json` para validar los slugs).

## Tests

```powershell
.venv\Scripts\python -m pytest                       # todo
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy --strict app/game
.venv\Scripts\python tests/sim/run_bots.py 300      # simulador de bots (N partidas); --leaks activa el antitrampas en cada paso
```
