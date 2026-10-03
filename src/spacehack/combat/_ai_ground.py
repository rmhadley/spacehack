"""Ground combat enemy AI — movement + fire logic for on-foot enemies.

Mirrors :mod:`combat._ai` which handles ship enemy behavior. The
VOLLEY loop (doc 48 SETTLED 41 — the one-shot cap is dead): every
decision point scores BOTH carried sets' weapons by EV-per-AP through
the same hit math the shot resolves with, fires the top affordable
scorer, and repeats until AP or ammo run out. When the best score
lives in the other set: a silent 1-AP swap (doc 48 SETTLED 43 — dry,
point-blank, and cornered switches are EMERGENT from the scorer).
Movement legs manage RANGE (doc 48 SETTLED 26): back off inside min,
close beyond max or without LOS, dance with leftovers — melee never
repositions (no knife-dancers). Guards leash to their post at the
RANGED slot weapon's ``max_range + 2`` (SETTLED 18/37/43).

A WEAPONLESS spec (doc 48 phase 9 — the Watcher, whose stare is its
attack) runs the drift instead: dial-gated LOS-keeping steps, real
ledger cells, logs nothing.
"""

from __future__ import annotations

from .. import world
from .. import message_log as _ml
from .. import ground_loadout
from ..engine import RNG
from .. import animation_timing
from ..dungeon_fov import cell_in_sight
from ._animations import (
    _damage_popup_for,
    _responsive_sleep,
    _present,
)
from ._messages import enemy_attack_line as _enemy_attack_line
from ._shot_animations import _animate_ground_shot

_STEP_DIRS: tuple[tuple[int, int], ...] = (
    (-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1),
)


async def run_ground_enemy_turn(
    ctx,
    *,
    enemy_spec,
    enemy_stats,
    enemy_ap: int,
    player_pos: world.Position,
    enemy_entity: world.Entity,
    game_map: world.GameMap,
    armor_defense: int,
    console=None,
    render_callback=None,
    player_dodge: int = 0,
) -> tuple[int, int, bool, int]:
    """One enemy ground turn: the volley loop over both carried sets
    (SETTLED 41/43 — the weapon comes from the entity's loadout stamp,
    never a parameter).

    Mutates ``enemy_entity.pos`` in place; the caller applies the
    returned damage. Returns ``(remaining_ap, damage_dealt, fired,
    cells_moved)`` — cells are REAL movement only, the input the
    movement-dodge ledger books (a reload or swap never inflates
    dodge).
    """
    if enemy_ap <= 0:
        return (enemy_ap, 0, False, 0)
    _stamp = ground_loadout.ensure_loadout(enemy_entity, game_map, enemy_spec)
    if not ground_loadout.has_any_weapon(_stamp):
        return await _weaponless_drift(
            ctx, console, render_callback, game_map, enemy_entity,
            player_pos, enemy_spec, enemy_ap,
        )
    return await _spend_ground_ap(
        ctx, console, render_callback, game_map,
        enemy_entity, enemy_spec, enemy_stats,
        armor_defense, player_dodge, enemy_ap, _stamp,
    )


async def _weaponless_drift(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_spec, enemy_ap,
):
    """The weaponless turn (doc 48 p9: the Watcher carries no weapon
    row — the stare is its attack): leftover AP goes to drift steps —
    each a WALKABLE, LOS-KEEPING step (legal sans a weapon band),
    each gated by the SAME aggressiveness dial rolled per decision
    point (below holds; at/above steps one) so the authored dial
    composes: the low-dial machine drifts, the high-dial one sits.
    A weaponless turn LOGS NOTHING (wordless — no position spam);
    never a statue while a legal step exists. The returned cells ARE
    the ledger: the drift is movement dodge."""
    _ap, _cells = enemy_ap, 0
    while _ap > 0:
        if RNG.randint(1, 100) < enemy_spec.ai_aggressiveness:
            break  # hold
        if not await _reposition_step(
            ctx, console, render_callback, game_map, enemy_entity,
            player_pos, None,
        ):
            break  # no legal drift step — hold
        _ap -= 1
        _cells += 1
    return (_ap, 0, False, _cells)


