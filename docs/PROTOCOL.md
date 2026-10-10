# HitsterCasero: contrato cliente-servidor

Fuente: `apps/server/app/ws/protocol.py` (mensajes), `apps/server/app/game/projection.py` (`RoomView`), `apps/server/app/api/*` (REST). Este documento describe lo que el servidor hace hoy. Si algo no coincide con el código, manda el código y hay que corregir este fichero.

Convenciones:

- **Dos estilos de claves, a propósito.** El `payload` de los mensajes WS usa `snake_case` (`session_token`, `deadline_ts`, `ref_id`). Todo lo que sale de `RoomView` (campo `view` de `state`) y las cartas dentro de `reveal` usan `camelCase` (`instanceId`, `deckRemaining`). REST usa `snake_case`.
- Los campos opcionales de `RoomView` llegan siempre, con valor `null` cuando no aplican (nunca ausentes).
- Los tiempos `*_ts` son epoch del servidor en **segundos** (float). Para pintar cuentas atrás, corrige el desfase con `pong.server_ts` (`offset = server_ts - Date.now()/1000`).
- Las claves de `token_delta` son slots como **cadena** (`"1"`), porque van en JSON.
- Los slots son enteros `0..3`. El slot `0` es el anfitrión al crear la sala (`host_slot` puede migrar en el lobby, ver más abajo).

---

## 1. Flujo de unión (D1: solo el anfitrión usa Spotify)

### Anfitrión

1. `POST /api/session` → guarda `session_token` en `localStorage`. Es la identidad del móvil. Todas las llamadas REST la mandan como `Authorization: Bearer <session_token>`; el WS la manda en el primer mensaje `hello` (nunca en la URL). El token lo emite y firma el servidor (`base64url(random32).HMAC-SHA256`, unos 87 caracteres): un token que el servidor no firmó se rechaza (REST `401 invalid_session`, WS cierre `4401`). Si recibes eso, descarta el token y pide uno nuevo con `POST /api/session`.
2. `GET /api/auth/status` (Bearer) → `{auth_mode, logged_in, premium_verified}`.
   - `auth_mode: "fake"`: salta todo el login de Spotify (ver sección 7).
   - `auth_mode: "spotify"` y `logged_in: false`: llama a `POST /api/auth/spotify/start {return_to: "/ruta/de/vuelta"}` (Bearer, `credentials: 'include'`). El servidor guarda un nonce en la cookie `hc_oauth_nonce` (`HttpOnly; SameSite=Lax; Path=/api/auth/spotify`, `Secure` si `PUBLIC_ORIGIN` es https) y devuelve `{url}`; navega con `window.location.assign(url)`. Spotify redirige al callback del servidor, que exige esa cookie y te devuelve a `PUBLIC_ORIGIN + return_to`. Cualquier sesión válida puede iniciar el login (ocurre antes de crear la sala).
3. Inicializa el Web Playback SDK con `getOAuthToken` = `GET /api/auth/spotify/token`. Al recibir `ready(device_id)`, llama a `POST /api/auth/spotify/verify-premium {device_id}`. Si `premium` es `false`, bloquea (`reason`: `premium_required`, `user_not_registered`, `no_session`, `device_gone`, `rate_limited`, `unknown`). **Debe hacerse antes de enviar `device_ready` por WS**, porque el servidor lee ese resultado al recibir `device_ready`.
4. `POST /api/rooms {settings, name, color}` → `{code, ws_url, ws_path, slot: 0}`. El anfitrión ya ocupa el hueco 0.
5. Abre el WS en `ws_url` (sin token) y envía `hello {session_token, last_version}` como primer mensaje. Con el primer gesto del usuario (`AudioGate`): llama a `player.activateElement()` y envía `device_ready` y después `audio_unlocked`.
6. **En cada reconexión del WS** el anfitrión debe volver a enviar `device_ready` y `audio_unlocked`: el servidor marca el audio como no listo en cuanto el anfitrión se desconecta.

### Resto de equipos (sin Spotify ni login)

