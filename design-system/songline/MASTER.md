# SongLine · Design System MASTER

Fuente de verdad visual para los implementadores. Sustituye a `design-system/hitstercasero/MASTER.md` (estilo clay claro, obsoleto).
Explicación y razones: `docs/DISENO-VISUAL.md`. Maqueta viva: `docs/design-preview.html`.

**Estilo:** Neon Pop sobre noche cerrada. Modo oscuro único (no hay modo claro). Brillo de color solo en lo que importa: la línea del tiempo, la carta en juego, el turno activo y las fichas.
**Generado con:** `ui-ux-pro-max` (consultas de música, party game, synthwave y mobile game; dominios `style`, `typography`, `ux`, `stack react`), ajustado a mano. Lo que la skill propuso y se descartó está en la última sección.

## 1. Tokens CSS (pegar en `apps/web/src/styles/tokens.css`)

```css
:root {
  color-scheme: dark;

  /* Fondos y superficies */
  --color-bg: #0D0E15;            /* Midnight Vinyl */
  --color-surface: #151726;       /* tarjetas, paneles */
  --color-surface-2: #1D2033;     /* elevada: modales, tarjeta de carta */
  --color-surface-3: #272B45;     /* hover, pistas de barras */
  --color-overlay: rgba(6, 6, 12, 0.78);
  --color-border: #2E3250;        /* decorativo, no sirve de límite de control */
  --color-border-strong: #6C72A8; /* bordes de controles, 3:1 */

  /* Texto */
  --color-fg: #F4F1FF;
  --color-fg-2: #B4B0D0;
  --color-fg-3: #8E8BB0;
  --color-fg-disabled: #6E7096;

  /* Marca y estados */
  --color-primary: #7B2CBF;       /* Electric Purple: relleno de acción */
  --color-primary-hover: #8A35D1;
  --color-primary-pressed: #6A1FA8;
  --color-primary-light: #B77CFF; /* Ultraviolet: texto/iconos sobre oscuro */
  --color-on-primary: #FFFFFF;
  --color-accent: #00F5D4;        /* Neon Cyan: línea del tiempo, aciertos */
  --color-accent-pressed: #00C9AE;
  --color-on-accent: #0D0E15;
  --color-magenta: #FF007F;       /* Hot Pink: retos, borde y glow */
  --color-magenta-light: #FF4DA6; /* texto sobre oscuro */
  --color-danger: #D6006B;        /* relleno de botón peligro */
  --color-danger-pressed: #B80059;
  --color-on-danger: #FFFFFF;
  --color-gold: #FFB703;          /* Retro Amber: fichas, ganador */
  --color-gold-deep: #C98700;
  --color-on-gold: #0D0E15;
  --color-focus: #00F5D4;

  /* Equipos (color + forma) */
  --color-team-1: #FF6B4A;        /* círculo */
  --color-team-2: #4D8DFF;        /* triángulo */
  --color-team-3: #4ADE80;        /* cuadrado */
  --color-team-4: #C084FC;        /* rombo */

  /* Década (vinilo de la carta revelada) */
  --decade-50: #FFD166; --decade-60: #FF9F1C; --decade-70: #FF6B4A; --decade-80: #FF007F;
  --decade-90: #B77CFF; --decade-00: #4D8DFF; --decade-10: #00F5D4; --decade-20: #4ADE80;

  /* Glow (sombras de color) */
  --glow-primary: 0 0 0 1px rgba(183,124,255,.45), 0 0 18px rgba(123,44,191,.60), 0 0 48px rgba(123,44,191,.30);
  --glow-accent: 0 0 0 1px rgba(0,245,212,.50), 0 0 14px rgba(0,245,212,.55), 0 0 40px rgba(0,245,212,.22);
  --glow-magenta: 0 0 0 1px rgba(255,0,127,.50), 0 0 16px rgba(255,0,127,.55), 0 0 44px rgba(255,0,127,.25);
  --glow-gold: 0 0 0 1px rgba(255,183,3,.55), 0 0 16px rgba(255,183,3,.55), 0 0 44px rgba(255,183,3,.22);
  --glow-text-accent: 0 0 12px rgba(0,245,212,.65);
  --glow-text-magenta: 0 0 12px rgba(255,0,127,.70);
  --glow-text-gold: 0 0 14px rgba(255,183,3,.60);

  /* Sombras de elevación (sobre fondo oscuro, más opacas) */
  --shadow-sm: 0 2px 6px rgba(0,0,0,.45);
  --shadow-md: 0 8px 20px rgba(0,0,0,.50), inset 0 1px 0 rgba(255,255,255,.06);
  --shadow-lg: 0 20px 48px rgba(0,0,0,.60), inset 0 1px 0 rgba(255,255,255,.08);
  --shadow-btn-press: inset 0 3px 8px rgba(0,0,0,.45);

  /* Radios */
  --radius-xs: 6px;
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 24px;
  --radius-pill: 999px;

  /* Espacio (rejilla de 4) */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 20px; --space-6: 24px; --space-8: 32px; --space-10: 40px; --space-12: 48px;
  --touch-min: 48px;

  /* Tipografía */
  --font-display: 'Unbounded', 'Arial Black', 'Segoe UI', system-ui, sans-serif;
  --font-ui: 'Outfit', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;

  /* Movimiento */
  --ease-out: cubic-bezier(.22, 1, .36, 1);
  --ease-in-out: cubic-bezier(.65, 0, .35, 1);
  --ease-spring: cubic-bezier(.34, 1.56, .64, 1);
  --motion-press: 90ms;
  --motion-fast: 160ms;
  --motion-base: 240ms;
  --motion-slow: 360ms;
  --motion-flip: 700ms;
  --motion-celebrate: 1200ms;
}
@media (prefers-reduced-motion: reduce) {
  :root { --motion-press: 0ms; --motion-fast: 0ms; --motion-base: 0ms; --motion-slow: 0ms; --motion-flip: 0ms; --motion-celebrate: 0ms; }
}

/* Alias de compatibilidad con los nombres del diseño clay anterior.
   Quitarlos cuando ya no se use ningún `bg-card`, `text-muted-foreground`, etc. */
:root {
  --color-background: var(--color-bg);
  --color-foreground: var(--color-fg);
  --color-card: var(--color-surface);
  --color-card-foreground: var(--color-fg);
  --color-muted: var(--color-surface-2);
  --color-muted-foreground: var(--color-fg-2);
  --color-destructive: var(--color-danger);
  --color-ring: var(--color-focus);
  --color-secondary: var(--color-primary-light);
  --color-on-secondary: #0D0E15;
  --color-on-destructive: var(--color-on-danger);
}
```

