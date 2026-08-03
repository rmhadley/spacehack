"""Main quest spawn management: quest-tagged bounty/salvage spawns."""

from __future__ import annotations

from .. import world
from ..data.main_quest import find_main_quest_step
from ._core import STATUS_ACTIVE, STATUS_AVAILABLE


def ensure_quest_spawns(ctx, system_id: str) -> bool:
    """Create quest-tagged bounty spawns for live bounty/salvage steps
    targeting system_id.

    For ``bounty`` steps: creates the leader spawn + any escort spawns
    (see ``bounty_escort_ids``).  Only the leader triggers completion.

    For ``salvage`` steps: creates the bounty enemies guarding the
    derelict PLUS a non-combatant salvage wreck (boardable derelict)
    whose interior contains the quest-tagged loot.
    """
    _created = False
    for _step_id, _st in list(ctx.main_quest_progress.items()):
        if _st not in (STATUS_AVAILABLE, STATUS_ACTIVE):
            continue
        try:
            _step = find_main_quest_step(_step_id)
        except KeyError:
            continue
        if _step.objective_type not in ("bounty", "salvage"):
            continue
        if not _step.requires_spawn_id:
            continue
        if _step.trigger_system_id != system_id:
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

        # --- Leader spawn ---
        _leader_id = _step.bounty_enemy_id or ""
        if _leader_id:
            _spawns.append(BountySpawn(
                spawn_id=_step.requires_spawn_id,
                enemy_id=_leader_id,
                pos=_pos,
                comms_warning_range=12,
            ))

        # --- Escort spawns ---
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

        # --- Salvage wreck (salvage objectives only) ---
        if (_step.objective_type == "salvage"
                and _step.salvage_wreck_enemy_id
                and _step.salvage_layout_id):
            _wreck_id = f"{_step.requires_spawn_id}_wreck"
            if not any(_bs.spawn_id == _wreck_id for _bs in _spawns):
                _wpos = world.Position(
                    min(_pos.x + 5, _system.width - 1),
                    _pos.y,
                )
                _spawns.append(BountySpawn(
                    spawn_id=_wreck_id,
                    enemy_id=_step.salvage_wreck_enemy_id,
                    pos=_wpos,
                    comms_warning_range=0,
                    salvage_wreck=True,
                ))
        _created = True
    return _created
