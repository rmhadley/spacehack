"""Main quest spawn management: quest-tagged bounty/salvage spawns."""

from __future__ import annotations

from .. import world
from ._core import STATUS_ACTIVE, STATUS_AVAILABLE, _iter_known_steps
from .handlers import handler_for


def _quest_spawn_pos(ctx, step, system_id: str, spawns):
    """Pick a free spawn position + system for step's quest-tagged group.

    Returns ``(system, pos)`` or ``None`` when the leader spawn already
    exists, the system is unknown, or no spawn position is available.
    """
    if any(_bs.spawn_id == step.requires_spawn_id for _bs in spawns):
        return None
    from ..data.solar_systems import find_solar_system as _fss
    from ..navigation import _pick_bounty_spawn_pos as _pick
    try:
        _system = _fss(system_id)
    except KeyError:
        return None
    _used = frozenset((_bs.pos.x, _bs.pos.y) for _bs in spawns)
    _pos = _pick(_system, used_positions=_used)
    if _pos is None:
        return None
    return _system, _pos


def _quest_leader_spawn(step, pos):
    """The leader BountySpawn for step's group, or None if it has no leader."""
    if not step.bounty_enemy_id:
        return None
    from ..game_context import BountySpawn
    return BountySpawn(
        spawn_id=step.requires_spawn_id,
        enemy_id=step.bounty_enemy_id,
        pos=pos,
        comms_warning_range=12,
    )


def _quest_escort_spawns(step, system, pos) -> list:
    """Escort BountySpawns for step's group (one per ``bounty_escort_ids``)."""
    from ..game_context import BountySpawn
    _escort_offsets = [(2, 0), (-2, 0), (0, 2), (0, -2), (2, 2)]
    _spawns = []
    for _ei, _enemy_id in enumerate(step.bounty_escort_ids):
        if _ei >= len(_escort_offsets):
            break
        _ox, _oy = _escort_offsets[_ei]
        _epos = world.Position(pos.x + _ox, pos.y + _oy)
        if 0 <= _epos.x < system.width and 0 <= _epos.y < system.height:
            _spawns.append(BountySpawn(
                spawn_id=f"{step.requires_spawn_id}_esc_{_ei}",
                enemy_id=_enemy_id,
                pos=_epos,
                squad_group_id=step.requires_spawn_id,
                comms_warning_range=0,
            ))
    return _spawns


def _quest_salvage_wreck(step, system, pos):
    """The boardable derelict-wreck BountySpawn for a salvage step, or None."""
    if not step.salvage_wreck_enemy_id or not step.salvage_layout_id:
        return None
    from ..game_context import BountySpawn
    return BountySpawn(
        spawn_id=f"{step.requires_spawn_id}_wreck",
        enemy_id=step.salvage_wreck_enemy_id,
        pos=world.Position(min(pos.x + 5, system.width - 1), pos.y),
        comms_warning_range=0,
        salvage_wreck=True,
    )


def _create_quest_spawn_group(
    ctx,
    step,
    system_id: str,
    *,
    with_wreck: bool,
) -> bool:
    """Create the leader + escort (+ optional wreck) spawns for a live step.

    Shared by the bounty and salvage handlers so the leader/escort placement
    is not duplicated. Returns True once the creation block is reached (the
    caller ignores the value — behaviour mirrors the pre-refactor loop).
    """
    _spawns = ctx.bounty_spawns.setdefault(system_id, [])
    _placed = _quest_spawn_pos(ctx, step, system_id, _spawns)
    if _placed is None:
        return False
    _system, _pos = _placed
    _leader = _quest_leader_spawn(step, _pos)
    if _leader is not None:
        _spawns.append(_leader)
    _spawns.extend(_quest_escort_spawns(step, _system, _pos))
    if with_wreck:
        _wreck = _quest_salvage_wreck(step, _system, _pos)
        if _wreck is not None and not any(
            _bs.spawn_id == _wreck.spawn_id for _bs in _spawns
        ):
            _spawns.append(_wreck)
    return True


def _ensure_bounty_spawns(ctx, step, system_id: str) -> bool:
    """Create the leader + escort spawns for a live bounty step.

    Only the leader triggers step completion; escorts are bonus kills.
    """
    return _create_quest_spawn_group(ctx, step, system_id, with_wreck=False)


def _ensure_salvage_spawns(ctx, step, system_id: str) -> bool:
    """Create the bounty enemies guarding the derelict PLUS a non-combatant
    salvage wreck (boardable derelict) whose interior holds the quest loot."""
    return _create_quest_spawn_group(ctx, step, system_id, with_wreck=True)


def ensure_quest_spawns(ctx, system_id: str) -> bool:
    """Create quest-tagged bounty spawns for live bounty/salvage steps
    targeting system_id.

    Dispatch is data-driven: only steps whose objective handler exposes an
    ``ensure_spawns`` hook (bounty / salvage) are considered.
    """
    _created = False
    for _step_id, _st, _step in _iter_known_steps(ctx):
        if _st not in (STATUS_AVAILABLE, STATUS_ACTIVE):
            continue
        _handler = handler_for(_step.objective_type)
        if _handler is None or _handler.ensure_spawns is None:
            continue
        if not _step.requires_spawn_id:
            continue
        if _step.trigger_system_id != system_id:
            continue
        if _handler.ensure_spawns(ctx, _step, system_id):
            _created = True
    return _created
