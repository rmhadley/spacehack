"""Readability regressions for the terminal presentation."""

from __future__ import annotations

import ast
import hashlib
import io
import sys
import tokenize
from pathlib import Path

import pygame
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import engine, hud, message_log, ui, world



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


def test_engine_import_does_not_eagerly_import_pygame():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import sys; import src.spacehack.engine; print('pygame' in sys.modules)"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_bitmap_tileset_is_native_and_is_the_only_font_configuration():
    """The game uses the bundled bitmap at its native dimensions."""
    data_dir = Path(__file__).resolve().parents[1] / "src" / "spacehack" / "data"
    assert engine.TILE_WIDTH == 16
    assert engine.TILE_HEIGHT == 16
    assert engine.TILE_WIDTH == engine.TILE_HEIGHT
    assert engine.TILE_WIDTH * engine.TILESHEET_COLUMNS == 512
    assert engine.TILE_HEIGHT * engine.TILESHEET_ROWS == 128
    assert (data_dir / engine.TILESHEET_FILENAME).is_file()
    assert not hasattr(engine, "TRUETYPE_FONT_FILENAME")
    assert not hasattr(engine, "LEGACY_TRUETYPE_FONT_FILENAME")


def test_project_charmap_matches_bundled_sheet_contract():
    assert len(engine.CP437_CHARMAP) == 160
    assert engine.CP437_CHARMAP[:3] == (32, 33, 34)
    assert engine.CP437_CHARMAP[96:104] == tuple(range(ord("A"), ord("I")))
    assert engine.CP437_CHARMAP[128:134] == tuple(range(ord("a"), ord("g")))
    assert engine.CP437_CHARMAP[90] == 0


def test_direct_bitmap_loader_preserves_native_dimensions_and_representative_glyphs():
    tileset = engine.load_tileset()

    assert isinstance(tileset, engine.PygameTileset)
    assert (tileset.tile_width, tileset.tile_height) == (16, 16)
    for codepoint in (ord("A"), ord("a"), ord("."), ord("@"), 0x2591, 0x00B7, 0x2663):
        assert tileset[codepoint].get_size() == (16, 16)
    assert tileset[0x2591].get_at((0, 0))[3] == 255
    assert tileset[0x00B7].get_bounding_rect().size == (4, 4)


def test_processed_glyph_raster_matches_the_phase_3_baseline_digest():
    tileset = engine.load_tileset()
    digest = hashlib.sha256()
    count = 0
    for codepoint in sorted(set(engine.CP437_CHARMAP)):
        if codepoint in (0, 32):
            continue
        digest.update(codepoint.to_bytes(4, "little"))
        digest.update(bytes(tileset[codepoint].get_view("0")))
        count += 1

    assert count == 140
    assert digest.hexdigest() == (
        "9211a90e2938fe9066050abb97e5e8658f81f346227ff0a79b498dcf0ce14cef"
    )


def test_bitmap_loader_rejects_wrong_dimensions(monkeypatch):
    class FakeSheet:
        def get_size(self):
            return (16, 16)

    fake_pygame = type(
        "FakePygame",
        (),
        {
            "image": type("Image", (), {"load": staticmethod(lambda _path: FakeSheet())}),
            "error": RuntimeError,
        },
    )
    monkeypatch.setattr(engine, "_pygame_module", lambda: fake_pygame)

    with pytest.raises(engine.EngineError, match="expected"):
        engine.load_tileset()


def test_bitmap_loader_converts_pygame_errors_to_engine_error(monkeypatch):
    class FakePygame:
        error = RuntimeError
        image = type(
            "Image",
            (),
            {"load": staticmethod(lambda _path: (_ for _ in ()).throw(RuntimeError("bad png")))},
        )

    monkeypatch.setattr(engine, "_pygame_module", lambda: FakePygame)

    with pytest.raises(engine.EngineError, match="bad png"):
        engine.load_tileset()


def test_bitmap_loader_raises_when_the_native_sheet_is_missing(monkeypatch):
    """Bitmap-only mode fails explicitly instead of silently changing fonts."""
    monkeypatch.setattr(engine, "_data_path", lambda _name: Path("missing.png"))
    try:
        engine.load_tileset()
    except engine.EngineError as exc:
        assert engine.TILESHEET_FILENAME in str(exc)
    else:
        raise AssertionError("missing bitmap should raise EngineError")


