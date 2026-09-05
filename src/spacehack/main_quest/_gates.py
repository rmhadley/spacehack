"""Main quest time gating: minimum-wait gates + one-way summons."""

from __future__ import annotations

from ..data.main_quest import (
    MainQuestStep,
    find_main_quest_step,
    list_main_quest_steps,
    main_quest_step_after,
)
from ._core import STATUS_AVAILABLE, step_status


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

def _apply_step_renames(ctx) -> None:
    """RENAMES: status + gate move; a completed combined step completes
    every target, anything else maps onto the first."""
    from ..data.main_quest.migrations import RENAMES

    for _old, _target in RENAMES.items():
        _status = ctx.main_quest_progress.pop(_old, None)
        _gate = ctx.main_quest_gate.pop(_old, None)
        _targets = (_target,) if isinstance(_target, str) else _target
        if _status == "completed":
            for _new in _targets:
                ctx.main_quest_progress.setdefault(_new, "completed")
        elif _status is not None:
            ctx.main_quest_progress.setdefault(_targets[0], _status)
        if _gate is not None:
            ctx.main_quest_gate[_targets[-1]] = _gate


def _apply_step_backfills_and_retirements(ctx) -> None:
    """BACKFILLS / FIELD_FOLDS / RETIRED (see migrations.py)."""
    from ..data.main_quest.migrations import (
        BACKFILLS, FIELD_FOLDS, RETIRED,
    )
    from . import _core as _quest_core

    for _old, (_field, _value) in FIELD_FOLDS.items():
        if getattr(ctx, _old, "") and not getattr(ctx, _field, ""):
            setattr(ctx, _field, _value)
    for _later, _targets in BACKFILLS.items():
        if ctx.main_quest_progress.get(_later) in ("active", "completed"):
            for _target in _targets:
                ctx.main_quest_progress.setdefault(_target, "completed")
    for _old, _implies in RETIRED.items():
        _status = ctx.main_quest_progress.pop(_old, None)
        ctx.main_quest_gate.pop(_old, None)
        if _status != "completed":
            continue
        for _template in _implies:
            _new = _template.format(chain=getattr(ctx, "main_quest_chain", ""))
            try:
                _quest_core.find_main_quest_step(_new)
            except KeyError:
                continue
            ctx.main_quest_progress.setdefault(_new, "completed")


def apply_step_migrations(ctx) -> None:
    """Apply the declared RENAMES/RETIRED save migrations (doc 33).

    Idempotent: renamed ids leave the table once applied; retired ids
    drop out of the maps. Runs before gate checks so old gates fire
    against the new ids. The table is data/main_quest/migrations.py —
    quest catalogs keep their ids; this is the save/load contract.
    """
    _apply_step_renames(ctx)
    _apply_step_backfills_and_retirements(ctx)


def check_quest_gates(ctx) -> bool:
    """Flip time-gated chain steps to available once their gate date passes."""
    apply_step_migrations(ctx)
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
