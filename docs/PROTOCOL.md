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
| `update_settings` | Parcial: `team_count` (2 a 4), `mode` (`"app"`\|`"voice"`), `target_cards` (3 a 30), `objection_window_s` (5 a 60), `audio_source` (`"spotify"`\|`"preview"`), `packs` (lista de slugs de packs de géneros, ver `GET /api/catalog/packs`; al menos uno, sin repetidos, solo slugs conocidos; por defecto `["mix"]`), `hints_enabled` (booleano, por defecto `true`), `initial_tokens` (entero 0 a 3, por defecto **1**: fichas con las que empieza cada equipo, también en la revancha) | LOBBY, anfitrión. Cualquier otra clave da `invalid_settings` (las reglas D1 a D9 son fijas). `team_count` no puede dejar huecos ocupados fuera. `packs` lo sustituye entero (no es un parche de la lista). |
| `start_game` | `{}` | LOBBY, anfitrión. Ver guardas abajo. |
| `play_request` | `{}` | TURN_READY o PLACING, equipo activo. En PLACING repite la canción («Repetir»). |
| `place_preview` | `{index}` | PLACING, activo. Máximo 10 por segundo; el exceso se ignora con `ack`. |
| `place_confirm` | `{index}` | PLACING, activo. `0 ≤ index ≤ nº de cartas de su línea`. |
| `place_cancel` | `{}` | GUESSING, activo, antes de responder. Deshace el `place_confirm` y vuelve a PLACING (ver abajo). |
| `guess_submit` | `{title, artist}` | GUESSING, activo, modo `app`. Vale vacío («No lo sé»). |
| `voice_confirm` | `{}` | GUESSING, activo, modo `voice`. |
| `audio_control` | `{action, delta_ms?}`; `action` = `"seek"` \| `"pause"` \| `"resume"` \| `"restart"`. `seek` exige `delta_ms` **entero** en `[-30000, 30000]` (la web envía ±10000); en las demás acciones `delta_ms` no puede venir. Claves extra, tipos no enteros (`1.5`, `"10000"`, `true`) o acciones desconocidas: `bad_payload` | Mini reproductor. Solo el **equipo del turno**; fases PLACING, GUESSING u OBJECTION y con la canción ya iniciada (`turn.startedPlaying`). Ver «Control de audio» abajo. |
| `use_hint` | `{kind}`; `kind` = `"artist"` \| `"title"`. Sin claves extra | Pista con ficha. Solo el equipo del turno, en PLACING o GUESSING. Ver «Pistas» abajo. |
| `objection` | `{index}` | OBJECTION, equipos distintos del activo con ficha. `index` es un hueco de **la línea del equipo activo**, distinto de `placedIndex`. |
| `objection_pass` | `{}` | OBJECTION, equipos elegibles (ver `eligibleObjectors`). |
| `honor_claim` | `{title_ok, artist_ok}` | REVEAL, activo, modo `voice`. Se puede enviar varias veces hasta salir de REVEAL. |
| `accept_guess` | `{}` | REVEAL, **cualquier equipo con hueco**, modo `app` («Dar por bueno»). |
| `next_turn` | `{}` | REVEAL, activo. Antes de `revealUnlocksAt` da `too_early`. |
| `rematch` | `{}` | GAME_OVER, anfitrión. Vuelve a LOBBY conservando equipos y dispositivos. |
| `end_game` | `{}` | Cualquier fase de partida (COUNTDOWN a REVEAL y PAUSED), solo anfitrión. En LOBBY y GAME_OVER da `wrong_phase`; si no es el anfitrión, `not_host`. Termina la partida con `game_over` `reason: "host_ended"`: ganan los equipos en posición 1 (más cartas; las fichas no desempatan, los empatados comparten posición). La carta en curso no se revela ni entra en ninguna línea. |
| `ping` | `{t?}` | Cada 15 s. Responde `pong`. `t` es número o cadena de hasta 64 caracteres. |

