# Plan de mejoras (ronda 2)

Estado: **definido, pendiente de lanzar**. El usuario aún prepara «otra forma de juego», que se añadirá al final.
Las decisiones de esta página prevalecen sobre `docs/DISENO.md` donde lo contradigan.

## Decisiones cerradas

| Tema | Decisión |
|---|---|
| Pistas: coste | **1 ficha por pista.** Dos tipos: artista o título. Se pueden pedir las dos pagando dos. |
| Pistas: quién las ve | **Solo el equipo del turno** ve el texto enmascarado. Los demás ven «X ha pedido una pista de artista/título». |
| Pistas: temporizador | **1 minuto para responder** desde que se pide la pista. Si se agota, se confirma lo que haya en pantalla (hueco y respuesta). |
| Pistas: enmascarado | Calculado en el servidor, letras reveladas en posiciones fijas por turno (pedir de nuevo no destapa más), espacios y signos visibles, siempre quedan letras ocultas. |
| Audio: inicio | `start_position_ms` pasa de 10 s a **15 s** (el servidor lo envía; el fragmento de Deezer sigue empezando en 0). |
| Audio: control | **Mini reproductor** para el equipo del turno: −10 s, +10 s, pausa/reanudar y «desde el principio». Actúa sobre el reproductor del anfitrión sin enviar metadatos de la canción. Sin deslizador libre. |
| Pregunta «¿Acertasteis canción y artista?» | **No se quita** (en modo voz decide la ficha, regla D5). Se reescribe con texto claro y se coloca después del resumen. |

## Fases

### Fase 1: solo web (bajo riesgo)

- Cambiar hueco (`place_cancel`): servidor hecho (web pendiente). Máximo 3 cambios por turno; no vale tras confirmación automática de la pista.
- **#3** El año de la carta se ajusta al ancho de la tarjeta (proporcional con mínimo legible), sin desbordes.
- **#6** Cuando te toca objetar: pulso neón en «Objetar aquí» con el color del equipo, aviso «Te toca objetar», vibración corta; los equipos sin fichas ven que no pueden objetar.
- **#2** Tras confirmar el hueco, todos ven «Habéis puesto la carta entre 2012 y 2015» / «antes de 2012» / «después de 2015». Reescribir «¿Acertasteis canción y artista?» como «Ficha: ¿dijisteis bien la canción y el artista?», dejando claro que solo sirve para la ficha.

### Fase 2: carrusel (solo web, riesgo medio)
- **#5** Las cartas del mismo año se apilan en vertical y forman una sola parada del carrusel. No cambia ningún acierto: los huecos entre cartas del mismo año son equivalentes al hueco anterior o posterior del grupo (los años iguales valen a ambos lados). Mantiene ◀ ▶, etiqueta accesible y `validFrom..validTo` coherentes.

### Fase 3: audio (servidor + web + móvil real) — **servidor hecho, web hecha (pendiente de prueba en móvil real)**
- **#4** Segundo 15 y mini reproductor. Mensajes nuevos del equipo del turno al servidor y de este al anfitrión (`audio_control`: seek relativo, pausa/reanudar, reiniciar), solo válidos para el equipo activo y con límite de frecuencia. Verificar en un móvil real que el salto funciona en el reproductor de Spotify.

### Fase 4: pistas (servidor primero, web después; la más grande) — **servidor hecho, web hecha (pendiente de prueba en móvil real)**
- **#1** Comando `use_hint {kind: "artist" | "title"}`: cuesta una ficha, exige fase PLACING/GUESSING y equipo activo, y arranca un temporizador de 60 s. Estado en el turno; el texto enmascarado solo se proyecta al equipo activo. Web: botón «Pista» con contador de fichas, ventana con el texto y la cuenta atrás.
- Pruebas obligatorias: antitrampas (los demás equipos y el log no reciben el texto), motor, simulador de bots, E2E.
- Decisión cerrada: ajuste de sala `initial_tokens` (0 a 3) con **1 por defecto**, y `hints_enabled` (por defecto activado). Contrato en `docs/PROTOCOL.md` (`audio_control`, `use_hint`, `hint_used`, `turn.hints`, `audio.paused`).

## Pendiente
- Describir la «otra forma de juego» y decidir dónde encaja (ajuste de sala o modo nuevo).
- Despliegue en Vercel (web) y contenedor (servidor), explicado aparte.
- Reguetón: ~100 canciones por buscar en Spotify tras levantarse el bloqueo (lunes 12 sobre las 18:30).
