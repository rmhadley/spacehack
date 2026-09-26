"""Mission intake — accepting a board mission and wiring its spawns.

Extracted from ``game_interactions`` (the size-ratchet split, doc 54
phase 2's touch): the game-loop side of mission acceptance —
committing an accepted offering onto the loop state and preparing the
bounty/wreck spawns the mission needs. The mission domain logic lives
in :mod:`spacehack.mission`; this module owns the FLOW (state writes,
spawn placement).
"""

from __future__ import annotations

from . import mission as mission_module
from . import world
from .data import solar_systems as solar_systems_module
from .game_context import BountySpawn
from .navigation import _pick_bounty_spawn_pos
from .time import add_days_to_date

import time


def _accept_mission(state, npc_obj, picked, board, log):
    """Commit an accepted mission and set up its bounty/wreck spawns."""
    ctx = state.ctx
    mission_module.board_remove(board, picked.id)
    _bounty_spawn_id, _wreck_spawn_id, _spawn_ok = _prepare_mission_spawns(ctx, picked, board, log)
    if not _spawn_ok:
        return None
    _dl_days = getattr(picked, 'deadline_days', 0)
    _deadline = None
    if _dl_days > 0:
        _deadline = add_days_to_date(ctx.time_day, ctx.time_month, ctx.time_year, _dl_days)
    _is_proc = picked.id in ctx.generated_missions
    _del_npc = picked.delivery_target_npc_id
    _del_planet = picked.delivery_target_planet_id
    _heist_good = getattr(picked, 'heist_target_good_id', None)
    if _heist_good is not None:
        _del_npc = npc_obj.id
        _del_planet = state.current_city_id
    _new_active = mission_module.ActiveMission(mission_id=picked.id, is_procedural=_is_proc, title=picked.title, required_cargo_size=picked.required_cargo_size, delivery_target_npc_id=_del_npc, delivery_target_planet_id=_del_planet, deadline_days=_dl_days, accept_day=ctx.time_day + (ctx.time_month - 1) * 30, time_deadline=_deadline, reward_credits=picked.reward_credits, reward_xp=picked.reward_xp, early_bonus_pct=picked.early_bonus_pct, bounty_spawn_id=_bounty_spawn_id, target_enemy_id=picked.target_enemy_id, target_system_id=picked.target_system_id, bounty_target_name=getattr(picked, 'bounty_target_name', None), bounty_target_squad_size=getattr(picked, 'bounty_target_squad_size', 1), bounty_target_loadout_pct=getattr(picked, 'bounty_target_loadout_pct', 0), bounty_wingmate_enemy_id=getattr(picked, 'bounty_wingmate_enemy_id', None), tier=picked.tier, heist_target_good_id=_heist_good, salvage_wreck_enemy_id=getattr(picked, 'salvage_wreck_enemy_id', None), salvage_layout_id=getattr(picked, 'salvage_layout_id', None), salvage_wreck_spawn_id=_wreck_spawn_id, is_smuggle=getattr(picked, 'is_smuggle', False), smuggle_good_id=getattr(picked, 'smuggle_good_id', None))
    mission_module.commit_accept_mission(picked, state.player_owned_ship, log)
    state.player_active_missions.append(_new_active)
    ctx.player_active_missions = state.player_active_missions

