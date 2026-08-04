"""Main quest core: step lifecycle + smuggle crate mechanics + shared helpers.

Foundation module — every other module in this package depends on it.
"""

from __future__ import annotations

from .. import message_log
from ..time import add_days_to_date as _add_days_to_date
from ..data.main_quest import (
    find_main_quest_step,
    main_quest_step_after,
)

STATUS_AVAILABLE = "available"
STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"


def step_status(ctx, step_id: str) -> str:
    """Return the status of ``step_id`` (``""`` if unknown)."""
    return ctx.main_quest_progress.get(step_id, "")


def _iter_known_steps(ctx):
    """Yield ``(step_id, status, step)`` for every progress entry.

    Entries whose id no longer resolves in the data catalog (stale
    saves, renamed steps) are skipped instead of crashing callers.
    Shared by every progress-scanning loop in the package.
    """
    for _step_id, _st in ctx.main_quest_progress.items():
        try:
            _step = find_main_quest_step(_step_id)
        except KeyError:
            continue
        yield _step_id, _st, _step


def start_step(ctx, step_id: str) -> bool:
    """Move an ``available`` step to ``active``. Returns True if started."""
    if step_status(ctx, step_id) != STATUS_AVAILABLE:
        return False
    ctx.main_quest_progress[step_id] = STATUS_ACTIVE
    return True


def complete_step(ctx, step_id: str) -> bool:
    """Complete a step: apply rewards, then auto-advance the next step."""
    _status = step_status(ctx, step_id)
    if _status not in (STATUS_AVAILABLE, STATUS_ACTIVE):
        return False
    _step = find_main_quest_step(step_id)
    ctx.main_quest_progress[step_id] = STATUS_COMPLETED
    ctx.log.add(f"[MAIN QUEST] {_step.title} — complete.")
    if _step.rewards_credits:
        ctx.stats.credits += _step.rewards_credits
        ctx.log.add(f"+{_step.rewards_credits}$ reward.")
    if _step.rewards_xp:
        from ..xp import add_xp as _add_xp
        _add_xp(ctx, _step.rewards_xp)
    if _step.rewards_rep:
        from ..faction import modify_rep as _modify_rep
        for _fac, _delta in _step.rewards_rep.items():
            _modify_rep(ctx, _fac, _delta)
    if _step.rewards_item:
        ctx.main_quest_unlocked_items.add(_step.rewards_item)
    if _step.completion_flavor:
        ctx.log.add(_step.completion_flavor)
    _next = main_quest_step_after(step_id, chain=ctx.main_quest_chain)
    if _next is not None and step_status(ctx, _next.id) == "":
        if _step.wait_days > 0:
            ctx.main_quest_gate[_next.id] = _add_days_to_date(
                ctx.time_day, ctx.time_month, ctx.time_year, _step.wait_days,
            )
        else:
            ctx.main_quest_progress[_next.id] = STATUS_AVAILABLE
    if _step.unlocks_step and step_status(ctx, _step.unlocks_step) == "":
        ctx.main_quest_progress[_step.unlocks_step] = STATUS_AVAILABLE
    return True


# ---------------------------------------------------------------------------
# Smuggle crate mechanics
# ---------------------------------------------------------------------------


def _smuggle_crate_held(ctx, step_id: str) -> bool:
    """True when the smuggle step's hot crate is already in the mission hold."""
    for _am in ctx.player_active_missions:
        if getattr(_am, "main_quest_step_id", "") == step_id:
            return True
    return False


def _trigger_smuggle_crate(ctx, _step) -> bool:
    """Load the hot crate into the mission hold and start the smuggle step."""
    if step_status(ctx, _step.id) != STATUS_AVAILABLE:
        return False
    from .. import mission as _mission
    _owned = ctx.player_owned_ship
    if _owned is None:
        ctx.log.add("You don't have a ship to carry the crate.")
        return False
    if len(ctx.player_active_missions) >= _mission.MAX_ACTIVE_MISSIONS:
        ctx.log.add(
            f"Your mission log is full "
            f"({_mission.MAX_ACTIVE_MISSIONS}/{_mission.MAX_ACTIVE_MISSIONS}). "
            "Abandon one first (Q)."
        )
        return False
    _size = _step.smuggle_cargo_size
    if _size > 0:
        # Mission cargo is virtual hold space (``mission_reserved``), not
        # trade inventory — a main-quest crate is story-required, so it
        # always loads regardless of current trade cargo.  No capacity
        # rejection here: failing silently would strand the player with
        # the step AVAILABLE and no delivery target (and no retry path).
        _owned.mission_reserved += _size
    _am = _mission.ActiveMission(
        mission_id=f"mq:{_step.id}",
        is_procedural=True,
        status=_mission.MissionStatus.IN_PROGRESS,
        title=_step.title,
        required_cargo_size=_size,
        delivery_target_npc_id=_step.requires_npc_id,
        delivery_target_planet_id=_step.trigger_planet_id,
        target_system_id=_step.trigger_system_id,
        is_smuggle=_step.smuggle_hot,
        smuggle_good_id=_step.smuggle_good_id,
        main_quest_step_id=_step.id,
    )
    ctx.player_active_missions.append(_am)
    start_step(ctx, _step.id)
    _good = _step.smuggle_good_id.replace('_', ' ')
    ctx.log.add_colored(
        f"{_good} loaded into your mission hold. Deliver it to "
        "complete the job.",
        message_log.COLOR_IMPORTANT_EVENT,
    )
    return True