def _mutual_sight(game_map, cell, player_pos) -> bool:
    """The enemy-side sight read (the 09-02 symmetry, 2026-10-02
    unified): the enemy sees the player iff its own cell sits in the
    player's sight grid — the same predicate the player's fire and
    aggro read, so an engagement can never be one-sided."""
    return cell_in_sight(game_map, cell.x, cell.y, player_pos.x, player_pos.y)


def _score_ground_weapon(
    ws, quality: int, dist, enemy_stats, armor_defense: int,
    player_dodge: int, ctx,
) -> float:
    """EV-per-AP through the SAME math the shot resolves with (doc 48
    SETTLED 41 — the space scorer's ground twin): damage x hit-chance
    x shots-per-action / ap_cost, quality folded in on both terms and
    the burst folded so burst weapons score their burst."""
    from ._ground_math import (
        ground_damage_raw,
        ground_hit_chance_raw,
        ground_point_blank_penalty,
    )

    _chance = ground_hit_chance_raw(
        ws.id, enemy_stats.reflexes, ctx.ground_stats.reflexes,
        target_dodge_bonus=player_dodge,
        range_penalty=ground_point_blank_penalty(ws.id, int(dist)),
        quality=quality,
    )
    _damage = ground_damage_raw(
        ws.id, enemy_stats.strength, armor_defense, quality=quality,
    )
    _shots = max(1, ws.shots_per_action)
    return _damage * (_chance / 100.0) * _shots / ws.ap_cost


def _volley_pick(
    stamp, enemy_stats, armor_defense, player_dodge, dist, los, ap, ctx,
):
    """The decision point's weapon: the top total-EV candidate across
    BOTH carried sets (doc 48 SETTLED 43 — switching is emergent).
    A candidate must be within max range with LOS (inside min stays
    pickable at the point-blank penalty — see :func:`_pickable`),
    ammo-feedable (magazine or pool), and affordable including the
    cross-set swap's 1 AP and a dry magazine's reload cost; total EV
    scales
    EV-per-AP by the actions the remaining bank buys, so the swap
    overhead folds in honestly. Ties break to the ACTIVE set, then
    the ranged slot. ``None`` when nothing qualifies."""
    from ..data.ground_weapons import find_ground_weapon as _find_gw

    _active = ground_loadout.active_set(stamp)
    _best = None
    for _order, _set_name in enumerate(
        (_active, ground_loadout.other_set(_active)),
    ):
        _pair = ground_loadout.pair_for(stamp, _set_name)
        if _pair is None:
            continue
        try:
            _ws = _find_gw(_pair[0])
        except KeyError:
            continue
        if not _pickable(_ws, stamp, dist, los):
            continue
        _ev = _total_ev(
            stamp, _set_name == _active, _ws, _pair[1], ap,
            dist, enemy_stats, armor_defense, player_dodge, ctx,
        )
        if _ev < 0:
            continue  # unaffordable this decision point
        _key = (_ev, -_order)
        if _best is None or _key > _best[0]:
            _best = (_key, _set_name, _pair, _ws)
    return None if _best is None else _best[1:]


