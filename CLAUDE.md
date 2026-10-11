# SongLine

PWA multijugador casera tipo Hitster (nombre interno anterior: HitsterCasero). El diseño completo y las decisiones cerradas (D1–D9) están en `docs/DISENO.md`. **§0.0 de ese documento prevalece sobre el resto.**

## Reglas que no se negocian
- El servidor es autoritativo. El cliente **nunca** recibe título, artista, año, `track_id`, URI ni `song_id` de la carta en curso antes de `REVEAL` (`apps/server/app/game/projection.py` es el único sitio que decide qué se envía).
- D1: el móvil del anfitrión es el único que reproduce audio (Spotify Web Playback SDK). Los demás móviles no hacen login en Spotify.
- El motor de juego (`apps/server/app/game/`) es puro: `reduce(state, command, now) -> (state, effects)`. Sin E/S, sin `datetime.now()` dentro.
- `AUTH_MODE=fake` debe permitir jugar de extremo a extremo sin Spotify (desarrollo y E2E).

## Stack
- Servidor: Python 3.12 (`py -3.12`), FastAPI, Pydantic v2, SQLAlchemy 2 async + asyncpg, Alembic, pytest + hypothesis. Entorno virtual en `apps/server/.venv` (no hay `uv` instalado: `py -3.12 -m venv .venv`).
- Cliente: Vite + React 18 + TypeScript estricto, Zustand, React Router, Embla Carousel, Tailwind, vite-plugin-pwa, Playwright.
- Infra: Docker Compose (caddy, api, postgres).

## Diseño visual
- Fuente de verdad: `design-system/songline/MASTER.md` (tokens y componentes) y `docs/DISENO-VISUAL.md` (dirección de arte A-E). Estilo Neon Pop nocturno, solo modo oscuro. Sustituye al sistema anterior (`design-system/hitstercasero/`, obsoleto).
- Tipografía: Unbounded (logo, años, titulares, contadores) y Outfit (interfaz). Iconos SVG de lucide-react, nunca emojis. Cada equipo lleva forma además de color.
- Textos de la UI en español, pasados por la skill `stop-slop`: frases directas, sin relleno ni rayas largas.

## Convenciones
- Código y nombres de dominio en inglés; textos de la UI en `apps/web/src/i18n/es.ts`.
- Conventional Commits. No hacer commit ni push salvo que el orquestador lo pida.
- Cada agente toca solo su carpeta asignada; los cambios fuera de ella se piden al orquestador.

## Agentes
La sesión principal actúa como **orquestador** (`.claude/agents/orquestador.md` describe su papel). Los implementadores están definidos en `.claude/agents/`.
