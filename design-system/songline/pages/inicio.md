# Inicio · Escaparate de SongLine

Esta página concreta la dirección visual del inicio y prevalece sobre los
patrones de pantalla compacta del MASTER solo para `/`. Las pantallas del juego
mantienen su diseño y ancho actuales bajo `/app`. `/jugar` es un alias de `/app`.

## Estructura

Adaptación de la composición de referencia Tándem: cabecera contenida, titular
central, interacción visual protagonista, tres tarjetas y dos paneles amplios,
banda informativa y pie compacto. No se importan su identidad, tipografías,
formularios, sobre, newsletter ni mensajes de una agencia de IA.

- Cabecera: marca original, anclas a juego/experiencia y cuenta.
- Hero: titular Unbounded seguido del único botón «Jugar», que abre `/app`;
  después, la demo de una carta. Crear, unirse y recuperar sala están en el
  inicio compacto de la aplicación, con la identidad visual anterior.
- Demo independiente sin audio: Wannabe (1996) se sitúa respecto a Africa (1982)
  y Believe (1998). Datos presentes en el catálogo. El año permanece oculto hasta
  elegir hueco. Se explica el resultado y se puede repetir con teclado o toque.
- Tres tarjetas: escuchar, colocar, objetar/pedir pistas. Dos paneles: juego
  presencial y colección de packs.
- Banda Free: 2 equipos, Mix variado, hasta 5 cartas incluida la inicial. Un
  enlace a planes; compras adicionales en preparación.
- Pie: marca, copyright y un único acceso a las reglas completas.

## Identidad y comportamiento

Se conservan el fondo Midnight Vinyl, morado eléctrico, cian, magenta, ámbar,
Unbounded, Outfit y los activos SVG de SongLine. El ancho del escaparate se
amplía para aprovechar escritorio; el resto de la aplicación no cambia.

Estilos aislados con prefijo `sl-` en `apps/web/src/styles/landing.css`.
Animaciones limitadas a la interacción y a entradas breves; todo el contenido
está visible por defecto. `prefers-reduced-motion` permite probar la demo sin
animaciones. Sin reproducción automática, captura de emails ni formularios de
éxito simulado. Objetivos táctiles de al menos 44 px, controles principales de 48 px y foco visible.

## Fotografía

`/images/songline-game-night.webp` (1536×1024) y versión 768×512: imagen generada
para SongLine de cuatro amigos con móviles y altavoz. Es una ilustración de uso,
no una fotografía de clientes ni un testimonio. Se preserva el original en
`/workspace/generated_images`; los WebP son copias optimizadas para la web.

Se evita incrustar una interfaz inventada en los teléfonos. Las ilustraciones
del resto de paneles muestran componentes del lenguaje visual del juego.
