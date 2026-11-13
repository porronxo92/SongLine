# Pista histórica del año

El catálogo musical versionado abarca de **1937** (Blancanieves, pack Disney) a **2026** (pack indie español). `catalog/year_events.json` contiene **185 acontecimientos**, de dos a tres por cada año de ese intervalo, incluidos los años sin canciones actuales.

## Datos y mantenimiento

La IA ayuda a redactar el catálogo inicial; el juego no llama a un modelo durante la partida. Cada registro conserva un identificador estable, año, categoría, texto de la pista, fecha del acontecimiento y URL de referencia. Las categorías son deporte, política, música, conflictos, ciencia, cultura y sociedad. El texto no incluye el año explícito. Para 2026 solo se incluyen hechos ocurridos, nunca resultados previstos.

La migración `0004` crea y siembra `year_events` en PostgreSQL. En Render se ejecuta al arrancar la nueva imagen, igual que las migraciones anteriores. No necesita una conexión nueva ni claves de IA y no modifica las cuentas, canciones ni partidas guardadas. En desarrollo con catálogo CSV se usa el mismo JSON. Las cartas de partidas guardadas antes de esta funcionalidad no contienen los nuevos acontecimientos: la pista estará disponible al crear otra partida o una revancha.

La tabla permite desactivar una pista conservando su referencia. Las consultas de producción usan los registros habilitados de PostgreSQL. Añadir o corregir acontecimientos requiere revisar fecha, fuente y redacción: no se publica automáticamente lo que genere un modelo. Si se amplía el catálogo musical fuera del intervalo cubierto, hay que añadir acontecimientos para esos años; mientras falten, esa pista no está disponible y no cobra fichas.

## Uso en la partida

- Solo el equipo activo puede solicitarla, durante la colocación y antes de confirmar el hueco.
- Gasta **dos fichas siempre, sin devolución**, aunque coloque correctamente la carta. Esta decisión del usuario es distinta de las pistas recuperables de título y artista.
- El premio adicional sigue siendo de una ficha como máximo y exige hueco, título y artista correctos.
- Se puede pedir una vez por carta. La selección entre los acontecimientos del año depende de la instancia aleatoria de la carta: cambia entre partidas y se conserva al reconectar, repetir solicitudes o restaurar el servidor.
- Comparte el límite existente de 60 segundos desde la primera pista. Pedir otra no reinicia el plazo.
- Los demás equipos solo ven que se ha usado una pista del año. El destinatario recibe únicamente texto y categoría: no recibe año, fecha, identificador ni URL que puedan revelar la respuesta.

El resultado muestra por separado el gasto definitivo de las dos fichas de la pista del año y las devoluciones de las pistas de título/artista. Estas últimas siguen costando una ficha cada una y se recuperan por acertar su dato, aunque falle el hueco.

## Verificación

Los tests comprueban cobertura y validación del catálogo, fondos insuficientes, fases y permisos, estabilidad de la selección, protección de metadatos, saldo neto, devoluciones repetidas, reconexión y restauración. La migración debe probarse también contra una base PostgreSQL desechable antes de desplegar.
