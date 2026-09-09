"""Space-combat kill resolution: entity pop, death animation, loot,
and defeat bookkeeping.

Extracted from ``_rules_space`` (ratchet split); the functions take
the encounter ``state`` explicitly instead of reading the module
global. ``_rules_space.on_kill`` remains the rules interface.
"""

from __future__ import annotations

from typing import Any

from .. import world
from ._types import EnemyInstance, SpaceCombatState


def pop_dead_entity(
    state: SpaceCombatState, game_map: world.GameMap, enemy: EnemyInstance,
) -> Any:
    """Remove the killed enemy from the map and return its entity."""
    _dead_ent = None
    for _i, _inst in enumerate(state.enemy_insts):
        if _inst is enemy:
            if _i in state.enemy_ents:
                _dead_ent = state.enemy_ents.pop(_i)
            break
    if _dead_ent is not None and _dead_ent in game_map.entities:
        game_map.entities.remove(_dead_ent)
    return _dead_ent


def _animate_kill_explosion(
    state: SpaceCombatState, ctx, game_map: world.GameMap,
    enemy: EnemyInstance,
) -> None:
    """Play the death explosion animation for a killed enemy ship."""
    from ._animations import _animate_explosion
    from ._rules_space import _build_hit_chances, _calc_camera, _calc_dodge_bonus

    _cam_x, _cam_y = _calc_camera()
    _hit_chances = _build_hit_chances(enemy)
    _evade = _calc_dodge_bonus(
        state.player_state.get("cells_moved_this_turn", 0),
        int(state.player_state.get("piloting", 0) * 0.5),
    )
    _animate_explosion(
        state.console, ctx, game_map,
        enemy.pos,
        cam_x=_cam_x, cam_y=_cam_y,
        view_w=state.view_w, view_h=state.view_h,
        player_state=state.player_state,
        enemies=state.enemy_insts,
        target_idx=state.target_idx,
        log=state.log,
        weapon_list=tuple(state.weapons_list),
        active_weapons=state.active_weapons,
        evade_bonus=_evade,
        hit_chances=_hit_chances,
    )


def _spawn_heist_loot(
    state: SpaceCombatState, ctx, game_map: world.GameMap,
    enemy: EnemyInstance, dead_ent: Any,
) -> None:
    """Spawn mission-specific intercept cargo at the wreck, if any."""
    _m = heist_cargo_mission(ctx, dead_ent)
    if _m is None:
        return
    from .. import message_log as _ml
    _good_id = _m.heist_target_good_id
    _loot_ent = world.Entity(
        char='%', fg=(0, 255, 255),
        pos=enemy.pos,
        name=f'Mission Cargo: {_good_id.replace("_", " ").title()}',
        width=1, height=1,
        loot_data={"good_id": _good_id, "quantity": 1},
    )
    # Mission-specific flag — set post-construction (not a dataclass
    # field), same pattern as bounty_spawn_id / heist_spawn_id on
    # spawn entities. Read by trade.open_loot_pickup via getattr.
    _loot_ent.heist_mission = True
    _loot_ent.heist_mission_id = _m.mission_id
    game_map.entities.append(_loot_ent)
    state.log.add_colored(
        f'Intercept: {_good_id.replace("_", " ").title()} salvaged from wreckage! Collect it to complete the mission.',
        _ml.COLOR_IMPORTANT_EVENT,
    )


def remove_procedural_squad(ctx, dead_ent: Any) -> None:
    """Drop a killed procedural-squad spawn from the system's spawn list."""
    if dead_ent is None:
        return
    _mid = getattr(dead_ent, 'procedural_squad_id', None)
    _nid = getattr(dead_ent, 'npc_ship_id', None)
    if not (_mid and _nid):
        return
    from .. import solar_system as _ss
    _sys_id = _ss.current_solar_system_id
    _spawns = ctx.procedural_spawns.get(_sys_id, [])
    for _i, _sp in enumerate(_spawns):
        if _sp.squad_id == _mid and _sp.npc_id == _nid:
            _spawns.pop(_i)
            break