**Aviso para Tailwind (`tailwind.config.js`).** En el diseño viejo `accent` era ámbar y se usaba para el anillo del turno (`ring-accent`). Ahora `accent` es cian y el ámbar es `gold`. Revisad cada `accent` y `ring-accent` del código: el anillo del turno pasa a usar el color del equipo.

### Fuentes (añadir a `index.html`, ya permitido por la CSP)

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Unbounded:wght@600;700;800&display=swap" rel="stylesheet">
```

Ambas cubren á é í ó ú ü ñ ¿ ¡. Quitar Fredoka y Quicksand. `font-display: swap` ya viene en la URL.

### Base global

```css
html, body { margin: 0; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-ui); font-size: 16px; line-height: 1.5; -webkit-font-smoothing: antialiased; }
:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 3px; }
body { background-image: radial-gradient(120% 40% at 50% 0%, rgba(123,44,191,.35), transparent 70%); background-repeat: no-repeat; }
```

## 2. Paleta y contraste

| Token | HEX | Uso |
|---|---|---|
| `--color-bg` | `#0D0E15` | Fondo de pantalla (Midnight Vinyl) |
| `--color-surface` | `#151726` | Paneles, tarjetas de pack, TeamPanel |
| `--color-surface-2` | `#1D2033` | Modales, tarjetas de carta, botón secundario |
| `--color-surface-3` | `#272B45` | Pistas de barras, hover |
| `--color-border` | `#2E3250` | Separadores decorativos |
| `--color-border-strong` | `#6C72A8` | Borde de controles y huecos (3:1) |
| `--color-fg` / `-2` / `-3` | `#F4F1FF` / `#B4B0D0` / `#8E8BB0` | Texto principal / secundario / ayuda |
| `--color-fg-disabled` | `#6E7096` | Texto deshabilitado (exento de AA) |
| `--color-primary` | `#7B2CBF` | Relleno de acción (Electric Purple) |
| `--color-primary-light` | `#B77CFF` | Texto e iconos morados sobre oscuro |
| `--color-accent` | `#00F5D4` | Línea del tiempo, aciertos, selección (Neon Cyan) |
| `--color-magenta` | `#FF007F` | Retos: borde, brillo, icono. Nunca texto pequeño |
| `--color-magenta-light` | `#FF4DA6` | Texto de reto sobre oscuro |
| `--color-danger` | `#D6006B` | Relleno de botón peligro |
| `--color-gold` | `#FFB703` | Fichas, ganador, recompensa (Retro Amber) |
| `--color-team-1..4` | `#FF6B4A` `#4D8DFF` `#4ADE80` `#C084FC` | Equipos, siempre con forma: círculo, triángulo, cuadrado, rombo |

