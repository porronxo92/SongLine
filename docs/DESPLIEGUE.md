# Despliegue: servidor en Render y web en Vercel

El servidor guarda las partidas en memoria y necesita **un solo proceso continuo** con WebSockets, por eso va en Render. La web es estática y va en Vercel. La web reenvía `/api/*` al servidor (así el login de Spotify y su cookie funcionan como en local) y abre el WebSocket directamente contra Render.

Nombres que usa la configuración (cámbialos en los dos sitios si eliges otros):

| Pieza | Nombre / URL |
|---|---|
| Servicio de Render | `songline-api` → `https://songline-api.onrender.com` |
| Proyecto de Vercel | `songline` → `https://songline.vercel.app` (o tu dominio) |

## 1. Render (servidor)

1. En https://dashboard.render.com → **New → Blueprint** → conecta el repositorio `porronxo92/SongLine`. Render lee `render.yaml` de la raíz.
2. Si Render no puede darte el nombre `songline-api` (ya existe), te asignará otro: anota la URL `https://<nombre>.onrender.com` y cámbiala en `apps/web/vercel.json` (dos sitios: la reescritura de `/api` y `connect-src` de la CSP) y en `VITE_WS_URL` de Vercel.
3. Rellena las variables marcadas como secretas (`sync: false`) en el panel de Render. **No las subas al repositorio ni las pegues en un chat.**

| Variable | Valor |
|---|---|
| `DATABASE_URL` | La cadena de Neon tal cual (`postgresql://…?sslmode=require&channel_binding=require`) |
| `SPOTIFY_CLIENT_ID` | El Client ID de tu app de Spotify |
| `TOKEN_ENC_KEY` | Una clave Fernet. Genérala con `apps/server/.venv/Scripts/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `PUBLIC_ORIGIN` | `https://songline.vercel.app` (la URL final de la web, sin barra final) |
| `SPOTIFY_REDIRECT_URI` | `https://songline.vercel.app/api/auth/spotify/callback` |

`SESSION_SECRET` lo genera Render solo. `AUTH_MODE`, `CATALOG_SOURCE`, `PERSISTENCE` y `FORWARDED_ALLOW_IPS` ya vienen fijados en `render.yaml`.

4. Despliega y comprueba `https://songline-api.onrender.com/api/healthz` (debe responder 200) y `https://songline-api.onrender.com/api/catalog/packs` (los packs con su número de canciones).

**Plan gratuito:** el servicio se duerme tras un rato sin uso y la primera visita tarda en despertarlo (puede rondar un minuto). Durante una partida hay tráfico constante y no se duerme. Las salas se guardan en Neon (`PERSISTENCE=postgres`) y sobreviven a un reinicio.

## 2. Vercel (web)

1. En https://vercel.com → **Add New → Project** → importa `porronxo92/SongLine`.
2. **Root Directory:** `apps/web`. Vercel detecta Vite y usa `apps/web/vercel.json` (build `npm run build`, salida `dist`).
3. **Environment Variables** (Production): `VITE_WS_URL` = `wss://songline-api.onrender.com`.
4. Despliega. Si el nombre `songline` está ocupado, Vercel te dará otra URL: usa esa en `PUBLIC_ORIGIN` y `SPOTIFY_REDIRECT_URI` de Render y vuelve a desplegar Render.

## 3. Spotify

En https://developer.spotify.com/dashboard → tu app → **Settings**:
- **Redirect URIs:** añade `https://songline.vercel.app/api/auth/spotify/callback` (deja también las de `127.0.0.1` para desarrollo).
- **User Management:** las cuentas que vayan a ser **anfitrionas** (hasta 5 en modo desarrollo). El resto de jugadores no necesita cuenta.

## 4. Prueba

1. Abre la web en el móvil del anfitrión, crea una sala y haz el login de Spotify.
2. Únete desde otro móvil con el código y juega una partida corta.
3. Comprueba que suena en el móvil del anfitrión y que el mini reproductor salta ±10 s.

## Notas de seguridad

- **Límites por IP.** Con `FORWARDED_ALLOW_IPS="*"` el servidor confía en la cabecera `X-Forwarded-For` que pone el proxy de Render (Render no publica un rango fijo de IPs). Las peticiones REST llegan reescritas por Vercel, así que el límite de intentos de código de sala puede quedar compartido o ser menos preciso. Para un juego entre amigos es aceptable; para uso público habría que revisarlo.
- **CSP.** `apps/web/vercel.json` replica las cabeceras que pone Caddy en Docker Compose, con `connect-src` limitado a la propia web, al WebSocket de Render y a los hosts de Spotify.
- **Docker Compose sigue funcionando igual:** el Dockerfile usa por defecto el puerto 8000 y la subred de Caddy.