def mark_static_spawn_defeated(ctx, dead_ent: Any) -> None:
    """Tombstone a killed STATIC spawn (system.enemies) so the next
    map build doesn't re-stamp it (doc 41: a defeated picket stays
    dead across save/load and re-entry). Non-static kills match no
    spawn row and record nothing; fakes without the ledger skip."""
    _ledger = getattr(ctx, 'defeated_static_spawns', None)
    if _ledger is None or dead_ent is None:
        return
    _nid = getattr(dead_ent, 'npc_ship_id', '')
    if not _nid:
        return
    from .. import solar_system as _ss
    _system = _ss.current_system()
    for _spawn in getattr(_system, 'enemies', ()) or ():
        if (_spawn.enemy_id == _nid
                and _spawn.pos.x == dead_ent.pos.x
                and _spawn.pos.y == dead_ent.pos.y):
            from ..solar_system import static_spawn_key as _key
            _ledger.add(_key(_system, _spawn))
            return


def _record_defeat(cr, ctx, dead_ent: Any) -> None:
    """Append the kill to the encounter result and drop the spawn."""
    if dead_ent is not None:
        _bid = getattr(dead_ent, 'bounty_spawn_id', None)
        _hid = getattr(dead_ent, 'heist_spawn_id', None)
        # Intercept missions use bounty_spawn_id for spawn lifecycle but
        # must NOT auto-complete on kill — they complete on delivery.
        if _bid is not None and _hid is None:
            cr.defeated_bounty_ids.append(_bid)
        if _hid is not None:
            cr.defeated_heist_ids.append(_hid)
    remove_procedural_squad(ctx, dead_ent)
    # Quest guard patrols: tombstone the spawn record so the dead patrol
    # isn't re-stamped on the next system entry (kill farm).
    from ..main_quest import mark_quest_guard_defeated as _mark_guard
    _mark_guard(ctx, dead_ent)
    # Static system spawns (the Line's pickets): tombstone the same way.
    mark_static_spawn_defeated(ctx, dead_ent)


def record_kill_pass(cr, ctx, spec, name: str, spec_id: str,
                     dead_ent: Any) -> None:
    """The shared kill-core: XP, counters, defeat record (doc 40 6d).

    Everything a kill books except the exterior loot drop, which is
    the caller's distinction: ``_finalize_kill`` scatters it at the
    death position; a capture consume suppresses it (the loot rides
    the interior). ``name``/``spec_id`` come from the enemy instance
    on the kill path, the boarded spec at the consume site."""
    from ..data.ships import find_ship as _find_ship_cat
    from ..xp import add_xp as _add_xp
    if spec is not None:
        try:
            _sc = _find_ship_cat(spec.ship_id)
            _add_xp(ctx, _sc.base_hull * 2)
        except (KeyError, ImportError):
            pass
    if hasattr(ctx, 'player_counters'):
        ctx.player_counters.total_kills += 1
    cr.defeated_names.append(name)
    cr.defeated_spec_ids.append(spec_id)
    _record_defeat(cr, ctx, dead_ent)


def heist_cargo_mission(ctx, dead_ent: Any):
    """The intercept mission whose target is this entity, or None.

    Shared by the kill path (exterior cargo drop) and the capture
    consume (cargo rides the interior): matched by the entity's
    ``heist_spawn_id`` against the mission's ``bounty_spawn_id``,
    requiring a ``heist_target_good_id``."""
    _heist_id = getattr(dead_ent, 'heist_spawn_id', None) \
        if dead_ent is not None else None
    if _heist_id is None:
        return None
    for _m in getattr(ctx, 'player_active_missions', []):
        if getattr(_m, 'bounty_spawn_id', None) != _heist_id:
            continue
        if not getattr(_m, 'heist_target_good_id', ''):
            break
        return _m
    return None


def _finalize_kill(
    state: SpaceCombatState, ctx, game_map: world.GameMap,
    enemy: EnemyInstance, dead_ent: Any,
) -> None:
    """Spawn loot, grant XP, and record defeat bookkeeping for a kill."""
    from ._actions import _spawn_loot_drops

    _correct_spec = next(
        (_sp for _sp in state.enemy_specs if getattr(_sp, 'id', None) == enemy.spec_id),
        state.enemy_specs[0] if state.enemy_specs else None,
    )
    if _correct_spec is not None:
        _spawn_loot_drops(game_map, enemy.pos, _correct_spec)
    record_kill_pass(state.cr, ctx, _correct_spec, enemy.name,
                     enemy.spec_id, dead_ent)


def on_kill(
    state: SpaceCombatState, game_map: world.GameMap,
    enemy: EnemyInstance, ctx,
) -> None:
    _dead_ent = pop_dead_entity(state, game_map, enemy)
    _animate_kill_explosion(state, ctx, game_map, enemy)
    _spawn_heist_loot(state, ctx, game_map, enemy, _dead_ent)
    _finalize_kill(state, ctx, game_map, enemy, _dead_ent)
