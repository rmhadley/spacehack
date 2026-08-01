"""libtcod (python-tcod) setup helpers for spacehack.

Everything in this module is pure setup: load the tileset, open a
window context, create an offscreen console, decide whether an event
should quit the game. Keeping it isolated means the rest of the game
can import plain data structures without dragging SDL/SDL3 in by
accident.
"""
from __future__ import annotations

import random as _random
import sys
from pathlib import Path

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


# Screen dimensions in character cells. With the 16x16 tilesheet this
# gives a 1600 x 960 logical-pixel window - the standard libtcod
# roguelike-starter size.
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

# Glyph size in pixels. Used by both the CP437 tilesheet (implicit in
# the 32x8 grid) and the TrueType font rasterizer.
TILE_WIDTH: int = 16
TILE_HEIGHT: int = 16

# Optional TrueType/OpenType font. If present in the data/ directory,
# it is loaded in preference to the CP437 tilesheet below. Drop any
# monospace .ttf or .otf here and the game picks it up automatically.
TRUETYPE_FONT_FILENAME: str = "IosevkaTerm-Regular.ttf"

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


def load_tileset() -> tcod.tileset.Tileset:
    """Load a tileset for the game window.

    Tries the bundled TrueType font first (see
    :data:`TRUETYPE_FONT_FILENAME`).  If the file is missing or the
    rasterizer fails, falls back to the CP437 tilesheet
    (:data:`TILESHEET_FILENAME`).

    Only raises :class:`EngineError` when **both** loaders fail.
    """
    _ttf_path = _data_path(TRUETYPE_FONT_FILENAME)
    if _ttf_path.is_file():
        try:
            return tcod.tileset.load_truetype_font(
                str(_ttf_path),
                tile_width=TILE_WIDTH,
                tile_height=TILE_HEIGHT,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            # TTF didn't work — carry on to the tilesheet fallback.
            print(
                f"Warning: failed to load {_ttf_path} ({exc}). "
                f"Falling back to {TILESHEET_FILENAME}.",
                file=sys.stderr,
            )

    _tilesheet_path = _data_path(TILESHEET_FILENAME)
    if not _tilesheet_path.is_file():
        raise EngineError(
            f"No tileset found. "
            f"Expected {TRUETYPE_FONT_FILENAME} or {TILESHEET_FILENAME} "
            f"in the data/ directory."
        )
    try:
        return tcod.tileset.load_tilesheet(
            str(_tilesheet_path),
            columns=TILESHEET_COLUMNS,
            rows=TILESHEET_ROWS,
            charmap=tcod.tileset.CHARMAP_TCOD,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise EngineError(
            f"Failed to load tilesheet from {_tilesheet_path}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Context + console
# ---------------------------------------------------------------------------


def open_terminal(tileset: tcod.tileset.Tileset) -> tcod.context.Context:
    """Open the libtcod terminal-window context for the game."""
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
