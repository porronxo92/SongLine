# SongLine

Escucha, adivina y ordena la historia de la música. ¿Qué año suena?

**SongLine** es una PWA multijugador para casa, tipo Hitster. El anfitrión reproduce la música desde su móvil con Spotify y el resto de jugadores adivinan título, artista y año desde el suyo.

El diseño completo y las decisiones cerradas están en [`docs/DISENO.md`](docs/DISENO.md). Las reglas de `CLAUDE.md` mandan sobre cualquier otro documento.

## Arrancar en desarrollo

Requisitos: Node 24, Python 3.12 y Docker.

```bash
cp .env.example .env     # AUTH_MODE=fake permite jugar sin Spotify
make db                  # Postgres en localhost:5432
make dev-api             # API en http://127.0.0.1:8000
make dev-web             # Web en http://localhost:5173
```

## Producción

```bash
docker compose -f infra/docker-compose.yml up -d
```

Caddy sirve la web y hace de proxy de `/api` y `/ws` a la API. Para el TLS automático, define `DOMAIN` en el entorno de la shell (`DOMAIN=tu-dominio docker compose ...`) o en `infra/.env`, porque Compose interpola las variables desde esa carpeta. La API lee el resto de variables de `.env` de la raíz.