**Control de audio (`audio_control`).** Guardas, en este orden: `paused` (partida en PAUSED) o `wrong_phase` (fase distinta de PLACING, GUESSING, OBJECTION) → `not_your_turn` (emisor distinto del equipo activo, o espectador) → `wrong_phase` (la canción aún no ha empezado: `startedPlaying` es `false`) → `bad_payload` → `rate_limited`. Dos límites de frecuencia: **4 comandos por segundo y por conexión** (cubo con ráfaga de 4; el exceso da `rate_limited` y no cambia nada) y **80 por turno** (después, `rate_limited` hasta el siguiente turno). El servidor no llama a la Web API de Spotify: reenvía el comando al móvil del anfitrión (`audio_command`, ver 3.2) y este lo ejecuta en local. El anfitrión no recibe ningún dato de la canción.
- `seek`: salto **relativo** de `delta_ms` desde la posición actual (negativo = atrás). El reproductor del anfitrión debe limitarlo a `[0, duración]`.
- `pause` / `resume`: pausa y reanuda.
- `restart`: vuelve a la posición 0 de la canción (el principio, no el segundo 15) y deja la canción sonando.
- Estado visible: tras cada comando válido el servidor difunde un `state` con `audio.paused` (intención del equipo: `true` tras `pause`, `false` tras `resume`, `restart`, `play_request` o un `audio_report {playing:true}`). `audio.playing` sigue siendo lo que el anfitrión informa con `audio_report`. Para mostrar el botón: «pausado» = `audio.paused`; «suena» = `audio.playing && !audio.paused`.

**Cambiar hueco (`place_cancel`).** Permite corregir un hueco confirmado por error. Guardas, en este orden: `paused` o `wrong_phase` (fase distinta de GUESSING) → `not_your_turn` (emisor distinto del equipo activo, o espectador) → `already_guessed` (el equipo ya tiene respuesta guardada) → `wrong_phase` (el hueco lo confirmó el servidor al vencer el límite de la pista: la confirmación automática es definitiva) → `too_many_changes` (ya hubo 3 cambios en el turno). En modo `app` y en modo `voice`, `guess_submit` y `voice_confirm` salen de GUESSING, así que tras responder la fase ya no es GUESSING y el código es `wrong_phase`. `already_guessed` es una guarda defensiva. Efecto: la fase vuelve a **PLACING**, `view.turn.placedIndex` pasa a `null`, se conserva `previewIndex` (el hueco que acababa de confirmar, para que la web lo deje seleccionado) y se descarta cualquier respuesta guardada del turno. No cambia fichas, pistas, ni el temporizador «límite para responder»: sigue su curso y, si vence en PLACING, confirma `previewIndex` como siempre. No hay objeción hasta salir de GUESSING. Se difunde el `state` habitual; no sale ningún dato de la canción. La vista expone `turn.placeChangesLeft` (3 menos los cambios usados) y `turn.placedAuto` (hueco confirmado por el servidor) a todos, para que la web oculte el botón sin esperar al error. Un rechazo no cambia nada ni cuenta como cambio.

