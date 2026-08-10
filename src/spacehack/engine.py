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


# Screen dimensions in character cells. With the native 16x16 bitmap
# tiles this gives a 1600 x 960 logical-pixel window while preserving the
# existing character-cell layout.
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

# Glyph size in pixels. Keep the grid at the tilesheet's native dimensions
# so bitmap glyphs stay crisp and are never rescaled.
TILE_WIDTH: int = 16
TILE_HEIGHT: int = 16

# Keep the dimensions easy to tune as a pair; the native bitmap and its
# procedural patches use these dimensions.

# Sole rendering asset: a native CP437 bitmap tilesheet.
TILESHEET_FILENAME: str = "dejavu16x16_gs_tc.png"
TILESHEET_COLUMNS: int = 32
TILESHEET_ROWS: int = 8

# Keep ordinary text glyphs at their native sheet widths. Punctuation, map
# symbols, and box drawing also retain native geometry so the bitmap renderer
# stays faithful to the authored CP437 raster.
_TEXT_GLYPHS: tuple[int, ...] = tuple(
    ord(char) for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
)
_TEXT_GLYPH_EXTRA_COLUMNS: int = 0


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


# --- Procedural bitmap texture patches -------------------------------------
#
# The native sheet already supplies the text and box-drawing glyphs. These
# patches fill the few game-specific texture codepoints that are absent or
# inconsistent under CHARMAP_TCOD. Ordinary alphanumeric glyphs remain
# unscaled so their authored bitmap edges stay crisp.

# --- Procedural block elements / shades / suits ----------------------------
#
# Procedural patches keep blocks and shades full-bleed, center the floor dot,
# and guarantee visible card suits for trees (♣), fountains (♦), and drinks (♥).
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

    The bundled bitmap patterns are authored at 16x16. Centering the
    pattern keeps procedural glyphs aligned in the native raster.
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
            if ch == "#" and 0 <= target_x < tw and 0 <= target_y < th:
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


def _widen_glyph_tile(
    tile: np.ndarray, extra_columns: int = _TEXT_GLYPH_EXTRA_COLUMNS
) -> np.ndarray:
    """Return a centered glyph with its ink widened by ``extra_columns``.

    Only the non-transparent horizontal ink bounds are resized. The tile
    remains the same shape, and nearest-neighbour sampling keeps the bitmap
    fully crisp.
    """
    alpha = tile[..., 3]
    _ys, xs = np.where(alpha > 0)
    if not len(xs) or extra_columns <= 0:
        return tile.copy()
    left, right = int(xs.min()), int(xs.max())
    source_width = right - left + 1
    target_width = min(tile.shape[1], source_width + extra_columns)
    if target_width <= source_width:
        return tile.copy()
    source = tile[:, left : right + 1, :]
    source_columns = np.floor(
        np.arange(target_width) * source_width / target_width
    ).astype(int)
    widened = source[:, source_columns, :]
    result = np.zeros_like(tile)
    target_left = (tile.shape[1] - target_width) // 2
    result[:, target_left : target_left + target_width, :] = widened
    return result


def _widen_text_glyphs(tileset: tcod.tileset.Tileset) -> tcod.tileset.Tileset:
    """Apply the optional text-width experiment without changing the cell grid."""
    if _TEXT_GLYPH_EXTRA_COLUMNS <= 0:
        return tileset
    for codepoint in _TEXT_GLYPHS:
        tileset[codepoint] = _widen_glyph_tile(
            np.asarray(tileset[codepoint])
        )
    return tileset


def load_tileset() -> tcod.tileset.Tileset:
    """Load the native CP437 bitmap tileset.

    The bitmap is the sole rendering path so glyphs remain crisp and
    pixel-stable across platforms. Texture patches and the text-spacing
    texture patches are applied after the sheet loads.
    """
    _tilesheet_path = _data_path(TILESHEET_FILENAME)
    if not _tilesheet_path.is_file():
        raise EngineError(
            f"No bitmap tileset found. Expected {TILESHEET_FILENAME} "
            "in the data/ directory."
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
            f"Failed to load bitmap tilesheet from {_tilesheet_path}: {exc}"
        ) from exc
    return _widen_text_glyphs(_procedural_texture_glyphs(_sheet))


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
