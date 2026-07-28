"""libtcod (python-tcod) setup helpers for spacehack.

Everything in this module is pure setup: load the tileset, open a
window context, create an offscreen console, decide whether an event
should quit the game. Keeping it isolated means the rest of the game
can import plain data structures without dragging SDL/SDL3 in by
accident.
"""
from __future__ import annotations

import os
import random as _random
import sys
import urllib.error
import urllib.request
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

# The canonical DejaVu 16x16 tilesheet from the libtcod engine's
# data/fonts/ directory. 16 pixels per glyph makes the text much more
# readable than the 10x10 default; the URL is derived from the filename
# so a tilesheet swap is a one-line constant change.
TILESHEET_FILENAME: str = "dejavu16x16_gs_tc.png"
TILESHEET_URL: str = (
    "https://raw.githubusercontent.com/libtcod/libtcod/main/"
    f"data/fonts/{TILESHEET_FILENAME}"
)
TILESHEET_COLUMNS: int = 32
TILESHEET_ROWS: int = 8


class EngineError(RuntimeError):
    """Raised when the engine cannot finish initialising."""


# ---------------------------------------------------------------------------
# Tileset
# ---------------------------------------------------------------------------


def default_tilesheet_dir() -> Path:
    """Return (and create) the per-user directory we cache the tilesheet in."""
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    target_dir = root / "spacehack"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def default_tilesheet_path() -> Path:
    """Full path to the cached tilesheet PNG on disk."""
    return default_tilesheet_dir() / TILESHEET_FILENAME


def ensure_tilesheet(path: Path | None = None) -> Path:
    """Download the bundled DejaVu tilesheet if it is not already on disk."""
    target = path or default_tilesheet_path()
    if target.is_file():
        return target

    try:
        with urllib.request.urlopen(TILESHEET_URL, timeout=15) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EngineError(
            f"Could not download '{TILESHEET_FILENAME}' from {TILESHEET_URL}: "
            f"{exc}. Place the file at {target} manually, or check your network."
        ) from exc

    if not payload:
        raise EngineError(
            f"Server returned an empty body for '{TILESHEET_URL}'. "
            f"Try again later or place {TILESHEET_FILENAME} at {target} manually."
        )

    target.write_bytes(payload)
    return target


def load_tileset() -> tcod.tileset.Tileset:
    """Load the project's default DejaVu tileset (downloading it if needed).

    If the cached PNG ever fails to load, we wipe the cached file and
    try once more. The catch is intentionally narrowed: ``ImportError`` /
    ``AttributeError`` / ``NameError`` are NOT caught on purpose because
    those signal an API drift and should surface as a loud traceback,
    not get masked by a wipe + redownload that can't actually fix
    the cause.
    """
    last_error: BaseException | None = None
    for attempt in (1, 2):
        tilesheet_path = ensure_tilesheet()
        try:
            return tcod.tileset.load_tilesheet(
                str(tilesheet_path),
                columns=TILESHEET_COLUMNS,
                rows=TILESHEET_ROWS,
                charmap=tcod.tileset.CHARMAP_TCOD,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            last_error = exc
            print(
                f"spacehack: tilesheet at {tilesheet_path} failed to load "
                f"({type(exc).__name__}: {exc}); re-downloading.",
                file=sys.stderr,
            )
            try:
                tilesheet_path.unlink(missing_ok=True)
            except OSError:
                pass

    raise EngineError(
        f"Failed to load tilesheet after retrying: {last_error}. "
        f"Try removing the cached file manually and running again."
    ) from last_error


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
