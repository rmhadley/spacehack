"""Boardable wreck + derelict interior loading (split from
``game_interactions`` — the architecture ratchet's cohesive
extraction, doc 48 phase 4).

One responsibility: load the authored interior behind a boardable
wreck — the generic derelict, an active mission's salvage wreck, or a
main-quest wreck — stamping every ENEMY marker with the parent
planet's band and resolving role tokens through the pirate crew table
(doc 48 SETTLED 28/35: markers fix specs; the site's band sizes
stats/gear; wrecks attract pirate squatters). Every wreck interior is
hostile on entry (doc 48 SETTLED 3/38). Helpers that only this family
uses moved along.
"""

from __future__ import annotations

from . import main_quest as main_quest_module, solar_system as solar_system_module, world
from .game_flow import _first_walkable, _prep_cached_dungeon


def _parent_band(ctx) -> int:
    """The boarding site's band: the city planet's mission tier
    (city id == planet id at landing). Doc 48 SETTLED 35 — capture
    decks and wrecks size their crews by the parent planet."""
    from . import ground_scale
    from .data.planets import find_planet_spec as _fps
    try:
        return ground_scale.planet_band(
            _fps(getattr(ctx, "current_city_id", "")).mission_tier,
        )
    except KeyError:
        return 1




def _find_boarding_mission(state, wreck_sid):
    """Return the active mission whose salvage wreck matches wreck_sid."""
    if wreck_sid is None:
        return None
    for _am in state.player_active_missions:
        if getattr(_am, 'salvage_wreck_spawn_id', None) == wreck_sid:
            return _am
    return None



def _build_generic_derelict(ctx, blocker, npcspec, log):
    """The generic derelict interior: scout_a plus the site-pad roll
    (doc 42 phase 4). Returns (map, spawn, handled)."""
    from .digs import maybe_spawn_wreck_pad
    from .dungeon import load_layout as _load_layout
    try:
        _dungeon_map, _spawn = _load_layout('scout_a', loot_budget=npcspec.loot_budget, wreck_scatter=True, spawn_band=_parent_band(ctx), crew_faction='pirate', security_drones=getattr(npcspec, 'security_drones', 1.0))
    except (FileNotFoundError, ValueError):
        log.add("The derelict's interior is too damaged to explore.")
        return (None, None, True)
    maybe_spawn_wreck_pad(_dungeon_map)
    _dungeon_map.derelict_interior = True
    _dungeon_map.hostile_interior = True
    _despawn_blocker(ctx, blocker, npcspec)
    return (_dungeon_map, _spawn, False)



def _boardable_wreck_layout(state, blocker, npcspec):
    """Return (dungeon_map, spawn, is_reboard) for a boardable wreck."""
    ctx = state.ctx
    log = state.log
    from .dungeon import load_layout as _load_layout
    _wreck_sid = getattr(blocker, 'salvage_wreck_spawn_id', None)
    _mission = _find_boarding_mission(state, _wreck_sid)
    _dungeon_map = None
    _spawn = None
    _is_reboard = False
    if _wreck_sid is not None and _wreck_sid in ctx.interiors:
        _dungeon_map = ctx.interiors[_wreck_sid]
        _spawn = _prep_cached_dungeon(_dungeon_map)
        _is_reboard = True
    elif _mission is not None and _mission.salvage_layout_id:
        try:
            _dungeon_map, _spawn = _load_layout(_mission.salvage_layout_id, loot_budget=npcspec.loot_budget, component_good_id=_mission.heist_target_good_id, component_mission_id=_mission.mission_id, wreck_scatter=True, spawn_band=_parent_band(state.ctx), crew_faction='pirate', security_drones=getattr(npcspec, 'security_drones', 1.0))
        except (FileNotFoundError, ValueError):
            log.add("The derelict's interior is too damaged to explore.")
            return (None, None, False)
        _dungeon_map.wreck_spawn_id = _wreck_sid
        _dungeon_map.entry_spawn = _spawn
        _dungeon_map.hostile_interior = True
        ctx.interiors[_wreck_sid] = _dungeon_map
    elif _wreck_sid is not None and _wreck_sid.endswith('_wreck'):
        _dungeon_map, _spawn, _handled = _build_main_quest_wreck(ctx, npcspec, _wreck_sid, log)
        if _handled:
            return (None, None, False)
    if _dungeon_map is None and _mission is None and (not (_wreck_sid or '').endswith('_wreck')):
        _dungeon_map, _spawn, _handled = _build_generic_derelict(ctx, blocker, npcspec, log)
        if _handled:
            return (None, None, False)
    if _dungeon_map is None:
        log.add("The derelict's interior is too damaged to explore.")
        return (None, None, False)
    if _spawn is None:
        _spawn = _first_walkable(_dungeon_map)
    return (_dungeon_map, _spawn, _is_reboard)



