"""Main quest breadcrumb: quest-log objective display."""

from __future__ import annotations

from ..data.main_quest import find_main_quest_step
from ._core import STATUS_ACTIVE, STATUS_AVAILABLE
from ._gates import _gating_step_for


def current_main_quest_objective(ctx) -> tuple[str, str] | None:
    """Return (title, description) of the current breadcrumb step."""
    for _step_id, _status in ctx.main_quest_progress.items():
        if _status not in (STATUS_AVAILABLE, STATUS_ACTIVE):
            continue
        try:
            _step = find_main_quest_step(_step_id)
        except KeyError:
            continue
        return (_step.title, _step.description)
    if ctx.main_quest_gate:
        _next_id = next(iter(ctx.main_quest_gate))
        try:
            _next = find_main_quest_step(_next_id)
        except KeyError:
            return None
        _fac = _next.chain.capitalize() if _next.chain else "faction"
        _gating = _gating_step_for(ctx, _next_id)
        _desc = (
            _gating.completion_flavor
            if _gating is not None and _gating.completion_flavor
            else "The faction will contact you when they're ready."
        )
        return (f"Awaiting word from the {_fac}...", _desc)
    return None