def _total_ev(
    stamp, is_active, ws, quality, ap, dist, enemy_stats, armor_defense,
    player_dodge, ctx,
) -> float:
    """One candidate's total EV for the remaining bank: EV-per-AP
    scaled by the actions it can still buy, net of the cross-set swap
    and the dry-magazine reload — both overheads fold in honestly
    (SETTLED 43: the swap cost folded in; p9 b4 adds the reload)."""
    _overheads = (0 if is_active else 1)
    if ground_loadout.needs_reload(stamp, ws):
        _overheads += ws.reload_ap_cost
    if ws.ap_cost + _overheads > ap:
        return -1.0  # unaffordable, never picked
    _score = _score_ground_weapon(
        ws, quality, dist, enemy_stats, armor_defense, player_dodge, ctx,
    )
    return _score * ((ap - _overheads) // ws.ap_cost)


def _within_max(ws, dist, los) -> bool:
    """The max-band law both fire gates share: within max range with
    LOS. Inside min fires at the point-blank penalty (the player's
    emergency-shot mirror, p9 b3); beyond max never fires."""
    return dist <= ws.max_range and bool(los)


def _pickable(ws, stamp, dist, los) -> bool:
    """A volley candidate's gates: :func:`_within_max` plus ammo —
    the magazine pays a shot, or the pool can refill it (the reload
    era's gate: a dry-magazine gun stays pickable while its carried
    pool lives; the fire path pays the reload first)."""
    return _within_max(ws, dist, los) and ground_loadout.can_feed_shot(
        stamp, ws,
    )


def _reload_active(ctx, stamp, ws, enemy_spec) -> tuple:
    """Pay the weapon's ``reload_ap_cost``, chamber rounds from the
    carried pool (the player's reload law), and log the tell — the
    player's window on the enemy's ammo (doc 48 SETTLED 43; the line's
    wording is the approved brief's). The beat books ZERO movement
    cells: a reload never inflates the dodge ledger."""
    _moved = ground_loadout.reload_from_pool(stamp, ws)
    if _moved <= 0:
        return 0, 0, False, 0, True  # defensive: cannot happen pickable
    ctx.log.add_colored(
        f"{enemy_spec.name} slams in a fresh magazine.",
        _ml.COLOR_ENEMY_ACTION,
    )
    return max(1, ws.reload_ap_cost), 0, False, 0, False


async def _spend_ground_ap(
    ctx, console, render_callback, game_map, enemy_entity,
    enemy_spec, enemy_stats, armor_defense, player_dodge, enemy_ap, stamp,
):
    """Run the volley loop (SETTLED 41): per-AP fire across both sets
    until AP, ammo, or options run out. Returns ``(remaining_ap,
    damage, fired, cells_moved)`` — see :func:`run_ground_enemy_turn`.
    The player's position re-reads from ``ctx`` every decision point
    (a knockback displacement mid-turn must not leave later points
    aiming at the vacated cell)."""
    _ap, _dmg, _fired, _cells = enemy_ap, 0, False, 0
    _nav: list = [None, None]  # cached advance path, path goal
    while _ap > 0:
        _spent, _cell, _shot, _hit_dmg, _halt = await _volley_step(
            ctx, console, render_callback, game_map, enemy_entity,
            ctx.player.pos, enemy_spec, enemy_stats, armor_defense,
            player_dodge, stamp, _ap, _nav,
        )
        _ap -= _spent
        _cells += _cell
        _fired = _fired or _shot
        _dmg += _hit_dmg
        if _halt or _spent == 0:
            break
    if not _fired:
        ctx.log.add_colored(
            f"{enemy_spec.name} moves into position.", _ml.COLOR_ENEMY_ACTION,
        )
    return (_ap, _dmg, _fired, _cells)


async def _volley_step(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_spec, enemy_stats, armor_defense, player_dodge, stamp, ap, nav,
):
    """One decision point: ``(ap_spent, cells, fired, damage, halt)``.

    Hugged: back off. With a pick: the dial's fire-vs-dance roll, then
    swap or FIRE. Without: dry-switch, range legs, leftover dance."""
    _aws = _active_weapon_spec(stamp)
    if _aws is None:
        return 0, 0, False, 0, True  # unknown id that left the catalog:
        # inert. (Weaponless stamps never reach here — they route to
        # the drift at :func:`run_ground_enemy_turn`.)
    _dist = _dist_to(enemy_entity.pos.x, enemy_entity.pos.y, player_pos)
    _los = _mutual_sight(game_map, enemy_entity.pos, player_pos)
    if _dist < _aws.min_range and await _back_off_step(
        ctx, console, render_callback, game_map, enemy_entity,
        player_pos, _aws,
    ):
        nav[0] = None  # off the advance path — recompute later
        return 1, 1, False, 0, False
    _pick = _volley_pick(
        stamp, enemy_stats, armor_defense, player_dodge, _dist, _los,
        ap, ctx,
    )
    if _pick is not None:
        return await _pick_or_dance(
            ctx, console, render_callback, game_map, enemy_entity,
            player_pos, enemy_spec, enemy_stats, armor_defense,
            player_dodge, stamp, nav, _aws, _pick,
        )
    return await _gap_step(
        ctx, console, render_callback, game_map, enemy_entity, player_pos,
        stamp, _aws, _dist, _los, nav,
    )


async def _pick_or_dance(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_spec, enemy_stats, armor_defense, player_dodge, stamp, nav,
    aws, pick,
):
    """The with-a-pick decision tail: the dial's fire-vs-dance roll,
    then the pick resolves (a cross-set pick pays the swap first)."""
    _danced = await _maybe_dance_instead(
        ctx, console, render_callback, game_map, enemy_entity,
        player_pos, enemy_spec, aws,
    )
    if _danced:
        nav[0] = None  # off the advance path — recompute later
        return 1, 1, False, 0, False
    return await _fire_the_pick(
        ctx, console, render_callback, game_map, enemy_entity,
        enemy_spec, enemy_stats, armor_defense,
        player_dodge, stamp, pick,
    )


def _active_weapon_spec(stamp):
    """The active weapon's catalog spec, or ``None`` (a weaponless
    stamp, or an id that left the catalog — an inert turn either way)."""
    from ..data.ground_weapons import find_ground_weapon as _find_gw

    _pair = ground_loadout.active_pair(stamp)
    if _pair is None:
        return None
    try:
        return _find_gw(_pair[0])
    except KeyError:
        return None


async def _maybe_dance_instead(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_spec, aws,
) -> bool:
    """The aggressiveness dial (SETTLED 23/43, RAW ground-side): roll
    below fires; at/above buys ONE in-band reposition step instead —
    re-rolled every decision point, ranged-only (no knife-dancers),
    and nowhere legal to dance reads as False so the caller fires."""
    if RNG.randint(1, 100) < enemy_spec.ai_aggressiveness:
        return False  # fire
    if aws.max_range <= 1:
        return False  # melee holds
    return await _reposition_step(
        ctx, console, render_callback, game_map, enemy_entity,
        player_pos, aws,
    )


async def _fire_the_pick(
    ctx, console, render_callback, game_map, enemy_entity,
    enemy_spec, enemy_stats, armor_defense, player_dodge, stamp, pick,
):
    """Resolve one scorer pick: a cross-set pick first pays the silent
    1-AP swap (once per switch, never per shot — SETTLED 43); the
    active pick fires one full burst action at its own AP cost."""
    _set_name, _pair, _ws = pick
    if _set_name != ground_loadout.active_set(stamp):
        ground_loadout.swap_active(stamp)  # silent 1-AP switch
        return 1, 0, False, 0, False
    if ground_loadout.needs_reload(stamp, _ws):
        return _reload_active(ctx, stamp, _ws, enemy_spec)
    _dmg = await _fire_enemy_burst(
        ctx, console, render_callback, game_map, enemy_entity,
        _pair[0], _ws, enemy_spec, enemy_stats,
        armor_defense, player_dodge, _pair[1], stamp,
    )
    return _ws.ap_cost, 0, True, _dmg, False


async def _gap_step(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    stamp, aws, dist, los, nav,
):
    """The no-pick tail: dry-switch to the other set, advance toward
    the chase goal, or spend a leftover AP on the dance (SETTLED 40's
    termination shape — dodge while a legal in-band step exists)."""
    if ground_loadout.is_dry(stamp, aws) and ground_loadout.pair_for(
        stamp, ground_loadout.other_set(ground_loadout.active_set(stamp)),
    ) is not None:
        ground_loadout.swap_active(stamp)  # dry: 1-AP swap to melee
        return 1, 0, False, 0, False
    if dist > aws.max_range or not los:
        _stepped, nav[0], nav[1], _halt = await _ground_advance(
            ctx, console, render_callback, game_map, enemy_entity,
            player_pos, nav[0], nav[1],
        )
        return (1 if _stepped else 0), (1 if _stepped else 0), False, 0, _halt
    if aws.max_range > 1 and await _reposition_step(
        ctx, console, render_callback, game_map, enemy_entity,
        player_pos, aws,
    ):
        nav[0] = None  # off the advance path — recompute later
        return 1, 1, False, 0, False
    return 0, 0, False, 0, True


def _free_cell(game_map, enemy_entity, x: int, y: int) -> bool:
    """A walkable cell no body stands on."""
    return game_map.is_walkable(x, y) and game_map.blocking_entity_at(
        x, y, exclude=enemy_entity,
    ) is None


async def _step_to(
    ctx, console, render_callback, game_map, enemy_entity, x, y,
) -> bool:
    """Move one cell and present the step (combat animates every move)."""
    enemy_entity.pos = world.Position(x, y)
    if render_callback is not None and console is not None:
        if animation_timing.render_frames_enabled():
            render_callback(console, ctx, game_map)
            _present(ctx, console)
        await _responsive_sleep(animation_timing.GROUND_STEP, ctx.context)
    return True


def _dist_to(x: int, y: int, player_pos) -> float:
    from ._stats import _distance

    return _distance(world.Position(x, y), player_pos)


async def _back_off_step(
    ctx, console, render_callback, game_map, enemy_entity, player_pos, _ews,
):
    """One step toward restoring ``>= min_range`` — restoring steps
    first, LOS-keeping preferred, then any step that strictly widens
    the gap (SETTLED 26). Pinned with no qualifying cell: inert, by
    design — cornering a ranged face is the counter-play."""
    def _rank(cell):
        _x, _y = cell
        _d = _dist_to(_x, _y, player_pos)
        return (
            _d >= _ews.min_range,
            _mutual_sight(game_map, world.Position(_x, _y), player_pos),
            _d,
        )

    _cur = _dist_to(
        enemy_entity.pos.x, enemy_entity.pos.y, player_pos,
    )
    _pool = [
        (enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy)
        for _dx, _dy in _STEP_DIRS
        if _free_cell(
            game_map, enemy_entity,
            enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy,
        )
        and (
            _dist_to(enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy,
                     player_pos) >= _ews.min_range
            or _dist_to(enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy,
                        player_pos) > _cur
        )
    ]
    if not _pool:
        return False
    _x, _y = max(_pool, key=_rank)
    return await _step_to(
        ctx, console, render_callback, game_map, enemy_entity, _x, _y,
    )


async def _reposition_step(
    ctx, console, render_callback, game_map, enemy_entity, player_pos, _ews,
):
    """One random in-band LOS-keeping step — the skirmisher dance that
    leftover AP buys after the one-shot cap (SETTLED 26). No such cell:
    hold position. ``_ews=None`` is the WEAPONLESS drift (doc 48 p9):
    any walkable LOS-keeping cell, no weapon band."""
    _pool = [
        (enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy)
        for _dx, _dy in _STEP_DIRS
        if _free_cell(
            game_map, enemy_entity,
            enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy,
        )
        and (
            _ews is None
            or _ews.min_range <= _dist_to(
                enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy, player_pos,
            ) <= _ews.max_range
        )
        and _mutual_sight(
            game_map,
            world.Position(enemy_entity.pos.x + _dx, enemy_entity.pos.y + _dy),
            player_pos,
        )
    ]
    if not _pool:
        return False
    _x, _y = RNG.choice(_pool)
    return await _step_to(
        ctx, console, render_callback, game_map, enemy_entity, _x, _y,
    )


async def _try_ground_fire(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, _ews, enemy_spec, enemy_stats, armor_defense,
    player_dodge, enemy_weapon_quality=0, stamp=None,
):
    """One shot when in range with LOS: ``(damage, ap_cost)``, else None.

    The flee reaction volley's seam (doc 54): it re-checks band and
    LOS itself, then resolves one FIRE action through the shared
    burst — magazine drain included when the stamp is passed.
    """
    from ._stats import _distance

    _dist = _distance(enemy_entity.pos, player_pos)
    _los = _mutual_sight(game_map, enemy_entity.pos, player_pos)
    if _ews is None or not _within_max(_ews, _dist, _los):
        return None  # beyond max or blind: no parting shot. Inside min
        # pays the point-blank penalty — the player's emergency-shot
        # mirror (p9 b3).
    _total = await _fire_enemy_burst(
        ctx, console, render_callback, game_map, enemy_entity,
        enemy_weapon_id, _ews, enemy_spec, enemy_stats, armor_defense,
        player_dodge, enemy_weapon_quality, stamp,
    )
    return _total, (_ews.ap_cost if _ews else 1)


async def _fire_enemy_burst(
    ctx, console, render_callback, game_map, enemy_entity,
    enemy_weapon_id, _ews, enemy_spec, enemy_stats, armor_defense,
    player_dodge, enemy_weapon_quality, stamp=None,
) -> int:
    """Roll and present one FIRE action's shots (``shots_per_action``
    rolls, doc 50 SETTLED 8); total damage. The burst stops mid-action
    when the magazine cannot pay another shot (the player's quiet
    dry-break mirror) and drains ``ammo_per_shot`` per shot fired.

    Every burst stamps the ground fight's ``enemy_fired`` (doc 49
    SETTLED 5): an enemy shot closes the Pirate opener window, hit
    or miss."""
    from . import _rules_ground

    if _rules_ground._state is not None:
        _rules_ground._state.enemy_fired = True
    _total = 0
    for _ in range(max(1, _ews.shots_per_action) if _ews else 1):
        if stamp is not None and not ground_loadout.magazine_pays_shot(
            stamp, _ews,
        ):
            break  # burst ran dry mid-action — stop quietly
        _total += await _one_enemy_shot(
            ctx, console, render_callback, game_map, enemy_entity,
            enemy_weapon_id, enemy_weapon_quality, enemy_spec,
            enemy_stats, armor_defense, player_dodge,
        )
        if stamp is not None:
            ground_loadout.drain_action(stamp, _ews, 1)  # per shot
    return _total


async def _one_enemy_shot(
    ctx, console, render_callback, game_map, enemy_entity,
    enemy_weapon_id, enemy_weapon_quality, enemy_spec, enemy_stats,
    armor_defense, player_dodge,
) -> int:
    """One shot of a burst: the firing report (SETTLED 22), then
    either the field's absorption (doc 48 SETTLED 42) or the roll.
    Returns the shot's damage; the player's position reads LIVE from
    ``ctx`` (a knockback mid-burst must not leave later shots aiming
    at the vacated cell)."""
    from .. import noise
    from ._ancients import absorb_shot, carries_field

    _player_pos = ctx.player.pos
    noise.emit(
        ctx, game_map, enemy_entity.pos, enemy_weapon_id, by_player=False,
    )
    _absorbed = absorb_shot(
        game_map, enemy_entity.pos, _player_pos,
        shooter_carries_field=carries_field(enemy_spec),
    )
    if _absorbed is not None:
        return await _absorbed_enemy_shot(
            ctx, console, render_callback, game_map, enemy_entity,
            _player_pos, enemy_weapon_id, enemy_weapon_quality,
            enemy_spec, _absorbed,
        )
    return await _resolve_enemy_shot(
        ctx, console, render_callback, game_map, enemy_entity,
        _player_pos, enemy_weapon_id, enemy_weapon_quality, enemy_spec,
        enemy_stats, armor_defense, player_dodge,
    )


async def _resolve_enemy_shot(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, enemy_weapon_quality, enemy_spec, enemy_stats,
    armor_defense, player_dodge,
) -> int:
    """The unobstructed shot's tail: the roll, the per-event
    player-defense reduction (doc 49 — each landed shot pays it,
    never the summed turn), presentation, and the knockback tail."""
    from ..xp import apply_ground_damage_reduction as _reduce
    from ._stats import _distance

    _hit, _damage, _popup = _roll_ground_shot(
        ctx, enemy_weapon_id, enemy_stats, armor_defense, player_dodge,
        int(_distance(enemy_entity.pos, player_pos)), enemy_weapon_quality,
    )
    if _damage > 0:
        _damage = _reduce(ctx, _damage)
    await _present_enemy_shot(
        ctx, console, render_callback, game_map,
        enemy_entity, player_pos, enemy_weapon_id, enemy_weapon_quality,
        enemy_spec, _hit, _damage, _popup,
    )
    if _hit:
        _apply_hit_knockback(
            ctx, game_map, enemy_entity, player_pos, enemy_weapon_id,
        )
    return _damage


async def _absorbed_enemy_shot(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, enemy_weapon_quality, enemy_spec, absorbed,
) -> int:
    """The field prices projectiles uniformly (doc 48 SETTLED 42): a
    shot crossing a shell tile pays the TILE — the report reads as a
    miss (wordless: the player-facing absorb prose is the player
    seam's own), and nothing reaches the player. The miss presents
    BEFORE the tile pays, so a breaking tile's line reads after it."""
    from ._ancients import damage_field_tile, projectile_damage

    await _present_enemy_shot(
        ctx, console, render_callback, game_map,
        enemy_entity, player_pos, enemy_weapon_id, enemy_weapon_quality,
        enemy_spec, False, 0, None,
    )
    damage_field_tile(
        ctx, game_map, absorbed,
        projectile_damage(enemy_weapon_id, enemy_weapon_quality),
    )
    return 0


def _apply_hit_knockback(ctx, game_map, enemy_entity, player_pos, weapon_id):
    """A knockback-carrying hit displaces the victim along the
    attacker→victim vector (doc 48 SETTLED 42 — the Warden's slam;
    the property is weapon data). Wordless by design: the
    displacement IS the tell. Pure displacement — no collision
    damage. The player's new cell re-reveals, mirroring the
    in-combat player step and the charge displacement."""
    from ..data.ground_weapons import find_ground_weapon as _find_gw
    from ..dungeon import reveal_around as _reveal_around
    from ._actions import apply_knockback

    try:
        _kb = _find_gw(weapon_id).knockback
    except KeyError:
        return
    if _kb <= 0:
        return
    _dx = (
        (player_pos.x > enemy_entity.pos.x)
        - (player_pos.x < enemy_entity.pos.x)
    )
    _dy = (
        (player_pos.y > enemy_entity.pos.y)
        - (player_pos.y < enemy_entity.pos.y)
    )
    if apply_knockback(game_map, ctx.player, _dx, _dy, _kb):
        _reveal_around(
            game_map, ctx.player.pos, radius=game_map.sight_radius,
        )


async def _present_enemy_shot(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    enemy_weapon_id, enemy_weapon_quality, enemy_spec, hit, damage, popup,
) -> None:
    """Log and animate one enemy shot at the wielded variant's label."""
    from ..ground_equipment import display_name

    _line = _enemy_attack_line(
        enemy_spec.name, enemy_weapon_id,
        display_name("weapon", enemy_weapon_id, enemy_weapon_quality),
        hit=hit, hull_dmg=damage, quality=enemy_weapon_quality,
    )
    ctx.log.add_colored(_line, _ml.COLOR_ENEMY_ACTION, runs=_line.runs)
    if console is not None and render_callback is not None:
        await _animate_ground_shot(
            console, ctx, game_map,
            enemy_entity.pos, player_pos,
            enemy_weapon_id, is_hit=hit,
            damage=popup,
            render_callback=render_callback,
        )


def _roll_ground_shot(
    ctx, enemy_weapon_id, enemy_stats, armor_defense, player_dodge,
    distance: int, enemy_weapon_quality=0,
):
    """(hit, damage, popup) for one ground shot — miss damage is 0.

    ``enemy_stats`` is the instance's band-derived block (doc 48
    SETTLED 35). The wielded weapon fights at its equip-time rolled
    quality (SETTLED 13): what was firing at you is what drops. The
    point-blank penalty applies to enemy shots too (doc 48 phase 9 —
    ONE hit math, both sides: the player's own rule mirrored, which is
    what makes the hug-driven set-switch honest rather than vacuous).
    """
    from ._ground_math import (
        ground_damage_raw,
        ground_hit_chance_raw,
        ground_point_blank_penalty,
    )

    _penalty = ground_point_blank_penalty(enemy_weapon_id, distance)
    _hit = RNG.randint(1, 100) <= ground_hit_chance_raw(
        enemy_weapon_id, enemy_stats.reflexes, ctx.ground_stats.reflexes,
        target_dodge_bonus=player_dodge, range_penalty=_penalty,
        quality=enemy_weapon_quality,
    )
    if not _hit:
        return False, 0, None
    _damage = ground_damage_raw(
        enemy_weapon_id, enemy_stats.strength, armor_defense,
        quality=enemy_weapon_quality,
    )
    return True, _damage, _damage_popup_for(_damage, 0, False)


def _chase_goal(
    player_pos, guard_post, enemy_entity, game_map=None,
) -> tuple[int, int]:
    """The chase goal: the player, or the guard post beyond the leash
    — the entity's rolled weapon ``max_range + 2`` (doc 48 SETTLED
    18/37; the hardcoded radius 8 retired with it)."""
    from ._stats import _distance

    if guard_post is not None:
        from .. import noise

        if _distance(player_pos, guard_post) > noise.guard_leash(
            enemy_entity, game_map,
        ):
            return (guard_post.x, guard_post.y)
    return (player_pos.x, player_pos.y)


async def _ground_advance(
    ctx, console, render_callback, game_map, enemy_entity, player_pos,
    _cached_path, _path_goal,
):
    """One step toward the chase goal.

    Returns ``(stepped, cached_path, path_goal, halt)``: the path is
    computed once per goal and recomputed when a step is blocked;
    ``halt`` ends the enemy's turn (no path, or at the player).
    """
    _goal = _chase_goal(
        player_pos, getattr(enemy_entity, 'guard_post', None),
        enemy_entity, game_map,
    )

    if _cached_path is None or _path_goal != _goal:
        _cached_path = world.find_path(
            (enemy_entity.pos.x, enemy_entity.pos.y),
            {_goal},
            game_map,
            exclude_entity=enemy_entity,
        )
        _path_goal = _goal
    if not _cached_path:
        return False, _cached_path, _path_goal, True  # no path to goal

    _nx, _ny = _cached_path.pop(0)
    if (_nx, _ny) == (player_pos.x, player_pos.y):
        return False, _cached_path, _path_goal, True  # don't move into player
    if not _free_cell(game_map, enemy_entity, _nx, _ny):
        return False, None, _path_goal, False  # blocked — recompute path
    await _step_to(
        ctx, console, render_callback, game_map, enemy_entity, _nx, _ny,
    )
    return True, _cached_path, _path_goal, False
