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
from ..data.quality import effective_ship_weapon_spec
from ..data.weapons import find_weapon

from ._messages import enemy_attack_line as _enemy_attack_line
from . import _ai_conservation as _ac
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
from . import _missile_flight as _mf


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
    # The orphan sweep (doc 57.2): a dead shooter's missiles fly at
    # the START of the enemy phase, ahead of the live shooters' turns
    # — at most one move per missile per round.
    if await _mf.advance_orphan_flights(state, ctx, state.game_map) == "DEFEAT":
        return "DEFEAT"
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


async def _advance_toward_standoff(
    state, _ei, _e_idx, _esp, _cached_path, *, hit_chances, evade_bonus, calc_cam,
) -> tuple[str, list | None]:
    """The out-of-position verb (doc 48 SETTLED 40): beyond the
    preferred range or without LOS, ONE step toward the player.
    Returns ``(outcome, cached_path)`` — ``"MOVED"``, ``"BREAK"``
    (blocked with no LOS: never fire through cover), or ``"ENGAGE"``
    (in position, or blocked with LOS: today's fall-through — the
    weapon may still reach from here)."""
    _p_pos = state.player_state["pos"]
    _can_shoot = _has_los(
        state.game_map, _ei.pos.x, _ei.pos.y,
        _p_pos.x, _p_pos.y,
    )
    if _distance(_p_pos, _ei.pos) <= _esp.ai_preferred_range and _can_shoot:
        return "ENGAGE", _cached_path
    _moved, _cached_path = await _advance_one_step(
        state, _ei, _e_idx, _cached_path,
        hit_chances=hit_chances, evade_bonus=evade_bonus, calc_cam=calc_cam,
    )
    if _moved:
        return "MOVED", _cached_path
    return ("BREAK" if not _can_shoot else "ENGAGE"), _cached_path