def _build_main_quest_wreck(ctx, npcspec, wreck_sid, log):
    """Build a main-quest wreck layout; returns (map, spawn, handled)."""
    from .dungeon import load_layout as _load_layout
    _mq_spawn_id = wreck_sid[:-6]
    _mq_step = main_quest_module.find_salvage_step_for_spawn(ctx, _mq_spawn_id)
    _mq_ok = (
        _mq_step is not None
        and ctx.main_quest_progress.get(_mq_step.id) in ('available', 'active')
        and _mq_step.salvage_layout_id
    )
    if not _mq_ok:
        return (None, None, False)
    try:
        _dungeon_map, _spawn = _load_layout(_mq_step.salvage_layout_id, loot_budget=npcspec.loot_budget, wreck_scatter=True, spawn_band=_parent_band(ctx), crew_faction='pirate', security_drones=getattr(npcspec, 'security_drones', 1.0))
    except (FileNotFoundError, ValueError):
        log.add("The derelict's interior is too damaged to explore.")
        return (None, None, True)
    _lr = _pick_quest_loot_pos(_dungeon_map, _spawn)
    _mq_goods = list(_mq_step.delve_good_ids)
    if not _mq_goods:
        log.add('The derelict holds no quest data.')
        return (None, None, True)
    _place_quest_loot(_dungeon_map, _lr, _mq_step.id, _mq_goods)
    _dungeon_map.wreck_spawn_id = wreck_sid
    _dungeon_map.entry_spawn = _spawn
    _dungeon_map.hostile_interior = True
    ctx.interiors[wreck_sid] = _dungeon_map
    return (_dungeon_map, _spawn, False)



def _pick_quest_loot_pos(dungeon_map, spawn):
    """Pick a walkable tile adjacent to existing loot for quest placement."""
    _mq_candidates = []
    for _e in dungeon_map.entities:
        if getattr(_e, 'loot_data', None) is None:
            continue
        for _dy in (-2, 0, 2):
            for _dx in (-2, 0, 2):
                _nx = _e.pos.x + _dx
                _ny = _e.pos.y + _dy
                if 0 <= _nx < dungeon_map.width and 0 <= _ny < dungeon_map.height and dungeon_map.tiles[_ny][_nx].walkable and (not any((_oe.pos.x == _nx and _oe.pos.y == _ny for _oe in dungeon_map.entities))):
                    _mq_candidates.append((_nx, _ny))
    if not _mq_candidates:
        _mq_candidates = [(spawn.x, spawn.y)]
    from .engine import RNG as _RNG
    return _mq_candidates[_RNG.randint(0, len(_mq_candidates) - 1)]



def _place_quest_loot(dungeon_map, pos, step_id, goods):
    """Drop the quest component at pos and tag it with the step id."""
    from .data.trade_goods import find_trade_good as _ftg
    try:
        _gname = _ftg(goods[0][0]).name
    except (KeyError, ImportError):
        _gname = goods[0][0].replace('_', ' ').title()
    _mq_loot_name = f'Quest Component: {_gname}'
    from .loot_common import loot_fg
    _mq_payload = {'goods': goods}
    _mq_loot = world.Entity(char='%', fg=loot_fg(_mq_payload), pos=world.Position(pos[0], pos[1]), name=_mq_loot_name, width=1, height=1, loot_data=_mq_payload)
    _mq_loot.main_quest_step_id = step_id
    dungeon_map.entities.append(_mq_loot)



def _despawn_blocker(ctx, blocker, npcspec):
    """Remove a boarded scout wreck from the system and procedural spawns."""
    try:
        ctx.game_map.entities.remove(blocker)
        _sys_id = solar_system_module.current_solar_system_id
        if _sys_id in ctx.procedural_spawns:
            ctx.procedural_spawns[_sys_id] = [_ps for _ps in ctx.procedural_spawns[_sys_id] if _ps.npc_id != npcspec.id or _ps.pos != blocker.pos]
    except (ValueError, AttributeError):
        pass

