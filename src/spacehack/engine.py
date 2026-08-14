"""Engine setup helpers for spacehack.

Everything in this module is pure setup: load the bitmap glyph atlas and
create project-owned framebuffers. Keeping it isolated means the rest of the
game can import plain data structures without opening a display at import
time.
"""
from __future__ import annotations

import random as _random
import sys
from pathlib import Path
from typing import Any

from .framebuffer import FrameBuffer

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

# Widen only ordinary text glyphs. Punctuation, map symbols, and box drawing
# retain the native sheet geometry so the bitmap experiment cannot disturb
# spatial symbols or UI frames.
_TEXT_GLYPHS: tuple[int, ...] = tuple(
    ord(char) for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
)
_TEXT_GLYPH_EXTRA_COLUMNS: int = 3

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

# The project-owned map is the exact 160-entry order used by the bundled
# 32x8 sheet. Zero entries are intentionally blank slots in the source atlas.
CP437_CHARMAP: tuple[int, ...] = (
    32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
    48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63,
    64, 91, 92, 93, 94, 95, 96, 123, 124, 125, 126, 9617, 9618, 9619,
    9474, 9472, 9532, 9508, 9524, 9500, 9516, 9492, 9484, 9488, 9496,
    9624, 9629, 9600, 9622, 9626, 9616, 9623, 8593, 8595, 8592, 8594,
    9650, 9660, 9668, 9658, 8597, 8596, 9744, 9745, 9675, 9673, 9553,
    9552, 9580, 9571, 9577, 9568, 9574, 9562, 9556, 9559, 9565, 0, 0, 0,
    0, 0, 0, 0, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77,
    78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 0, 0, 0, 0,
    0, 0, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
    110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 0,
    0, 0, 0, 0, 0,
)


def _pygame_module() -> Any:
    """Load Pygame only when the bitmap pipeline is used."""
    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise EngineError("Pygame is required to load the bitmap tilesheet.") from exc
    return pygame


def _bitmap_to_alpha_tile(tile: Any) -> Any:
    """Convert grayscale sheet pixels to white-alpha bitmap ink."""
    pygame = _pygame_module()
    result = pygame.Surface(tile.get_size(), pygame.SRCALPHA, 32)
    width, height = tile.get_size()
    for y in range(height):
        for x in range(width):
            red, green, blue, _alpha = tile.get_at((x, y))
            alpha = (red + green + blue) // 3
            result.set_at((x, y), (255, 255, 255, alpha))
    return result


class PygameTileset:
    """Project-owned processed glyph tiles loaded from the bundled PNG."""

    def __init__(self, tile_width: int, tile_height: int):
        self.tile_width = tile_width
        self.tile_height = tile_height
        self._tiles: dict[int, Any] = {}

    def __getitem__(self, codepoint: int) -> Any:
        return self._tiles[codepoint]

    def __setitem__(self, codepoint: int, tile: Any) -> None:
        self._tiles[codepoint] = tile

# --- Procedural bitmap texture patches -------------------------------------
#
# The native sheet already supplies the text and box-drawing glyphs. These
# patches fill the few game-specific texture codepoints that are absent or
# inconsistent in source atlases. Ordinary alphanumeric glyphs receive the
# small readability widening pass below; spatial glyphs remain unscaled.

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

def _render_shade_tile(tw: int, th: int, kind: str) -> Any:
    """Build one block/shade glyph tile (RGBA) matching the tilesheet look.

    ``kind`` is one of ``"full"`` / ``"light"`` / ``"medium"`` / ``"dark"``.
    All patterns are full-bleed so adjacent tiles read as one continuous
    surface.
    """
    pygame = _pygame_module()
    tile = pygame.Surface((tw, th), pygame.SRCALPHA, 32)
    tile.fill((0, 0, 0, 0))
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
                tile.set_at((x, y), (255, 255, 255, 255))
    return tile

