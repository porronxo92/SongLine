import pytest

from app.game.validate_guess import match_artist, match_title, normalize, validate_guess

# (canonical title, canonical artist, guess title, guess artist, title_ok, artist_ok) - DISENO 8.3
CASES = [
    ("Despacito", "Luis Fonsi, Daddy Yankee", "despasito", "daddy yanki", True, True),
    ("Bohemian Rhapsody", "Queen", "bohemian rapsody", "queen", True, True),
    ("Mediterráneo", "Joan Manuel Serrat", "mediterraneo", "serrat", True, True),
    ("La Bamba", "Los Lobos", "bamba", "lobos", True, True),
    ("Don't Stop Me Now", "Queen", "dont stop me now", "queen", True, True),
    ("Billie Jean", "Michael Jackson", "billy jean", "michael jakson", True, True),
    ("Get Lucky", "Daft Punk feat. Pharrell Williams", "get lucky", "pharrell", True, True),
    ("Hijo de la Luna", "Mecano", "hijo de luna", "mecano", True, True),
    ("Hijo de la Luna", "Mecano", "hijos del sol", "mecano", False, True),
    ("Entre dos aguas", "Paco de Lucía", "entre dos tierras", "paco de lucia", False, True),
    ("Like a Prayer", "Madonna", "like a virgin", "madonna", False, True),
    ("Insurrección", "El Último de la Fila", "insureccion", "el ultimo de la fila", True, True),
    ("Rolling in the Deep", "Adele", "rolling deep", "adele", True, True),
    ("Y.M.C.A.", "Village People", "ymca", "village people", True, True),
    ("Mi gran noche", "Raphael", "raphael", "mi gran noche", False, False),
    ("Bad Romance", "Lady Gaga", "", "", False, False),
    ("Sweet Child O' Mine", "Guns N' Roses", "sweet child of mine", "guns and roses", True, True),
    ("Wonderwall", "Oasis", "wonderwal", "oasis", True, True),
]


@pytest.mark.parametrize("title,artist,g_title,g_artist,t_ok,a_ok", CASES)
def test_cases(title: str, artist: str, g_title: str, g_artist: str, t_ok: bool, a_ok: bool) -> None:
    assert match_title(g_title, title) is t_ok
    assert match_artist(g_artist, artist) is a_ok
    r = validate_guess(g_title, g_artist, card_title=title, card_artist=artist)
    assert (r.title_ok, r.artist_ok) == (t_ok, a_ok)


def test_aliases() -> None:
    assert match_title("un ano mas", "Un año más") is True
    assert match_title("one more year", "Un año más", ["One More Year"]) is True
    assert match_artist("freddie", "Queen", ["Freddie Mercury"]) is True


def test_normalize() -> None:
    assert normalize("Bohemian Rhapsody (Remastered 2011)") == "bohemian rhapsody"
    assert normalize("Song - 2011 Remaster") == "song"
    assert normalize("The Rolling Stones") == "rolling stones"
    assert normalize("Y.M.C.A.") == "ymca"
