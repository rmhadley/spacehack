"""Main quest breadcrumb: quest-log objective display."""

from __future__ import annotations

from ..data.main_quest import find_main_quest_step
from ..text import get as t_get
from ._core import STATUS_ACTIVE, STATUS_AVAILABLE, _iter_known_steps
from ._gates import _gating_step_for


def _active_step_objective(ctx) -> tuple[str, str] | None:
    """Return the first available or active catalog step objective."""
    _step = _active_payment_step(ctx)
    if _step is not None:
        return (_step.title, _step.description)
    for _step_id, _status, _step in _iter_known_steps(ctx):
        if _status == STATUS_ACTIVE:
            # A started step narrates its remaining route (the tau-b
            # collection leg is done; Q points at Vega) — the two-text
            # pattern gates use, applied to live steps (playtest v13).
            _active_desc = t_get(f"step.{_step_id}.active_description")
            return (_step.title, _active_desc or _step.description)
        if _status == STATUS_AVAILABLE:
            return (_step.title, _step.description)
    return None


def _active_payment_step(ctx):
    """The live payment step, if any (Q renders its cost from data)."""
    for _step_id, _status, _step in _iter_known_steps(ctx):
        if _status in (STATUS_AVAILABLE, STATUS_ACTIVE) and _step.payment_credits:
            return _step
    return None


def _gated_objective(ctx) -> tuple[str, str] | None:
    """Return the breadcrumb for the first pending time-gated step."""
    if not ctx.main_quest_gate:
        return None
    _next_id = next(iter(ctx.main_quest_gate))
    try:
        _next = find_main_quest_step(_next_id)
    except KeyError:
        return None
    _fac = _next.chain or ctx.main_quest_chain or "faction"
    _gating = _gating_step_for(ctx, _next_id)
    _description = (
        _gating.completion_flavor
        if _gating is not None and _gating.completion_flavor
        else t_get("runtime.quest_gated_fallback")
    )
    return (
        t_get("runtime.quest_gated_title").format(faction=_fac.capitalize()),
        _description,
    )


def _departure_objective(ctx) -> tuple[str, str] | None:
    """Return the required Mars departure objective before the orbit scene."""
    if (
        ctx.main_quest_progress.get("act1_prison") == "completed"
        and not getattr(ctx, "post_prison_orbit_seen", False)
        and not getattr(ctx, "main_quest_complete", False)
    ):
        return (
            t_get("runtime.quest_departure_title"),
            t_get("runtime.quest_departure_body"),
        )
    return None


def current_main_quest_objective(ctx) -> tuple[str, str] | None:
    """Return (title, description) of the current breadcrumb step."""
    _active = _active_step_objective(ctx)
    if _active is not None:
        return _active
    _gated = _gated_objective(ctx)
    if _gated is not None:
        return _gated
    return _departure_objective(ctx)
