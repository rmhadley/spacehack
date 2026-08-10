"""Readability regressions for the terminal presentation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import engine, hud, message_log, ui


class _FakeTileset:
    """Minimal tileset stand-in for font-loader fallback tests."""

    tile_width = engine.TILE_WIDTH
    tile_height = engine.TILE_HEIGHT

    def __setitem__(self, codepoint, tile):
        pass


class _FakeTcodTileset:
    """Loader namespace used to exercise the fallback chain."""

    CHARMAP_TCOD = object()

    def __init__(self, failures: int):
        self.failures = failures
        self.calls: list[str] = []

    def load_truetype_font(self, path, *, tile_width, tile_height):
        self.calls.append(path)
        if len(self.calls) <= self.failures:
            raise RuntimeError("simulated font failure")
        return _FakeTileset()

    def load_tilesheet(self, *args, **kwargs):
        self.calls.append("tilesheet")
        return _FakeTileset()


class _FakePath:
    def __init__(self, name: str, exists: bool = True):
        self.name = name
        self.exists = exists

    def is_file(self):
        return self.exists

    def __str__(self):
        return self.name



def _relative_luminance(color: tuple[int, int, int]) -> float:
    """Return approximate sRGB relative luminance for contrast checks."""
    channels = []
    for value in color:
        normalized = value / 255
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_against_black(color: tuple[int, int, int]) -> float:
    return (_relative_luminance(color) + 0.05) / 0.05


def test_bundled_font_is_explicit_and_has_more_raster_breathing_room():
    """The chosen DejaVu font is bundled and rendered at a comfortable size."""
    data_dir = Path(__file__).resolve().parents[1] / "src" / "spacehack" / "data"
    assert engine.TRUETYPE_FONT_FILENAME == "DejaVuSansMono.ttf"
    assert (data_dir / engine.TRUETYPE_FONT_FILENAME).is_file()
    assert (data_dir / engine.LEGACY_TRUETYPE_FONT_FILENAME).is_file()
    assert engine.TILE_WIDTH == engine.TILE_HEIGHT
    assert engine.TILE_WIDTH >= 18


def test_font_loader_prefers_dejavu_then_hack_then_tilesheet(monkeypatch):
    """Broken preferred fonts fall through without making startup brittle."""
    fake_tcod = _FakeTcodTileset(failures=0)
    monkeypatch.setattr(engine.tcod, "tileset", fake_tcod)
    monkeypatch.setattr(
        engine,
        "_data_path",
        lambda name: _FakePath(name, exists=name != engine.TRUETYPE_FONT_FILENAME),
    )
    engine.load_tileset()
    assert fake_tcod.calls == [engine.LEGACY_TRUETYPE_FONT_FILENAME]

    fake_tcod = _FakeTcodTileset(failures=2)
    monkeypatch.setattr(engine.tcod, "tileset", fake_tcod)
    monkeypatch.setattr(engine, "_data_path", lambda name: _FakePath(name))
    engine.load_tileset()
    assert fake_tcod.calls == [
        engine.TRUETYPE_FONT_FILENAME,
        engine.LEGACY_TRUETYPE_FONT_FILENAME,
        "tilesheet",
    ]


def test_bitmap_glyphs_center_when_raster_is_larger():
    """Procedural texture glyphs stay aligned with a larger TTF tile."""
    tile = engine._render_bitmap_tile(18, 18, ("#",))
    assert tile[8, 8, 3] == 255
    assert tile[0, 0, 3] == 0
    offset_tile = engine._render_bitmap_tile(18, 18, ("", "##"))
    assert offset_tile[9, 8, 3] == 255
    assert not engine._render_bitmap_tile(18, 18, ()).any()


def test_primary_reading_palette_is_high_contrast_on_black():
    """Common text roles remain comfortably readable on the playfield."""
    for color in (
        ui.COLOR_OPTION,
        ui.COLOR_DESCRIPTION,
        ui.COLOR_INSTRUCTION,
        ui.COLOR_VALUE_DIM,
        message_log.COLOR_MESSAGE,
        message_log.COLOR_MESSAGE_DIM,
        hud.COLOR_LABEL,
        hud.COLOR_SHIP_LABEL,
    ):
        assert _contrast_against_black(color) >= 7.0, color


def test_blue_is_reserved_for_bright_accents():
    """Cyan accents are bright enough not to become dark-blue body text."""
    assert ui.COLOR_TITLE[2] >= 230
    assert ui.COLOR_TITLE[0] >= 140
    assert hud.COLOR_SHIP_NAME[2] >= 245
