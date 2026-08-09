"""Main quest breadcrumb: quest-log objective display."""

from __future__ import annotations

from ..data.main_quest import find_main_quest_step
from ._core import STATUS_ACTIVE, STATUS_AVAILABLE, _iter_known_steps
from ._gates import _gating_step_for


def current_main_quest_objective(ctx) -> tuple[str, str] | None:
    """Return (title, description) of the current breadcrumb step."""
    for _step_id, _st, _step in _iter_known_steps(ctx):
        if _st not in (STATUS_AVAILABLE, STATUS_ACTIVE):
            continue
        return (_step.title, _step.description)
    if ctx.main_quest_gate:
        _next_id = next(iter(ctx.main_quest_gate))
        try:
            _next = find_main_quest_step(_next_id)
        except KeyError:
            return None
        _fac = _next.chain or ctx.main_quest_chain or "faction"
        _gating = _gating_step_for(ctx, _next_id)
        _desc = (
            _gating.completion_flavor
            if _gating is not None and _gating.completion_flavor
            else "The faction will contact you when they're ready."
        )
        return (f"Awaiting word from the {_fac.capitalize()}...", _desc)
    if (
        ctx.main_quest_progress.get("act1_prison") == "completed"
        and not getattr(ctx, "post_prison_orbit_seen", False)
        and not getattr(ctx, "main_quest_complete", False)
    ):
        return (
            "Leave Mars",
            "Return to your ship and launch from Mars. The recovered archive "
            "is waiting for its first reading.",
        )
    return None