async def _take_enemy_turn(
    state, _ei, _e_idx, _esp, *, hit_chances, evade_bonus, calc_cam, ctx,
) -> str | None:
    """One enemy's AP turn as decision points (doc 48 SETTLED 40):
    each AP spends on a verb — advance to stand-off, or the in-position
    engagement decision. The turn breaks when no verb is legal —
    never a spin. Honest costs stand (SETTLED 39)."""
    # This shooter's mini-turn first (doc 57 SETTLED 11.9, the enemy
    # mirror): its missiles move before its first verb.
    if await _mf.advance_flights(
        state, ctx, state.game_map, side="enemy", shooter=_ei,
    ) == "DEFEAT":
        return "DEFEAT"
    _cached_path: list[tuple[int, int]] | None = None
    while _ei.ap_remaining > 0:
        _verb, _cached_path = await _advance_toward_standoff(
            state, _ei, _e_idx, _esp, _cached_path,
            hit_chances=hit_chances, evade_bonus=evade_bonus, calc_cam=calc_cam,
        )
        if _verb == "MOVED":
            continue
        if _verb == "BREAK":
            break
        _outcome = await _engagement_decision(
            state, _ei, _e_idx, _esp, _distance(state.player_state["pos"], _ei.pos),
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
    fire the VOLLEY (doc 56 SETTLED 24: every affordable weapon, the
    player's burst-fire mirror), or one reposition step in band (the
    dodge-tank). With nothing affordable, leftover AP goes to
    repositioning while a legal step exists — a power-dry ship dodges
    while it recharges. The roll reads the BEND (doc 57.2.5): a
    tanking ship's temperament scales with its shields; a failing
    hull raises it (the cornered last stand). Returns ``"SPENT"``,
    ``"BREAK"`` (no verb legal), or ``"DEFEAT"``."""
    _steer = dict(hit_chances=hit_chances, evade_bonus=evade_bonus, calc_cam=calc_cam)
    _fire, _band = _volley_picks(_ei, _edist, state.player_state)
    if _band is not None and _edist < _band.min_range:
        if await _back_off_step(state, _ei, _e_idx, **_steer):
            return "SPENT"
        # Cornered: fall through to the volley — whose members carry
        # the missile floor gate (doc 57.2), so a cornered rack-only
        # ship fires nothing and breaks; lasers still fire at the
        # min-penalty (doc 56 SETTLED 24, guns unchanged).
    _rep = _find_reposition(state, _ei, _e_idx, _band) if _band is not None else None
    if _fire is not None and (
        _rep is None
        or RNG.randint(1, 100) < _ac._effective_aggressiveness(_ei, _esp)
    ):
        if await _enemy_volley(
            state, _ei, target=_flak_pick(state, _ei, _fire), **_steer, ctx=ctx,
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
    gunnery: int, target_dodge: int, weapon_quality: int = 0,
) -> float:
    """Expected value per AP (doc 48 SETTLED 40): damage x
    hit-chance-at-distance / ap_cost — the SAME ``calc_hit_chance``
    the shot resolves with, so range-band penalties fold into the
    choice. ``weapon_quality`` scales both terms (doc 47 SETTLED 2 —
    the ranking sees the tier the volley rolls, so a base heavy laser
    no longer outscores the overclocked light it actually loses to).
    Shield-strip weapons score their expected STRIP instead: an EMP on
    bare shields scores 0 and is never picked."""
    _chance = calc_hit_chance(
        ws.id, gunnery, distance, target_dodge,
        weapon_quality=weapon_quality,
    )
    _ap = weapon_costs(ws)[0]
    if ws.shield_strip_pct > 0 or ws.shield_strip > 0:
        _strip = (
            target_shields if ws.shield_strip_pct > 0
            else min(ws.shield_strip, target_shields)
        )
        return _strip * (_chance / 100.0) / _ap
    _damage = effective_ship_weapon_spec(ws.id, weapon_quality).damage
    return _damage * (_chance / 100.0) / _ap


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


def _member_included(
    _ei, slot: int, ws, distance: float, *, flak: bool = False,
) -> bool:
    """The volley's per-member legality (doc 56 SETTLED 24 + doc 57.2
    + doc 57.2.5): real affordability, the missile floor (a flight
    rack inside its catalog floor is a dead stick this action, the
    player ``can_fire`` mirror — supersedes doc 56 SETTLED 24's
    fire-at-penalized-floor for MISSILE members only), and the
    conservation reserve (a member sits out when firing it would dip
    the pool below the protected divert — flak exempt). The ranked
    affordable walk shares this predicate, so the fire pick is
    always a member: never a zero-AP "SPENT" spin."""
    return (
        _weapon_affordable(_ei, slot, ws)
        and not _mf.catalog_floor(ws) > distance
        and _ac._funds_within_reserve(_ei, ws, flak=flak)
    )


def _flak_capable(ws) -> bool:
    """Whether ``ws`` can affect an in-flight missile (doc 57.2): a
    damage gun — a flight rack can never connect with ordnance
    (SETTLED 11.6: missiles never collide with missiles) and strip
    weapons no-op on a shields-0 target by construction (SETTLED 7).
    The AI's toggles-off expression of the player's own flak escort
    (SETTLED 8). Reads the direct flight detector, not the floor
    (57.3 owns the floor dials)."""
    return (
        not _mf.is_flight_weapon(ws.id)
        and ws.shield_strip == 0 and ws.shield_strip_pct == 0
    )


def score_flak(
    ws, distance: float, missile, gunnery: int, weapon_quality: int = 0,
) -> float:
    """Expected intercept value per AP (doc 57.2): the SAME
    ``calc_hit_chance`` the shot resolves with (missiles dodge 0) ×
    the share of the inbound's hull one shot covers, scaled by the
    threat it neutralizes (the rack damage it would arrive with) —
    the ``score_weapon`` shape, so flak competes with volley EV in the
    same per-AP currency."""
    _chance = calc_hit_chance(
        ws.id, gunnery, distance, 0, weapon_quality=weapon_quality,
    )
    _dmg = effective_ship_weapon_spec(ws.id, weapon_quality).damage
    _threat = effective_ship_weapon_spec(
        missile.weapon_id, missile.quality,
    ).damage
    _coverage = min(_dmg, missile.hull) / max(1, missile.hull)
    return _coverage * _threat * (_chance / 100.0) / weapon_costs(ws)[0]


def _flak_pick(state, _ei, _fire):
    """The flak decision (doc 57.2): the best ``(score, inbound)`` over
    affordable flak guns × the player's live missiles, fired at ONLY
    when its intercept EV beats the fire pick's volley EV —
    score(inbound) vs score(shooter), the scorer pattern, never
    branches. ``_fire`` is the ``(slot, spec)`` pick (the ranked walk
    strips its score), so the volley EV is recomputed from the pick's
    own weapon at the live player distance. ``None`` = shoot the
    shooter. Strip weapons never score here by construction (the
    score-zero never-picked rule); the pick scans the SAME gated
    membership the flak volley builds (doc 57.2.5: flak-exempt from
    the reserve), so a non-None pick always funds at least one firing
    member — never a zero-AP "SPENT" spin."""
    _pd = state.player_state
    _shoot_ev = _member_score_vs(
        _ei, _fire[0], _fire[1], _distance(_pd["pos"], _ei.pos), _pd,
    )
    _best = None
    for _slot, _ws in _affordable_members(_ei, 0.0, flak=True):
        for _missile in state.in_flight:
            if _missile.side != "player" or not _missile.alive:
                continue
            _score = score_flak(
                _ws, _distance(_ei.pos, _missile.pos), _missile,
                _ei.pilot_gunnery, _ei.weapons[_slot].quality,
            )
            if _score > 0 and (_best is None or _score > _best[0]):
                _best = (_score, _missile)
    if _best is None or _best[0] <= _shoot_ev:
        return None
    return _best[1]


def _ranked_weapons(
    _ei, distance: float, player_state: dict, *, affordable_only: bool = True,
) -> list:
    """The volley's candidates in score order (EV per AP, tie first
    slot). ``affordable_only=False`` ignores the budget — the ranked
    wish list a power-dry ship dances to the top of (SETTLED 40);
    that wish list also ignores the missile floor, keeping a hugged
    rack-carrier's band governor intact, but NOT an empty magazine
    (doc 57.2.5's dry filter: the band follows what the ship can
    still feed — power recovers next turn, spent rounds do not; a
    loaded magazine behaves as today down to the last round, no
    hoarding). The affordable walk carries the floor and reserve
    gates (doc 57.2 / 57.2.5): a grounded or unfundable weapon is
    not a fire candidate — the fire pick and the volley's members
    share one legality read, so a non-None pick always fires
    something."""
    _dodge = _player_dodge(player_state)
    _ranked = []
    for _slot, _ws in _slot_weapons(_ei):
        if not affordable_only and _ac._magazine_dry(_ei, _slot, _ws):
            continue
        if affordable_only and not _member_included(_ei, _slot, _ws, distance):
            continue
        _score = score_weapon(
            _ws, distance, player_state.get("shields", 0),
            _ei.pilot_gunnery, _dodge,
            weapon_quality=_ei.weapons[_slot].quality,
        )
        if _score > 0:
            _ranked.append((_score, _slot, _ws))
    _ranked.sort(key=lambda _pick: (-_pick[0], _pick[1]))
    return _ranked


def _volley_picks(_ei, distance: float, player_state: dict):
    """``(fire, band)``: the affordable top scorer to FIRE, and the
    band weapon governing the dance (back-off floor + reposition
    window) — the WISH-LIST top over all weapons, budget and floor
    ignored (empty magazines drop out, doc 57.2.5). Doc 56 SETTLED
    24, as amended by docs 57.2/57.2.5: the fire pick's ROLE is the
    fire-vs-dodge gate only, and volley inclusion is affordability
    plus the floor, reserve, and score-zero gates (the enemy's
    expression of the player's toggles — a strip weapon into bare
    shields sits out). The band reads the wish list so a rack benched
    by its floor still governs the dance: a hugged mixed loadout
    backs off to restoration instead of collapsing into gun range
    with the rack silent forever (doc 57.2 playtest fix — the
    rack-only power-dry read generalized: the ship dances where its
    best weapon fights from). Both ``None`` = weaponless: no decision
    point, breaks at once (SETTLED 40)."""
    _fire = _select_fire_weapon(_ei, distance, player_state)
    _wish = _ranked_weapons(_ei, distance, player_state, affordable_only=False)
    return _fire, (_wish[0][2] if _wish else None)


def _reaction_pick(_ei, distance: float, player_state: dict):
    """The flee volley's weapon (doc 54; doc 57.2): the top-scoring
    affordable weapon that REACHES the player — the ranked scores stay
    positive at the 5% hit floor beyond max range, so the reaction
    filter is an explicit ``max_range >= distance`` over the ranked
    order — and is not a FLIGHT rack: a crossing missile cannot catch
    a fleeing ship (the fight ends before arrival — wasted rounds);
    the instant EMP pulse stays a reaction weapon.
    ``(slot, weapon_spec)`` or ``None`` when nothing reaches."""
    for _score, _slot, _ws in _ranked_weapons(_ei, distance, player_state):
        if _ws.max_range >= distance and not _mf.is_flight_weapon(_ws.id):
            return (_slot, _ws)
    return None


def _player_dodge(player_state: dict) -> int:
    """The player's current dodge read — the same value the shot and
    the scorer resolve with."""
    return _calc_dodge_bonus(
        player_state.get("cells_moved_this_turn", 0),
        int(player_state.get("piloting", 0) * 0.5),
    )


def _pay_shot_consumables(_ei, slot: int, ws) -> None:
    """The per-weapon power/ammo draw — what every fired member of a
    volley pays itself (doc 56 SETTLED 24); the volley's AP is
    max-once, so members never pay AP here."""
    _power, _ammo = weapon_costs(ws)[1:]
    if _power:
        _ei.power_pool -= _power
    if _ammo:
        _left = _ei.weapon_ammo.get(slot, 0)
        _ei.weapon_ammo[slot] = max(0, _left - _ammo)


def _pay_fire_costs(_ei, slot: int, ws) -> None:
    """Every shot pays its real costs (SETTLED 39): AP, power for
    energy/plasma, rounds for missiles — the player's own economy.
    The SINGLE-SHOT model (doc 56 phase 5): the engagement fire path
    volleys now; doc 54's flee reaction keeps this per-attack
    primitive."""
    _ei.ap_remaining -= weapon_costs(ws)[0]
    _pay_shot_consumables(_ei, slot, ws)


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
        state.player_state, _mf.merged_targets(state), state.target_idx, state.log,
        weapon_list=tuple(state.weapons_list),
        active_weapons=state.active_weapons,
        evade_bonus=evade_bonus,
        hit_chances=hit_chances,
        player_mode="WAIT",
    )
    await _responsive_sleep(animation_timing.GROUND_STEP, state.ctx.context)


async def _animate_enemy_shot(
    state, _ei, _wid, _e_hit, _e_dmg_popup, evade_bonus, calc_cam,
    to_pos=None,
) -> None:
    """Present the enemy's shot through the shared animator (at the
    player, or at an intercept's ordnance position — doc 57.2)."""
    _ecx, _ecy = calc_cam()
    _to = state.player_state["pos"] if to_pos is None else to_pos
    await _animate_weapon_shot(
        state.console, state.ctx, state.game_map,
        _ei.pos, _to,
        _wid, is_hit=_e_hit,
        damage=_e_dmg_popup,
        cam_x=_ecx, cam_y=_ecy,
        view_w=state.view_w, view_h=state.view_h,
        player_state=state.player_state,
        enemies=_mf.merged_targets(state),
        target_idx=state.target_idx,
        log=state.log,
        weapon_list=tuple(state.weapons_list),
        active_weapons=state.active_weapons,
        evade_bonus=evade_bonus,
    )


