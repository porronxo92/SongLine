# Banco de canciones

`songs.csv` es el catálogo curado (180 canciones, 1970 a 2025). El **año del CSV es la fuente de verdad**: lo cura una persona. Spotify solo aporta el `track_id` y el ISRC; su `release_date` es la del álbum que contiene la pista (remaster, recopilatorio) y no sirve como año original.

## Formato

UTF-8, separado por comas, cabecera exacta:

`ID,Cancion,Artista,Anio,Genero,Origen,AliasTitulo,AliasArtista,Nota,SpotifyTrackId,ISRC,Estado`

- `ID`: S001 a S180. `Genero`: pop, rock, dance, latin, indie, hiphop, rnb. `Origen`: es o intl.
- `AliasTitulo` y `AliasArtista`: variantes separadas por `|` (por ejemplo «YMCA», «Fito»).
- `SpotifyTrackId` e `ISRC` los rellena el script.
- `Estado`: `verified` (año seguro) o `disputed` (hay duda, explicada en `Nota`).

## Regla del año

Año de la primera publicación comercial de **esa grabación**: single o álbum, lo que salga antes.

- Single de finales de año con álbum al siguiente: año del single. Si el álbum salió antes, el del álbum.
- Las reentradas en listas no cuentan («Running Up That Hill» es 1985).
- Las versiones usan el año de la versión (Fugees, «Killing Me Softly», 1996).
- Remasters y recopilatorios no cuentan.

## Uso del script

```
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
set SPOTIFY_CLIENT_ID=...
set SPOTIFY_CLIENT_SECRET=...
python import_spotify.py songs.csv --market ES --out review/ [--only-pending] [--musicbrainz] [--write-csv]
```

- Busca con `limit=10`, puntúa candidatos (`0.45·título + 0.35·artista + 0.20·año`, con penalizaciones por remaster, directo, versión o recopilatorio) y respeta `Retry-After` en los 429.
- `--musicbrainz` comprueba el año por ISRC (1 petición por segundo).
- `--only-pending` salta las filas que ya tienen `SpotifyTrackId`.
- `--write-csv` reescribe `SpotifyTrackId`, `ISRC` y `Estado`. **Nunca toca `Anio`.**
- Una fila marcada `disputed` por la persona curadora nunca se promociona a `verified`.

Salida en `review/`:

- `dudosas.csv`: motivos y los 3 mejores candidatos con enlace `open.spotify.com` para escucharlos.
- `desajustes_anio.csv`: filas donde Spotify o MusicBrainz discrepan del año del CSV.
- `matches.csv`: la coincidencia elegida para cada fila.

## Tests

```
.venv\Scripts\python -m pytest tests
```

Incluyen la validación de `songs.csv` (cabecera, 180 filas, distribución por década, máximo 3 por artista) y el importador con respuestas simuladas.
