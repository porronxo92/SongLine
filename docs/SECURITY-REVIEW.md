# Revisión de seguridad #1 (backend + infra) — 2026-10-10

Hecha por el agente `security-auditor` con la skill `security-audit` en modo guía, solo lectura. Las pruebas de concepto se hicieron en proceso, sin red. No hay hallazgos críticos. **No se encontró ninguna fuga antitrampas** en la proyección, los mensajes WS, los errores, los logs ni el proxy de audio.

## Backlog de arreglos (decisión del orquestador)

| Id | Sev. | Problema | Arreglo acordado | Estado |
|---|---|---|---|---|
| H1 | Alta | Login CSRF / fijación de sesión. `GET /api/auth/spotify/login?session_token=X` sin autenticar: si el anfitrión abre un enlace de un atacante con un token X que este controla, el atacante obtiene el access token de Spotify del anfitrión con `GET /api/auth/spotify/token` (`auth.py:36-74`, `oauth.py:75-110`) | Pasar a `POST /api/auth/spotify/start` con `Authorization: Bearer`. Genera un nonce, lo guarda en `PendingAuth` y en una cookie `HttpOnly; Secure; SameSite=Lax; Path=/api/auth/spotify`, y devuelve `{url}`. El callback exige que la cookie coincida con el nonce y luego la borra. Solo el **anfitrión de una sala** puede iniciar el login | corregido |
| H2 | Media | `session_token` en la query del WS y del login: queda en el access log de uvicorn (`ws/router.py:132`) | El token se envía en el primer mensaje `hello` (quitar `?token=`); `uvicorn --no-access-log` en el Dockerfile y en el Makefile | corregido |
| H3 | Media | `_pending` de OAuth crece sin tope; `_gc` es O(n²) | Rate limit por IP en `start` + tope de 200 entradas (descartando las más antiguas) | corregido |
| H4 | Media | WS sin límites: mensajes de 16 MiB, `ping.t` sin tope que se devuelve en el eco, conexiones ilimitadas por sala | `--ws-max-size 16384`; `t` con `max_length=64`; máximo 12 conexiones por sala; token-bucket de 20 mensajes/s por conexión (cierre 4429); límite de conexiones por IP; capturar `RecursionError` | corregido |
| H5 | Media | IP del cliente tomada de `X-Forwarded-For[0]`, que el cliente controla; el limiter crea claves al consultar | Usar `request.client.host` con `uvicorn --proxy-headers --forwarded-allow-ips=<red de caddy>`; purgar claves vacías | corregido |
| H6 | Baja | Fuerza bruta de códigos de 4 dígitos | Riesgo aceptado (juego casero); queda mitigado con H4 y H5 | aceptado |
| H7 | Baja | El equipo activo puede pulsar «Dar por bueno» | **No se arregla: es el comportamiento pedido por el usuario** («Dar por bueno» lo decide el propio equipo). El botón es visible para todos, lo que lo hace transparente | por diseño |
| H8 | Baja | Postgres de dev publicado en 0.0.0.0 con credenciales triviales; los snapshots contienen el mazo | `127.0.0.1:5432:5432` y contraseña desde `.env` (también en el compose de producción) | corregido |
| H9 | Baja | `color` sin validar; `SongPatch` sin rangos; `compare_digest` con no-ASCII → 500; admin expuesto por Caddy; `session_token` arbitrario aceptado | `color` con regex `^#[0-9a-fA-F]{6}$`; rangos en `SongPatch`; comparar bytes; `ADMIN_TOKEN` de 32 caracteres o más, si no se desactiva admin; no exponer `/api/admin` en Caddy; tokens de sesión firmados con HMAC (`SESSION_SECRET`) | corregido |
| H10 | Baja | CSP con `wss:` comodín; falta `no-store` en `/api/*`; falta límite de cuerpo; el modo fake se puede activar en producción | CSP `connect-src 'self' wss://{$DOMAIN}` + hosts de Spotify; `Cache-Control: no-store` en `/api/*`; `request_body max_size 64KB`; guard al arrancar: `AUTH_MODE=fake` prohibido si `PUBLIC_ORIGIN` no es localhost/127.0.0.1; quitar `SPOTIFY_CLIENT_SECRET` del ejemplo; `HEALTHCHECK` en el Dockerfile | corregido |
| DEP | — | Sin lockfile ni `pip-audit` | Generar lock con hashes y ejecutar `pip-audit` (requiere red) | pendiente |

## Notas de implementación (2026-10-10)

- **H1, regla elegida.** Cualquier sesión válida y firmada puede iniciar el login. No se exige ser anfitrión de una sala porque en `HostFlow.tsx` el login ocurre *antes* de `POST /api/rooms`, así que ese requisito rompería el flujo. La defensa contra el CSRF es el nonce: va en `PendingAuth` y en una cookie `HttpOnly; SameSite=Lax; Path=/api/auth/spotify` que solo recibe el navegador que hizo el `POST` (un sitio ajeno no puede hacerlo: CORS solo admite `PUBLIC_ORIGIN` y hace falta el Bearer). El callback exige que coincida, quema el `state` y borra la cookie. `Secure` se activa cuando `PUBLIC_ORIGIN` es https (en `http://localhost` de desarrollo no puede llevarlo). En `AUTH_MODE=fake`, `start` devuelve una URL interna al mismo callback, que sigue exigiendo la cookie.
- **H2.** El WS se acepta siempre y los rechazos son códigos de cierre: 4404 sala inexistente, 4401 sin `hello` en 5 s o token no firmado. Los intentos fallidos de ambos tipos cuentan para el límite de códigos (4429).
- **H4.** Además del `--ws-max-size` de uvicorn, el servidor comprueba el tamaño (16384 caracteres, cierre 1009) para no depender solo de la configuración. Conexiones: 12 por sala y 40 por IP (configurable); 20 mensajes/s con ráfaga de 30.
- **H5.** Los ficheros de Compose fijan la subred `172.28.0.0/24` para poder confiar solo en Caddy.
- **H8.** El Compose de producción lee `POSTGRES_PASSWORD` del `.env` (con `make up`, que pasa `--env-file .env`); sin ella Postgres no arranca. El de desarrollo la lee con valor por defecto `hitster` y publica solo en 127.0.0.1.
- **H9.** Los tokens firmados invalidan las sesiones guardadas antes del cambio y, con clave efímera, las de antes de cada reinicio; el cliente descarta el token y pide otro. `SESSION_SECRET` es obligatoria si `PUBLIC_ORIGIN` no es localhost.
- **DEP.** Sigue pendiente: no se comprobó acceso a red desde este entorno.

Riesgo aceptado por diseño (D1): el anfitrión tiene el token de Spotify y el SDK le entrega metadatos. Es un juego casero entre amigos.