**Pistas (`use_hint`).** Cuesta **1 ficha** (se resta en el acto y no se devuelve, acierte o no). Dos tipos y se pueden pedir los dos pagando dos; cada tipo una vez por turno. Guardas, en este orden: `paused` o `wrong_phase` (fase distinta de PLACING y GUESSING) → `not_your_turn` → `hints_disabled` (`settings.hintsEnabled` es `false`) → `bad_payload` → `hint_already_used` (ese tipo ya se pidió este turno) → `no_tokens` (el equipo tiene 0 fichas). Un rechazo no cuesta nada.
- **Solo el equipo del turno ve el texto enmascarado** (en `view.turn.hints.used[].masked` de su propio `state`). Los demás equipos, el anfitrión (si no es el activo) y los espectadores solo ven `used: [{"kind": "artist"}]`; con ese dato y con el evento `hint_used` la web puede mostrar «X ha pedido una pista de artista/título». El texto no sale en ningún evento efímero, ni en errores, ni en logs.
- **Enmascarado** (calculado en el servidor, `mask_text`): solo se ocultan las **letras** (acentuadas y ñ incluidas) y se sustituyen por `_`; espacios, dígitos y signos salen tal cual. Se revela alrededor del 40 % de las letras (siempre entre el 25 % y el 60 %) en posiciones fijas por `(carta del turno, tipo)`: pedir de nuevo o recargar nunca destapa más, y la pista de artista no revela nada del título ni al revés. Cada palabra de 3 o más letras muestra al menos una letra y oculta al menos una; con 2 o más letras en total siempre queda alguna oculta. `"artist"` enmascara el artista de la carta; `"title"`, el título. Ejemplo: `"Alejandro Sanz"` → `"A___a__r_ _a_z"` (las posiciones concretas dependen de la carta; el formato es este).
- **Temporizador «límite para responder» (60 s).** Al pedir la **primera** pista del turno arranca; una segunda pista no lo reinicia. `view.turn.hints.deadlineTs` (epoch s) es el final visible: 60 s exactos tras la primera pista. El servidor actúa a los **62 s** (2 s de gracia), para que el cliente tenga tiempo de enviar lo que haya en pantalla justo a los 60 s; si el cliente llega a tiempo, el servidor cancela su temporizador al salir de GUESSING. Al vencer:
  - En **PLACING**: el servidor confirma el hueco de `previewIndex` (si es `null`, el hueco central: `floor(n / 2)` con `n` cartas en la línea) como si el equipo hubiera enviado `place_confirm`, y pasa a GUESSING. Como la respuesta aún falta, arranca una **última ventana de 8 s** (`hints.deadlineTs` pasa a ser `ahora + 8`, el servidor actúa a los 10 s) para no dejar el turno colgado.
  - En **GUESSING**: modo `voice`, equivale a `voice_confirm`; modo `app`, se envía una respuesta vacía (`guess = {title:"", artist:""}`, cuenta como «No lo sé» y no da ficha). Después sigue el flujo normal (OBJECTION o REVEAL).
  - El temporizador se cancela al salir de GUESSING (a OBJECTION o REVEAL), al terminar o saltarse el turno y en `end_game`.
  - **Pausa:** si la partida pasa a PAUSED (anfitrión o equipo activo desconectados), el temporizador se congela y se reanuda con el tiempo restante al volver (igual que el de objeción). Mientras dura la pausa `hints.deadlineTs` conserva el valor anterior; al reanudar se recalcula. Calcula la cuenta atrás en el cliente con `pause`/`deadlineTs`, no con un reloj propio.
- `turn_resolved.token_delta` y `result.tokenDelta` **no** incluyen las fichas gastadas en pistas (ya se restaron en `teams[].tokens` al pedirlas).

**Guardas de `start_game`** (en este orden): remitente = anfitrión (`not_host`); fase LOBBY (`wrong_phase`); todos los huecos de `team_count` ocupados (`teams_incomplete`); todos conectados (`teams_offline`); audio del anfitrión listo (`audio_not_ready`: `unlocked` y `sdkReady`+`premiumOk`, o `audio_source = "preview"` y `unlocked`); canciones suficientes (`catalog_too_small`). El mazo se construye con las canciones habilitadas de `settings.packs`, sin duplicados (por `track_id` y por título+artista normalizados); `catalog_too_small` se evalúa sobre ese mazo ya filtrado. La revancha conserva `packs`.

Ejemplos:

```json
{"type":"claim_slot","id":"b1c2…","payload":{"slot":1,"name":"Los Rojos","color":"#E63946"}}
{"type":"device_ready","id":"…","payload":{"device_id":"9f3c…","provider":"sdk"}}
{"type":"update_settings","id":"…","payload":{"mode":"app","target_cards":8}}
{"type":"place_confirm","id":"…","payload":{"index":2}}
{"type":"place_cancel","id":"…","payload":{}}
{"type":"guess_submit","id":"…","payload":{"title":"bohemian rapsody","artist":"queen"}}
{"type":"objection","id":"…","payload":{"index":0}}
{"type":"honor_claim","id":"…","payload":{"title_ok":true,"artist_ok":false}}
{"type":"ping","id":"…","payload":{"t":1760000000123}}
{"type":"audio_control","id":"…","payload":{"action":"seek","delta_ms":-10000}}
{"type":"audio_control","id":"…","payload":{"action":"pause"}}
{"type":"use_hint","id":"…","payload":{"kind":"artist"}}
{"type":"update_settings","id":"…","payload":{"hints_enabled":true,"initial_tokens":2}}
```

### 3.2 Servidor a cliente

