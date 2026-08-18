"""Main quest faction heat hooks: bar militia heat, consortium heat.

Heat is declared on the step data (``MainQuestStep.heat``) as behavior tags;
these functions turn live steps into world behaviour. Tag semantics:

    ``militia_scan``  — militia scan-chance floor while the step is live
                        (bar chain: the proof run + power-cell legs)
    ``militia_aggro`` — militia auto-aggro in Sol while the step's crate is
                        held (bar chain: the charged power cell)
    ``consortium``    — consortium pirate heat while the step is live
                        (merchant chain: the ore transport + calibration)

Expiry is implicit: the final chain step carries no heat tag, so once it is
the only live step the filters naturally return False.
"""

from __future__ import annotations

from ._core import (
    STATUS_ACTIVE,
    STATUS_AVAILABLE,
    _iter_known_steps,
    _smuggle_crate_held,
)


_HEAT_TAGS = frozenset({"militia_scan", "militia_aggro", "consortium"})


def registered_heat_tags() -> tuple[str, ...]:
    """Return heat tags supported by the data-driven heat table."""
    return tuple(sorted(_HEAT_TAGS))


def _live_heat_steps(ctx, tag: str):
    """Yield available/active steps carrying ``tag``."""
    for _step_id, _st, _step in _iter_known_steps(ctx):
        if _st not in (STATUS_AVAILABLE, STATUS_ACTIVE):
            continue
        if tag in _step.heat:
            yield _step


def _heat_crate_held(ctx, tag: str) -> bool:
    """True while any step carrying ``tag`` has its crate in the mission hold."""
    return any(
        _smuggle_crate_held(ctx, _step.id)
        for _step_id, _st, _step in _iter_known_steps(ctx)
        if tag in _step.heat
    )


def bar_heat_active(ctx) -> bool:
    """True while the bar chain's militia scan heat is live."""
    if ctx.main_quest_chain != "bar":
        return False
    return any(_live_heat_steps(ctx, "militia_scan"))


def charged_cell_in_sol(ctx, system_id: str) -> bool:
    """True while the player is carrying the power cell — militia auto-aggro."""
    if ctx.main_quest_chain != "bar":
        return False
    return _heat_crate_held(ctx, "militia_aggro")


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
    return any(_live_heat_steps(ctx, "consortium"))