Ratios medidos (fórmula WCAG 2.1, luminancia relativa sRGB):

| Pareja | Ratio | Resultado |
|---|---|---|
| `fg` sobre `bg` / `surface` / `surface-2` / `surface-3` | 17,3 / 16,0 / 14,4 / 12,4 | AAA |
| `fg-2` sobre `bg` / `surface` / `surface-3` | 9,2 / 8,5 / 6,6 | AAA |
| `fg-3` sobre `bg` / `surface` / `surface-2` | 5,9 / 5,5 / 4,95 | AA |
| `fg-disabled` sobre `bg` | 4,05 | Exento (deshabilitado) |
| `accent` sobre `bg` / `surface` / `surface-3` | 13,8 / 12,7 / 9,9 | AAA |
| `on-accent` (`#0D0E15`) sobre `accent` | 13,8 | AAA |
| `gold` sobre `bg` / `surface` / `surface-2` | 11,0 / 10,2 / 9,2 | AAA |
| `on-gold` sobre `gold` | 11,0 | AAA |
| `primary-light` sobre `bg` / `surface` / `surface-3` | 6,7 / 6,2 / 4,8 | AA |
| `#FFFFFF` sobre `primary` / `primary-hover` / `primary-pressed` | 7,1 / 6,0 / 8,8 | AAA |
| `#7B2CBF` sobre `bg` (como texto o borde) | 2,7 | No usar. Usa `primary-light` |
| `magenta` sobre `bg` / `surface` / `surface-2` | 5,1 / 4,7 / 4,25 | Borde e icono (3:1) y texto grande. Texto pequeño usa `magenta-light` |
| `magenta-light` sobre `bg` / `surface` / `surface-3` | 6,3 / 5,8 / 4,5 | AA |
| `#FFFFFF` sobre `#FF007F` | 3,8 | Falla. Por eso el relleno peligro es `#D6006B` |
| `#FFFFFF` sobre `danger` / `danger-pressed` | 5,2 / 6,6 | AA |
| `border-strong` sobre `bg` / `surface` / `surface-2` | 4,2 / 3,9 / 3,5 | 3:1 para controles |
| `border` (`#2E3250`) sobre `bg` | 1,55 | Solo decorativo, nunca el único indicador |
| Equipos 1..4 sobre `surface` | 6,3 / 5,6 / 10,2 / 6,7 | AA |
| Equipos 1..4 sobre `surface-3` | 4,9 / 4,3 / 7,9 / 5,2 | Borde e icono (3:1) |

Regla: el estado nunca depende solo del color. Equipo = color + forma. Turno = halo + etiqueta «Turno». Conexión = icono wifi/wifi-off + texto para lectores. Hueco bloqueado = candado.

## 3. Tipografía

| Rol | Fuente | Peso | Tamaño / interlínea | Tracking |
|---|---|---|---|---|
| Año hero (carta grande revelada) | Unbounded | 800 | 56 / 1 | -0,02em |
| Año de carta (línea del tiempo) | Unbounded | 800 | 24 / 1 | -0,01em |
| Titular de pantalla (h1) | Unbounded | 800 | 32 / 1,1 | -0,02em |
| Subtítulo de sección (h2) | Unbounded | 700 | 22 / 1,2 | -0,01em |
| Contador (`6/10`), fichas | Unbounded | 700 | 18 / 1 | 0 |
| Canción (carta grande) | Outfit | 700 | 24 / 1,2 | 0 |
| Etiqueta del hueco («Entre 1978 y 1991») | Outfit | 600 | 20 / 1,2 | 0 |
| Cuerpo | Outfit | 400 | 16 / 1,5 | 0 |
| Artista (carta grande) | Outfit | 500 | 16 / 1,3 | 0 |
| Botón | Outfit | 700 | 16 (grande 18) / 1 | +0,02em |
| Nombre de equipo | Outfit | 700 | 14 / 1,2 | 0 |
| Título y artista en carta pequeña | Outfit | 600 / 500 | 12 / 1,2 | 0 |
| Texto de ayuda | Outfit | 400 | 14 / 1,45 | 0 |
| Etiqueta (overline) | Outfit | 600 | 12 / 1,2 | +0,12em, mayúsculas |