| type | payload | Destinatario |
|---|---|---|
| `state` | `{version: number, view: RoomView}` | Cada conexión recibe **su** vista proyectada. Se envía al conectar y tras cada cambio. |
| `ack` | `{ref_id}` | Remitente. |
| `error` | `{ref_id, code, message}` | Remitente. `ref_id` es el `id` del mensaje rechazado (cadena vacía si no se pudo leer). `message` está en español. |
| `countdown` | `{deadline_ts, first_slot}` | Todos, al empezar. Dura 3 s. |
| `audio_command` | `{action, delta_ms?}`; `"prepare"` \| `"tap_required"` \| `"play_preview"` \| `"stop"` \| `"seek"` \| `"pause"` \| `"resume"` \| `"restart"`. `delta_ms` (entero) solo viene con `seek` | **Solo el móvil del anfitrión.** Nunca lleva URI ni datos de la canción. |
| `audio_status` | `{playing: boolean, source: "spotify"\|"preview"}` | Todos (para mostrar «Sonando…»). |
| `audio_error` | `{code, retry: boolean}`; `code` = `"premium_required"` \| `"device_gone"` \| `"rate_limited"` \| `"unknown"` | Todos. |
| `hint_used` | `{slot: number, kind: "artist"\|"title"}` | Todos (incluido el activo), cuando un equipo paga una pista. **Nunca lleva el texto**; el enmascarado solo está en `state` del equipo activo. Sirve para el aviso «X ha pedido una pista de artista». |
| `reveal` | ver abajo | Todos, al entrar en REVEAL. |
| `turn_resolved` | `{to_slot: number\|null, token_delta: {"<slot>": number}}` | Todos, al salir de REVEAL (resultado definitivo de fichas). |
| `deck_low` | `{remaining}` | Todos, al empezar un turno con menos de 5 cartas en el mazo. |
| `kicked` | `{reason: "host"}` | Solo el expulsado; después se cierra su WS con `4403`. |
| `game_over` | `{winners: number[], reason: "target"\|"deck_exhausted"\|"host_ended", standings: {slot,name,cards,tokens,rank}[]}` | Todos. `winners` son los equipos con `rank` 1. `standings` va ordenada por `rank` y luego por `slot`. |
| `pong` | `{t, server_ts}` | Remitente del `ping`. |

Semántica de `audio_command` (solo anfitrión):

- `prepare`: el servidor ya ha ordenado `PUT /me/player/play` en tu `device_id`. No muestres nada. Si en ~1,5 s el SDK no ha pasado a `paused=false` recibirás `tap_required`.
- `tap_required`: muestra a pantalla completa «Toca para que suene» (sin metadatos) y llama a `player.resume()` dentro del gesto. Después envía `audio_report {playing:true}`.
- `play_preview`: el turno usa la reserva (D7). Pide el audio con `GET /api/turn/audio?code=<code>` (Bearer del anfitrión), reprodúcelo en un `<audio>` desde el inicio (0 s) y envía `audio_report {playing:true}`.
- `stop`: pausa/detén todo (se envía al salir de REVEAL).
- `seek` `{delta_ms}`: salta `delta_ms` ms respecto a la posición actual (p. ej. `player.getCurrentState()` + `player.seek(pos + delta_ms)` en el SDK; en preview, `audio.currentTime`). Limita el resultado a `[0, duración]`. No envíes `audio_report` por esto.
- `pause`: `player.pause()` / `audio.pause()`. Envía `audio_report {playing:false}`.
- `resume`: `player.resume()` / `audio.play()`. Envía `audio_report {playing:true}`.
- `restart`: `player.seek(0)` y, si estaba en pausa, `resume`. Envía `audio_report {playing:true}`. Es el principio de la canción, no el segundo 15.
- Estos cuatro comandos solo se envían a petición del equipo del turno, validados y limitados por el servidor; ejemplos: `{"type":"audio_command","id":"…","payload":{"action":"seek","delta_ms":-10000}}` y `{"type":"audio_command","id":"…","payload":{"action":"pause"}}`.

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

### 3.2.1 `turn.result`: por qué un hueco es correcto o no

Fuente única: `view.turn.result` dentro de `state`. Los eventos `reveal` y `turn_resolved` **no** llevan estos campos (las fichas pueden cambiar tras el `reveal` con `honor_claim`/`accept_guess`, y `state` siempre trae la versión vigente). Solo existe en REVEAL (y en PAUSED si se pausó desde REVEAL); en cualquier otra fase `turn.result` es `null` y no hay `songYear` en ningún sitio. En GAME_OVER `turn` es `null`.