1. `POST /api/session` (o reutiliza el token guardado).
2. `GET /api/rooms/{code}` → comprueba `status` (`open|started|full`) y los huecos libres con `suggested_color`.
3. Abre el WS `/ws/rooms/{code}` y envía `hello {session_token}`. Llega un `state` con `you.slot = null` (espectador).
4. Envía `claim_slot {slot, name, color}`. Si responde `ack`, llega un `state` con `you.slot = <slot>`.

### Reconexión

Mismo `session_token`, mismo WS. El servidor identifica el hueco por el hash del token y envía el `state` completo al conectar. Reconectar no necesita `claim_slot`. Usa backoff exponencial (0,5 s a 8 s). Si el WS se cierra con `4404` la sala ya no existe: borra `room_code` del `localStorage`. Con `4401` la sesión no vale: borra el token y pide otro.

---

## 2. Códigos de cierre del WebSocket

El WS se acepta siempre (`accept`) y los rechazos llegan como cierre con código, así el navegador puede distinguirlos. Orden: sala inexistente (`4404`), luego `hello` en 5 s como máximo (`4401`).

| Código | Significado |
|---|---|
| `4401` | No llegó `hello` en 5 s, el primer mensaje no era `hello`, o el token no está firmado por este servidor. |
| `4404` | Sala inexistente. |
| `4429` | Demasiados intentos fallidos desde esta IP (20 por minuto), demasiadas conexiones (12 por sala, 40 por IP) o más de 20 mensajes/s sostenidos (ráfaga de 30). |
| `1009` | Mensaje de más de 16 KiB. |
| `4403` | Expulsado por el anfitrión (llega antes un mensaje `kicked`). |
| `1000` | La sala se ha destruido (GC) o el servidor se apaga. |

---|---|
| `4404` | Sala inexistente o token ausente/demasiado corto (< 16 caracteres). |
| `4429` | Demasiados intentos fallidos desde esta IP (20 por minuto). |
| `4403` | Expulsado por el anfitrión (llega antes un mensaje `kicked`). |
| `1000` | La sala se ha destruido (GC) o el servidor se apaga. |

Si el rechazo ocurre antes del `accept`, el cliente de navegador solo ve que la conexión falla (equivale a HTTP 403). Trátalo como «sala no encontrada».

---

## 3. Mensajes WebSocket

Sobre: `{"type": string, "id": string, "payload": object}`. El cliente pone un `id` único (uuid) en cada mensaje que quiere confirmar. Los mensajes del servidor llevan su propio `id` (uuid).

**Orden en que el servidor emite tras un comando válido:** `ack` al remitente, luego `state` a todos (si algo cambió), luego los eventos efímeros (`reveal`, `countdown`, `audio_command`…). Para una orden rechazada solo se envía `error` al remitente y el estado no cambia. No dependas del orden entre `ack` y `state` de **otros** mensajes: usa `state.version` (monótono por sala) y descarta los estados con versión menor o igual a la que ya tienes.

### 3.1 Cliente a servidor

La identidad del emisor sale **siempre del token**, nunca del payload.

