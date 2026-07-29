"""Player weapon fire — pre-flight checks, animation, damage, loot.

Extracted from ``_loop.py`` during Phase 3 of the combat loop
refactoring. Single entry point ``_fire_weapons`` that validates
requirements, fires all active weapons in sequence, animates shots,
resolves damage, and spawns loot on kill.

Also exports ``_check_fire_ready`` used by the event handler for
pre-flight validation.
"""

from __future__ import annotations

from typing import Any

from .. import world
from ..engine import RNG
from ..data.weapons import find_weapon
from ..message_log import COLOR_PLAYER_ACTION, COLOR_COMBAT_EVENT

from ._types import EnemyInstance
from ._stats import (
    calc_hit_chance,
    _calc_dodge_bonus,
    _distance,
)
from ._actions import resolve_damage
from ._animations import (
    _animate_laser_shot,
    _animate_explosion,
)


def _p_log(msg: str, log) -> None:
    """Log a player-facing combat event (green)."""
    log.add_colored(msg, COLOR_PLAYER_ACTION)


def _c_log(msg: str, log) -> None:
    """Log a system combat event (gold)."""
    log.add_colored(msg, COLOR_COMBAT_EVENT)


def _check_fire_ready(
    player_state: dict,
    weapon_id: str,
    target_idx: int,
    enemies: list[EnemyInstance],
) -> tuple[bool, str]:
    """Quick pre-flight check before firing.

    Returns (ok, reason_message). Called for each weapon in the
    active list to validate target availability and resource cost.
    """
    if not (0 <= target_idx < len(enemies) and enemies[target_idx].alive):
        return False, "No valid target."
    from ._actions import can_afford_action as _caa
    return _caa(player_state, weapon_id)


def _fire_weapons(
    console,
    context,
    game_map: world.GameMap,
    player_state: dict,
    enemy_insts: list[EnemyInstance],
    enemy_specs: list,
    _enemy_ents: dict[int, Any],
    target_idx: int,
    log,
    weapons_list: list,
    active_weapons: list,
    _weapon_hit_chances: dict,
    _evade_bonus: int,
    view_w: int,
    view_h: int,
    _calc_cam,
    _defeated_spec_ids: list[str],
    _defeated_names: list[str],
    _closest_enemy,
    flee_chance: int,
) -> None:
    """Fire all active weapons at the current target.

    Validates combined requirements (AP, power, ammo), then
    iterates each active weapon — animating a shot, resolving
    damage, handling kills (death log, entity removal, explosion,
    loot drop), and deducting per-weapon costs. Mutates
    ``player_state``, ``enemy_insts``, ``_enemy_ents``,
    ``_defeated_spec_ids``, and ``game_map.entities`` in place.
    """
    # Collect all active weapon IDs
    _fire_list = [
        weapons_list[wi] for wi, wa in enumerate(active_weapons)
        if wa and wi < len(weapons_list)
    ]
    if not _fire_list:
        _p_log("No active weapons to fire.", log)
        return
    if not (0 <= target_idx < len(enemy_insts) and enemy_insts[target_idx].alive):
        _p_log("No valid target.", log)
        return

    # Check combined requirements: max AP cost among selected weapons,
    # total power cost, and ammo availability.
    _max_ap = 0
    _total_power = 0
    _all_ok = True
    for _fwid in _fire_list:
        _ok, _reason = _check_fire_ready(
            player_state, _fwid, target_idx, enemy_insts,
        )
        if not _ok:
            _p_log(f"{_fwid}: {_reason}", log)
            _all_ok = False
            break
        _fws = find_weapon(_fwid)
        _max_ap = max(_max_ap, _fws.ap_cost)
        _total_power += _fws.power_cost
    if not _all_ok:
        return
    # Fail-fast: check combined power cost before firing.
    if player_state["power_pool"] < _total_power:
        _p_log(f"Not enough power: need {_total_power}, have {player_state['power_pool']}.", log)
        return

    # Fire each active weapon in sequence.
    _target_enemy = enemy_insts[target_idx]
    _target_pos = _target_enemy.pos
    for _fwid in _fire_list:
        if not _target_enemy.alive:
            break
        _fws = find_weapon(_fwid)
        # Calculate hit chance (respect target state).
        _player_dist = _distance(player_state["pos"], _target_pos)
        _target_dodge = _calc_dodge_bonus(
            _target_enemy.cells_moved_this_turn,
            int(_target_enemy.pilot_piloting * 0.5),
        )
        _hit_chance = calc_hit_chance(
            _fwid, player_state["gunnery"],
            _player_dist, _target_dodge,
        )
        _is_hit = RNG.randint(1, 100) <= _hit_chance

        _cam_x, _cam_y = _calc_cam()
        _animate_laser_shot(
            console, context, game_map,
            player_state["pos"], _target_pos,
            is_hit=_is_hit,
            cam_x=_cam_x, cam_y=_cam_y,
            view_w=view_w, view_h=view_h,
            player_state=player_state,
            enemies=enemy_insts,
            target_idx=target_idx,
            log=log,
            weapon_list=tuple(weapons_list),
            active_weapons=active_weapons,
            evade_bonus=_evade_bonus,
            hit_chances=_weapon_hit_chances,
            flee_chance=flee_chance,
        )

        if _is_hit:
            _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
                _fwid,
                _target_enemy.hull,
                _target_enemy.shields,
                target_pilot_piloting=_target_enemy.pilot_piloting,
            )
            _target_enemy.shields = max(0, _target_enemy.shields - _sdmg)
            _target_enemy.hull = _fh
            _verb = "glancing hit" if _is_glancing else "hits"
            _p_log(f"{_fwid} {_verb} {_target_enemy.name} for {_dmg}!", log)
            if _fh <= 0:
                _target_enemy.alive = False
                _defeated_spec_ids.append(_target_enemy.spec_id)
                _defeated_names.append(_target_enemy.name)
                _c_log(f"{_target_enemy.name} destroyed!", log)
                # Remove dead entity from the game map
                from ._loop import _remove_dead_entity as _rde
                _rde(game_map, _enemy_ents, target_idx)
                # Explosion at target position
                _cam_x, _cam_y = _calc_cam()
                _animate_explosion(
                    console, context, game_map,
                    _target_pos,
                    cam_x=_cam_x, cam_y=_cam_y,
                    view_w=view_w, view_h=view_h,
                    player_state=player_state,
                    enemies=enemy_insts,
                    target_idx=target_idx,
                    log=log,
                    weapon_list=tuple(weapons_list),
                    active_weapons=active_weapons,
                    evade_bonus=_evade_bonus,
                    hit_chances=_weapon_hit_chances,
                    flee_chance=flee_chance,
                )
                # Loot drop: find correct spec by matching spec_id
                _correct_spec = next(
                    (_sp for _sp in enemy_specs if getattr(_sp, 'id', None) == _target_enemy.spec_id),
                    enemy_specs[0] if enemy_specs else None,
                )
                if _correct_spec is not None:
                    from ._loop import _spawn_loot_drops as _sld
                    _sld(game_map, _target_pos, _correct_spec)
        else:
            _p_log(f"{_fwid} misses {_target_enemy.name}!", log)
        # Deduct per-weapon costs
        if _fws.slot_type == "energy":
            player_state["power_pool"] -= _fws.power_cost
        elif _fws.slot_type == "missile":
            old = player_state["weapon_ammo"][_fwid]
            player_state["weapon_ammo"][_fwid] = old - _fws.ammo_per_shot
    # Deduct combined AP (max cost among fired weapons)
    player_state["ap_remaining"] -= _max_ap