def _slot_weapons(_ei):
    """Every flown weapon slot as ``(slot, weapon_spec)`` — unknown
    ids skip, the shared walk both candidate lists build on."""
    for _slot, _entry in enumerate(_ei.weapons):
        try:
            yield _slot, find_weapon(_entry.item_id)
        except KeyError:
            continue


def _member_score_vs(_ei, slot: int, ws, distance: float, player_state: dict):
    """One member's expected value against the player — the score-zero
    read the ship volley's membership takes (doc 57.2.5)."""
    return score_weapon(
        ws, distance, player_state.get("shields", 0),
        _ei.pilot_gunnery, _player_dodge(player_state),
        weapon_quality=_ei.weapons[slot].quality,
    )


def _affordable_members(
    _ei, distance: float, player_state: dict | None = None, *,
    flak: bool = False,
) -> list:
    """The volley's inclusion walk (doc 56 SETTLED 24 as amended by
    docs 57.2/57.2.5): weapon SLOTS by the per-member legality check
    (affordability, missile floor, conservation reserve), never
    ``_ranked_weapons`` wholesale — the walks sort differently and the
    volley fires in slot order. A SHIP volley also drops SCORE-ZERO
    members when the target is readable (doc 57.2.5: expected value
    vs the player is 0 — a strip weapon into bare shields sits out;
    the enemy's toggles-off expression). A FLAK volley at ordnance
    requires capability instead (racks can never connect with a
    missile, strip weapons no-op on it) and never pays the reserve
    (point defense is survival)."""
    _members = []
    for _slot, _ws in _slot_weapons(_ei):
        if not _member_included(_ei, _slot, _ws, distance, flak=flak):
            continue
        if flak and not _flak_capable(_ws):
            continue
        if (
            not flak and player_state is not None
            and _member_score_vs(_ei, _slot, _ws, distance, player_state) <= 0
        ):
            continue
        _members.append((_slot, _ws))
    return _members


