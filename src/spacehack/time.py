"""Game time: day/month/year clock and tick helpers.

Central choke-point for all time-advancing actions. Time passes
through movement: every 10 space moves (manual + auto-nav) = 1 day.
Every subsystem that needs to react to time passing hooks in
through :func:`advance_time`.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_context import GameContext


def advance_time(ctx: GameContext, days: int) -> None:
    """Advance the game clock by ``days``.

    Wraps months at 30, years at 12. Fires subscriber hooks for
    month/year rollover. Also ticks the economy on every advance.

    This is THE single function that mutates ``ctx.time_*`` --
    all call sites go through it.
    """
    if days <= 0:
        return

    old_month = ctx.time_month
    old_year = ctx.time_year

    ctx.time_day += days

    while ctx.time_day > 30:
        ctx.time_day -= 30
        ctx.time_month += 1

    while ctx.time_month > 12:
        ctx.time_month -= 12
        ctx.time_year += 1

    from . import message_log as _mlog
    if ctx.time_month != old_month:
        ctx.log.add_colored("A new month begins.", _mlog.COLOR_IMPORTANT_EVENT)
        _on_month_change(ctx)
    if ctx.time_year != old_year:
        ctx.log.add_colored(f"A new year begins \u2014 {ctx.time_year}.", _mlog.COLOR_IMPORTANT_EVENT)

    from .trade import tick_economy as _tick_economy
    _tick_economy(ctx)


def _on_month_change(ctx: GameContext) -> None:
    """Called by :func:`advance_time` when the month rolls over.

    Resets shop visit counters so the next mechanic visit on each
    planet gets fresh RNG inventory. Logs a restock message.

    Module-level (not an inner function) per reviewer checklist —
    it has no meaningful closure over ``advance_time``'s scope.
    """
    ctx.mech_visit_count.clear()
    from . import message_log as _mlog
    ctx.log.add_colored(
        "Shops have restocked for the new month.",
        _mlog.COLOR_IMPORTANT_EVENT,
    )


def tick_move(ctx: GameContext) -> None:
    """Count a space movement and advance time based on ship speed.

    Call this on every manual space move and auto-nav step.
    Reads the player ship's ``speed`` stat (moves per day) to
    determine when to advance the clock. Fast ships cover more
    ground per day; slow ships take longer.

    The counter accumulates across all space actions (jumps and
    landings do NOT reset it).
    """
    from .ship import find_ship as _find_ship
    speed = 10  # fallback if ship lookup fails
    if ctx.player_owned_ship is not None:
        try:
            speed = _find_ship(ctx.player_owned_ship.ship_id).speed
        except (KeyError, ImportError):
            pass

    ctx.move_counter += 1
    if ctx.move_counter >= speed:
        advance_time(ctx, 1)
        ctx.move_counter = 0


def format_date(ctx: GameContext) -> str:
    """Return a compact date string for HUD display.

    Sci-fi YYYYMMDD format: ``"Date: 22000115"`` for Day 15, Month 1, Year 2200.
    Fits comfortably within HUD_WIDTH (20 chars).
    """
    return f"Date: {ctx.time_year}{ctx.time_month:02d}{ctx.time_day:02d}"
