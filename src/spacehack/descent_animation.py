"""The deep-elevator descent: a wordless full-screen animation.

The cage drops through a near-black shaft — rails, a lit platform,
the @ standing on it — and the only words are the log line after the
cage settles. Communicates the LONG descent purely through motion:
an easing speed curve, landings scrolling past as wall seams, and the
platform's warm light spilling upward into the dark (user design,
2026-09-02: "we don't need words").
"""

from __future__ import annotations

import math

from .engine import SCREEN_HEIGHT, SCREEN_WIDTH

# Shaft palette: near-black rock, dim steel rails, warm cage light.
_BLACK = (6, 7, 10)
_WALL_FG = (70, 76, 88)
_SEAM_FG = (150, 120, 70)
_PLATFORM_FG = (255, 190, 90)
_PLATFORM_BG = (48, 32, 14)
_PLAYER_FG = (235, 235, 235)

# The platform's light reaches a few rows up, fading with distance.
_GLOW_ROWS = 5
_GLOW_TOP = (30, 20, 9)

# One seam every LEVEL_SPAN world-rows: the landings you pass.
_LEVEL_SPAN = 7
_SEAM_PHASE = 3

# Cage travel: starts near the top, exits the bottom, then two extra
# rows so the dark fully arrives before the fade to F5.
_START_ROW = 3
_EXTRA_ROWS = 2


def descent_rows(total_frames: int, height: int) -> list[int]:
    """Cage row per frame — pure, monotonic, eased end to end.

    Slow start, fast middle, slow finish: a real cage, and the speed
    curve IS the "this is deep" message. Tests assert the easing shape
    without a presenter.
    """
    travel = height - _START_ROW + _EXTRA_ROWS
    rows = []
    for frame in range(total_frames):
        eased = 0.5 - 0.5 * math.cos((frame + 1) / total_frames * math.pi)
        rows.append(_START_ROW + int(round(eased * travel)))
    return rows


def _glow_bg(distance: int) -> tuple[int, int, int]:
    """Platform-light background ``distance`` rows above the cage."""
    if distance <= 0 or distance > _GLOW_ROWS:
        return _BLACK
    fade = 1.0 - (distance - 1) / _GLOW_ROWS
    return tuple(
        int(_BLACK[i] + (_GLOW_TOP[i] - _BLACK[i]) * fade) for i in range(3)
    )


def paint_descent_frame(console, cage_row: int) -> None:
    """Paint one shaft frame: rails, seams, cage, upward light.

    Pure with respect to game state; mutates only ``console``.
    """
    console.clear(bg=_BLACK)
    cx = console.width // 2
    for y in range(console.height):
        world_row = y + cage_row
        is_seam = world_row % _LEVEL_SPAN == _SEAM_PHASE
        rail_fg = _SEAM_FG if is_seam else _WALL_FG
        # The centre column is open shaft — it carries the light spill.
        console.print(x=cx, y=y, string=" ", bg=_glow_bg(cage_row - y - 1))
        for dx in (-1, 1):
            console.print(x=cx + dx, y=y, string="=", fg=rail_fg, bg=_BLACK)
    # The cage: the rider centred on the lit platform.
    console.print(
        x=cx - 1, y=cage_row, string="===",
        fg=_PLATFORM_FG, bg=_PLATFORM_BG,
    )
    console.print(
        x=cx, y=cage_row - 1, string="@",
        fg=_PLAYER_FG, bg=_glow_bg(1),
    )


def animate_descent(ctx, console, *, frame_seconds: float = 0.075) -> None:
    """Play the descent: eased cage travel; any key skips to the end.

    Presents through the shared Pygame runtime — the same present +
    responsive-sleep pattern as the city launch glide.
    """
    from .navigation_travel import _responsive_sleep

    context = getattr(ctx, "context", None)
    total_frames = max(24, int(SCREEN_HEIGHT * 0.9))
    for cage_row in descent_rows(total_frames, SCREEN_HEIGHT):
        paint_descent_frame(console, min(cage_row, console.height + 1))
        if context is not None:
            context.present(console)
        if _skip_requested(context):
            break
        _responsive_sleep(frame_seconds)


def _skip_requested(context) -> bool:
    """Whether the player pressed anything to skip the ride."""
    if context is None:
        return False
    return bool(context.events())


__all__ = [
    "animate_descent",
    "descent_rows",
    "paint_descent_frame",
    "SCREEN_WIDTH",
    "SCREEN_HEIGHT",
]