async def _launch_enemy_missile(state, _ei, _slot: int, ws) -> str | None:
    """The flight mirror of the player's spawn seam (doc 57.2): the
    volley member deploys as a crossing missile homing on the player —
    WORDLESS launch (the glyph crossing is the notice; the attack line
    lands with the warhead at arrival). Returns ``"DEFEAT"`` when the
    launch half-move connects on the player: Euclidean floors pass at
    diagonal standoffs a light's half-move can cross (the hp seam —
    ``spawn_flight_missile`` returns the missile, ADVISE 1)."""
    await _mf.spawn_flight_missile(
        state, ws.id, _mf.PlayerHomingTarget(state),
        side="enemy", quality=_ei.weapons[_slot].quality,
        launch_pos=_ei.pos, shooter=_ei, gunnery=_ei.pilot_gunnery,
    )
    if state.player_state["hull"] <= 0:
        return "DEFEAT"
    return None


def _apply_flak_damage(missile, _wid: str, quality: int) -> int:
    """Resolve one flak hit onto ``missile_hp`` through the shared
    damage path (missiles have no shields; piloting 0: no glances).
    Returns the damage dealt."""
    _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
        _wid, missile.hull, missile.shields,
        target_pilot_piloting=0, weapon_quality=quality,
    )
    missile.hull = _fh
    return _dmg


