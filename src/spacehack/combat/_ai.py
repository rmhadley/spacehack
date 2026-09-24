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
from ..message_log import COLOR_ENEMY_ACTION
from ..data.weapons import find_weapon

from ._messages import enemy_attack_line as _enemy_attack_line
from ._stats import (
    calc_hit_chance,
    _calc_dodge_bonus,
    _distance,
)
from ._actions import (
    start_enemy_turn,
    resolve_damage,
    weapon_costs,
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


async def _run_enemy_turn(
    state,
    *,
    hit_chances: dict,
    evade_bonus: int,
    calc_cam,
    ctx=None,
) -> str | None:
    """Execute the AI turn for all alive enemies.

    Returns ``"DEFEAT"`` if the player is destroyed, ``None``
    otherwise. Mutates ``state`` in place.
    """
    for _e_idx, _ei in enumerate(state.enemy_insts):
        if not _ei.alive:
            continue
        start_enemy_turn(_ei)
        _esp = next(
            (_sp for _sp in state.enemy_specs if getattr(_sp, 'id', None) == _ei.spec_id),
            state.enemy_specs[0] if state.enemy_specs else None,
        )
        if _esp is None:
            continue
        if await _take_enemy_turn(
            state, _ei, _e_idx, _esp,
            hit_chances=hit_chances, evade_bonus=evade_bonus,
            calc_cam=calc_cam, ctx=ctx,
        ) == "DEFEAT":
            return "DEFEAT"
    return None


async def _take_enemy_turn(
    state, _ei, _e_idx, _esp, *, hit_chances, evade_bonus, calc_cam, ctx,
) -> str | None:
    """One enemy's AP turn: advance into range, then fire each AP.

    Honest costs (doc 48 SETTLED 39): every shot pays its weapon's
    real AP/power/ammo; when nothing is affordable the turn ends —
    never a spin, never moving while in firing band."""
    _cached_path: list[tuple[int, int]] | None = None
    while _ei.ap_remaining > 0:
        _p_pos = state.player_state["pos"]
        _can_shoot = _has_los(
            state.game_map, _ei.pos.x, _ei.pos.y,
            _p_pos.x, _p_pos.y,
        )
        _edist = _distance(_p_pos, _ei.pos)

        if _edist > _esp.ai_preferred_range or not _can_shoot:
            _moved, _cached_path = await _advance_one_step(
                state, _ei, _e_idx, _cached_path,
                hit_chances=hit_chances, evade_bonus=evade_bonus,
                calc_cam=calc_cam,
            )
        else:
            _moved = False

        if not _moved:
            # LOS is a firing precondition (the player's can_fire
            # twin: "Blocked by obstacle") — a blocked no-LOS step
            # breaks the turn rather than firing through cover.
            _slot = _first_affordable_weapon(_ei) if _can_shoot else None
            if _slot is None:
                break
            if await _enemy_attack(
                state, _ei, _slot,
                hit_chances=hit_chances, evade_bonus=evade_bonus,
                calc_cam=calc_cam, ctx=ctx,
            ) == "DEFEAT":
                return "DEFEAT"
    return None


def _first_affordable_weapon(_ei) -> int | None:
    """The Tier-0 walk: the FIRST weapon the ship can actually fire —
    real AP, power, and ammo. Unaffordable entries are SKIPPED, never
    waited on (a 2-AP missile at 1 AP is skipped). Real best-weapon
    selection is Tier 1 (SETTLED 39)."""
    for _slot, _entry in enumerate(_ei.weapons):
        try:
            _ws = find_weapon(_entry.item_id)
        except KeyError:
            continue
        _ap, _power, _ammo = weapon_costs(_ws)
        if _ei.ap_remaining < _ap:
            continue
        if _power and _ei.power_pool < _power:
            continue
        if _ammo and _ei.weapon_ammo.get(_slot, 0) < _ammo:
            continue
        return _slot
    return None


def _pay_fire_costs(_ei, slot: int, ws) -> None:
    """Every shot pays its real costs (SETTLED 39): AP, power for
    energy/plasma, rounds for missiles — the player's own economy."""
    _ap, _power, _ammo = weapon_costs(ws)
    _ei.ap_remaining -= _ap
    if _power:
        _ei.power_pool -= _power
    if _ammo:
        _left = _ei.weapon_ammo.get(slot, 0)
        _ei.weapon_ammo[slot] = max(0, _left - _ammo)


async def _advance_one_step(
    state, _ei, _e_idx, _cached_path, *, hit_chances, evade_bonus, calc_cam,
):
    """One step toward the player; returns ``(moved, cached_path)``.

    The cache invalidates when the step is blocked (someone took the
    cell); an empty path leaves the enemy in place without spending AP.
    """
    _p_pos = state.player_state["pos"]
    if _cached_path is None:
        _exclude = state.enemy_ents.get(_e_idx) if _e_idx >= 0 else None
        _cached_path = world.find_path(
            (_ei.pos.x, _ei.pos.y),
            {(_p_pos.x, _p_pos.y)},
            state.game_map,
            exclude_entity=_exclude,
        )
    if not _cached_path:
        return False, None
    _nx, _ny = _cached_path[0]
    _exclude = state.enemy_ents.get(_e_idx) if _e_idx >= 0 else None
    _blocked_by_other = any(
        _oe is not _ei and _oe.alive
        and _oe.pos.x == _nx and _oe.pos.y == _ny
        for _oe in state.enemy_insts
    )
    if _blocked_by_other or not (
        state.game_map.is_walkable(_nx, _ny)
        and state.game_map.blocking_entity_at(_nx, _ny, exclude=_exclude) is None
    ):
        return False, None
    _ei.pos = world.Position(_nx, _ny)
    _ei.cells_moved_this_turn += 1
    _ei.ap_remaining -= 1
    if _e_idx >= 0 and _e_idx in state.enemy_ents:
        state.enemy_ents[_e_idx].pos = _ei.pos
    _cached_path.pop(0)
    await _render_step_frame(state, calc_cam(), hit_chances, evade_bonus)
    return True, _cached_path


async def _render_step_frame(state, cam, hit_chances, evade_bonus) -> None:
    """One WAIT-mode frame of the enemy's move, then its pacing sleep."""
    _render_anim_frame(
        state.console, state.ctx, state.game_map,
        cam[0], cam[1], state.view_w, state.view_h,
        state.player_state, state.enemy_insts, state.target_idx, state.log,
        weapon_list=tuple(state.weapons_list),
        active_weapons=state.active_weapons,
        evade_bonus=evade_bonus,
        hit_chances=hit_chances,
        player_mode="WAIT",
    )
    await _responsive_sleep(animation_timing.GROUND_STEP, state.ctx.context)


async def _animate_enemy_shot(
    state, _ei, _wid, _e_hit, _e_dmg_popup, evade_bonus, calc_cam,
) -> None:
    """Present the enemy's shot through the shared animator."""
    _ecx, _ecy = calc_cam()
    await _animate_weapon_shot(
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
    )


async def _enemy_attack(
    state, _ei, _slot: int, *, hit_chances, evade_bonus, calc_cam, ctx,
) -> str | None:
    """Fire the enemy's weapon in ``_slot`` at the player (one attack),
    paying its real costs. Returns ``"DEFEAT"`` when the hit destroys
    the player.
    """
    _entry = _ei.weapons[_slot]
    _wid = _entry.item_id
    (
        _e_hit, _e_dmg, _e_sdmg, _e_fh, _e_is_strip,
        _is_glancing, _e_dmg_popup,
    ) = _resolve_enemy_shot(state, _ei, _wid, _entry.quality)
    _e_ws = find_weapon(_wid)
    await _animate_enemy_shot(
        state, _ei, _wid, _e_hit, _e_dmg_popup, evade_bonus, calc_cam,
    )
    _pay_fire_costs(_ei, _slot, _e_ws)
    if not _e_hit:
        _line = _enemy_attack_line(_ei.name, _wid, _e_ws.name, hit=False)
        _e_log(_line, state.log)
        return None
    return await _apply_enemy_hit(
        state, _ei, _wid, _e_ws,
        _e_dmg, _e_sdmg, _e_fh, _e_is_strip, _is_glancing,
        hit_chances=hit_chances, evade_bonus=evade_bonus, calc_cam=calc_cam,
        ctx=ctx,
    )


def _resolve_enemy_shot(state, _ei, _wid, _weapon_quality: int = 0):
    """Roll and resolve one enemy shot.

    Damage resolves BEFORE animating so the floating damage number
    rides the shot's impact frames. Misses return zeroed damage with
    the current hull. ``_weapon_quality`` is the flown instance's
    rolled tier (doc 48.7) — quality multiplies damage.
    """
    _dist = _distance(state.player_state["pos"], _ei.pos)
    _dodge = _calc_dodge_bonus(
        state.player_state.get("cells_moved_this_turn", 0),
        int(state.player_state.get("piloting", 0) * 0.5),
    )
    _chance = calc_hit_chance(_wid, _ei.pilot_gunnery, _dist, _dodge)
    _e_hit = RNG.randint(1, 100) <= _chance
    _e_dmg, _e_sdmg, _e_fh, _is_glancing = 0, 0, state.player_state["hull"], False
    _e_is_strip = False
    _e_dmg_popup = None
    if _e_hit:
        _e_dmg, _e_sdmg, _e_fh, _is_glancing = resolve_damage(
            _wid, state.player_state["hull"],
            state.player_state["shields"],
            target_pilot_piloting=state.player_state.get("piloting", 0),
            weapon_quality=_weapon_quality,
        )
        _e_ws = find_weapon(_wid)
        _e_is_strip = _e_ws.shield_strip > 0 and _e_sdmg > 0
        _e_dmg_popup = _damage_popup_for(
            _e_dmg, _e_sdmg, _e_is_strip,
            glancing=_is_glancing,
        )
    return _e_hit, _e_dmg, _e_sdmg, _e_fh, _e_is_strip, _is_glancing, _e_dmg_popup


async def _apply_enemy_hit(
    state, _ei, _wid, _e_ws, _e_dmg, _e_sdmg, _e_fh, _e_is_strip,
    _is_glancing, *, hit_chances, evade_bonus, calc_cam, ctx,
) -> str | None:
    """Apply a landed enemy hit; ``"DEFEAT"`` when hull reaches zero."""
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
    if _e_fh > 0:
        return None
    _e_log("Your ship has been destroyed!", state.log)
    _ecx, _ecy = calc_cam()
    await _animate_explosion(
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
    )
    return "DEFEAT"