def test_text_glyph_widening_is_the_tightened_bitmap_baseline():
    """The stronger readability pass widens letters without changing cells."""
    assert engine._TEXT_GLYPH_EXTRA_COLUMNS == 3
    tile = pygame.Surface((16, 16), pygame.SRCALPHA, 32)
    tile.fill((0, 0, 0, 0))
    for y in range(16):
        for x in range(5, 11):
            tile.set_at((x, y), (255, 255, 255, 255))
    widened = engine._widen_glyph_tile(tile)
    assert widened.get_size() == tile.get_size()
    original_ink = sum(tile.get_at((x, y))[3] > 0 for y in range(16) for x in range(16))
    widened_ink = sum(widened.get_at((x, y))[3] > 0 for y in range(16) for x in range(16))
    assert widened_ink > original_ink
    xs = [x for y in range(16) for x in range(16) if widened.get_at((x, y))[3] > 0]
    assert (min(xs), max(xs)) == (3, 11)


def test_bitmap_glyphs_center_in_the_native_raster():
    """Procedural texture glyphs stay aligned in the native bitmap tile."""
    tile = engine._render_bitmap_tile(16, 16, ("#",))
    assert tile.get_at((7, 7))[3] == 255
    assert tile.get_at((0, 0))[3] == 0
    offset_tile = engine._render_bitmap_tile(16, 16, ("", "##"))
    assert offset_tile.get_at((7, 8))[3] == 255
    tall_tile = engine._render_bitmap_tile(16, 16, tuple("#" for _ in range(20)))
    assert tall_tile.get_size() == (16, 16)
    assert all(
        engine._render_bitmap_tile(16, 16, ()).get_at((x, y))[3] == 0
        for y in range(16) for x in range(16)
    )


def _runtime_string_tokens():
    """Yield source string tokens that can reach runtime output.

    Module/function docstrings are documentation rather than rendered
    game text, so they are excluded from the compatibility assertion.
    """
    source_root = Path(__file__).resolve().parents[1] / "src" / "spacehack"
    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        line_starts = [0]
        for line in text.splitlines(keepends=True):
            line_starts.append(line_starts[-1] + len(line))

        def _offset(position):
            return line_starts[position[0] - 1] + position[1]

        docstring_spans = []
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if not isinstance(body, list) or not body:
                continue
            first = body[0]
            value = getattr(first, "value", None)
            if not isinstance(first, ast.Expr) or not isinstance(value, ast.Constant):
                continue
            if not isinstance(value.value, str):
                continue
            docstring_spans.append((
                _offset((value.lineno, value.col_offset)),
                _offset((value.end_lineno, value.end_col_offset)),
            ))

        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type != tokenize.STRING:
                continue
            span = (_offset(token.start), _offset(token.end))
            if any(start <= span[0] and span[1] <= end for start, end in docstring_spans):
                continue
            yield path, token.string


def test_runtime_strings_avoid_missing_bitmap_codepoints():
    """Player-facing literals use characters the bitmap renderer supports."""
    missing = set("Öε—–…×∞≈")
    escaped_missing = (
        r"\\u00d6", r"\\u03b5", r"\\u2014", r"\\u2013",
        r"\\u2026", r"\\u00d7", r"\\u221e", r"\\u2248",
    )
    offenders = [
        f"{path}:{literal}"
        for path, literal in _runtime_string_tokens()
        if any(char in literal for char in missing)
        or any(escape in literal.lower() for escape in escaped_missing)
    ]
    assert offenders == []


def test_ascii_replacements_cover_known_runtime_glyphs():
    """Representative map/UI replacements remain explicit and readable."""
    assert world.TABLE.char == "~"
    assert ui.fit_text("A long mission title", 10) == "A long mi..."
    assert hud._UNLIMITED_AMMO_LABEL == "INF"


def test_exploration_hud_advertises_console_log_in_space_and_ground_modes():
    from src.spacehack.framebuffer import FrameBuffer

    from src.spacehack.ship import OwnedShip

    ctx = type("HudContext", (), {
        "character_info": {
            "species_name": "Human", "class_name": "Merchant",
        },
        "stats": hud.HudStats(10, 10, 100),
        "player_owned_ship": OwnedShip(ship_id="starter"),
        "player_xp": 0,
        "player_level": 1,
        "player_skill_points": 0,
        "ground_stats": None,
        "ground_hp": 10,
        "ground_max_hp": 10,
        "time_day": 1,
        "time_month": 1,
        "time_year": 2200,
    })()

    for mode in ("space", "dungeon"):
        console = FrameBuffer(100, 54)
        hud.render_hud(
            console,
            ctx,
            screen_width=100,
            hud_view_height=54,
            mode=mode,
        )
        assert any(
            command.char == "\\"
            and "Console" in "".join(
                cell.char
                for cell in sorted(
                    (
                        item for item in console.commands
                        if item.y == command.y and item.x >= 80
                    ),
                    key=lambda item: item.x,
                )
            )
            for command in console.commands
            if command.char == "\\"
        )


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