async def _enemy_flak_shot(
    state, _ei, _slot: int, missile, *, evade_bonus, calc_cam, ctx,
) -> str | None:
    """One flak member at an in-flight missile (doc 57.2): the roll at
    dodge 0 (deterministic traveler), damage onto ``missile_hp``, the
    enemy attack line with the target's name, and the INTERCEPT finish
    on the kill — never ``on_kill`` (no credit for ordnance)."""
    _entry = _ei.weapons[_slot]
    _wid = _entry.item_id
    _ws = find_weapon(_wid)
    _chance = calc_hit_chance(
        _wid, _ei.pilot_gunnery, _distance(_ei.pos, missile.pos), 0,
        weapon_quality=_entry.quality,
    )
    _hit = RNG.randint(1, 100) <= _chance
    _dmg = _apply_flak_damage(missile, _wid, _entry.quality) if _hit else 0
    await _animate_enemy_shot(
        state, _ei, _wid, _hit,
        _damage_popup_for(_dmg, 0, False) if _hit else None,
        evade_bonus, calc_cam, to_pos=missile.pos,
    )
    _e_log(
        _enemy_attack_line(
            _ei.name, _wid, _ws.name, hit=_hit, hull_dmg=_dmg,
            quality=_entry.quality, target_name=missile.name,
        ),
        state.log,
    )
    if _hit and missile.hull <= 0:
        await _mf.finish_intercept(state, ctx, state.game_map, missile)
    return None


