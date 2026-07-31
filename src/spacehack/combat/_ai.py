"""Enemy AI — movement and fire logic for combat enemies.

Extracted from ``_loop.py`` during Phase 2 of the combat loop
refactoring. Single entry point ``_run_enemy_turn`` that iterates
all alive enemies, moves them toward the player, and fires when
in range.

Receives whole session state as a :class:`SpaceCombatState` instance
rather than individual fields — the state encapsulation flows through.
"""

from __future__ import annotations

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
    _has_los,
    _render_anim_frame,
    _responsive_sleep,
)


def _e_log(msg: str, log) -> None:
    log.add_colored(msg, COLOR_ENEMY_ACTION)


def _c_log(msg: str, log) -> None:
    log.add_colored(msg, COLOR_COMBAT_EVENT)


def _run_enemy_turn(
    state,
    *,
    hit_chances: dict,
    evade_bonus: int,
    flee_attempts: int,
    calc_cam,
    ctx=None,
) -> str | None:
    """Execute the AI turn for all alive enemies.

    Receives the whole :class:`SpaceCombatState` plus per-turn
    computed values (hit chances, evade bonus, camera callback).
    Returns ``"DEFEAT"`` if the player is destroyed, ``None``
    otherwise. Mutates ``state`` in place.
    """
    for _ei in state.enemy_insts:
        if not _ei.alive:
            continue
        start_enemy_turn(_ei)

        _esp = next(
            (_sp for _sp in state.enemy_specs if getattr(_sp, 'id', None) == _ei.spec_id),
            state.enemy_specs[0] if state.enemy_specs else None,
        )
        if _esp is None:
            continue

        _e_idx = next(
            (_j for _j, _je in enumerate(state.enemy_insts) if _je is _ei),
            -1,
        )

        _alive = [e for e in state.enemy_insts if e.alive]
        _closest_enemy = min(
            _alive,
            key=lambda _e: _distance(state.player_state["pos"], _e.pos),
        )
        _flee_chance = calc_flee_chance(
            state.player_state["piloting"],
            _closest_enemy.pilot_piloting,
            state.player_state["hull"] / max(state.player_state["max_hull"], 1),
            _distance(state.player_state["pos"], _closest_enemy.pos),
            flee_attempts,
        )

        _cached_path: list[tuple[int, int]] | None = None

        while _ei.ap_remaining > 0:
            _edist = _distance(state.player_state["pos"], _ei.pos)
            _moved = False

            _p_pos = state.player_state["pos"]
            _can_shoot = _has_los(
                state.game_map, _ei.pos.x, _ei.pos.y,
                _p_pos.x, _p_pos.y,
            )

            if _edist > _esp.ai_preferred_range or not _can_shoot:
                if _cached_path is None:
                    _exclude = state.enemy_ents.get(_e_idx) if _e_idx >= 0 else None
                    _cached_path = world.find_path(
                        (_ei.pos.x, _ei.pos.y),
                        {(_p_pos.x, _p_pos.y)},
                        state.game_map,
                        exclude_entity=_exclude,
                    )
                if _cached_path:
                    _nx, _ny = _cached_path[0]
                else:
                    _nx, _ny = _ei.pos.x, _ei.pos.y
                _blocked_by_other = any(
                    _oe is not _ei and _oe.alive
                    and _oe.pos.x == _nx and _oe.pos.y == _ny
                    for _oe in state.enemy_insts
                )
                if not _blocked_by_other and (
                    state.game_map.is_walkable(_nx, _ny)
                    and state.game_map.entity_at(_nx, _ny, exclude=None) is None
                ):
                    _ei.pos = world.Position(_nx, _ny)
                    _ei.cells_moved_this_turn += 1
                    _ei.ap_remaining -= 1
                    if _e_idx >= 0 and _e_idx in state.enemy_ents:
                        state.enemy_ents[_e_idx].pos = _ei.pos
                    _moved = True
                    _cached_path.pop(0)
                    _cam_x, _cam_y = calc_cam()
                    _render_anim_frame(
                        state.console, state.ctx.context, state.game_map,
                        _cam_x, _cam_y, state.view_w, state.view_h,
                        state.player_state, state.enemy_insts, state.target_idx, state.log,
                        weapon_list=tuple(state.weapons_list),
                        active_weapons=state.active_weapons,
                        evade_bonus=evade_bonus,
                        hit_chances=hit_chances,
                        flee_chance=_flee_chance,
                        player_mode="WAIT",
                    )
                    _responsive_sleep(0.05)
                else:
                    _cached_path = None

            if not _moved:
                if _ei.weapons and _can_shoot:
                    _wid = _ei.weapons[0]
                    _dist = _distance(state.player_state["pos"], _ei.pos)
                    _dodge = _calc_dodge_bonus(
                        state.player_state.get("cells_moved_this_turn", 0),
                        int(state.player_state.get("piloting", 0) * 0.5),
                    )
                    _chance = calc_hit_chance(
                        _wid, _ei.pilot_gunnery, _dist, _dodge,
                    )
                    _e_hit = RNG.randint(1, 100) <= _chance
                    _ecx, _ecy = calc_cam()
                    _animate_laser_shot(
                        state.console, state.ctx.context, state.game_map,
                        _ei.pos, state.player_state["pos"],
                        is_hit=_e_hit,
                        cam_x=_ecx, cam_y=_ecy,
                        view_w=state.view_w, view_h=state.view_h,
                        player_state=state.player_state,
                        enemies=state.enemy_insts,
                        target_idx=state.target_idx,
                        log=state.log,
                        weapon_list=tuple(state.weapons_list),
                        active_weapons=state.active_weapons,
                        evade_bonus=evade_bonus,
                        flee_chance=_flee_chance,
                    )
                    if _e_hit:
                        _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
                            _wid, state.player_state["hull"],
                            state.player_state["shields"],
                            target_pilot_piloting=state.player_state.get("piloting", 0),
                        )
                        state.player_state["shields"] = max(
                            0, state.player_state["shields"] - _sdmg,
                        )
                        state.player_state["hull"] = _fh
                        if ctx is not None:
                            ctx.player_counters.total_damage_taken += _dmg
                        _verb = "glancing hit" if _is_glancing else "hits"
                        _e_log(f"{_ei.name} {_verb} for {_dmg} hull damage!", state.log)
                        if _fh <= 0:
                            _e_log("Your ship has been destroyed!", state.log)
                            _ecx, _ecy = calc_cam()
                            _animate_explosion(
                                state.console, state.ctx.context, state.game_map,
                                state.player_state["pos"],
                                cam_x=_ecx, cam_y=_ecy,
                                view_w=state.view_w, view_h=state.view_h,
                                player_state=state.player_state,
                                enemies=state.enemy_insts,
                                target_idx=state.target_idx,
                                log=state.log,
                                weapon_list=tuple(state.weapons_list),
                                active_weapons=state.active_weapons,
                                evade_bonus=evade_bonus,
                                hit_chances=hit_chances,
                                flee_chance=_flee_chance,
                            )
                            return "DEFEAT"
                    else:
                        _e_log(f"{_ei.name} misses!", state.log)
                    _ei.ap_remaining -= 1
                else:
                    break
    return None