Todo se calcula con las líneas **antes** de insertar la carta (después los vecinos cambian), sobre la línea del equipo activo.

```ts
interface SlotCheck {
  index: number;               // hueco elegido (0 = antes de la primera carta, n = tras la última)
  leftYear: number | null;     // año de la carta vecina izquierda (null en el extremo)
  rightYear: number | null;    // año de la vecina derecha (null en el extremo)
  ok: boolean;
  reason: "inside" | "equal_left" | "equal_right" | "equal_both" | "too_early" | "too_late";
  validFrom: number;           // primer hueco que habría sido correcto
  validTo: number;             // último hueco correcto (inclusive); con años iguales hay varios
}
```

`reason`:

| valor | significado |
|---|---|
| `inside` | el año queda estrictamente entre los vecinos, o en un extremo sin igualdad |
| `equal_left` / `equal_right` / `equal_both` | correcto porque el año es igual al vecino izquierdo / derecho / ambos (los años iguales valen a ambos lados) |
| `too_early` | la canción es anterior al vecino izquierdo: debía ir antes |
| `too_late` | la canción es posterior al vecino derecho: debía ir después |

`objection` es `null` si nadie objetó. Si no, es un `SlotCheck` del hueco del objetor en la línea del activo, más `slot` (equipo objetor) y `tokenSpent` (siempre `true`, D2).

`token.reason`: `awarded` (hueco + título + artista correctos, D5), `wrong_slot` (colocó mal), `title_wrong`, `artist_wrong`, `title_and_artist_wrong`. Es el valor vigente: en modo voz, hasta que el activo hace `honor_claim` se muestra `title_and_artist_wrong` (provisional); cambia con cada `honor_claim`/`accept_guess`. `already_lost_to_objection` no existe: con las reglas actuales la objeción no cambia la ficha del activo.

`headline` (titular del desenlace):

| valor | caso |
|---|---|
| `kept` | la carta se queda en el activo, sin objeción |
| `kept_objection_failed` | hubo objeción y el activo tenía razón (el objetor pierde su ficha) |
| `stolen` | el activo falló y el objetor acertó: la carta va a `toSlot` |
| `discarded` | el activo falló, nadie objetó: carta descartada |
| `discarded_objection_failed` | el activo falló y el objetor también: carta descartada |

Ejemplo 1: el activo pone la carta (2012) entre 2012 y 2015, año igual al vecino izquierdo. `validFrom` es 0 porque ponerla antes del 2012 también valía.

```json
{"songYear":2012,"placedOk":true,"outcome":"kept","toSlot":0,"headline":"kept",
 "placement":{"index":1,"leftYear":2012,"rightYear":2015,"ok":true,"reason":"equal_left","validFrom":0,"validTo":1},
 "objection":null,
 "token":{"awarded":true,"reason":"awarded"}}
```

Ejemplo 2: la carta (1990) se colocó tras 2000 (debía ir antes); el equipo 1 objetó en el hueco 1 y se la queda.

```json
{"songYear":1990,"placedOk":false,"outcome":"stolen","toSlot":1,"headline":"stolen",
 "objectionSlot":1,"objectionOk":true,
 "placement":{"index":2,"leftYear":2000,"rightYear":null,"ok":false,"reason":"too_early","validFrom":1,"validTo":1},
 "objection":{"slot":1,"index":1,"leftYear":1980,"rightYear":2000,"ok":true,"reason":"inside","validFrom":1,"validTo":1,"tokenSpent":true},
 "token":{"awarded":false,"reason":"wrong_slot"}}
```