async def _volley_member(
    state, _ei, _slot: int, _ws, target, *,
    hit_chances, evade_bonus, calc_cam, ctx,
) -> str | None:
    """One volley member's tail by kind (doc 57.2): a flight rack
    deploys a crossing missile, a gun at ordnance takes the flak
    shot, everything else the shared shot tail at the player. Stamps
    and cost models belong to the caller."""
    if _mf.is_flight_weapon(_ws.id):
        return await _launch_enemy_missile(state, _ei, _slot, _ws)
    if target is not None:
        return await _enemy_flak_shot(
            state, _ei, _slot, target,
            evade_bonus=evade_bonus, calc_cam=calc_cam, ctx=ctx,
        )
    return await _enemy_shot_tail(
        state, _ei, _slot,
        hit_chances=hit_chances, evade_bonus=evade_bonus,
        calc_cam=calc_cam, ctx=ctx,
    )


async def _run_volley_members(
    state, _ei, _members, target, *,
    hit_chances, evade_bonus, calc_cam, ctx,
) -> tuple[str | None, int]:
    """The member loop (doc 56 SETTLED 24; docs 57.2/57.2.5): fire in
    slot order with the per-member affordability + reserve RE-GATE
    (the pool never overdrafts and never dips below the protected
    divert — sequential fire enforces the floor cumulatively; flak
    pays no reserve), break on player death or the flak target's
    death (the player mirror's mid-volley break), pay power/ammo per
    member. Returns ``(outcome, max_ap)`` — the AP payment is the
    caller's."""
    _flak = target is not None
    _max_ap = 0
    _outcome = None
    for _slot, _ws in _members:
        if not _weapon_affordable(_ei, _slot, _ws):
            continue  # mid-volley decay: an earlier member drained the pool
        if not _ac._funds_within_reserve(_ei, _ws, flak=_flak):
            continue  # the reserve holds — the tanking ship stops here
        if target is not None and not target.alive:
            break  # the inbound died mid-volley — stop wasting rounds
        _outcome = await _volley_member(
            state, _ei, _slot, _ws, target,
            hit_chances=hit_chances, evade_bonus=evade_bonus,
            calc_cam=calc_cam, ctx=ctx,
        )
        _pay_shot_consumables(_ei, _slot, _ws)
        _max_ap = max(_max_ap, weapon_costs(_ws)[0])
        if _outcome == "DEFEAT":
            break
    return _outcome, _max_ap


