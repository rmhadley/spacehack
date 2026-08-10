"""libtcod (python-tcod) setup helpers for spacehack.

Everything in this module is pure setup: load the tileset, open a
window context, create an offscreen console, decide whether an event
should quit the game. Keeping it isolated means the rest of the game
can import plain data structures without dragging SDL/SDL3 in by
accident.
"""
from __future__ import annotations

import random as _random
import os as _os
import sys
from pathlib import Path

import numpy as np
import tcod.console
import tcod.context
import tcod.event
import tcod.tileset

# ---------------------------------------------------------------------------
# Public configuration. Centralising the "magic numbers" here keeps the rest
# of the game free of them and makes it obvious where to tweak screen size /
# font when those decisions come up.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Seeded random number generator for reproducible game sessions.
# Seed is set at game start (see __main__.py). All combat rolls and
# other game-logic randomness uses this shared instance so replays
# with the same seed produce identical outcomes. Map generation
# (starfield, terrain) intentionally uses the global random module
# so maps vary across runs even with the same seed.
# ---------------------------------------------------------------------------

RNG: _random.Random = _random.Random()

# The initial seed value used for deterministic per-run operations
# (e.g. mechanic inventory generation, planet loot tables). Saved
# when :func:`seed_rng` is called so downstream helpers can create
# isolated :class:`random.Random` instances seeded from a hash of
# ``INIT_SEED + planet_id + refresh_count`` without mutating the
# main RNG or depending on its ephemeral state.
INIT_SEED: int = 0


def seed_rng(seed: int) -> None:
    """Re-seed the shared :data:`RNG` with ``seed``.

    Call this once at game start. The player may supply a seed in
    a future iteration; for now we derive one from ``os.urandom()``
    or the caller can pass their own integer.
    """
    global RNG, INIT_SEED
    RNG = _random.Random(seed)
    INIT_SEED = seed


# Screen dimensions in character cells. With the 14x18 font raster this
# gives a 1400 x 1080 logical-pixel window while preserving the existing
# character-cell layout.
SCREEN_WIDTH: int = 100
SCREEN_HEIGHT: int = 60

# Screen layout, used by world.py / hud.py / message_log.py / __main__.py:
#    [ MAP region (SCREEN_WIDTH - HUD_WIDTH wide) ]  [ HUD (HUD_WIDTH wide) ]
#    [                                         ]  [                   ]
#    [                                MSG_LOG_HEIGHT rows of msg log  ]
#    [ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - ]
#    |                     message_log region                        |
#    +---------------------------------------------------------------+
HUD_WIDTH: int = 20
MSG_LOG_HEIGHT: int = 6

WINDOW_TITLE: str = "spacehack"

# Glyph size in pixels. The 14x18 cell keeps the readable vertical raster
# while matching DejaVu Sans Mono's narrower visual advance, reducing the
# excessive horizontal air visible with the previous 18x18 square cell.
TILE_WIDTH: int = 14
TILE_HEIGHT: int = 18

# Keep the dimensions easy to tune as a pair; the bundled font is loaded
# at these dimensions and the procedural glyph patches below adapt to them.

# Preferred bundled TrueType font. DejaVu Sans Mono has a generous
# x-height and clearer 0/O/1/l/I shapes than the previous Hack default.
TRUETYPE_FONT_FILENAME: str = "DejaVuSansMono.ttf"

# Secondary bundled TTF fallback retained for asset compatibility.
LEGACY_TRUETYPE_FONT_FILENAME: str = "Hack-Regular.ttf"

# Fallback CP437 tilesheet. Only used when the TrueType font above
# is missing or fails to load.
TILESHEET_FILENAME: str = "dejavu16x16_gs_tc.png"
TILESHEET_COLUMNS: int = 32
TILESHEET_ROWS: int = 8


class EngineError(RuntimeError):
    """Raised when the engine cannot finish initialising."""


# ---------------------------------------------------------------------------
# Tileset
# ---------------------------------------------------------------------------