def _complete_smuggle_handover(ctx, _step) -> bool:
    """Complete a smuggle step whose crate is already in the hold."""
    _owned = ctx.player_owned_ship
    if _owned is not None and _step.smuggle_cargo_size > 0:
        _owned.mission_reserved = max(
            0, (_owned.mission_reserved or 0) - _step.smuggle_cargo_size,
        )
    _am = None
    for _m in ctx.player_active_missions:
        if getattr(_m, "main_quest_step_id", "") == _step.id:
            _am = _m
            break
    if _am is not None:
        ctx.player_active_missions.remove(_am)
    ctx.log.add_colored(
        "The crate is handed over.",
        message_log.COLOR_IMPORTANT_EVENT,
    )
    return complete_step(ctx, _step.id)


def _hold_has_goods(ctx, requires_goods) -> bool:
    """True when the player's hold holds every (good_id, qty) pair."""
    _owned = ctx.player_owned_ship
    if _owned is None:
        return False
    for _gid, _qty in requires_goods:
        if _owned.inventory.get(_gid, 0) < _qty:
            return False
    return True


def _consume_goods(ctx, requires_goods) -> None:
    """Remove every (good_id, qty) pair from the player's hold."""
    _owned = ctx.player_owned_ship
    if _owned is None:
        return
    for _gid, _qty in requires_goods:
        _remaining = _owned.inventory.get(_gid, 0) - _qty
        if _remaining <= 0:
            _owned.inventory.pop(_gid, None)
        else:
            _owned.inventory[_gid] = _remaining
    ctx.log.add("The required goods are handed over.")


# ---------------------------------------------------------------------------
# Shared objective helpers (used by _objectives.py AND _act0.py)
# ---------------------------------------------------------------------------


def _active_objective_step(
    ctx,
    objective_type: str,
    *,
    npc_id: str = "",
    spawn_id: str = "",
    planet_id: str = "",
) -> str | None:
    """First available/active step matching ``objective_type``, else None."""
    for _step_id, _st, _step in _iter_known_steps(ctx):
        if _st not in (STATUS_AVAILABLE, STATUS_ACTIVE):
            continue
        if _step.objective_type != objective_type:
            continue
        if _step.chain and _step.chain != ctx.main_quest_chain:
            continue
        if npc_id and _step.requires_npc_id != npc_id:
            continue
        if spawn_id and _step.requires_spawn_id != spawn_id:
            continue
        if planet_id and _step.trigger_planet_id != planet_id:
            continue
        return _step_id
    return None


def _complete_bump_objective(ctx) -> str:
    """Complete an active ``bump`` objective on this door bump.

    Returns the completed step id, or ``""`` if no bump objective is
    live (e.g. the Mars door is just being opened normally).  When
    the next chain step is a smuggle (e.g. lab_q2_delivery), the
    sample is auto-loaded into the mission hold so the player can
    deliver it — same pattern as :func:`secure_quest_loot`.
    """
    _step_id = _active_objective_step(ctx, "bump")
    if _step_id is None:
        return ""
    ctx.log.add_colored(
        "You chip a fragment of the alien material off the door's "
        "surface. The seal holds.",
        message_log.COLOR_IMPORTANT_EVENT,
    )
    complete_step(ctx, _step_id)
    _maybe_auto_trigger_next_smuggle(ctx, _step_id)
    return _step_id


def _maybe_auto_trigger_next_smuggle(ctx, step_id: str) -> None:
    """Auto-load the next step's crate when it is a smuggle delivery.

    Called right after a step completes (delve / bump / salvage): if
    the next step is an immediately-available ``smuggle`` and its
    crate isn't already held, load it so the player can deliver it
    straight away (bar_q3 → bar_q4, lab_q5 → lab_q6_return, ...).
    """
    _next = main_quest_step_after(step_id, chain=ctx.main_quest_chain)
    if (_next is not None
            and _next.objective_type == "smuggle"
            and step_status(ctx, _next.id) == STATUS_AVAILABLE
            and not _smuggle_crate_held(ctx, _next.id)):
        _trigger_smuggle_crate(ctx, _next)