| type | payload | Fase y quién |
|---|---|---|
| `hello` | `{session_token, last_version?}` | **Obligatorio como primer mensaje** (autentica la conexión; el servidor responde `ack` y luego `state`). Un `hello` posterior reenvía `state`; si el token no coincide con el de la conexión: `error bad_token`. |
| `claim_slot` | `{slot, name, color?}` | LOBBY, cualquiera. `name` 1 a 40 caracteres (se recorta a 20). `color` opcional con formato `#RRGGBB`. Si ya tienes otro hueco (no anfitrión), lo liberas y pasas a este. Si ya tienes ese hueco, actualiza nombre y color. |
| `device_ready` | `{device_id, provider}`; `provider` = `"sdk"` \| `"connect"` \| `"preview"` \| `"fake"` | Solo anfitrión. LOBBY y partida. `"preview"` indica que no hay SDK. |
| `audio_unlocked` | `{}` | Solo anfitrión. Tras el gesto del `AudioGate`. |
| `audio_report` | `{playing: boolean}` | Solo anfitrión. Envíalo cuando el audio empieza o se detiene de verdad. El servidor lo difunde como `audio_status`. |
| `audio_failed` | `{code}`; `"premium_required"` \| `"device_gone"` \| `"rate_limited"` \| `"unknown"` | Solo anfitrión. `device_gone` y `premium_required` pausan la partida. |
| `kick` | `{slot}` | LOBBY, anfitrión. No puede expulsarse a sí mismo. |
| `update_settings` | Parcial: `team_count` (2 a 4), `mode` (`"app"`\|`"voice"`), `target_cards` (3 a 30), `objection_window_s` (5 a 60), `audio_source` (`"spotify"`\|`"preview"`) | LOBBY, anfitrión. Cualquier otra clave da `invalid_settings` (las reglas D1 a D9 son fijas). `team_count` no puede dejar huecos ocupados fuera. |
| `start_game` | `{}` | LOBBY, anfitrión. Ver guardas abajo. |
| `play_request` | `{}` | TURN_READY o PLACING, equipo activo. En PLACING repite la canción («Repetir»). |
| `place_preview` | `{index}` | PLACING, activo. Máximo 10 por segundo; el exceso se ignora con `ack`. |
| `place_confirm` | `{index}` | PLACING, activo. `0 ≤ index ≤ nº de cartas de su línea`. |
| `guess_submit` | `{title, artist}` | GUESSING, activo, modo `app`. Vale vacío («No lo sé»). |
| `voice_confirm` | `{}` | GUESSING, activo, modo `voice`. |
| `objection` | `{index}` | OBJECTION, equipos distintos del activo con ficha. `index` es un hueco de **la línea del equipo activo**, distinto de `placedIndex`. |
| `objection_pass` | `{}` | OBJECTION, equipos elegibles (ver `eligibleObjectors`). |
| `honor_claim` | `{title_ok, artist_ok}` | REVEAL, activo, modo `voice`. Se puede enviar varias veces hasta salir de REVEAL. |
| `accept_guess` | `{}` | REVEAL, **cualquier equipo con hueco**, modo `app` («Dar por bueno»). |
| `next_turn` | `{}` | REVEAL, activo. Antes de `revealUnlocksAt` da `too_early`. |
| `rematch` | `{}` | GAME_OVER, anfitrión. Vuelve a LOBBY conservando equipos y dispositivos. |
| `ping` | `{t?}` | Cada 15 s. Responde `pong`. `t` es número o cadena de hasta 64 caracteres. |

**Guardas de `start_game`** (en este orden): remitente = anfitrión (`not_host`); fase LOBBY (`wrong_phase`); todos los huecos de `team_count` ocupados (`teams_incomplete`); todos conectados (`teams_offline`); audio del anfitrión listo (`audio_not_ready`: `unlocked` y `sdkReady`+`premiumOk`, o `audio_source = "preview"` y `unlocked`); canciones suficientes (`catalog_too_small`).

Ejemplos:

```json
{"type":"claim_slot","id":"b1c2…","payload":{"slot":1,"name":"Los Rojos","color":"#E63946"}}
{"type":"device_ready","id":"…","payload":{"device_id":"9f3c…","provider":"sdk"}}
{"type":"update_settings","id":"…","payload":{"mode":"app","target_cards":8}}
{"type":"place_confirm","id":"…","payload":{"index":2}}
{"type":"guess_submit","id":"…","payload":{"title":"bohemian rapsody","artist":"queen"}}
{"type":"objection","id":"…","payload":{"index":0}}
{"type":"honor_claim","id":"…","payload":{"title_ok":true,"artist_ok":false}}
{"type":"ping","id":"…","payload":{"t":1760000000123}}
```

### 3.2 Servidor a cliente

