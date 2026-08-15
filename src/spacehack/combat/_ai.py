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
from ..data.weapons import find_weapon

from ._messages import enemy_attack_line as _enemy_attack_line
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
from .. import animation_timing
from ._animations import (
    _animate_explosion,
    _has_los,
    _render_anim_frame,
    _responsive_sleep,
    _damage_popup_for,
)
from ._shot_animations import _animate_weapon_shot


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
                    and state.game_map.blocking_entity_at(_nx, _ny, exclude=_exclude) is None
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
                        state.console, state.ctx, state.game_map,
                        _cam_x, _cam_y, state.view_w, state.view_h,
                        state.player_state, state.enemy_insts, state.target_idx, state.log,
                        weapon_list=tuple(state.weapons_list),
                        active_weapons=state.active_weapons,
                        evade_bonus=evade_bonus,
                        hit_chances=hit_chances,
                        flee_chance=_flee_chance,
                        player_mode="WAIT",
                    )
                    _responsive_sleep(animation_timing.GROUND_STEP)
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
                    # Resolve damage BEFORE animating so the floating
                    # damage number rides the shot's impact frames.
                    # The weapon spec is resolved before the hit check
                    # so the miss line can name the weapon too.
                    _e_ws = find_weapon(_wid)
                    _e_dmg_popup = None
                    _e_dmg = 0
                    _e_sdmg = 0
                    _e_fh = state.player_state["hull"]
                    _e_is_strip = False
                    _is_glancing = False
                    if _e_hit:
                        _e_dmg, _e_sdmg, _e_fh, _is_glancing = resolve_damage(
                            _wid, state.player_state["hull"],
                            state.player_state["shields"],
                            target_pilot_piloting=state.player_state.get("piloting", 0),
                        )
                        _e_is_strip = _e_ws.shield_strip > 0 and _e_sdmg > 0
                        _e_dmg_popup = _damage_popup_for(
                            _e_dmg, _e_sdmg, _e_is_strip,
                            glancing=_is_glancing,
                        )
                    _ecx, _ecy = calc_cam()
                    _animate_weapon_shot(
                        state.console, state.ctx, state.game_map,
                        _ei.pos, state.player_state["pos"],
                        _wid, is_hit=_e_hit,
                        damage=_e_dmg_popup,
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
                        state.player_state["shields"] = max(
                            0, state.player_state["shields"] - _e_sdmg,
                        )
                        state.player_state["hull"] = _e_fh
                        if ctx is not None:
                            ctx.player_counters.total_damage_taken += _e_dmg
                        _e_log(
                            _enemy_attack_line(
                                _ei.name, _wid, _e_ws.name,
                                hit=True, hull_dmg=_e_dmg,
                                shield_dmg=_e_sdmg,
                                is_strip=_e_is_strip,
                                is_glancing=_is_glancing and not _e_is_strip,
                            ),
                            state.log,
                        )
                        if _e_fh <= 0:
                            _e_log("Your ship has been destroyed!", state.log)
                            _ecx, _ecy = calc_cam()
                            _animate_explosion(
                                state.console, state.ctx, state.game_map,
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
                        _e_log(
                            _enemy_attack_line(
                                _ei.name, _wid, _e_ws.name, hit=False,
                            ),
                            state.log,
                        )
                    _ei.ap_remaining -= 1
                else:
                    break
    return None
