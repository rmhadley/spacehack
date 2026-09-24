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
    """One enemy's AP turn as decision points (doc 48 SETTLED 40):
    each AP spends on a verb — advance to stand-off, or the in-position
    engagement decision. The turn breaks when no verb is legal —
    never a spin. Honest costs stand (SETTLED 39)."""
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
            if _moved:
                continue
            if not _can_shoot:
                # A blocked step with no LOS breaks the turn rather
                # than firing through cover.
                break
            # Blocked with LOS: fall through — the weapon may still
            # reach from here (today's blocked-advance behavior).
        _outcome = await _engagement_decision(
            state, _ei, _e_idx, _esp, _edist,
            hit_chances=hit_chances, evade_bonus=evade_bonus,
            calc_cam=calc_cam, ctx=ctx,
        )
        if _outcome == "DEFEAT":
            return "DEFEAT"
        if _outcome == "BREAK":
            break
    return None


async def _engagement_decision(
    state, _ei, _e_idx, _esp, _edist, *, hit_chances, evade_bonus, calc_cam, ctx,
) -> str:
    """The in-position decision point (doc 48 SETTLED 40): fire the
    volley's top-scoring affordable weapon, greedily re-evaluated each
    spend of AP. Returns ``"SPENT"`` (a verb consumed AP), ``"BREAK"``
    (nothing legal — the turn ends), or ``"DEFEAT"``."""
    _fire = _select_fire_weapon(_ei, _edist, state.player_state)
    if _fire is None:
        return "BREAK"
    if await _enemy_attack(
        state, _ei, _fire[0],
        hit_chances=hit_chances, evade_bonus=evade_bonus,
        calc_cam=calc_cam, ctx=ctx,
    ) == "DEFEAT":
        return "DEFEAT"
    return "SPENT"


def score_weapon(
    ws, distance: float, target_shields: int,
    gunnery: int, target_dodge: int,
) -> float:
    """Expected value per AP (doc 48 SETTLED 40): damage x
    hit-chance-at-distance / ap_cost — the SAME ``calc_hit_chance``
    the shot resolves with, so range-band penalties fold into the
    choice. Shield-strip weapons score their expected STRIP instead:
    an EMP on bare shields scores 0 and is never picked."""
    _chance = calc_hit_chance(ws.id, gunnery, distance, target_dodge)
    _ap = weapon_costs(ws)[0]
    if ws.shield_strip > 0:
        return min(ws.shield_strip, target_shields) * (_chance / 100.0) / _ap
    return ws.damage * (_chance / 100.0) / _ap


def _weapon_affordable(_ei, slot: int, ws) -> bool:
    """Real AP, power, and ammo in the bank for one shot of ``ws``."""
    _ap, _power, _ammo = weapon_costs(ws)
    if _ei.ap_remaining < _ap:
        return False
    if _power and _ei.power_pool < _power:
        return False
    if _ammo and _ei.weapon_ammo.get(slot, 0) < _ammo:
        return False
    return True


def _select_fire_weapon(_ei, distance: float, player_state: dict):
    """The volley's next pick: the top-scoring WEAPON, not the first
    affordable one (supersedes the Tier-0 list walk). Tie-break is
    first slot. Returns ``(slot, weapon_spec)`` or ``None``."""
    _dodge = _calc_dodge_bonus(
        player_state.get("cells_moved_this_turn", 0),
        int(player_state.get("piloting", 0) * 0.5),
    )
    _best: tuple[float, int, object] | None = None
    for _slot, _entry in enumerate(_ei.weapons):
        try:
            _ws = find_weapon(_entry.item_id)
        except KeyError:
            continue
        if not _weapon_affordable(_ei, _slot, _ws):
            continue
        _score = score_weapon(
            _ws, distance, player_state.get("shields", 0),
            _ei.pilot_gunnery, _dodge,
        )
        if _score <= 0:
            continue
        if _best is None or _score > _best[0]:
            _best = (_score, _slot, _ws)
    return None if _best is None else (_best[1], _best[2])


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
