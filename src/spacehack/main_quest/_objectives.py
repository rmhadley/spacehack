"""Main quest objectives: delve, visit, bounty, smuggle delivery hooks."""

from __future__ import annotations

from ..data.main_quest import find_main_quest_step, main_quest_step_after
from ._core import (
    STATUS_ACTIVE,
    STATUS_AVAILABLE,
    step_status,
    complete_step,
    _smuggle_crate_held,
    _trigger_smuggle_crate,
    _active_objective_step,
)
from .. import message_log


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
    _next_step = main_quest_step_after(
        _step.id, chain=ctx.main_quest_chain,
    )
    if (_next_step is not None
            and _next_step.id in ctx.main_quest_gate):
        _what_next = (
            f"The {_next_step.chain.capitalize()} will contact "
            "you when they're ready for the next step. "
            "Check your quest log (Q) for updates."
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
    if _step.objective_type not in ("delve", "salvage"):
        return False
    _owned = ctx.player_owned_ship
    if _owned is not None:
        for _gid, _qty in goods:
            _owned.inventory[_gid] = _owned.inventory.get(_gid, 0) + _qty
    _result = complete_step(ctx, _step_id)
    # Salvage wrecks: remove the derelict BountySpawn so it doesn't
    # respawn on re-entry.  The exit handler (__main__.py) removes
    # the wreck entity from space_map; this removes the spawn record.
    if _result and _step.objective_type == "salvage" and _step.requires_spawn_id:
        _wreck_id = f"{_step.requires_spawn_id}_wreck"
        if _step.trigger_system_id:
            from ..navigation import _remove_bounty_spawn as _rbs
            _rbs(ctx, _wreck_id, _step.trigger_system_id)
            # Also remove the leader + escort bounty spawns (they
            # were guarding the wreck; quest is complete now).
            _rbs(ctx, _step.requires_spawn_id, _step.trigger_system_id)
            _esc_prefix = f"{_step.requires_spawn_id}_esc_"
            _spawns = ctx.bounty_spawns.get(_step.trigger_system_id, [])
            for _esc_bs in list(_spawns):
                if _esc_bs.spawn_id.startswith(_esc_prefix):
                    _rbs(ctx, _esc_bs.spawn_id, _step.trigger_system_id)
    if _result:
        _next = main_quest_step_after(
            _step_id, chain=ctx.main_quest_chain,
        )
        if (_next is not None
                and _next.objective_type == "smuggle"
                and step_status(ctx, _next.id) == STATUS_AVAILABLE
                and not _smuggle_crate_held(ctx, _next.id)):
            _trigger_smuggle_crate(ctx, _next)
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
        if _step.trigger_system_id:
            from ..navigation import _remove_bounty_spawn as _rbs
            _rbs(ctx, _spawn_id, _step.trigger_system_id)
            # Also clean up any escort spawns (derived IDs like
            # ``mer_consortium_leader_esc_0``) left behind when
            # the leader was killed.
            _esc_prefix = f"{_step.requires_spawn_id}_esc_"
            _spawns = ctx.bounty_spawns.get(_step.trigger_system_id, [])
            for _esc_bs in list(_spawns):
                if _esc_bs.spawn_id.startswith(_esc_prefix):
                    _rbs(ctx, _esc_bs.spawn_id, _step.trigger_system_id)
        return True
    return False


def maybe_complete_smuggle_delivery(ctx, active) -> bool:
    """Complete a smuggle step whose hot crate was delivered via the mission DELIVER flow."""
    _step_id = getattr(active, "main_quest_step_id", "")
    if not _step_id:
        return False
    if step_status(ctx, _step_id) not in (STATUS_AVAILABLE, STATUS_ACTIVE):
        return False
    _step = find_main_quest_step(_step_id)
    if _step.objective_type != "smuggle":
        return False
    return complete_step(ctx, _step_id)


def fail_smuggle_step(ctx, active) -> bool:
    """Reset a smuggle step whose crate was confiscated or abandoned."""
    _step_id = getattr(active, "main_quest_step_id", "")
    if not _step_id:
        return False
    if step_status(ctx, _step_id) != STATUS_ACTIVE:
        return False
    _step = find_main_quest_step(_step_id)
    _good = _step.smuggle_good_id.replace('_', ' ')
    ctx.main_quest_progress[_step_id] = STATUS_AVAILABLE
    if _step.smuggle_hot:
        # Contraband (bar chain): the giver NPC re-offers the crate
        # via their quest dialogue option.
        ctx.log.add_colored(
            "The crate is lost. Talk to the quest giver for another "
            "one.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        return True
    # Non-contraband payload (lab/militia/merchant): story-required
    # mission cargo auto-reloads so the chain never strands the
    # player with a live step and no delivery target.
    if _trigger_smuggle_crate(ctx, _step):
        ctx.log.add_colored(
            f"The {_good} is re-secured in your mission hold.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
    return True