| type | payload | Destinatario |
|---|---|---|
| `state` | `{version: number, view: RoomView}` | Cada conexión recibe **su** vista proyectada. Se envía al conectar y tras cada cambio. |
| `ack` | `{ref_id}` | Remitente. |
| `error` | `{ref_id, code, message}` | Remitente. `ref_id` es el `id` del mensaje rechazado (cadena vacía si no se pudo leer). `message` está en español. |
| `countdown` | `{deadline_ts, first_slot}` | Todos, al empezar. Dura 3 s. |
| `audio_command` | `{action}`; `"prepare"` \| `"tap_required"` \| `"play_preview"` \| `"stop"` | **Solo el móvil del anfitrión.** Nunca lleva URI. |
| `audio_status` | `{playing: boolean, source: "spotify"\|"preview"}` | Todos (para mostrar «Sonando…»). |
| `audio_error` | `{code, retry: boolean}`; `code` = `"premium_required"` \| `"device_gone"` \| `"rate_limited"` \| `"unknown"` | Todos. |
| `reveal` | ver abajo | Todos, al entrar en REVEAL. |
| `turn_resolved` | `{to_slot: number\|null, token_delta: {"<slot>": number}}` | Todos, al salir de REVEAL (resultado definitivo de fichas). |
| `deck_low` | `{remaining}` | Todos, al empezar un turno con menos de 5 cartas en el mazo. |
| `kicked` | `{reason: "host"}` | Solo el expulsado; después se cierra su WS con `4403`. |
| `game_over` | `{winners: number[], reason: "target"\|"deck_exhausted", standings: {slot,name,cards,tokens}[]}` | Todos. |
| `pong` | `{t, server_ts}` | Remitente del `ping`. |

Semántica de `audio_command` (solo anfitrión):

- `prepare`: el servidor ya ha ordenado `PUT /me/player/play` en tu `device_id`. No muestres nada. Si en ~1,5 s el SDK no ha pasado a `paused=false` recibirás `tap_required`.
- `tap_required`: muestra a pantalla completa «Toca para que suene» (sin metadatos) y llama a `player.resume()` dentro del gesto. Después envía `audio_report {playing:true}`.
- `play_preview`: el turno usa la reserva (D7). Pide el audio con `GET /api/turn/audio?code=<code>` (Bearer del anfitrión), reprodúcelo en un `<audio>` desde el inicio (0 s) y envía `audio_report {playing:true}`.
- `stop`: pausa/detén todo (se envía al salir de REVEAL).

Ejemplo de `reveal` (claves de la carta en camelCase):

```json
{"type":"reveal","id":"…","payload":{
  "card":{"instanceId":"3fa9…","year":1975,"title":"Bohemian Rhapsody","artist":"Queen","note":null},
  "correct_slot":true,
  "outcome":"kept",
  "to_slot":0,
  "objection_result":{"slot":2,"index":0,"correct":false},
  "guess_auto":{"title_ok":true,"artist_ok":true,"score":0.98},
  "reveal_unlocks_at":1760000005.0
}}
```

- `outcome`: `"kept"` (la carta va a la línea del activo), `"stolen"` (va a la línea del objetor `to_slot`) o `"discarded"` (`to_slot = null`).
- `objection_result` es `null` si nadie objetó; si no, `correct` indica si el hueco del objetor era válido.
- `guess_auto` es `null` en modo `voice`.
- **La carta ya está insertada en la línea ganadora cuando llega el `state` de REVEAL**, y `fichas` ya reflejan el reparto provisional. `turn.result` (en `RoomView`) dice a dónde fue. Si quieres animar la inserción, hazlo comparando con `turn.result.toSlot`.

Ejemplo de `error`:

```json
{"type":"error","id":"…","payload":{"ref_id":"b1c2…","code":"objection_closed","message":"La ventana de objecion ya se cerro"}}
```

### 3.3 Códigos de `error`

