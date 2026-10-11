"""seed_songs.py: source discovery and row parsing (no database)."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_songs.py"
MULTI = Path(__file__).resolve().parents[1] / "fixtures" / "multipack"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_songs", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_sources_are_songs_csv_plus_every_pack_file(tmp_path: Path) -> None:
    seed = load_script()
    (tmp_path / "songs.csv").write_text("x", encoding="utf-8")
    assert seed.default_sources(tmp_path) == [tmp_path / "songs.csv"]  # no packs dir: does not fail
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "b.csv").write_text("x", encoding="utf-8")
    (tmp_path / "packs" / "a.csv").write_text("x", encoding="utf-8")
    names = [p.name for p in seed.default_sources(tmp_path)]
    assert names == ["songs.csv", "a.csv", "b.csv"]


def test_pack_of_and_rows_carry_the_pack() -> None:
    seed = load_script()
    assert seed.pack_of(Path("x/songs.csv")) == "mix"
    assert seed.pack_of(Path("x/packs/disney.csv")) == "disney"
    rows = seed.read_rows(MULTI / "packs" / "kids-test.csv", "kids-test")
    assert {r["pack"] for r in rows} == {"kids-test"} and rows[0]["year"] == 1937
    assert rows[0]["track_id"] == "trK1" and rows[0]["isrc"] is None  # empty -> NULL so COALESCE keeps the DB value


def test_pack_defs_and_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    seed = load_script()
    defs = seed.read_pack_defs(MULTI / "packs.json")
    assert [d["slug"] for d in defs] == ["kids-test", "mix", "rock-test", "empty-test"]
    assert seed.read_pack_defs(MULTI / "missing.json") == []
    asyncio.run(
        seed.main(
            [MULTI / "songs.csv", MULTI / "packs" / "kids-test.csv"], dry_run=True, packs_json=MULTI / "packs.json"
        )
    )
    out = capsys.readouterr().out
    assert "mix: 4 canciones" in out and "kids-test: 3 canciones" in out and "--dry-run" in out
