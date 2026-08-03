"""Main quest time gating: minimum-wait gates + one-way summons."""

from __future__ import annotations

from ..data.main_quest import (
    MainQuestStep,
    find_main_quest_step,
    list_main_quest_steps,
    main_quest_step_after,
)
from ._core import STATUS_AVAILABLE, step_status


def _gating_step_for(ctx, next_id: str) -> MainQuestStep | None:
    """Return the completed step that set the gate for next_id."""
    for _s in list_main_quest_steps():
        _nxt = main_quest_step_after(_s.id, chain=ctx.main_quest_chain)
        if _nxt is not None and _nxt.id == next_id:
            return _s
    return None


def check_quest_gates(ctx) -> bool:
    """Flip time-gated chain steps to available once their gate date passes."""
    if not ctx.main_quest_gate:
        return False
    _now = (ctx.time_year, ctx.time_month, ctx.time_day)
    _fired = False
    for _next_id, (_gd, _gm, _gy) in list(ctx.main_quest_gate.items()):
        if (_gy, _gm, _gd) > _now:
            continue
        ctx.main_quest_gate.pop(_next_id, None)
        if step_status(ctx, _next_id) == "":
            ctx.main_quest_progress[_next_id] = STATUS_AVAILABLE
        _gating = _gating_step_for(ctx, _next_id)
        if _gating is not None and _gating.ready_message:
            ctx.main_quest_pending_message = _gating.ready_message
            try:
                _next_step = find_main_quest_step(_next_id)
                ctx.main_quest_pending_objective = _next_step.description
            except KeyError:
                ctx.main_quest_pending_objective = ""
        _fired = True
    return _fired