| code | Cuándo |
|---|---|
| `bad_message`, `unknown_type`, `bad_payload` | Sobre o payload inválido (JSON ilegible o demasiado anidado, `color` mal formado, `t` demasiado largo). |
| `bad_token` | `hello` con un token distinto al de la conexión. |
| `internal` | Fallo inesperado del servidor. |
| `paused` | La partida está en PAUSED y la orden es de juego. |
| `wrong_phase` | La orden no vale en la fase actual. |
| `not_your_turn` | El emisor no es el equipo activo (o es espectador). |
| `not_host` | Orden exclusiva del anfitrión. |
| `not_allowed` | Emisor sin permiso (p. ej. el activo intentando objetar, o espectador). |
| `invalid_slot`, `invalid_name`, `slot_taken`, `host_cannot_move`, `game_started` | Errores de `claim_slot` / `kick`. |
| `invalid_settings` | `update_settings` con claves no editables o valores fuera de rango. |
| `teams_incomplete`, `teams_offline`, `audio_not_ready`, `catalog_too_small` | Guardas de `start_game`. |
| `invalid_index` | `index` fuera de `0..len(línea)`. |
| `wrong_mode` | Orden de modo `app` en sala `voice` o al revés. |
| `objection_closed` | Llegó tarde: ya hay objeción o ya se pasó a REVEAL. No gasta ficha. |
| `no_token` | Objeción sin ficha. |
| `same_slot` | Objeción al mismo hueco que colocó el activo. |
| `too_early` | `next_turn` antes de `revealUnlocksAt` (5 s tras revelar). |

---

## 4. `RoomView` (TypeScript)

Es el contenido de `state.payload.view`. Todo viene ya filtrado para ese espectador.

```ts
type Phase =
  | "lobby" | "countdown" | "turn_ready" | "placing" | "guessing"
  | "objection" | "reveal" | "paused" | "game_over";

type CardPublic = {            // solo cartas ya reveladas
  instanceId: string;
  year: number;
  title: string;
  artist: string;
  note: string | null;         // p. ej. "Single de 1988"
};
type MysteryCard = { instanceId: string; hidden: true };   // la carta en juego antes de REVEAL

interface SettingsView {
  teamCount: number;               // 2..4
  mode: "app" | "voice";
  targetCards: number;             // 3..30
  initialCardCounts: true;         // D3, fijo
  initialTokens: number;           // 0
  objectionWindowS: number;        // 5..60, por defecto 15
  objectionCost: "always";         // D2, fijo
  tokenRequiresCorrectSlot: true;  // D5, fijo
  placementTimeoutS: null;         // D8, fijo
  disconnectGraceS: number;        // 60
  startPositionMs: number;         // 10000 (D9)
  audioSource: "spotify" | "preview";
}

interface TeamView {
  slot: number;
  name: string | null;
  color: string | null;
  claimed: boolean;        // hueco ocupado
  connected: boolean;
  isHost: boolean;
  timeline: CardPublic[];  // ordenada por año
  tokens: number;
  cardCount: number;       // cuenta la carta inicial (D3)
}

interface TurnView {
  teamSlot: number;                       // equipo activo
  card: MysteryCard | CardPublic;         // CardPublic solo en REVEAL
  placedIndex: number | null;             // desde GUESSING
  previewIndex: number | null;            // solo PLACING: hueco en directo del activo
  objection: { slot: number; index: number } | null;
  eligibleObjectors: number[] | null;     // solo OBJECTION: slots que pueden objetar (con ficha)
  deadlineTs: number | null;              // OBJECTION: fin de la ventana; REVEAL: auto-siguiente (30 s)
  guess: { title: string; artist: string } | null; // modo app: solo el activo hasta REVEAL; todos en REVEAL
  audioSource: "spotify" | "preview";     // "preview" si este turno usa la reserva
  startedPlaying: boolean;
  result: {                               // solo REVEAL
    placedOk: boolean;
    objectionSlot: number | null;
    objectionOk: boolean | null;
    outcome: "kept" | "stolen" | "discarded";
    toSlot: number | null;
    titleOk: boolean;
    artistOk: boolean;
    tokenAwarded: boolean;                // ficha +1 al activo (hueco + título + artista)
    tokenDelta: Record<string, number>;   // {"0": 1, "2": -1}; el objetor siempre -1
  } | null;
  revealUnlocksAt: number | null;         // solo REVEAL: desde aquí vale next_turn
}

interface RoomView {
  code: string;
  phase: Phase;
  settings: SettingsView;
  you: { slot: number | null; isHost: boolean };   // slot null = espectador sin hueco
  teams: TeamView[];                               // length = settings.teamCount
  turn: TurnView | null;                           // null en lobby, countdown y game_over
  deckRemaining: number;
  audio: {
    hostReady: boolean;     // anfitrión conectado y con audio listo
    playing: boolean;
    source: "spotify" | "preview";
  };
  pause: {                  // solo en PAUSED
    reason: "audio_host_offline" | "team_offline";
    slot: number | null;    // equipo desconectado (team_offline)
    deadlineTs: number | null; // team_offline: fin de la gracia (60 s); luego se salta el turno
    resumePhase: Phase | null;
  } | null;
  winners: number[] | null;          // solo game_over
  gameOverReason: "target" | "deck_exhausted" | null;
  standings: { slot: number; name: string | null; cards: number; tokens: number }[] | null; // solo game_over
}
```