(Los ejemplos omiten `titleOk`, `artistOk`, `tokenAwarded` y `tokenDelta`, que no cambian.)

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
| `invalid_settings` | `update_settings` con claves no editables o valores fuera de rango. Para `packs`: lista vacía, slugs repetidos, slug con formato inválido o slug desconocido. |
| `teams_incomplete`, `teams_offline`, `audio_not_ready`, `catalog_too_small` | Guardas de `start_game`. |
| `invalid_index` | `index` fuera de `0..len(línea)`. |
| `wrong_mode` | Orden de modo `app` en sala `voice` o al revés. |
| `objection_closed` | Llegó tarde: ya hay objeción o ya se pasó a REVEAL. No gasta ficha. |
| `no_token` | Objeción sin ficha. |
| `no_tokens` | `use_hint` con 0 fichas. |
| `hint_already_used` | `use_hint` de un tipo (`artist`/`title`) ya pedido en este turno. |
| `hints_disabled` | `use_hint` con `settings.hintsEnabled = false`. |
| `already_guessed` | `place_cancel` cuando el equipo ya respondió en este turno. |
| `too_many_changes` | `place_cancel` por cuarta vez en el turno (máximo 3). |
| `rate_limited` | `audio_control` por encima de 4 por segundo y conexión, o más de 80 en el turno. No cambia el estado. Es un `error` de WS (no confundir con el `audio_error` ni con el cierre `4429`). |
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
  initialTokens: number;           // 0..3, por defecto 1 (S2); se aplica al empezar y en la revancha
  hintsEnabled: boolean;           // por defecto true
  objectionWindowS: number;        // 5..60, por defecto 15
  objectionCost: "always";         // D2, fijo
  tokenRequiresCorrectSlot: true;  // D5, fijo
  placementTimeoutS: null;         // D8, fijo
  disconnectGraceS: number;        // 60
  startPositionMs: number;         // 15000 (D9, segundo 15)
  audioSource: "spotify" | "preview";
  packs: string[];
}