async def _enemy_volley(
    state, _ei, *, hit_chances, evade_bonus, calc_cam, ctx, target=None,
) -> str | None:
    """Fire the affordable VOLLEY (doc 56 SETTLED 24; doc 57.2's
    ``target`` parameter) — the player's burst-fire mirror at the
    player (``None``) or at one in-flight missile (flak). Every
    affordable (and, for flak, capable) weapon fires once in slot
    order — out-of-range members at the hit floor, exactly as the
    player's own volley does; AP = max(ap_cost) over FIRED members,
    paid once at the end (a killing volley still costs its full AP).
    ``enemy_fired`` stamps once per volley — the opener window closes
    on the volley, hit or miss (mirror of ``_spend_opener``; a volley
    with no affordable member never burns it)."""
    _dist = _distance(
        target.pos if target is not None else state.player_state["pos"],
        _ei.pos,
    )
    _members = _affordable_members(
        _ei, _dist, state.player_state, flak=target is not None,
    )
    if not _members:
        return None
    state.enemy_fired = True
    _outcome, _max_ap = await _run_volley_members(
        state, _ei, _members, target,
        hit_chances=hit_chances, evade_bonus=evade_bonus,
        calc_cam=calc_cam, ctx=ctx,
    )
    _ei.ap_remaining -= _max_ap
    return _outcome


async def _enemy_shot_tail(
    state, _ei, _slot: int, *, hit_chances, evade_bonus, calc_cam, ctx,
) -> str | None:
    """The per-shot tail both fire paths share (doc 56 phase 5,
    ADVISE minor 8): resolve → animate → log/apply the hit. Stamps and
    cost models belong to the callers — the single shot stamps per
    attack and pays per shot; the volley stamps once and pays
    power/ammo per member plus max-AP once."""
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
    if not _e_hit:
        _e_log(_enemy_attack_line(_ei.name, _wid, _e_ws.name, hit=False), state.log)
        return None
    return await _apply_enemy_hit(
        state, _ei, _wid, _e_ws,
        _e_dmg, _e_sdmg, _e_fh, _e_is_strip, _is_glancing,
        hit_chances=hit_chances, evade_bonus=evade_bonus, calc_cam=calc_cam,
        ctx=ctx,
    )


async def _enemy_attack(
    state, _ei, _slot: int, *, hit_chances, evade_bonus, calc_cam, ctx,
) -> str | None:
    """Fire the enemy's weapon in ``_slot`` at the player (one attack),
    paying its real costs. Returns ``"DEFEAT"`` when the hit destroys
    the player.

    Every attack stamps ``enemy_fired`` (doc 49 SETTLED 5): the shot
    closes the Pirate opener window hit or miss, before resolution.
    The SINGLE-SHOT primitive (doc 56 phase 5): the engagement
    decision fires the volley mirror instead; doc 54's flee reaction
    is this consumer and keeps its shape — one top-scoring reach
    weapon, stamped and paid per attack."""
    state.enemy_fired = True
    _e_ws = find_weapon(_ei.weapons[_slot].item_id)
    _pay_fire_costs(_ei, _slot, _e_ws)
    return await _enemy_shot_tail(
        state, _ei, _slot,
        hit_chances=hit_chances, evade_bonus=evade_bonus, calc_cam=calc_cam, ctx=ctx,
    )


def _resolve_enemy_shot(state, _ei, _wid, _weapon_quality: int = 0):
    """Roll and resolve one enemy shot.

    Damage resolves BEFORE animating so the floating damage number
    rides the shot's impact frames. Misses return zeroed damage with
    the current hull. ``_weapon_quality`` is the flown instance's
    rolled tier (doc 48.7) — quality scales damage AND accuracy
    (doc 47 SETTLED 2, space side landed 2026-09-28).
    """
    _dist = _distance(state.player_state["pos"], _ei.pos)
    # Resolution-only reads the Bounty Hunter's +5 evade (doc 49
    # SETTLED 7): the AI-belief sites (repositioning, weapon ranking)
    # stay unmodified, so enemies misjudge the hunter by design.
    from ..xp import bounty_hunter_evade_bonus
    _dodge = (
        _player_dodge(state.player_state)
        + bounty_hunter_evade_bonus(state.ctx)
    )
    _chance = calc_hit_chance(
        _wid, _ei.pilot_gunnery, _dist, _dodge,
        weapon_quality=_weapon_quality,
    )
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
        enemies=_mf.merged_targets(state),
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
