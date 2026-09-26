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
    """The in-position decision point (doc 48 SETTLED 40): back off
    when hugged inside the band floor, else the aggressiveness roll —
    fire the volley's top scorer, or one reposition step in band (the
    dodge-tank). With nothing affordable, leftover AP goes to
    repositioning while a legal step exists — a power-dry ship dodges
    while it recharges. Returns ``"SPENT"``, ``"BREAK"`` (no verb
    legal), or ``"DEFEAT"``."""
    _steer = dict(hit_chances=hit_chances, evade_bonus=evade_bonus, calc_cam=calc_cam)
    _fire, _band = _volley_picks(_ei, _edist, state.player_state)
    if _band is not None and _edist < _band.min_range:
        if await _back_off_step(state, _ei, _e_idx, **_steer):
            return "SPENT"
        # Cornered: fall through and fire through the min-penalty.
    _rep = _find_reposition(state, _ei, _e_idx, _band) if _band is not None else None
    if _fire is not None and (
        _rep is None or RNG.randint(1, 100) < _esp.ai_aggressiveness
    ):
        if await _enemy_attack(
            state, _ei, _fire[0], **_steer, ctx=ctx,
        ) == "DEFEAT":
            return "DEFEAT"
        return "SPENT"
    if _rep is not None:
        await _apply_step(state, _ei, _e_idx, _rep[0], _rep[1], **_steer)
        return "SPENT"
    return "BREAK"


_STEP_DELTAS = (
    (-1, -1), (0, -1), (1, -1), (-1, 0),
    (1, 0), (-1, 1), (0, 1), (1, 1),
)


def _other_bodies(state, _ei) -> set[tuple[int, int]]:
    """Cells held by other live combatants — ships never stack."""
    return {
        (_oe.pos.x, _oe.pos.y) for _oe in state.enemy_insts
        if _oe is not _ei and _oe.alive
    }


def _step_open(state, _ei, _e_idx, nx: int, ny: int, bodies) -> bool:
    """One cell's step legality — the rule every verb shares: no other
    live body on it, walkable terrain, no blocking entity."""
    if (nx, ny) in bodies:
        return False
    _exclude = state.enemy_ents.get(_e_idx) if _e_idx >= 0 else None
    if not state.game_map.is_walkable(nx, ny):
        return False
    return state.game_map.blocking_entity_at(nx, ny, exclude=_exclude) is None


def _legal_step_cells(state, _ei, _e_idx) -> list[tuple[int, int]]:
    """The 8-adjacent cells this ship may step into this tick
    (the one shared step-legality rule, swept over the ring)."""
    _bodies = _other_bodies(state, _ei)
    return [
        (_ei.pos.x + _dx, _ei.pos.y + _dy)
        for _dx, _dy in _STEP_DELTAS
        if _step_open(state, _ei, _e_idx, _ei.pos.x + _dx, _ei.pos.y + _dy, _bodies)
    ]


async def _back_off_step(
    state, _ei, _e_idx, *, hit_chances, evade_bonus, calc_cam,
) -> bool:
    """ONE greedy step away while hugged inside the band floor
    (SETTLED 40): the distance-maximizing neighbor, LOS-keeping
    preferred, stopping at restoration — one step's granularity may
    overshoot the floor, but the verb never fires again past it.
    ``False`` when cornered (no step increases distance); the caller
    fires through the min-penalty."""
    _p_pos = state.player_state["pos"]
    _now = _distance(_p_pos, _ei.pos)
    _best = None
    for _nx, _ny in _legal_step_cells(state, _ei, _e_idx):
        _gain = _distance(_p_pos, world.Position(_nx, _ny)) - _now
        if _gain <= 0:
            continue
        _keeps_los = _has_los(state.game_map, _nx, _ny, _p_pos.x, _p_pos.y)
        if _best is None or (_keeps_los, _gain) > (_best[0], _best[1]):
            _best = (_keeps_los, _gain, _nx, _ny)
    if _best is None:
        return False
    await _apply_step(
        state, _ei, _e_idx, _best[2], _best[3],
        hit_chances=hit_chances, evade_bonus=evade_bonus, calc_cam=calc_cam,
    )
    return True


def _find_reposition(state, _ei, _e_idx, _band_ws):
    """The best legal dodge cell (SETTLED 23/40): inside the band
    weapon's [min..max], LOS-keeping, ranked by the same scorer — the
    skirmisher drifts toward its ideal firing distance while dodge-
    stacking through the shared cells_moved economy. ``None`` when
    there is nowhere to dance."""
    _player = state.player_state
    _p_pos = _player["pos"]
    _best = None
    for _nx, _ny in _legal_step_cells(state, _ei, _e_idx):
        _dist = _distance(_p_pos, world.Position(_nx, _ny))
        if not _band_ws.min_range <= _dist <= _band_ws.max_range:
            continue
        if not _has_los(state.game_map, _nx, _ny, _p_pos.x, _p_pos.y):
            continue
        _score = score_weapon(
            _band_ws, _dist, _player.get("shields", 0),
            _ei.pilot_gunnery, _player_dodge(_player),
        )
        if _best is None or _score > _best[0]:
            _best = (_score, _nx, _ny)
    return None if _best is None else (_best[1], _best[2])


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
    _ranked = _ranked_weapons(_ei, distance, player_state)
    return None if not _ranked else (_ranked[0][1], _ranked[0][2])