// Para el equipo activo: { kind, masked }. Para todos los demás: { kind } (la clave `masked` no existe).
type HintUsed = { kind: "artist" | "title"; masked?: string };   // masked, p. ej. "A___a__r_ _a_z"

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
  placeChangesLeft: number;  // 3 menos los place_cancel usados este turno; visible para todos
  placedAuto: boolean;       // true si el servidor confirmó el hueco al vencer la pista (place_cancel ya no vale)
  // Pistas. null si hintsEnabled es false o si la carta ya está revelada (REVEAL; las pistas desaparecen).
  hints: {
    deadlineTs: number | null;            // fin visible de los 60 s (epoch s); null si no hay temporizador
    used: HintUsed[];                     // en orden de petición
  } | null;
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
    // Explicación estructurada (ver 3.2.1). Solo existe en REVEAL.
    songYear: number;
    placement: SlotCheck;                 // el hueco del equipo activo
    objection: (SlotCheck & { slot: number; tokenSpent: boolean }) | null;
    token: { awarded: boolean; reason: "awarded" | "wrong_slot" | "title_wrong" | "artist_wrong" | "title_and_artist_wrong" };
    headline: "kept" | "kept_objection_failed" | "stolen" | "discarded" | "discarded_objection_failed";
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
    playing: boolean;       // lo que informa el anfitrión con audio_report
    paused: boolean;        // el equipo del turno pidió pausa (audio_control); false en cualquier otro caso
    source: "spotify" | "preview";
  };
  pause: {                  // solo en PAUSED
    reason: "audio_host_offline" | "team_offline";
    slot: number | null;    // equipo desconectado (team_offline)
    deadlineTs: number | null; // team_offline: fin de la gracia (60 s); luego se salta el turno
    resumePhase: Phase | null;
  } | null;
  winners: number[] | null;          // solo game_over
  gameOverReason: "target" | "deck_exhausted" | "host_ended" | null;
  standings: { slot: number; name: string | null; cards: number; tokens: number; rank: number }[] | null; // solo game_over; ordenada por rank, luego slot
}
```

Reglas de interpretación:

- **Quién tiene el turno:** `view.turn.teamSlot`. «Es mi turno» = `view.you.slot === view.turn.teamSlot`.
- **Anfitrión:** `view.you.isHost`. Solo ese móvil recibe `audio_command` y reproduce audio.
- **Pistas:** `view.turn.hints?.used` con `masked` solo existe si `view.you.slot === view.turn.teamSlot`. Las fichas gastadas ya están restadas en `teams[].tokens`.
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
| `turn.hints.used[].masked` | n/a | **solo al equipo activo** (nunca a los demás, ni al anfitrión si no es el activo) | `null` si no hay pistas; el activo conserva `masked` mientras dure la fase | `hints = null` | n/a |
| `turn.hints.used[].kind`, `turn.hints.deadlineTs` | n/a | a todos | a todos (`deadlineTs = null`) | `hints = null` | n/a |
| `turn.previewIndex` | n/a | a todos (solo PLACING) | `null` | `null` | n/a |
| `turn.result` (incl. `songYear`, `placement`, `objection`, `token`, `headline`) | n/a | `null` | `null` | presente | n/a |
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
| `POST /api/rooms` (S) | `{"settings": {…editables…}, "name"?: string, "color"?: string}` | `200 {"code":"4821","ws_url":"ws://host/ws/rooms/4821","ws_path":"/ws/rooms/4821","slot":0}`. `401` sin sesión, `422` ajustes no editables o inválidos (incluye `settings.packs` vacío, repetido o con slugs desconocidos), `429 rate_limited` (5 creaciones por minuto y por IP), `503 rooms_full` |
| `GET /api/rooms/{code}` (S opcional) | | `200 {"status":"open"\|"started"\|"full","mode":"app"\|"voice","team_count":n,"target_cards":n,"slots":[{"slot":0,"taken":true,"name":"…","color":"…","suggested_color":"#E63946","is_host":true},…],"your_slot":number\|null}`. `404 room_not_found`; `429 rate_limited` tras 20 intentos fallidos por minuto y por IP |
| `GET /api/catalog/packs` | | `200 [{"slug":"mix","name":"Mix variado","description":"…","icon":"disc-3","count":180},…]` ordenado por `sort`. Público (sin sesión). `icon` es un nombre de icono de lucide-react. `count` son las canciones habilitadas del pack; un pack con `count` 0 se devuelve igualmente (la web lo muestra deshabilitado). Las definiciones salen de `catalog/packs.json` |
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
| Pistas | 1 ficha cada una (`artist`, `title`); 60 s para responder desde la primera (el servidor actúa a los 62 s); al vencer se confirma lo que haya (ver «Pistas» en 3.1) |
| Audio | La canción empieza en `settings.startPositionMs` (15 000 ms). El mini reproductor usa `audio_control` (±10 s, pausa, desde el principio) |
| Ficha | +1 al activo si hueco correcto **y** título **y** artista correctos (D5). La ficha del objetor se gasta siempre (D2). Se puede corregir (`honor_claim` / `accept_guess`) hasta salir de REVEAL |
| Resolución | Hueco del activo correcto: se queda la carta. Si no, objeción correcta: la carta va a la línea del objetor (en su sitio). Si no: se descarta |
| Fin | Al salir de REVEAL, si alguien tiene `targetCards` cartas (la inicial cuenta, D3) → `target`. Si el mazo está vacío al empezar un turno → `deck_exhausted`: ranking solo por cartas (ver abajo). El anfitrión puede cortar antes con `end_game` → `host_ended` (misma regla de ranking; la carta en curso, si no estaba revelada, vuelve al fondo del mazo sin enviarse a nadie) |
| Sin expulsión en partida | `kick` solo en LOBBY (D4) |
| Limpieza | 15 min en GAME_OVER sin revancha, o 2 h sin actividad ni conexiones: la sala se destruye |

---

## 9. Despliegue y límites (seguridad)

- El proxy (Caddy) no publica `/api/admin`; añade `Cache-Control: no-store` a `/api/*` y limita el cuerpo a 64 KB.
- La API corre con `--no-access-log --ws-max-size 16384` y `--proxy-headers --forwarded-allow-ips=<subred de Caddy>`: la IP del cliente es `request.client.host`; `X-Forwarded-For` solo cuenta si viene del proxy de confianza.
- Arranque: `AUTH_MODE=fake` se rechaza si `PUBLIC_ORIGIN` no es localhost o 127.0.0.1. Con otro origen, `SESSION_SECRET` es obligatorio.

### Ranking final

Se ordena solo por número de cartas en la línea (la inicial cuenta). Las fichas no desempatan. Los equipos con las mismas cartas comparten posición y el siguiente salta los huecos (1, 1, 3). `rank` es un entero >= 1. Dentro de un empate, el orden es por `slot`. `winners` son los equipos con `rank` 1, también en `target`, `deck_exhausted` y `host_ended`. Un equipo sin reclamar no aparece.