Mínimo 12 px. Cuerpo 16 px. Unbounded no tiene cifras tabulares: fijad un `min-width` en el contador para que no baile al cambiar de dígito.

## 4. Movimiento

| Token | Valor | Uso |
|---|---|---|
| `--motion-press` | 90 ms | Pulsación de botón (`translateY(2px) scale(.98)`) |
| `--motion-fast` | 160 ms | Hover, color, borde, brillo |
| `--motion-base` | 240 ms | Hueco seleccionado, entrada de modal |
| `--motion-slow` | 360 ms | Barra de progreso, cambio de turno |
| `--motion-flip` | 700 ms | Volteo de la carta misteriosa |
| `--motion-celebrate` | 1200 ms | Entrada de la pantalla de victoria |
| `--ease-out` | `cubic-bezier(.22,1,.36,1)` | Entradas y pulsaciones |
| `--ease-in-out` | `cubic-bezier(.65,0,.35,1)` | Volteo, pulso, bucles |
| `--ease-spring` | `cubic-bezier(.34,1.56,.64,1)` | Anclar carta, rebote de ficha |

Anima solo `transform`, `opacity`, `box-shadow` y `filter`. Máximo 2 elementos con animación continua por pantalla (la carta misteriosa y la línea de turno). Con `prefers-reduced-motion: reduce` los tokens de duración valen 0 ms y las animaciones continuas se paran; Embla usa `duration` bajo y el volteo es un cambio de cara inmediato.

## 5. Componentes y estados

| Componente | Reposo | Hover | Pulsado | Foco | Deshabilitado / otros |
|---|---|---|---|---|---|
| Botón primario | Degradado `#8A35D1`→`#7B2CBF`, texto blanco, `glow-primary`, radio 16, alto 48 (grande 56) | Degradado `#9A45E0`→`#8A35D1` | `#6A1FA8`, `shadow-btn-press`, `translateY(2px) scale(.98)` | Anillo cian 3 px, separación 3 px | Fondo `surface-2`, borde discontinuo `border`, texto `fg-disabled`, sin brillo |
| Botón secundario | `surface-2`, borde 2 px `border-strong`, texto `fg` | Borde y texto `accent` | Igual que primario | Igual | Igual |
| Botón acento | `accent`, texto `#0D0E15`, `glow-accent` | `accent-pressed` solo al pulsar | `accent-pressed` | Igual | Igual |
| Botón peligro | `danger`, texto blanco, `glow-magenta` | `#E0107A` | `danger-pressed` | Igual | Igual |
| Botón fantasma | Sin fondo, texto `primary-light` | Fondo `rgba(183,124,255,.12)` | Igual | Igual | Texto `fg-disabled` |
| Botón de icono (◀ ▶) | 48×48, como secundario | Igual | Igual | Igual | Opacidad 1, icono `fg-disabled` |
| Tarjeta de pack | `surface`, borde 2 px `border`, radio 16, alto mín. 96 | Borde `border-strong` | `scale(.97)` | Anillo | Marcado: borde `accent`, fondo con degradado cian al 14 %, `glow-accent`, casilla rellena con check |
| Mystery Disc | `surface` con borde degradado violeta→magenta→cian de 2 px, vinilo girando 6 s, `?` Unbounded 800 | n/a | n/a | n/a | Pulso de brillo 2400 ms alterno |
| Carta de año | `surface-2`, borde 2 px del color de la década, vinilo de surcos del mismo color al fondo | n/a | n/a | n/a | Acierto reciente: `anchor` 520 ms |
| Hueco (slot) | Borde discontinuo 2 px `border-strong`, fondo `rgba(13,14,21,.85)`, icono más | n/a | n/a | n/a | Seleccionado: borde sólido `accent`, `glow-accent`, `scale(1.1)`. Bloqueado: borde `magenta`, candado |
| Ficha (púa) | Degradado `#FFD166`→`#FFB703`, borde `#C98700`, nota musical oscura, brillo ámbar | n/a | n/a | n/a | Gastada: contorno discontinuo `border-strong`, sin relleno |
| TeamPanel | `surface`, borde 2 px `border`, radio 16, padding 10 | n/a | n/a | n/a | Activo: borde y halo del color del equipo, etiqueta «Turno». Sin conexión: icono wifi-off y texto «Sin conexión» |
| Modal | Fondo `surface-2`, radio 24, borde 1 px `border-strong`, `shadow-lg`; velo `overlay` con `backdrop-filter: blur(6px)` | n/a | n/a | Foco atrapado, anillo cian | Entrada: `translateY(16px) scale(.96)` a `none`, 240 ms `ease-out` |
| Insignia | Píldora, texto 12 px 700 mayúsculas, borde 1 px, fondo del color al 14 % | n/a | n/a | n/a | Variantes: oro, magenta, cian |

