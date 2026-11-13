# Acontecimientos para las pistas del año

`year_events.json` contiene **185 acontecimientos**, con dos por año y un tercero musical en cinco años, para los **90 años de 1937 a 2026**, ambos incluidos. El inicio del intervalo sale de las canciones más antiguas del pack Disney; el final también aparece en el pack Indie español. Se cubren todos los años intermedios, aunque no haya canciones de cada uno en los CSV actuales.

Los textos en español están preparados con asistencia de IA y vinculados a una fuente individual. Son un catálogo estático: no se llama a un modelo durante la partida. El servidor puede cargarlo en PostgreSQL, elegir un acontecimiento del año de la carta y conservar la elección durante el turno.

## Formato

Cada objeto tiene `id` estable, `year`, `category`, `text`, `source_url` y `occurred_on` (fecha ISO del acontecimiento). Las categorías son `sport`, `politics`, `music`, `conflict`, `science`, `culture` y `society`. Los textos no contienen el año en cifras ni la respuesta de una canción preparada a propósito como pista. La fecha y el enlace son metadatos de curación y no deben enviarse al equipo antes de revelar la carta.

## Criterios de selección

- Se escogen hechos con una fecha concreta, evitando pronósticos y sucesos que se extienden durante varios años sin un hito identificable.
- En películas se distingue la primera proyección o el estreno local del estreno general; en tratados se distingue firma de entrada en vigor. Dolly se fecha por su nacimiento, no por el anuncio posterior de su clonación.
- Se emplean fuentes primarias cuando se han localizado (ONU, UNICEF, NASA, National Archives, Intel, Motorola, Internet Society, Disney, Eurovisión, Unión Europea, Vaticano, BIE, COI y Academia de Hollywood). Los demás registros enlazan al artículo histórico específico de Wikipedia.
- Se consultaron los enlaces de los 185 registros y se contrastaron las fechas, incluida la diferencia entre formato europeo y estadounidense. Las páginas de algunos organismos pueden restringir rastreadores aunque el enlace público sea válido.
- La precisión editorial sigue necesitando mantenimiento: las fuentes externas pueden cambiar. Una modificación debe conservar el `id` de un acontecimiento existente; un hecho distinto debe recibir otro identificador.

## Corte temporal y comprobación de 2026

El corte es **13 de noviembre de 2026**. No se incluyen ganadores previstos ni acontecimientos futuros. Los dos registros del último año están respaldados por publicaciones posteriores al suceso:

- [Archivo del COI: ceremonia de apertura en Milán-Cortina, 6 de febrero](https://newsroom.olympics.com/record/3531).
- [Academia de Hollywood: ceremonia del 15 de marzo y premiados](https://www.oscars.org/oscars/ceremonies/2026). Se usa el título español «Una batalla tras otra» para la película ganadora.

Durante la revisión se descartaron dos opciones ambiguas: la fecha exacta de entrega de la primera propuesta de la Web y la diferencia entre la orden de creación del Distrito Manhattan y su entrada en efecto. Se sustituyeron por la represión de Tiananmén y la primera reacción nuclear controlada en Chicago, respectivamente.

## Validación al ampliar el catálogo

Comprobar que cada año cubierto tiene dos o tres entradas, que no se duplican identificadores ni textos, que `occurred_on` pertenece a `year`, que el enlace respalda el hecho y que el texto no da el año numérico. Para nuevos años, añadir hechos ya ocurridos y fuentes fechadas. No generar ni habilitar automáticamente acontecimientos futuros.
