"""Game time: day/month/year clock and tick helpers.

Central choke-point for all time-advancing actions (jump gates,
planet landings). Every subsystem that needs to react to time
passing hooks in through :func:`advance_time`.
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
    if ctx.time_year != old_year:
        ctx.log.add_colored(f"A new year begins \u2014 {ctx.time_year}.", _mlog.COLOR_IMPORTANT_EVENT)

    from .trade import tick_economy as _tick_economy
    _tick_economy(ctx)


def format_date(ctx: GameContext) -> str:
    """Return a compact date string for HUD display.

    Sci-fi YYYYMMDD format: ``"Date: 22000115"`` for Day 15, Month 1, Year 2200.
    Fits comfortably within HUD_WIDTH (20 chars).
    """
    return f"Date: {ctx.time_year}{ctx.time_month:02d}{ctx.time_day:02d}"
