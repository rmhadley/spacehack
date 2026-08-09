"""Main quest time gating: minimum-wait gates + one-way summons."""

from __future__ import annotations

from ..data.main_quest import (
    MainQuestStep,
    find_main_quest_step,
    list_main_quest_steps,
    main_quest_step_after,
)
from ..data.main_quest.act1_post_prison import find_archive_disclosure
from ..time import add_days_to_date as _add_days_to_date
from ._core import STATUS_AVAILABLE, STATUS_COMPLETED, step_status


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


def _repair_instant_research_completion(ctx) -> None:
    """Migrate saves where the old Alpha handoff translated instantly."""
    if step_status(ctx, "research_alpha") != STATUS_COMPLETED:
        return
    if step_status(ctx, "research_alpha_report") != "":
        return
    if "research_alpha_report" in ctx.main_quest_gate:
        return
    _step = find_main_quest_step("research_alpha")
    ctx.main_quest_gate["research_alpha_report"] = _add_days_to_date(
        ctx.time_day,
        ctx.time_month,
        ctx.time_year,
        _step.wait_days,
    )


def _research_handoff_ready_message(ctx) -> str | None:
    """Return the ready message that matches the player's orbit choice."""
    try:
        _disclosure = find_archive_disclosure(ctx.main_quest_disclosure)
    except KeyError:
        return None
    return _disclosure.ready_message or None


def _ready_message_for(ctx, next_id: str, gating_step: MainQuestStep | None) -> str:
    """Return a choice-aware summon message for a newly available step."""
    if next_id == "research_alpha":
        _research_message = _research_handoff_ready_message(ctx)
        if _research_message is not None:
            return _research_message
    return gating_step.ready_message if gating_step is not None else ""


def _normalize_pending_message(ctx) -> None:
    """Refresh persisted Act 1 gate text after a narrative wording update."""
    _pending = getattr(ctx, "main_quest_pending_message", "")
    if not _pending.startswith("The archive comparison is ready."):
        return
    if (
        "research_alpha" not in ctx.main_quest_gate
        and step_status(ctx, "research_alpha") != STATUS_AVAILABLE
    ):
        return
    _gating = _gating_step_for(ctx, "research_alpha")
    _message = _ready_message_for(ctx, "research_alpha", _gating)
    if _message:
        ctx.main_quest_pending_message = _message


def _gating_step_for(ctx, next_id: str) -> MainQuestStep | None:
    """Return the completed step that set the gate for next_id."""
    for _step in list_main_quest_steps():
        _next = main_quest_step_after(_step.id, chain=ctx.main_quest_chain)
        if _next is not None and _next.id == next_id:
            return _step
    return None


def _unlock_gated_step(ctx, next_id: str) -> None:
    """Mark a gate's next step available and queue its ready text."""
    ctx.main_quest_gate.pop(next_id, None)
    if step_status(ctx, next_id) == "":
        ctx.main_quest_progress[next_id] = STATUS_AVAILABLE
    _gating = _gating_step_for(ctx, next_id)
    _ready_message = _ready_message_for(ctx, next_id, _gating)
    if not _ready_message:
        return
    ctx.main_quest_pending_message = _ready_message
    try:
        _next_step = find_main_quest_step(next_id)
    except KeyError:
        ctx.main_quest_pending_objective = ""
    else:
        ctx.main_quest_pending_objective = _next_step.description


def check_quest_gates(ctx) -> bool:
    """Flip time-gated chain steps to available once their gate date passes."""
    _repair_sealed_archive_handoff(ctx)
    _repair_instant_research_completion(ctx)
    _normalize_pending_message(ctx)
    if not ctx.main_quest_gate:
        return False
    _now = (ctx.time_year, ctx.time_month, ctx.time_day)
    _fired = False
    for _next_id, (_gate_day, _gate_month, _gate_year) in list(
        ctx.main_quest_gate.items()
    ):
        if (_gate_year, _gate_month, _gate_day) > _now:
            continue
        _unlock_gated_step(ctx, _next_id)
        _fired = True
    return _fired