def _render_bitmap_tile(
    tw: int, th: int, rows: tuple[str, ...]
) -> Any:
    """Build a centered glyph tile (RGBA) from '#'/'.' bitmap rows.

    The bundled bitmap patterns are authored at 16x16. Centering the
    pattern keeps procedural glyphs aligned in the native raster.
    """
    pygame = _pygame_module()
    tile = pygame.Surface((tw, th), pygame.SRCALPHA, 32)
    tile.fill((0, 0, 0, 0))
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
                tile.set_at((target_x, target_y), (255, 255, 255, 255))
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
    tileset: PygameTileset,
) -> PygameTileset:
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
    tile: Any, extra_columns: int = _TEXT_GLYPH_EXTRA_COLUMNS
) -> Any:
    """Return a centered glyph with its ink widened by ``extra_columns``.

    Only the non-transparent horizontal ink bounds are resized. The tile
    remains the same shape, and nearest-neighbour sampling keeps the bitmap
    fully crisp.
    """
    pygame = _pygame_module()
    width, height = tile.get_size()
    xs = [
        x for y in range(height)
        for x in range(width)
        if tile.get_at((x, y))[3] > 0
    ]
    if not xs or extra_columns <= 0:
        return tile.copy()
    left, right = min(xs), max(xs)
    source_width = right - left + 1
    target_width = min(width, source_width + extra_columns)
    if target_width <= source_width:
        return tile.copy()
    result = pygame.Surface((width, height), pygame.SRCALPHA, 32)
    result.fill((0, 0, 0, 0))
    target_left = (width - target_width) // 2
    for y in range(height):
        for target_x in range(target_width):
            source_x = left + (target_x * source_width // target_width)
            result.set_at(
                (target_left + target_x, y),
                tile.get_at((source_x, y)),
            )
    return result

def _widen_text_glyphs(tileset: PygameTileset) -> PygameTileset:
    """Tighten ordinary bitmap text while preserving the fixed cell grid."""
    for codepoint in _TEXT_GLYPHS:
        tileset[codepoint] = _widen_glyph_tile(tileset[codepoint])
    return tileset

def load_tileset() -> PygameTileset:
    """Load the native CP437 bitmap tileset.

    The bitmap is the sole rendering path so glyphs remain crisp and
    pixel-stable across platforms. Texture patches and the text-spacing
    pass are applied after the sheet loads.
    """
    _tilesheet_path = _data_path(TILESHEET_FILENAME)
    if not _tilesheet_path.is_file():
        raise EngineError(
            f"No bitmap tileset found. Expected {TILESHEET_FILENAME} "
            "in the data/ directory."
        )
    pygame = _pygame_module()
    try:
        raw_sheet = pygame.image.load(str(_tilesheet_path))
        if raw_sheet.get_size() != (
            TILE_WIDTH * TILESHEET_COLUMNS,
            TILE_HEIGHT * TILESHEET_ROWS,
        ):
            raise ValueError(
                f"expected {TILE_WIDTH * TILESHEET_COLUMNS}x"
                f"{TILE_HEIGHT * TILESHEET_ROWS}, got {raw_sheet.get_size()}"
            )
        if raw_sheet.get_bytesize() != 4 or not raw_sheet.get_masks()[3]:
            raise ValueError("bitmap tilesheet must be a 32-bit RGBA surface")
        sheet = PygameTileset(TILE_WIDTH, TILE_HEIGHT)
        for index, codepoint in enumerate(CP437_CHARMAP):
            if codepoint == 0:
                continue
            x = (index % TILESHEET_COLUMNS) * TILE_WIDTH
            y = (index // TILESHEET_COLUMNS) * TILE_HEIGHT
            sheet[codepoint] = _bitmap_to_alpha_tile(raw_sheet.subsurface(
                (x, y, TILE_WIDTH, TILE_HEIGHT)
            ))
    except (OSError, RuntimeError, ValueError, pygame.error) as exc:
        raise EngineError(
            f"Failed to load bitmap tilesheet from {_tilesheet_path}: {exc}"
        ) from exc
    return _widen_text_glyphs(_procedural_texture_glyphs(sheet))

# ---------------------------------------------------------------------------
# Context + console
# ---------------------------------------------------------------------------

def make_console(
    width: int | None = None, height: int | None = None
) -> FrameBuffer:
    """Create a project-owned framebuffer. Default size resolves at call time."""
    return FrameBuffer(
        # One HUD-width extra column: the overlay paints HUD text at roughly
        # half cell width, so the right panel shows ~40 chars, not 20. The
        # extra cells only exist for the HUD; region renderers ignore them.
        width if width is not None else SCREEN_WIDTH + HUD_WIDTH,
        height if height is not None else SCREEN_HEIGHT,
    )