Reglas de interpretación:

- **Quién tiene el turno:** `view.turn.teamSlot`. «Es mi turno» = `view.you.slot === view.turn.teamSlot`.
- **Anfitrión:** `view.you.isHost`. Solo ese móvil recibe `audio_command` y reproduce audio.
- **Línea de objeción:** durante OBJECTION el objetor elige un hueco entre `0` y `teams[turn.teamSlot].timeline.length`, distinto de `turn.placedIndex`.
- **Hueco correcto:** `timeline[i-1].year <= año <= timeline[i].year`; los años iguales valen a ambos lados.
- **PAUSED:** `view.turn` sigue presente. `pause.resumePhase` indica a dónde se vuelve. Los temporizadores de objeción y revelación quedan congelados y se reanudan con el tiempo restante.
- **Fin de partida:** `phase = "game_over"`; el anfitrión puede enviar `rematch`.

---

## 5. Tabla de ocultación por fase

Carta en curso (la que se está jugando), por fase:

| Campo | LOBBY / COUNTDOWN | TURN_READY / PLACING / GUESSING | OBJECTION | REVEAL | GAME_OVER |
|---|---|---|---|---|---|
| `turn` | `null` | presente | presente | presente | `null` |
| `turn.card` | n/a | `{instanceId, hidden:true}` | `{instanceId, hidden:true}` | `CardPublic` completa | n/a |
| `title`, `artist`, `year`, `note` | nunca | **nunca** | **nunca** | sí | n/a |
| `track_id`, URI, ISRC, portada | nunca | nunca | nunca | **nunca** | nunca |
| `song_id` | nunca | nunca | nunca | **nunca** (solo `instanceId`, aleatorio por partida) | nunca |
| `turn.guess` (modo app) | n/a | solo al activo | solo al activo | a todos | n/a |
| `turn.previewIndex` | n/a | a todos (solo PLACING) | `null` | `null` | n/a |
| `turn.result` | n/a | `null` | `null` | presente | n/a |
| Mazo | solo `deckRemaining` | igual | igual | igual | igual |

Notas:

- En PAUSED se aplica la regla de la fase de la que se vino (`pause.resumePhase`); si se pausó desde REVEAL, la carta sigue revelada.
- Las cartas **ya colocadas** en las líneas (`teams[].timeline`) son públicas. Durante REVEAL la carta revelada ya está dentro de la línea ganadora.
- Aviso de diseño: el SDK de Spotify en el móvil del anfitrión sí conoce la pista (`player_state_changed`). El cliente no debe leer ni registrar `track_window`, y no mostrar nada en pantalla ni en Media Session.

---

## 6. REST (`/api`)

Cabecera de identidad en las rutas marcadas con (S): `Authorization: Bearer <session_token>`. Errores: JSON FastAPI `{"detail": "<codigo>"}`.

