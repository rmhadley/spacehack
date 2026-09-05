"""Main quest time gating: minimum-wait gates + one-way summons."""

from __future__ import annotations

from ..data.main_quest import (
    MainQuestStep,
    find_main_quest_step,
    list_main_quest_steps,
    main_quest_step_after,
)
from ._core import STATUS_AVAILABLE, STATUS_COMPLETED, step_status


def _ready_message_for(ctx, next_id: str, gating_step: MainQuestStep | None) -> str:
    """Return a choice-aware summon message for a newly available step."""
    return gating_step.ready_message if gating_step is not None else ""


def _normalize_pending_message(ctx) -> None:
    """Drop persisted Act 1 pending text that references removed steps."""
    _pending = getattr(ctx, "main_quest_pending_message", "")
    if "research_alpha" in _pending or _pending.startswith("The archive comparison"):
        ctx.main_quest_pending_message = ""
        ctx.main_quest_pending_objective = ""


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


_MERCHANTS_RENUMBER = {
    # 5-step era: calibrate/cutter were q4/q5; the survey run lives on
    # as mer_q6_survey, the cutter as mer_q7_cutter.
    "mer_q4_calibrate": "mer_q6_survey",
    "mer_q5_cutter": "mer_q7_cutter",
    # 6-step era: The Survey split into alloy pickup + Vega run.
    "mer_q5_calibration": "mer_q5_alloy",
    "mer_q6_cutter": "mer_q7_cutter",
}


def _repair_merchants_renumber(ctx) -> None:
    """Migrate saves from older merchants-chain layouts onto the 7-step one.

    Status-preserving id rename in progress and gate maps; runs before
    gate checks so old gates fire against the new ids. A renamed save
    whose survey step already started/completed never has the alloy
    step scheduled (it completed in a prior layout), so reconcile the
    missing link — the chain must not strand the player.
    """
    for _old, _new in _MERCHANTS_RENUMBER.items():
        if _old in ctx.main_quest_progress and _new not in ctx.main_quest_progress:
            ctx.main_quest_progress[_new] = ctx.main_quest_progress.pop(_old)
        if _old in ctx.main_quest_gate and _new not in ctx.main_quest_gate:
            ctx.main_quest_gate[_new] = ctx.main_quest_gate.pop(_old)
    _alloy = ctx.main_quest_progress.get("mer_q5_alloy")
    _survey = ctx.main_quest_progress.get("mer_q6_survey")
    if _survey in ("active", "completed") and _alloy is None:
        # The survey ran in a prior layout without the alloy step.
        ctx.main_quest_progress["mer_q5_alloy"] = "completed"
    elif _alloy == "completed" and _survey is None:
        # 6-step era: alloy + survey were one step, so both are done.
        ctx.main_quest_progress["mer_q6_survey"] = "completed"


def _repair_research_renumber(ctx) -> None:
    """Migrate pre-epilogue saves onto the disposition branch (doc 38).

    The old disclosure choices were all sharing paths, so any of them
    maps to 'delivered'. Research step ids vanish; a save that reached
    the first translation counts as a completed delivery, so its
    chain's epilogue reward step completes too (the old flow never
    paid a reward - anything short of the report leaves it live).
    """
    if (getattr(ctx, "main_quest_disclosure", "")
            and not getattr(ctx, "main_quest_disposition", "")):
        ctx.main_quest_disposition = "delivered"
    _had_report = ctx.main_quest_progress.pop("research_alpha_report", None)
    ctx.main_quest_progress.pop("research_alpha", None)
    ctx.main_quest_gate.pop("research_alpha_report", None)
    ctx.main_quest_gate.pop("research_alpha", None)
    if getattr(ctx, "main_quest_disposition", "") == "delivered" and _had_report:
        _reward = f"epilogue_reward_{ctx.main_quest_chain}"
        if step_status(ctx, _reward) == "":
            ctx.main_quest_progress[_reward] = STATUS_COMPLETED


def check_quest_gates(ctx) -> bool:
    """Flip time-gated chain steps to available once their gate date passes."""
    _repair_research_renumber(ctx)
    _repair_merchants_renumber(ctx)
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
