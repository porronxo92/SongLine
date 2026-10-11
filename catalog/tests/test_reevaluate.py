"""Tests de la reevaluacion offline (sin red ni BD)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import reevaluate_offline as ro  # noqa: E402


def match(**over):
    base = {"ID": "X001", "Cancion": "Libre", "Artista": "Nino Bravo", "Anio": "1972", "SpotifyTrackId": "T1",
            "ISRC": "I1", "Album": "Libre", "AlbumFecha": "1976-01-01", "Confianza": "0.80", "Flags": "year_mismatch",
            "MbPrimeraFecha": "", "EstadoCurado": "verified", "EstadoNuevo": "disputed", "Motivo": "confianza 0.80 < 0.9"}
    base.update(over)
    return base


def test_ignore_year_rescata_titulo_y_artista_perfectos_con_otro_anio_de_album():
    assert ro.rescue_ignore_year(match())
    assert ro.rescue_ignore_year(match(AlbumFecha="1973-01-01", Confianza="0.90"))  # 1 anio de diferencia


def test_ignore_year_no_rescata_directos_versiones_remasters_recopilatorios_ni_dudas_del_curador():
    for flags in ("year_mismatch,live", "year_mismatch,version", "remaster,year_mismatch", "compilation,year_mismatch"):
        assert not ro.rescue_ignore_year(match(Flags=flags))
    assert not ro.rescue_ignore_year(match(EstadoCurado="disputed"))
    assert not ro.rescue_ignore_year(match(Motivo="titulo o artista no coinciden"))
    assert not ro.rescue_ignore_year(match(Confianza="0.50"))  # titulo/artista flojos: no es un caso de solo anio
    assert not ro.rescue_ignore_year(match(EstadoNuevo="verified"))  # ya estaba habilitada


PACK = {"ID": "D1", "Cancion": "Give a Little Whistle", "Artista": "Cliff Edwards", "AliasTitulo": "",
        "AliasArtista": "Pinocchio", "Nota": "Pinocchio (1940)"}


def dmatch(**over):
    return match(ID="D1", Cancion="Give a Little Whistle", SpotifyTrackId="T9", Album="Greatest Hits",
                 Flags="year_mismatch", **over)


def test_soundtrack_prefiere_el_candidato_cuyo_album_menciona_la_pelicula():
    doubt = {"ID": "D1", "C1_Id": "T9", "C1_Nombre": "Give a Little Whistle", "C1_Album": "Greatest Hits", "C1_Flags": "",
             "C2_Id": "T2", "C2_Nombre": "Give a Little Whistle", "C2_Album": "Pinocchio (Original Soundtrack)", "C2_Flags": "year_mismatch"}
    assert ro.soundtrack_pick(dmatch(), doubt, PACK) == ("T2", "Pinocchio (Original Soundtrack)", False)


def test_soundtrack_descarta_directos_y_albumes_sin_pelicula():
    live = {"ID": "D1", "C1_Id": "T3", "C1_Nombre": "Give a Little Whistle", "C1_Album": "Pinocchio Live", "C1_Flags": "live"}
    assert ro.soundtrack_pick(dmatch(), live, PACK) is None
    sin = {"ID": "D1", "C1_Id": "T4", "C1_Nombre": "Give a Little Whistle", "C1_Album": "Otro disco", "C1_Flags": ""}
    assert ro.soundtrack_pick(dmatch(), sin, PACK) is None
    assert ro.soundtrack_pick(dmatch(EstadoCurado="disputed"), None, PACK) is None