| Ruta | Request | Response |
|---|---|---|
| `POST /api/session` | sin cuerpo | `200 {"session_token": "<base64url(32 bytes aleatorios)>.<HMAC-SHA256 base64url>"}` |
| `GET /api/auth/status` (S, opcional) | | `200 {"auth_mode":"fake"\|"spotify","logged_in":bool,"premium_verified":bool}` |
| `POST /api/auth/spotify/start` (S) | `{"return_to"?: "/ruta"}` (si no empieza por `/`, se usa `/`) | `200 {"url"}` y `Set-Cookie: hc_oauth_nonce`. `url` es la de Spotify (modo `spotify`) o `/api/auth/spotify/callback?code=fake&state=…` (modo `fake`). `401` sin sesión válida, `429 rate_limited` (10 por minuto y por IP) |
| `GET /api/auth/spotify/callback?code&state` | lo llama Spotify; exige la cookie `hc_oauth_nonce` del mismo navegador (se borra siempre) | `302` a `PUBLIC_ORIGIN + return_to`; `400 {"detail":"invalid_state"\|"token_exchange_failed"}` |
| `GET /api/auth/spotify/token` (S) | | `200 {"access_token","expires_at"}` (epoch s; se refresca si quedan < 5 min). `401 not_logged_in` si no hay login |
| `POST /api/auth/spotify/verify-premium` (S) | `{"device_id": "…"}` | `200 {"premium": true}` o `{"premium": false, "reason": "premium_required"\|"user_not_registered"\|"no_session"\|"device_gone"\|"rate_limited"\|"unknown"}` |
| `POST /api/auth/logout` (S) | | `204` |
| `POST /api/rooms` (S) | `{"settings": {…editables…}, "name"?: string, "color"?: string}` | `200 {"code":"4821","ws_url":"ws://host/ws/rooms/4821","ws_path":"/ws/rooms/4821","slot":0}`. `401` sin sesión, `422` ajustes no editables o inválidos, `429 rate_limited` (5 creaciones por minuto y por IP), `503 rooms_full` |
| `GET /api/rooms/{code}` (S opcional) | | `200 {"status":"open"\|"started"\|"full","mode":"app"\|"voice","team_count":n,"target_cards":n,"slots":[{"slot":0,"taken":true,"name":"…","color":"…","suggested_color":"#E63946","is_host":true},…],"your_slot":number\|null}`. `404 room_not_found`; `429 rate_limited` tras 20 intentos fallidos por minuto y por IP |
| `GET /api/catalog/stats` | | `200 {"total":n,"by_decade":{"1980s":n,…},"by_origin":{"es":n,"intl":n,"unknown":n}}` |
| `GET /api/turn/audio?code=4821` (S, solo anfitrión) | | `200` audio en streaming (`audio/mpeg`; en modo fake un WAV de silencio). `403 host_only`, `403 no_preview_turn` (solo vale mientras el turno en curso use `audioSource = "preview"`), `404 preview_unavailable`, `502 preview_upstream_error`. Cabecera `Cache-Control: no-store`. No expone la URL de Deezer |
| `GET /api/healthz` | | `200 {"status":"ok"}` |
| `GET /api/admin/songs?status=` | cabecera `X-Admin-Token` | lista de canciones (solo catálogo Postgres). `404 admin_disabled` (también si `ADMIN_TOKEN` tiene menos de 32 caracteres), `401 bad_admin_token`, `501` con catálogo CSV |
| `PATCH /api/admin/songs/{id}` | `{year? (1900..2100), year_status? (<=32), year_note? (<=500), title_aliases?/artist_aliases? (<=20 de <=200), enabled?}` | canción actualizada |

`suggested_color` es una paleta de 4 colores por hueco; el diseño visual puede ignorarla.

---

## 7. Cómo jugar en `AUTH_MODE=fake`

Arranque: `AUTH_MODE=fake CATALOG_SOURCE=csv PERSISTENCE=none uvicorn app.main:app --reload --port 8000` (ver `apps/server/README.md`).