def _prepare_mission_spawns(ctx, picked, board, log):
    """Set up bounty/wreck spawns; returns (bounty_id, wreck_id, ok)."""
    _bounty_spawn_id = None
    _wreck_spawn_id = None
    if picked.target_enemy_id is None or picked.target_system_id is None:
        return (_bounty_spawn_id, _wreck_spawn_id, True)
    _bounty_spawn_id = f'bounty_{picked.id}_{int(time.time())}'
    _squad_size = getattr(picked, 'bounty_target_squad_size', 1)
    try:
        _target_sys = solar_systems_module.find_solar_system(picked.target_system_id)
        _used = frozenset(((_bs.pos.x, _bs.pos.y) for _bs in ctx.bounty_spawns.get(picked.target_system_id, [])))
        _spawn_pos = _pick_bounty_spawn_pos(_target_sys, used_positions=_used)
    except KeyError:
        return (_bounty_spawn_id, _wreck_spawn_id, True)
    if _spawn_pos is None:
        mission_module.board_return_static(board, picked.id)
        log.add(f'Cannot accept: {_target_sys.name} bounty system full. Clear an existing bounty first.')
        return (_bounty_spawn_id, _wreck_spawn_id, False)
    _wreck_spawn_id = _place_bounty_squad(ctx, picked, _target_sys, _spawn_pos, _bounty_spawn_id, _squad_size, log)
    return (_bounty_spawn_id, _wreck_spawn_id, True)

def _place_bounty_squad(ctx, picked, target_sys, spawn_pos, bounty_spawn_id, squad_size, log):
    """Place a bounty squad and any salvage wreck; returns the wreck id."""
    from .data.npc_ships import find_npc_ship as _bfns
    _wingmate_enemy_id = getattr(picked, 'bounty_wingmate_enemy_id', None) or picked.target_enemy_id
    _bounty_warning_range = 0
    try:
        _bounty_spec = _bfns(picked.target_enemy_id)
        _bounty_warning_range = max(12, _bounty_spec.detect_radius * 2)
    except (KeyError, ImportError):
        pass
    _heist_sid = None
    if getattr(picked, 'heist_target_good_id', None) is not None and getattr(picked, 'salvage_layout_id', None) is None:
        _heist_sid = bounty_spawn_id
    _bs = BountySpawn(spawn_id=bounty_spawn_id, enemy_id=picked.target_enemy_id, pos=spawn_pos, bounty_target_name=getattr(picked, 'bounty_target_name', None), squad_size=squad_size, loadout_pct=getattr(picked, 'bounty_target_loadout_pct', 0), comms_warning_range=_bounty_warning_range, heist_spawn_id=_heist_sid)
    if picked.target_system_id not in ctx.bounty_spawns:
        ctx.bounty_spawns[picked.target_system_id] = []
    ctx.bounty_spawns[picked.target_system_id].append(_bs)
    _wing_offsets = [(2, 0), (-2, 0), (0, 2), (0, -2), (2, 2)]
    for _wi in range(min(squad_size - 1, len(_wing_offsets))):
        _wox, _woy = _wing_offsets[_wi]
        _wpos = world.Position(spawn_pos.x + _wox, spawn_pos.y + _woy)
        if 0 <= _wpos.x < target_sys.width and 0 <= _wpos.y < target_sys.height:
            _wbs = BountySpawn(spawn_id=f'{bounty_spawn_id}_wing{_wi}', enemy_id=_wingmate_enemy_id, pos=_wpos, bounty_target_name=None, squad_size=squad_size, loadout_pct=0, squad_group_id=bounty_spawn_id, comms_warning_range=0)
            ctx.bounty_spawns[picked.target_system_id].append(_wbs)
    _squad_note = f' ({squad_size}-ship squad)' if squad_size > 1 else ''
    _wreck_spawn_id = None
    if getattr(picked, 'salvage_wreck_enemy_id', None) is not None:
        _wreck_spawn_id = f'wreck_{picked.id}_{int(time.time())}'
        _wreck_pos = world.Position(min(spawn_pos.x + 5, target_sys.width - 1), spawn_pos.y)
        _wbs = BountySpawn(spawn_id=_wreck_spawn_id, enemy_id=picked.salvage_wreck_enemy_id, pos=_wreck_pos, bounty_target_name=None, squad_size=1, loadout_pct=0, salvage_wreck=True)
        ctx.bounty_spawns[picked.target_system_id].append(_wbs)
        log.add(f'Salvage site marked in {target_sys.name}: wreck + {squad_size}-ship patrol.')
    else:
        log.add(f'Bounty target marked in {target_sys.name}.{_squad_note}')
    return _wreck_spawn_id
