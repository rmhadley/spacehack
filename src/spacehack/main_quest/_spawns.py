"""Main quest spawn management: quest-tagged bounty/salvage spawns."""

from __future__ import annotations

from ..data.main_quest import find_main_quest_step
from ._core import STATUS_ACTIVE, STATUS_AVAILABLE


def ensure_quest_spawns(ctx, system_id: str) -> bool:
    """Create quest-tagged bounty spawns for live bounty steps targeting system_id."""
    _created = False
    for _step_id, _st in list(ctx.main_quest_progress.items()):
        if _st not in (STATUS_AVAILABLE, STATUS_ACTIVE):
            continue
        try:
            _step = find_main_quest_step(_step_id)
        except KeyError:
            continue
        if _step.objective_type != "bounty" or not _step.requires_spawn_id:
            continue
        if _step.trigger_system_id != system_id or not _step.bounty_enemy_id:
            continue
        _spawns = ctx.bounty_spawns.setdefault(system_id, [])
        if any(_bs.spawn_id == _step.requires_spawn_id for _bs in _spawns):
            continue
        from ..data.solar_systems import find_solar_system as _fss
        from ..navigation import _pick_bounty_spawn_pos as _pick
        try:
            _system = _fss(system_id)
        except KeyError:
            continue
        _used = frozenset((_bs.pos.x, _bs.pos.y) for _bs in _spawns)
        _pos = _pick(_system, used_positions=_used)
        if _pos is None:
            continue
        from ..game_context import BountySpawn
        _spawns.append(BountySpawn(
            spawn_id=_step.requires_spawn_id,
            enemy_id=_step.bounty_enemy_id,
            pos=_pos,
            comms_warning_range=12,
        ))
        _created = True
    return _created