## 6. Pantallas (resumen; detalle en `DISENO-VISUAL.md` §E)

| Pantalla | Resumen |
|---|---|
| Inicio | Isotipo 112 px con halo violeta, wordmark, eslogan, `Crear sala` (primario grande), `Unirse a una sala` (secundario grande), `Cómo se juega` (fantasma), rejilla synthwave cian al pie |
| Packs | Rejilla de 2 columnas, selección múltiple, icono lucide 28 px, nombre, nº de canciones |
| Lobby | Código en Unbounded 800 40 px con `glow-text-accent`, huecos de equipo con forma y color, botón `Empezar partida` |
| Cuenta atrás | 3-2-1 en Unbounded 800 160 px, ondas concéntricas cian |
| Juego | TeamPanel arriba, carta misteriosa y línea al centro, botones abajo |
| No es tu turno | Línea de solo lectura, tarjeta de turno con el color del equipo activo |
| Pausa | Velo `overlay`, icono, mensaje, cuenta atrás de salto de turno |
| Victoria | Trofeo, confeti, podio, estadísticas, `Revancha` |
| Partida terminada | Sin confeti, bandera `primary-light`, resumen de cabeza |

## 7. Lista de comprobación previa a entrega

- [ ] Sin emojis como iconos. Iconos Lucide, 24 px (16 px dentro de insignias y casillas), trazo 2.
- [ ] Todo objetivo táctil mide 48×48 o más, con 8 px de separación mínima.
- [ ] Contraste AA en cada texto. Los brillos son decoración, nunca llevan el significado.
- [ ] Foco visible en todo control. `prefers-reduced-motion` respetado.
- [ ] Sin scroll horizontal de página. Probado a 360, 390 y 430 px.
- [ ] Las cartas nunca muestran portada ni datos antes de `REVEAL`.
- [ ] Fuentes solo de `fonts.googleapis.com` y `fonts.gstatic.com`.

## Ajustes del director de arte (prevalecen)

1. **Modo oscuro único.** Las propuestas de la skill con modo claro se descartan. `color-scheme: dark`.
2. **Fuentes.** La skill sugirió Righteous/Poppins y Russo One/Chakra Petch. Se eligen Unbounded (años, logo, titulares) y Outfit (interfaz). Unbounded da cifras anchas y legibles de lejos, y Outfit se lee rápido a 12 px.
3. **Morado.** `#7B2CBF` solo sirve como relleno con texto blanco (7,1:1). Como texto o borde sobre oscuro falla (2,7:1), así que existe `primary-light` `#B77CFF`.
4. **Magenta.** `#FF007F` con texto blanco da 3,8:1. El relleno de peligro baja a `#D6006B` (5,2:1). El magenta puro queda para borde, brillo e icono.
5. **Fondo OLED de la skill (`#000`/`#0F0F23`).** Se mantiene el `#0D0E15` del cliente, que conserva el matiz violeta.
6. **Efecto CRT y scanlines** del estilo retro-futurista: descartados. Cansan en pantallas pequeñas y bajan el contraste. Solo queda la rejilla de perspectiva del inicio.
7. **Pixel art y Press Start 2P:** descartados. Los acentos del español salen mal y no llegan a 12 px legibles.
8. **Patrón de landing de la skill** (hero, testimonios): no aplica. La app es un juego, no una web de captación.
9. **Radio y sombras clay** del diseño anterior: eliminados. Sombras ahora son oscuras más brillo de color (`--glow-*`).
10. **Equipos.** Se mantienen cuatro colores y cuatro formas, y los nombres `Rojo, Azul, Verde, Morado` de `es.identity.colors`. Los valores suben de saturación para leerse sobre oscuro. El rojo es `#FF6B4A` (más naranja) para no confundirse con el magenta de los retos.
11. **Carta revelada sin portada.** Vinilo de surcos con el color de la década (`--decade-XX`), no imagen.
12. **Iconos PWA.** `theme_color` pasa a `#0D0E15` y `background_color` a `#0D0E15` en `vite.config.ts` (lo cambia el implementador).
