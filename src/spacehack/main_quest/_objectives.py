"""Main quest objectives: delve, visit, bounty, smuggle delivery hooks."""

from __future__ import annotations

from ..data.main_quest import find_main_quest_step, main_quest_step_after
from ._core import (
    STATUS_ACTIVE,
    STATUS_AVAILABLE,
    step_status,
    complete_step,
    _iter_known_steps,
    _trigger_smuggle_crate,
    _active_objective_step,
    _maybe_auto_trigger_next_smuggle,
)
from .handlers import handler_for
from .. import message_log
from ..text import get as t_get


def _remove_quest_spawn_group(ctx, step) -> None:
    """Remove the leader + escort BountySpawns for a completed quest step.

    Escort ids are derived as ``{requires_spawn_id}_esc_<n>`` (see
    :func:`spacehack.main_quest.ensure_quest_spawns`) — sweeping the
    prefix keeps the system clean when the leader is defeated or the
    salvage wreck is secured.
    """
    if not step.trigger_system_id or not step.requires_spawn_id:
        return
    from ..navigation import _remove_bounty_spawn as _rbs
    _esc_prefix = f"{step.requires_spawn_id}_esc_"
    for _bs in list(ctx.bounty_spawns.get(step.trigger_system_id, [])):
        if (_bs.spawn_id == step.requires_spawn_id
                or _bs.spawn_id.startswith(_esc_prefix)):
            _rbs(ctx, _bs.spawn_id, step.trigger_system_id)


def find_salvage_step_for_spawn(ctx, spawn_id: str):
    """Return the salvage step targeting ``spawn_id`` (any status).

    Callers check the step's live status via ``step_status`` (a
    completed step means the wreck was already secured; an
    available/active one means the wreck may still be boarded).
    """
    for _step_id, _st, _step in _iter_known_steps(ctx):
        if (_step.objective_type == "salvage"
                and _step.requires_spawn_id == spawn_id):
            return _step
    return None


def show_step_readout(ctx, _step) -> bool:
    """Show the quest readout popup for a just-completed step.

    Body = completion flavor + next-step guidance (a time-gate hint
    or the next objective's description).  No-op when the step has no
    completion flavor or no dialogue NPC to portrait.
    """
    _flavor = _step.completion_flavor
    if not _flavor or not _step.dialogues:
        return False
    from ..data.npcs import find_npc as _fn
    _npc = _fn(next(iter(_step.dialogues)))
    _next_step = (
        main_quest_step_after(_step.id, chain=ctx.main_quest_chain)
        if _step.auto_advance else None
    )
    if (_next_step is not None
            and _next_step.id in ctx.main_quest_gate):
        _what_next = t_get("runtime.readout_wait_hint").format(
            faction=_next_step.chain.capitalize(),
        )
    elif _next_step is not None:
        _what_next = _next_step.description
    else:
        _what_next = ""
    _body = _flavor
    if _what_next:
        _body = f"{_flavor}\n\n{_what_next}"
    from ._act0 import show_quest_readout
    show_quest_readout(ctx, _npc, _body)
    return True


def secure_quest_loot(ctx, loot_entity, goods: list[tuple[str, int]]) -> bool:
    """Complete a delve/salvage objective whose quest-tagged loot was secured."""
    _step_id = getattr(loot_entity, "main_quest_step_id", "")
    if not _step_id:
        return False
    if step_status(ctx, _step_id) not in (STATUS_AVAILABLE, STATUS_ACTIVE):
        return False
    _step = find_main_quest_step(_step_id)
    _handler = handler_for(_step.objective_type)
    if _handler is None or not _handler.secures_quest_loot:
        return False
    # Secured quest goods never enter the sellable hold (playtest v2,
    # bar pass: the delve ALSO handed over a sellable power cell next
    # to the mission crate's copy - a double and a farm). The step's
    # follow-up owns the cargo fiction: the next smuggle crate (the
    # ore/requisition/cell IS the crate) or the faction's hands.
    from ..data.trade_goods import display_name as _good_name
    for _gid, _qty in goods:
        ctx.log.add(f"Secured: {_good_name(_gid)} x{_qty}.")
    _result = complete_step(ctx, _step_id)
    if _result:
        # Salvage wrecks: the handler removes the derelict BountySpawn so it
        # doesn't respawn on re-entry (see _cleanup_salvage_wreck).
        if _handler.on_complete is not None:
            _handler.on_complete(ctx, _step)
        _maybe_auto_trigger_next_smuggle(ctx, _step_id)
        show_step_readout(ctx, _step)
    return _result


