"""Readability regressions for the terminal presentation."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import engine, help as game_help, hud, message_log, ui


class _FakeTileset:
    """Minimal tileset stand-in for font-loader fallback tests."""

    tile_width = engine.TILE_WIDTH
    tile_height = engine.TILE_HEIGHT

    def __init__(self):
        self.tiles = {}

    def __getitem__(self, codepoint):
        return self.tiles.get(
            codepoint,
            np.zeros((self.tile_height, self.tile_width, 4), dtype=np.uint8),
        )

    def __setitem__(self, codepoint, tile):
        self.tiles[codepoint] = tile


class _FakeTcodTileset:
    """Loader namespace used to exercise the fallback chain."""

    CHARMAP_TCOD = object()

    def __init__(self, failures: int, tilesheet_failures: int = 0):
        self.failures = failures
        self.tilesheet_failures = tilesheet_failures
        self.calls: list[str] = []

    def load_truetype_font(self, path, *, tile_width, tile_height):
        self.calls.append(path)
        if len(self.calls) <= self.failures:
            raise RuntimeError("simulated font failure")
        return _FakeTileset()

    def load_tilesheet(self, *args, **kwargs):
        self.calls.append("tilesheet")
        if self.tilesheet_failures:
            self.tilesheet_failures -= 1
            raise RuntimeError("simulated tilesheet failure")
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


def test_bitmap_tileset_is_native_and_ttf_fallbacks_are_bundled():
    """The bitmap is native-sized and both TTF fallbacks remain bundled."""
    data_dir = Path(__file__).resolve().parents[1] / "src" / "spacehack" / "data"
    assert engine.TRUETYPE_FONT_FILENAME == "DejaVuSansMono.ttf"
    assert (data_dir / engine.TRUETYPE_FONT_FILENAME).is_file()
    assert (data_dir / engine.LEGACY_TRUETYPE_FONT_FILENAME).is_file()
    assert engine.TILE_WIDTH == 16
    assert engine.TILE_HEIGHT == 16
    assert engine.TILE_WIDTH == engine.TILE_HEIGHT
    assert engine.TILE_WIDTH * engine.TILESHEET_COLUMNS == 512
    assert engine.TILE_HEIGHT * engine.TILESHEET_ROWS == 128


def test_font_loader_prefers_tilesheet_then_dejavu_then_hack(monkeypatch):
    """The crisp bitmap path wins, with both TTF fallbacks preserved."""
    fake_tcod = _FakeTcodTileset(failures=0)
    monkeypatch.setattr(engine.tcod, "tileset", fake_tcod)
    monkeypatch.setattr(engine, "_data_path", lambda name: _FakePath(name))
    engine.load_tileset()
    assert fake_tcod.calls == ["tilesheet"]

    fake_tcod = _FakeTcodTileset(failures=0)
    monkeypatch.setattr(engine.tcod, "tileset", fake_tcod)
    monkeypatch.setattr(
        engine,
        "_data_path",
        lambda name: _FakePath(name, exists=name != engine.TILESHEET_FILENAME),
    )
    engine.load_tileset()
    assert fake_tcod.calls == [engine.TRUETYPE_FONT_FILENAME]

    fake_tcod = _FakeTcodTileset(failures=2, tilesheet_failures=1)
    monkeypatch.setattr(engine.tcod, "tileset", fake_tcod)
    monkeypatch.setattr(engine, "_data_path", lambda name: _FakePath(name))
    engine.load_tileset()
    assert fake_tcod.calls == [
        "tilesheet",
        engine.TRUETYPE_FONT_FILENAME,
        engine.LEGACY_TRUETYPE_FONT_FILENAME,
    ]


def test_text_glyph_widening_preserves_grid_and_adds_ink():
    """The readability experiment widens letters without changing tiles."""
    tile = np.zeros((16, 16, 4), dtype=np.uint8)
    tile[:, 5:11, 3] = 255
    widened = engine._widen_glyph_tile(tile)
    assert widened.shape == tile.shape
    assert np.count_nonzero(widened[..., 3]) > np.count_nonzero(tile[..., 3])
    ys, xs = np.where(widened[..., 3] > 0)
    assert (int(xs.min()), int(xs.max())) == (4, 11)


def test_bitmap_glyphs_center_in_the_native_raster():
    """Procedural texture glyphs stay aligned in the native bitmap tile."""
    tile = engine._render_bitmap_tile(16, 16, ("#",))
    assert tile[7, 7, 3] == 255
    assert tile[0, 0, 3] == 0
    offset_tile = engine._render_bitmap_tile(16, 16, ("", "##"))
    assert offset_tile[8, 7, 3] == 255
    tall_tile = engine._render_bitmap_tile(16, 16, tuple("#" for _ in range(20)))
    assert tall_tile.shape == (16, 16, 4)
    assert not engine._render_bitmap_tile(16, 16, ()).any()


def test_help_selector_uses_a_renderable_cp437_marker():
    """The guide selection marker must be present in the bitmap font."""
    assert game_help.GUIDE_SELECTED_MARKER == ">"
    assert ord(game_help.GUIDE_SELECTED_MARKER) < 0x100

    tileset = engine.load_tileset()
    assert np.asarray(tileset[ord(game_help.GUIDE_SELECTED_MARKER)])[..., 3].any()


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
        hud.COLOR_HELP_DESC,
        hud.COLOR_POWER,
        hud.COLOR_COMBAT_WEAPON_DIM,
        hud.COLOR_COMBAT_ACTION,
    ):
        assert _contrast_against_black(color) >= 10.0, color

    assert _contrast_against_black(ui.COLOR_DIVIDER) >= 8.0
    assert _contrast_against_black(message_log.COLOR_MESSAGE_DIM) >= 10.0


def test_blue_is_reserved_for_bright_accents():
    """Cyan accents are bright enough not to become dark-blue body text."""
    assert ui.COLOR_TITLE[2] >= 230
    assert ui.COLOR_TITLE[0] >= 140
    assert hud.COLOR_SHIP_NAME[2] >= 245
