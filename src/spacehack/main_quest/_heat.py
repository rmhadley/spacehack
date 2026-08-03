"""Main quest faction heat hooks: bar militia heat, consortium heat."""

from __future__ import annotations

from ._core import (
    STATUS_ACTIVE,
    STATUS_AVAILABLE,
    STATUS_COMPLETED,
    step_status,
    _smuggle_crate_held,
)


def charged_cell_in_sol(ctx, system_id: str) -> bool:
    """True while the player is carrying the power cell — militia auto-aggro."""
    if ctx.main_quest_chain != "bar":
        return False
    return (
        _smuggle_crate_held(ctx, "bar_q4_blackmarket")
        or _smuggle_crate_held(ctx, "bar_q5_charged")
    )


def bar_heat_active(ctx) -> bool:
    """True while the bar chain's hot cargo is in the player's hold."""
    if ctx.main_quest_chain != "bar":
        return False
    if step_status(ctx, "bar_q6_rig") == STATUS_COMPLETED:
        return False
    for _am in ctx.player_active_missions:
        if getattr(_am, "main_quest_step_id", "") == "bar_q2_proof":
            return True
    return (
        step_status(ctx, "bar_q4_blackmarket") in (STATUS_AVAILABLE, STATUS_ACTIVE)
        or step_status(ctx, "bar_q5_charged") in (STATUS_AVAILABLE, STATUS_ACTIVE)
    )


def consortium_heat_active(ctx) -> bool:
    """True while the merchant chain's contested cargo is in play.

    During q3 (smuggle — raw ore) and q4 (bounty — smelted alloy),
    the consortium hires pirates to hunt the player.  All existing
    pirate ships auto-aggro, and new consortium squads (pirate
    leader + merchant escorts) spawn on system entry and randomly
    per tick.

    Mirrors the bar chain's militia heat but with organised-crime
    flavour: economic warfare, not criminal heat.
    """
    if ctx.main_quest_chain != "merchants":
        return False
    if step_status(ctx, "mer_q5_cutter") == STATUS_COMPLETED:
        return False
    return (
        step_status(ctx, "mer_q3_transport") in (STATUS_AVAILABLE, STATUS_ACTIVE)
        or step_status(ctx, "mer_q4_calibrate") in (STATUS_AVAILABLE, STATUS_ACTIVE)
    )