def _cleanup_salvage_wreck(ctx, step) -> None:
    """Remove the derelict wreck + guard spawns for a completed salvage step.

    The exit handler (__main__.py) removes the wreck entity from space_map;
    this removes the spawn record plus the leader + escort spawns that were
    guarding it.
    """
    if not step.requires_spawn_id or not step.trigger_system_id:
        return
    from ..navigation import _remove_bounty_spawn as _rbs
    _rbs(ctx, f"{step.requires_spawn_id}_wreck", step.trigger_system_id)
    _remove_quest_spawn_group(ctx, step)


def complete_step_by_type(ctx, objective_type: str) -> bool:
    """Complete the first available/active step matching ``objective_type``.

    Generic hook used by dungeon-extension interactions (e.g. the Floor 5
    data terminal completes the ``"prison"`` objective). Returns True when
    a step was completed. No-op when no such step is live.
    """
    _step_id = _active_objective_step(ctx, objective_type)
    if _step_id is None:
        return False
    _step = find_main_quest_step(_step_id)
    _result = complete_step(ctx, _step_id)
    if _result:
        show_step_readout(ctx, _step)
    return _result


def maybe_complete_visit(ctx, npc_id: str) -> bool:
    """Complete an active visit step when the player talks to the expert NPC."""
    _step_id = _active_objective_step(ctx, "visit", npc_id=npc_id)
    if _step_id is None:
        return False
    _step = find_main_quest_step(_step_id)
    _result = complete_step(ctx, _step_id)
    if _result:
        # A gated step's flavor is presented by the gate popup that
        # follows the trigger (maybe_continue_chain); showing a readout
        # too would present the same text twice (playtest v15).
        if not (_step.wait_days > 0 and _step.completion_flavor):
            show_step_readout(ctx, _step)
    return _result


def maybe_complete_bounty(ctx, defeated_spawn_ids) -> bool:
    """Complete an active bounty step whose quest-tagged BountySpawn was defeated."""
    for _spawn_id in (defeated_spawn_ids or ()):
        _step_id = _active_objective_step(ctx, "bounty", spawn_id=_spawn_id)
        if _step_id is None:
            continue
        if not complete_step(ctx, _step_id):
            return False
        _step = find_main_quest_step(_step_id)
        # Show the quest readout popup with completion flavor + next-step guidance.
        show_step_readout(ctx, _step)
        _remove_quest_spawn_group(ctx, _step)
        return True
    return False


def fail_smuggle_step(ctx, active) -> bool:
    """Reset a smuggle step whose crate was confiscated or abandoned."""
    _step_id = getattr(active, "main_quest_step_id", "")
    if not _step_id:
        return False
    if step_status(ctx, _step_id) != STATUS_ACTIVE:
        return False
    _step = find_main_quest_step(_step_id)
    from ..data.trade_goods import display_name as _good_name
    _good = _good_name(_step.smuggle_good_id)
    ctx.main_quest_progress[_step_id] = STATUS_AVAILABLE
    if _step.smuggle_hot:
        # Contraband (bar chain): the giver NPC re-offers the crate
        # via their quest dialogue option.
        ctx.log.add_colored(
            t_get("runtime.smuggle_lost_log"),
            message_log.COLOR_IMPORTANT_EVENT,
        )
        return True
    # Non-contraband payload (lab/militia/merchant): story-required
    # mission cargo auto-reloads so the chain never strands the
    # player with a live step and no delivery target.
    if _trigger_smuggle_crate(ctx, _step):
        ctx.log.add_colored(
            t_get("runtime.smuggle_resecured_log").format(good=_good),
            message_log.COLOR_IMPORTANT_EVENT,
        )
    return True