- `GET /api/auth/status` devuelve `logged_in: true` y `premium_verified: true`. `POST /api/auth/spotify/start` devuelve una `url` interna (`/api/auth/spotify/callback?code=fake&state=…`) que completa el login fake y redirige a `return_to`; `GET /api/auth/spotify/token` devuelve `fake-token`; `verify-premium` devuelve `{"premium": true}`. El frontend no debe cargar el SDK de Spotify.
- El anfitrión basta con que envíe **`device_ready {device_id:"fake", provider:"fake"}`** tras abrir el WS (en modo fake también marca `unlocked`, así que `audio_unlocked` no hace falta, aunque enviarlo es inofensivo). Repítelo en cada reconexión.
- `start_game` exige los mismos requisitos que en producción (todos los huecos ocupados y conectados, audio del anfitrión listo).
- `play_request` es un no-op en el servidor (solo registra el `instance_id` en el log). El anfitrión recibe igualmente `audio_command {action:"prepare"}`. Un `FakeAudioProvider` puede responder con `audio_report {playing:true}`; si no lo hace, a los 1,5 s llegará `audio_command {action:"tap_required"}` (es inofensivo, no pausa nada).
- Para probar la reserva: `update_settings {audio_source:"preview"}` en el lobby. `GET /api/turn/audio?code=…` devolverá un WAV de silencio de 3 s.
- Catálogo: lee `catalog/songs.csv` (columnas `ID,Cancion,Artista,Anio,Genero,Origen,AliasTitulo,AliasArtista,Nota,SpotifyTrackId,ISRC,Estado`; `Estado` vacío = verified; se excluyen `ambiguous` y `disputed`). Con menos de `team_count + 1` canciones, `start_game` da `catalog_too_small`.
- Para E2E en el servidor de pruebas, los temporizadores son los reales (cuenta atrás 3 s, ventana de objeción `objectionWindowS`, revelación mínima 5 s y automática a los 30 s).

---

## 8. Reglas y tiempos que el cliente debe conocer

| Tema | Valor |
|---|---|
| Cuenta atrás | 3 s (`countdown.deadline_ts`) |
| Ventana de objeción | `settings.objectionWindowS` (15 s por defecto). Se salta si ningún otro equipo tiene ficha. Vale la primera objeción; se cierra al recibirla o cuando todos los elegibles pasan |
| Revelación | `next_turn` permitido desde `revealUnlocksAt` (5 s). Avance automático a los 30 s (`turn.deadlineTs`) |
| Gracia por desconexión del equipo activo | 60 s (`pause.deadlineTs`). Si vence: se salta el turno y la carta vuelve al fondo del mazo. Si vuelve, se reanuda en la misma fase |
| Anfitrión sin conexión en partida | PAUSED `audio_host_offline`, sin temporizador de salto. Se reanuda cuando el anfitrión reconecta y envía `device_ready` + `audio_unlocked` |
| Anfitrión sin conexión en el lobby | A los 30 s el anfitrión pasa al siguiente hueco ocupado y conectado (`you.isHost`/`teams[].isHost` cambian) |
| Ficha | +1 al activo si hueco correcto **y** título **y** artista correctos (D5). La ficha del objetor se gasta siempre (D2). Se puede corregir (`honor_claim` / `accept_guess`) hasta salir de REVEAL |
| Resolución | Hueco del activo correcto: se queda la carta. Si no, objeción correcta: la carta va a la línea del objetor (en su sitio). Si no: se descarta |
| Fin | Al salir de REVEAL, si alguien tiene `targetCards` cartas (la inicial cuenta, D3) → `target`. Si el mazo está vacío al empezar un turno → `deck_exhausted`: gana quien tenga más cartas, luego más fichas; empate total = ganadores compartidos |
| Sin expulsión en partida | `kick` solo en LOBBY (D4) |
| Limpieza | 15 min en GAME_OVER sin revancha, o 2 h sin actividad ni conexiones: la sala se destruye |

---

## 9. Despliegue y límites (seguridad)

- El proxy (Caddy) no publica `/api/admin`; añade `Cache-Control: no-store` a `/api/*` y limita el cuerpo a 64 KB.
- La API corre con `--no-access-log --ws-max-size 16384` y `--proxy-headers --forwarded-allow-ips=<subred de Caddy>`: la IP del cliente es `request.client.host`; `X-Forwarded-For` solo cuenta si viene del proxy de confianza.
- Arranque: `AUTH_MODE=fake` se rechaza si `PUBLIC_ORIGIN` no es localhost o 127.0.0.1. Con otro origen, `SESSION_SECRET` es obligatorio.