def _ranked_weapons(
    _ei, distance: float, player_state: dict, *, affordable_only: bool = True,
) -> list:
    """The volley's candidates in score order (EV per AP, tie first
    slot). ``affordable_only=False`` ignores the budget — the ranked
    wish list a power-dry ship dances to the top of (SETTLED 40)."""
    _dodge = _player_dodge(player_state)
    _ranked = []
    for _slot, _entry in enumerate(_ei.weapons):
        try:
            _ws = find_weapon(_entry.item_id)
        except KeyError:
            continue
        if affordable_only and not _weapon_affordable(_ei, _slot, _ws):
            continue
        _score = score_weapon(
            _ws, distance, player_state.get("shields", 0),
            _ei.pilot_gunnery, _dodge,
        )
        if _score > 0:
            _ranked.append((_score, _slot, _ws))
    _ranked.sort(key=lambda _pick: (-_pick[0], _pick[1]))
    return _ranked


def _volley_picks(_ei, distance: float, player_state: dict):
    """``(fire, band)``: the affordable top scorer to FIRE, and the
    band weapon governing the dance (back-off floor + reposition
    window). With nothing affordable the band falls back to the top
    scorer IGNORING the budget — a power-dry ship dodges where it
    will fight from when power returns. Both ``None`` = weaponless:
    no decision point, breaks at once (SETTLED 40)."""
    _fire = _select_fire_weapon(_ei, distance, player_state)
    if _fire is not None:
        return _fire, _fire[1]
    _wish = _ranked_weapons(_ei, distance, player_state, affordable_only=False)
    return None, (_wish[0][2] if _wish else None)


def _reaction_pick(_ei, distance: float, player_state: dict):
    """The flee volley's weapon (doc 54): the top-scoring affordable
    weapon that REACHES the player — the ranked scores stay positive
    at the 5% hit floor beyond max range, so the reaction filter is
    an explicit ``max_range >= distance`` over the ranked order.
    ``(slot, weapon_spec)`` or ``None`` when nothing reaches."""
    for _score, _slot, _ws in _ranked_weapons(_ei, distance, player_state):
        if _ws.max_range >= distance:
            return (_slot, _ws)
    return None


def _player_dodge(player_state: dict) -> int:
    """The player's current dodge read — the same value the shot and
    the scorer resolve with."""
    return _calc_dodge_bonus(
        player_state.get("cells_moved_this_turn", 0),
        int(player_state.get("piloting", 0) * 0.5),
    )


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
    cell) or the ship left its route (back-off/reposition — see the
    stale-head check below); an empty path leaves the enemy in place
    without spending AP.
    """
    _p_pos = state.player_state["pos"]
    if _cached_path is not None and _cached_path:
        # Off-route invalidation: back-off/reposition relocate the
        # ship without following the route — a stale head is not
        # adjacent (or is the ship's own cell), so recompute instead
        # of teleporting or hopping in place.
        _hx, _hy = _cached_path[0]
        _cheb = max(abs(_hx - _ei.pos.x), abs(_hy - _ei.pos.y))
        if _cheb != 1:
            _cached_path = None
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
    if not _step_open(state, _ei, _e_idx, _nx, _ny, _other_bodies(state, _ei)):
        return False, None
    await _apply_step(
        state, _ei, _e_idx, _nx, _ny,
        hit_chances=hit_chances, evade_bonus=evade_bonus, calc_cam=calc_cam,
    )
    _cached_path.pop(0)
    return True, _cached_path


async def _apply_step(
    state, _ei, _e_idx, nx: int, ny: int, *, hit_chances, evade_bonus, calc_cam,
) -> None:
    """One movement step's shared tail — the ONE economy all three
    step verbs (advance, back-off, reposition) pay: position write,
    dodge accrual, 1 AP, entity sync, frame render."""
    _ei.pos = world.Position(nx, ny)
    _ei.cells_moved_this_turn += 1
    _ei.ap_remaining -= 1
    if _e_idx >= 0 and _e_idx in state.enemy_ents:
        state.enemy_ents[_e_idx].pos = _ei.pos
    await _render_step_frame(state, calc_cam(), hit_chances, evade_bonus)


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
    _dodge = _player_dodge(state.player_state)
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


async def _present_ship_destruction(state, *, evade_bonus, hit_chances, calc_cam):
    """Log the destruction line and play the player-ship explosion."""
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


async def _apply_enemy_hit(
    state, _ei, _wid, _e_ws, _e_dmg, _e_sdmg, _e_fh, _e_is_strip,
    _is_glancing, *, hit_chances, evade_bonus, calc_cam, ctx,
) -> str | None:
    """Apply a landed enemy hit; ``"DEFEAT"`` when hull reaches zero."""
    state.player_state["shields"] = max(
        0, state.player_state["shields"] - _e_sdmg,
    )
    state.player_state["hull"] = _e_fh
    state.last_attacker = f"{_ei.name}'s {_e_ws.name}"
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
    await _present_ship_destruction(
        state, evade_bonus=evade_bonus, hit_chances=hit_chances, calc_cam=calc_cam,
    )
    return "DEFEAT"
