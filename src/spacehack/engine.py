"""libtcod (python-tcod) setup helpers for spacehack.

Everything in this module is pure setup: load the tileset, open a
window context, create an offscreen console, decide whether an event
should quit the game. Keeping it isolated means the rest of the game
can import plain data structures without dragging SDL/SDL3 in by
accident.
"""
from __future__ import annotations

import random as _random
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

# The canonical DejaVu 16x16 tilesheet bundled in the source tree.
# 16 pixels per glyph makes the text much more readable than the
# 10x10 default.
TILESHEET_FILENAME: str = "dejavu16x16_gs_tc.png"
TILESHEET_COLUMNS: int = 32
TILESHEET_ROWS: int = 8


class EngineError(RuntimeError):
    """Raised when the engine cannot finish initialising."""


# ---------------------------------------------------------------------------
# Tileset
# ---------------------------------------------------------------------------


def _bundled_tilesheet_path() -> Path:
    """Full path to the tilesheet bundled in the source tree."""
    return Path(__file__).resolve().parent / "data" / TILESHEET_FILENAME


def load_tileset() -> tcod.tileset.Tileset:
    """Load the project's bundled DejaVu tilesheet.

    Looks for the tilesheet in ``src/spacehack/data/`` next to this
    module. No network access required.
    """
    tilesheet_path = _bundled_tilesheet_path()
    if not tilesheet_path.is_file():
        raise EngineError(
            f"Tilesheet not found at {tilesheet_path}. "
            f"Expected {TILESHEET_FILENAME} in the data/ directory."
        )
    try:
        return tcod.tileset.load_tilesheet(
            str(tilesheet_path),
            columns=TILESHEET_COLUMNS,
            rows=TILESHEET_ROWS,
            charmap=tcod.tileset.CHARMAP_TCOD,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise EngineError(
            f"Failed to load tilesheet from {tilesheet_path}: {exc}"
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