def _data_path(filename: str) -> Path:
    """Resolve ``filename`` relative to the ``data/`` directory.

    When running inside a PyInstaller bundle, assets are extracted to
    ``sys._MEIPASS`` and laid out under ``spacehack/data/``.
    Otherwise resolves relative to this source file on disk.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "spacehack" / "data" / filename
    return Path(__file__).resolve().parent / "data" / filename


# --- Procedural box drawing -------------------------------------------------
#
# libtcod's TrueType loader centers each glyph's ink bounding box inside the
# tile (see get_glyph_shift in tileset_truetype.c).  Symmetric glyphs (─ │ ┼)
# center correctly, but asymmetric corners (┌ ┐ └ ┘) have their ink in one
# corner of the em box, so centering drifts the strokes off the shared
# centerline — this is a font-independent rasterization issue.
#
# The fix: draw the box-drawing glyphs ourselves, straight strokes anchored
# to a common center, so every corner lands exactly on the same rows/cols as
# the lines. Geometry mirrors the CP437 tilesheet while adapting its 4px
# single/double bands to the active tile dimensions; single corners meet at
# the shared center and double corners meet at the outer-bar blocks.

_BOX_TOP = 0b0001
_BOX_BOTTOM = 0b0010
_BOX_LEFT = 0b0100
_BOX_RIGHT = 0b1000

# Single-line (light) box drawing, U+2500-253C.  Used for city building
# walls (world.py WALL_*) and loadout dividers.
_BOX_SINGLE = {
    0x2500: _BOX_LEFT | _BOX_RIGHT,        # ─
    0x2502: _BOX_TOP | _BOX_BOTTOM,        # │
    0x250C: _BOX_BOTTOM | _BOX_RIGHT,      # ┌
    0x2510: _BOX_BOTTOM | _BOX_LEFT,       # ┐
    0x2514: _BOX_TOP | _BOX_RIGHT,         # └
    0x2518: _BOX_TOP | _BOX_LEFT,          # ┘
    0x251C: _BOX_TOP | _BOX_BOTTOM | _BOX_RIGHT,   # ├
    0x2524: _BOX_TOP | _BOX_BOTTOM | _BOX_LEFT,    # ┤
    0x252C: _BOX_LEFT | _BOX_RIGHT | _BOX_BOTTOM,  # ┬
    0x2534: _BOX_LEFT | _BOX_RIGHT | _BOX_TOP,     # ┴
    0x253C: _BOX_TOP | _BOX_BOTTOM | _BOX_LEFT | _BOX_RIGHT,  # ┼
}

# Double-line box drawing, U+2550-256C.  Used for UI modal frames
# (ui.py) and the combat banner.
_BOX_DOUBLE = {
    0x2550: _BOX_LEFT | _BOX_RIGHT,        # ═
    0x2551: _BOX_TOP | _BOX_BOTTOM,        # ║
    0x2554: _BOX_BOTTOM | _BOX_RIGHT,      # ╔
    0x2557: _BOX_BOTTOM | _BOX_LEFT,       # ╗
    0x255A: _BOX_TOP | _BOX_RIGHT,         # ╚
    0x255D: _BOX_TOP | _BOX_LEFT,          # ╝
    0x2560: _BOX_TOP | _BOX_BOTTOM | _BOX_RIGHT,   # ╠
    0x2563: _BOX_TOP | _BOX_BOTTOM | _BOX_LEFT,    # ╣
    0x2566: _BOX_LEFT | _BOX_RIGHT | _BOX_BOTTOM,  # ╦
    0x2569: _BOX_LEFT | _BOX_RIGHT | _BOX_TOP,     # ╩
    0x256C: _BOX_TOP | _BOX_BOTTOM | _BOX_LEFT | _BOX_RIGHT,  # ╬
}


def _render_box_tile(
    tw: int, th: int, mask: int, double: bool
) -> np.ndarray:
    """Build one box-drawing glyph tile (RGBA) from its stroke mask.

    Horizontal strokes sit on the shared ``h_bands`` rows, vertical
    strokes on the shared ``v_bands`` columns; each half-stroke extends
    from the tile edge to the common center (single) or the opposite
    bar (double).  Because every glyph uses the same bands and center,
    corners connect with lines seamlessly.
    """
    tile = np.zeros((th, tw, 4), dtype=np.uint8)
    center_lo, center_hi = tw // 2 - 2, tw // 2 + 1
    if double:
        h_bands = [(th // 4 - 2, th // 4 + 1), (3 * th // 4 - 2, 3 * th // 4 + 1)]
        v_bands = [(tw // 4 - 2, tw // 4 + 1), (3 * tw // 4 - 2, 3 * tw // 4 + 1)]
    else:
        h_bands = [(center_lo, center_hi)]
        v_bands = [(center_lo, center_hi)]
    if double:
        # Double-line bands are disjoint (2-5 / 10-13), so a half-stroke
        # must reach the *opposite bar*, not the centre, or the corner
        # junction stays open.
        x0 = 0 if mask & _BOX_LEFT else v_bands[0][0]
        x1 = tw - 1 if mask & _BOX_RIGHT else v_bands[1][1]
        y0 = 0 if mask & _BOX_TOP else h_bands[0][0]
        y1 = th - 1 if mask & _BOX_BOTTOM else h_bands[1][1]
    else:
        x0 = 0 if mask & _BOX_LEFT else center_lo
        x1 = tw - 1 if mask & _BOX_RIGHT else center_hi
        y0 = 0 if mask & _BOX_TOP else center_lo
        y1 = th - 1 if mask & _BOX_BOTTOM else center_hi
    for r0, r1 in h_bands:
        tile[r0 : r1 + 1, x0 : x1 + 1, 3] = 255
    for c0, c1 in v_bands:
        tile[y0 : y1 + 1, c0 : c1 + 1, 3] = 255
    tile[..., :3] = 255  # white; the console tints via fg colour
    return tile


def _procedural_box_drawing(tileset: tcod.tileset.Tileset) -> tcod.tileset.Tileset:
    """Overwrite box-drawing codepoints in ``tileset`` with perfect strokes.

    Returns the (mutated) tileset.  Only the box-drawing block
    (U+2500-256C) is replaced; text glyphs are untouched.
    """
    tw, th = tileset.tile_width, tileset.tile_height
    for masks, double in ((_BOX_SINGLE, False), (_BOX_DOUBLE, True)):
        for cp, mask in masks.items():
            tileset[cp] = _render_box_tile(tw, th, mask, double)
    return tileset


# --- Procedural block elements / shades / suits ----------------------------
#
# Same root cause as the box drawing: TrueType fonts can render the game's
# texture glyphs with inconsistent scale or coverage. Procedural patches
# keep blocks and shades full-bleed, center the floor dot, and guarantee
# visible card suits for trees (♣), fountains (♦), and drinks (♥).
#
# The CP437 tilesheet's versions are classic full-bleed patterns (measured
# from dejavu16x16_gs_tc.png): light ░ = 1px dots at x%4==0 on even rows /
# x%4==2 on odd rows (25%); medium ▒ = (x+y)%2 checkerboard (50%); dark ▓ =
# inverse of light (75%); █ = solid.  Replicate that geometry procedurally
# so textures tile seamlessly and suits are visible again.

_BLOCK_AND_SHADES: dict[int, str] = {
    0x2588: "full",    # █ full block
    0x2591: "light",   # ░ light shade
    0x2592: "medium",  # ▒ medium shade
    0x2593: "dark",    # ▓ dark shade
}


def _render_shade_tile(tw: int, th: int, kind: str) -> np.ndarray:
    """Build one block/shade glyph tile (RGBA) matching the tilesheet look.

    ``kind`` is one of ``"full"`` / ``"light"`` / ``"medium"`` / ``"dark"``.
    All patterns are full-bleed so adjacent tiles read as one continuous
    surface.
    """
    tile = np.zeros((th, tw, 4), dtype=np.uint8)
    for y in range(th):
        for x in range(tw):
            if kind == "full":
                on = True
            elif kind == "light":
                on = x % 4 == (0 if y % 2 == 0 else 2)
            elif kind == "medium":
                on = (x + y) % 2 == 0
            else:  # dark
                on = x % 4 != (0 if y % 2 == 0 else 2)
            if on:
                tile[y, x] = (255, 255, 255, 255)
    return tile


def _render_bitmap_tile(
    tw: int, th: int, rows: tuple[str, ...]
) -> np.ndarray:
    """Build a centered glyph tile (RGBA) from '#'/'.' bitmap rows.

    The bundled bitmap patterns are authored at 16x16, while the TTF
    path may use a larger raster. Centering the pattern keeps procedural
    glyphs aligned with the font at either size.
    """
    tile = np.zeros((th, tw, 4), dtype=np.uint8)
    if not rows:
        return tile
    bitmap_width = max(map(len, rows), default=0)
    crop_left = max(0, (bitmap_width - tw) // 2)
    offset_x = max(0, (tw - bitmap_width) // 2)
    offset_y = max(0, (th - len(rows)) // 2)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            target_x = x - crop_left + offset_x
            target_y = y + offset_y
            if ch == "#" and 0 <= target_x < tw and target_y < th:
                tile[target_y, target_x] = (255, 255, 255, 255)
    return tile


# Floor middot — a clean 4x4 centred dot (reads as polished indoor floor).
_MIDDOT_BITMAP: tuple[str, ...] = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "......####......",
    "......####......",
    "......####......",
    "......####......",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
)

# Card suits — symmetric pixel art authored at the 16x16 reference size;
# _render_bitmap_tile centers them for the active raster dimensions.
_SUIT_BITMAPS: dict[int, tuple[str, ...]] = {
    0x2663: (  # ♣ club — city tree
        "................",
        "................",
        ".......###......",
        ".......###......",
        "......#####.....",
        "......#####.....",
        "....#########...",
        "....#########...",
        "....#########...",
        "....#########...",
        ".......###......",
        ".......###......",
        ".......###......",
        ".......###......",
        "................",
        "................",
    ),
    0x2666: (  # ♦ diamond — plaza fountain
        "................",
        "................",
        ".......##.......",
        "......####......",
        ".....######.....",
        "....########....",
        "...##########...",
        "..############..",
        ".##############.",
        "..############..",
        "...##########...",
        "....########....",
        ".....######.....",
        "......####......",
        ".......##.......",
        "................",
    ),
    0x2665: (  # ♥ heart — bar drink
        "................",
        "................",
        ".....###.###....",
        ".....#######....",
        "....#########...",
        "....#########...",
        "...###########..",
        "...###########..",
        "...###########..",
        "....#########...",
        "....#########...",
        ".....#######....",
        "......#####.....",
        ".......###......",
        "........#.......",
        "................",
    ),
}


def _procedural_texture_glyphs(
    tileset: tcod.tileset.Tileset,
) -> tcod.tileset.Tileset:
    """Overwrite texture codepoints in ``tileset`` with tilesheet-style pixels.

    Returns the (mutated) tileset.  Covers the full block, the three
    shade patterns, the floor middot, and the card suits the game uses
    for trees / fountains / drinks.
    """
    tw, th = tileset.tile_width, tileset.tile_height
    for cp, kind in _BLOCK_AND_SHADES.items():
        tileset[cp] = _render_shade_tile(tw, th, kind)
    tileset[0x00B7] = _render_bitmap_tile(tw, th, _MIDDOT_BITMAP)
    for cp, rows in _SUIT_BITMAPS.items():
        tileset[cp] = _render_bitmap_tile(tw, th, rows)
    return tileset


def load_tileset() -> tcod.tileset.Tileset:
    """Load a tileset for the game window.

    Tries bundled DejaVu Sans Mono first, then the retained Hack font.
    If both TrueType files are missing or their rasterizers fail, falls
    back to the CP437 tilesheet (:data:`TILESHEET_FILENAME`).

    Only raises :class:`EngineError` when all bundled loaders fail.
    """
    _ttf_paths = (
        _data_path(TRUETYPE_FONT_FILENAME),
        _data_path(LEGACY_TRUETYPE_FONT_FILENAME),
    )
    for _ttf_path in _ttf_paths:
        if not _ttf_path.is_file():
            continue
        try:
            _ts = tcod.tileset.load_truetype_font(
                str(_ttf_path),
                tile_width=TILE_WIDTH,
                tile_height=TILE_HEIGHT,
            )
            return _procedural_texture_glyphs(_procedural_box_drawing(_ts))
        except (OSError, RuntimeError, ValueError) as exc:
            print(
                f"Warning: failed to load {_ttf_path} ({exc}). "
                "Trying the next font fallback.",
                file=sys.stderr,
            )

    _tilesheet_path = _data_path(TILESHEET_FILENAME)
    if not _tilesheet_path.is_file():
        raise EngineError(
            f"No tileset found. "
            f"Expected {TRUETYPE_FONT_FILENAME}, {LEGACY_TRUETYPE_FONT_FILENAME}, "
            f"or {TILESHEET_FILENAME} "
            f"in the data/ directory."
        )
    try:
        _sheet = tcod.tileset.load_tilesheet(
            str(_tilesheet_path),
            columns=TILESHEET_COLUMNS,
            rows=TILESHEET_ROWS,
            charmap=tcod.tileset.CHARMAP_TCOD,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise EngineError(
            f"Failed to load tilesheet from {_tilesheet_path}: {exc}"
        ) from exc
    # The tilesheet is missing █ · ♣ ♦ ♥ under CHARMAP_TCOD; fill them
    # in with the same procedural glyphs as the font path.
    return _procedural_texture_glyphs(_sheet)


# ---------------------------------------------------------------------------
# Context + console
# ---------------------------------------------------------------------------


def open_terminal(tileset: tcod.tileset.Tileset) -> tcod.context.Context:
    """Open the libtcod terminal-window context for the game."""
    # SDL3 defaults to NEAREST texture scaling. On displays whose backing
    # scale is not an exact integer multiple of the console (fractional
    # Retina / "scaled" display modes), NEAREST drops pixel rows/columns
    # and glyphs come out with missing pixels. LINEAR is effectively
    # identical at integer scales and complete at fractional ones
    # (tcod 19.5.0 note: "Scaling defaults to nearest, set
    # SDL_RENDER_SCALE_QUALITY=linear if linear scaling was preferred").
    #
    # NOTE: this setdefault alone does NOT work — SDL3 snapshots env vars
    # into hints during the first ``import tcod``, which happens before
    # this function runs (verified: SDL_GetHint returns NULL here even
    # after setting the var). The authoritative set lives in
    # ``spacehack/__init__.py`` (package init, before any tcod import);
    # this one is kept as a harmless fallback for direct-engine callers.
    _os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")
    return tcod.context.new_terminal(
        columns=SCREEN_WIDTH,
        rows=SCREEN_HEIGHT,
        tileset=tileset,
        title=WINDOW_TITLE,
        vsync=True,
    )


def make_console(
    width: int | None = None, height: int | None = None
) -> tcod.console.Console:
    """Create an offscreen console. Default size resolves at call time."""
    return tcod.console.Console(
        width if width is not None else SCREEN_WIDTH,
        height if height is not None else SCREEN_HEIGHT,
    )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def _safe_syms(*names: str) -> tuple:
    """Resolve ``tcod.event.KeySym`` members by name, skipping any that
    aren't exported by the installed tcod version.
    """
    return tuple(
        s for s in (getattr(tcod.event.KeySym, name) for name in names)
        if s is not None
    )


_ESCAPE_SYMS = _safe_syms("ESCAPE")


def should_quit(event: tcod.event.Event) -> bool:
    """Return True if ``event`` should make the main loop exit cleanly."""
    if isinstance(event, tcod.event.Quit):
        return True
    if isinstance(event, tcod.event.KeyDown) and event.sym in _ESCAPE_SYMS:
        return True
    return False
