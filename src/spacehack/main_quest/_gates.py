"""Main quest time gating: minimum-wait gates + one-way summons."""

from __future__ import annotations

from ..data.main_quest import (
    MainQuestStep,
    find_main_quest_step,
    list_main_quest_steps,
    main_quest_step_after,
)
from ._core import STATUS_AVAILABLE, step_status


def _repair_sealed_archive_handoff(ctx) -> None:
    """Migrate old saves that incorrectly gated an intact archive delivery."""
    if getattr(ctx, "main_quest_disclosure", "") != "archive_sealed":
        return
    if step_status(ctx, "research_alpha") != "":
        return
    if "research_alpha" not in ctx.main_quest_gate:
        return
    ctx.main_quest_gate.pop("research_alpha", None)
    ctx.main_quest_pending_message = ""
    ctx.main_quest_pending_objective = ""
    ctx.main_quest_progress["research_alpha"] = STATUS_AVAILABLE


def _research_handoff_ready_message(ctx) -> str | None:
    """Return the ready message that matches the player's orbit choice."""
    _messages = {
        "diagnostic_fragment": (
            "The diagnostic fragment has been analyzed. Take the recovered archive "
            "to the Research Officer at Alpha Centauri's Science Port for an "
            "independent reading. The work will wait for you; the signal will not "
            "become clearer on its own."
        ),
        "safe_destination": (
            "A secure handoff route has been arranged. Take the sealed archive to "
            "the Research Officer at Alpha Centauri's Science Port for an independent "
            "reading. The work will wait for you; the signal will not become clearer "
            "on its own."
        ),
    }
    return _messages.get(getattr(ctx, "main_quest_disclosure", ""))


def _ready_message_for(ctx, next_id: str, gating_step: MainQuestStep | None) -> str:
    """Return a choice-aware summon message for a newly available step."""
    if next_id == "research_alpha":
        _research_message = _research_handoff_ready_message(ctx)
        if _research_message is not None:
            return _research_message
    return gating_step.ready_message if gating_step is not None else ""


def _normalize_pending_message(ctx) -> None:
    """Refresh persisted Act 1 gate text after a narrative wording update."""
    if not getattr(ctx, "main_quest_pending_message", "").startswith(
        "The archive comparison is ready."
    ):
        return
    if "research_alpha" not in ctx.main_quest_gate and step_status(ctx, "research_alpha") != STATUS_AVAILABLE:
        return
    _gating = _gating_step_for(ctx, "research_alpha")
    _message = _ready_message_for(ctx, "research_alpha", _gating)
    if _message:
        ctx.main_quest_pending_message = _message


def _gating_step_for(ctx, next_id: str) -> MainQuestStep | None:
    """Return the completed step that set the gate for next_id."""
    for _s in list_main_quest_steps():
        _nxt = main_quest_step_after(_s.id, chain=ctx.main_quest_chain)
        if _nxt is not None and _nxt.id == next_id:
            return _s
    return None


def check_quest_gates(ctx) -> bool:
    """Flip time-gated chain steps to available once their gate date passes."""
    _repair_sealed_archive_handoff(ctx)
    _normalize_pending_message(ctx)
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
        _ready_message = _ready_message_for(ctx, _next_id, _gating)
        if _ready_message:
            ctx.main_quest_pending_message = _ready_message
            try:
                _next_step = find_main_quest_step(_next_id)
                ctx.main_quest_pending_objective = _next_step.description
            except KeyError:
                ctx.main_quest_pending_objective = ""
        _fired = True
    return _fired
