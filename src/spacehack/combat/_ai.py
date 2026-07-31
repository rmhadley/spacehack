"""Enemy AI — movement and fire logic for combat enemies.

Extracted from ``_loop.py`` during Phase 2 of the combat loop
refactoring. Single entry point ``_run_enemy_turn`` that iterates
all alive enemies, moves them toward the player, and fires when
in range.

Callers pass state explicitly rather than relying on closures so
the function is self-contained and testable.
"""

from __future__ import annotations

from typing import Any

from .. import world
from ..engine import RNG
from ..message_log import COLOR_ENEMY_ACTION, COLOR_COMBAT_EVENT

from ._types import EnemyInstance
from ._stats import (
    calc_hit_chance,
    calc_flee_chance,
    _calc_dodge_bonus,
    _distance,
)
from ._actions import (
    start_enemy_turn,
    resolve_damage,
)
from ._animations import (
    _animate_laser_shot,
    _animate_explosion,
    _render_anim_frame,
    _responsive_sleep,
)


def _e_log(msg: str, log) -> None:
    """Log an enemy-facing combat event (red)."""
    log.add_colored(msg, COLOR_ENEMY_ACTION)


def _c_log(msg: str, log) -> None:
    """Log a system combat event (gold)."""
    log.add_colored(msg, COLOR_COMBAT_EVENT)


def _run_enemy_turn(
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
    flee_attempts: int,
    view_w: int,
    view_h: int,
    _calc_cam,
    ctx = None,
) -> str | None:
    """Execute the AI turn for all alive enemies.

    Iterates each alive enemy, starting their turn and running
    their movement/fire loop. Returns ``"DEFEAT"`` if the player
    is destroyed, ``None`` otherwise. Mutates ``enemy_insts``,
    ``player_state``, and ``_enemy_ents`` in place.
    """
    for _ei in enemy_insts:
        if not _ei.alive:
            continue
        start_enemy_turn(_ei)

        # Find matching spec for this enemy via spec_id
        _esp = next(
            (_sp for _sp in enemy_specs if getattr(_sp, 'id', None) == _ei.spec_id),
            enemy_specs[0] if enemy_specs else None,
        )
        if _esp is None:
            continue

        # Cache entity-index lookup once per enemy so the while loop
        # doesn't re-scan enemy_insts per move step.
        _e_idx = next(
            (_j for _j, _je in enumerate(enemy_insts) if _je is _ei),
            -1,
        )

        # Compute closest alive enemy for flee chance display
        _alive = [e for e in enemy_insts if e.alive]
        _closest_enemy = min(
            _alive,
            key=lambda _e: _distance(player_state["pos"], _e.pos),
        )
        _flee_chance = calc_flee_chance(
            player_state["piloting"],
            _closest_enemy.pilot_piloting,
            player_state["hull"] / max(player_state["max_hull"], 1),
            _distance(player_state["pos"], _closest_enemy.pos),
            flee_attempts,
        )

        while _ei.ap_remaining > 0:
            _edist = _distance(
                player_state["pos"], _ei.pos,
            )
            _moved = False
            if _edist > _esp.ai_preferred_range:
                # A* path to player — navigates around obstacles
                _p_pos = player_state["pos"]
                _exclude = _enemy_ents.get(_e_idx) if _e_idx >= 0 else None
                _path = world.find_path(
                    (_ei.pos.x, _ei.pos.y),
                    {(_p_pos.x, _p_pos.y)},
                    game_map,
                    exclude_entity=_exclude,
                    max_steps=2000,
                )
                if _path:
                    _nx, _ny = _path[0]
                else:
                    _nx, _ny = _ei.pos.x, _ei.pos.y  # no path, stay put
                _blocked_by_other = any(
                    _oe is not _ei and _oe.alive
                    and _oe.pos.x == _nx and _oe.pos.y == _ny
                    for _oe in enemy_insts
                )
                if not _blocked_by_other and (
                    game_map.is_walkable(_nx, _ny)
                    and game_map.entity_at(_nx, _ny, exclude=None) is None
                ):
                    _ei.pos = world.Position(_nx, _ny)
                    _ei.cells_moved_this_turn += 1
                    _ei.ap_remaining -= 1
                    if _e_idx >= 0 and _e_idx in _enemy_ents:
                        _enemy_ents[_e_idx].pos = _ei.pos
                    _moved = True
                    # Render a frame so the player sees the enemy move
                    _cam_x, _cam_y = _calc_cam()
                    _render_anim_frame(
                        console, context, game_map,
                        _cam_x, _cam_y, view_w, view_h,
                        player_state, enemy_insts, target_idx, log,
                        weapon_list=tuple(weapons_list),
                        active_weapons=active_weapons,
                        evade_bonus=_evade_bonus,
                        hit_chances=_weapon_hit_chances,
                        flee_chance=_flee_chance,
                        player_mode="WAIT",
                    )
                    _responsive_sleep(0.05)

            if not _moved:
                if _ei.weapons:
                    _wid = _ei.weapons[0]
                    _dist = _distance(player_state["pos"], _ei.pos)
                    _dodge = _calc_dodge_bonus(
                        player_state.get("cells_moved_this_turn", 0),
                        int(player_state.get("piloting", 0) * 0.5),
                    )
                    _chance = calc_hit_chance(
                        _wid, _ei.pilot_gunnery, _dist, _dodge,
                    )
                    _e_hit = RNG.randint(1, 100) <= _chance
                    _ecx, _ecy = _calc_cam()
                    _animate_laser_shot(
                        console, context, game_map,
                        _ei.pos, player_state["pos"],
                        is_hit=_e_hit,
                        cam_x=_ecx, cam_y=_ecy,
                        view_w=view_w, view_h=view_h,
                        player_state=player_state,
                        enemies=enemy_insts,
                        target_idx=target_idx,
                        log=log,
                        weapon_list=tuple(weapons_list),
                        active_weapons=active_weapons,
                        evade_bonus=_evade_bonus,
                        flee_chance=_flee_chance,
                    )
                    if _e_hit:
                        _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
                            _wid, player_state["hull"],
                            player_state["shields"],
                            target_pilot_piloting=player_state.get("piloting", 0),
                        )
                        player_state["shields"] = max(0, player_state["shields"] - _sdmg)
                        player_state["hull"] = _fh
                        if ctx is not None:
                            ctx.player_counters.total_damage_taken += _dmg
                        _verb = "glancing hit" if _is_glancing else "hits"
                        _e_log(f"{_ei.name} {_verb} for {_dmg} hull damage!", log)
                        if _fh <= 0:
                            _e_log("Your ship has been destroyed!", log)
                            _ecx, _ecy = _calc_cam()
                            _animate_explosion(
                                console, context, game_map,
                                player_state["pos"],
                                cam_x=_ecx, cam_y=_ecy,
                                view_w=view_w, view_h=view_h,
                                player_state=player_state,
                                enemies=enemy_insts,
                                target_idx=target_idx,
                                log=log,
                                weapon_list=tuple(weapons_list),
                                active_weapons=active_weapons,
                                evade_bonus=_evade_bonus,
                                hit_chances=_weapon_hit_chances,
                                flee_chance=_flee_chance,
                            )
                            return "DEFEAT"
                    else:
                        _e_log(f"{_ei.name} misses!", log)
                    _ei.ap_remaining -= 1
                else:
                    break
    return None
