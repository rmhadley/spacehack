"""Main quest spawn management: quest-tagged bounty/salvage spawns."""

from __future__ import annotations

from .. import world
from ..data.main_quest import find_main_quest_step
from ._core import STATUS_ACTIVE, STATUS_AVAILABLE


def ensure_quest_spawns(ctx, system_id: str) -> bool:
    """Create quest-tagged bounty spawns for live bounty steps targeting system_id.

    When the step specifies ``bounty_escort_ids``, additional non-leader
    spawns (escorts) are created alongside the leader.  Only the leader's
    spawn (``requires_spawn_id``) triggers step completion via
    :func:`maybe_complete_bounty`.
    """
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

        # --- Leader spawn (triggers step completion) ---
        _spawns.append(BountySpawn(
            spawn_id=_step.requires_spawn_id,
            enemy_id=_step.bounty_enemy_id,
            pos=_pos,
            comms_warning_range=12,
        ))

        # --- Escort spawns (bonus enemies — do NOT trigger completion) ---
        _escort_offsets = [(2, 0), (-2, 0), (0, 2), (0, -2), (2, 2)]
        for _ei, _enemy_id in enumerate(_step.bounty_escort_ids):
            if _ei >= len(_escort_offsets):
                break
            _ox, _oy = _escort_offsets[_ei]
            _epos = world.Position(_pos.x + _ox, _pos.y + _oy)
            if 0 <= _epos.x < _system.width and 0 <= _epos.y < _system.height:
                _spawns.append(BountySpawn(
                    spawn_id=f"{_step.requires_spawn_id}_esc_{_ei}",
                    enemy_id=_enemy_id,
                    pos=_epos,
                    comms_warning_range=0,
                ))
        _created = True
    return _created
