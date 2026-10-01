"""Missile flight — the crossing-entity domain (doc 57, SETTLED 11).

Flight model v2 (the playtest rework): a launched missile DEPLOYS into
a cell near the shooter (never the shooter's own), immediately makes
its launch HALF-move (half the normal move range, full collision
rules), then holds until the start of the shooter's turn — the
shooter's MINI-TURN moves every one of its missiles one at a time,
FULL speed, through the collision rules: same-shooter missiles are
actively avoided (never share a cell), any ship contact detonates the
warhead on that ship (full damage on contact, ruling), blocking
terrain detonates harmlessly, and missiles never detonate on missiles.

Pure advance math, the guidance roll, and the flight finishers live
here; the state-holder seams (spawn on fire, the round-boundary hook,
the intercept kill) hang off ``SpaceCombatState.in_flight``.

In-flight state is combat-transient: combat never saves mid-fight,
and :func:`sweep_flights` clears it on every combat end path —
nothing serializes, nothing leaks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import world
from ..data.quality import effective_ship_weapon_spec
from ..data.weapons import find_weapon as _find_weapon
from ._stats import _calc_dodge_bonus, _distance, clamp_hit_chance

# Family by shape, side by color (doc 57 SETTLED 10): the heavy's fat
# dense diamond reads as the flak-worthy crossing; the light's quick
# star as thin enough to maybe eat. Unknown racks fall back to the
# light read.
_GLYPH_BY_WEAPON: dict[str, str] = {"heavy_missile": "♦", "light_missile": "*"}

HOSTILE_FG: tuple[int, int, int] = (255, 80, 80)     # hot red — dread at a glance
PLAYER_FG: tuple[int, int, int] = (120, 225, 255)    # cyan friendly accent

_HALF_MOVE_DIVISOR = 2


def is_flight_weapon(weapon_id: str) -> bool:
    """Whether ``weapon_id`` resolves as a crossing flight missile
    (``flight_speed > 0``). The EMP pulse (0) stays instant."""
    try:
        return _find_weapon(weapon_id).flight_speed > 0
    except KeyError:
        return False


def catalog_floor(ws) -> int:
    """The hard fire floor for one rack spec (doc 57 SETTLED 2): flight
    missiles read the CATALOG min — Focus's doubled min-range never
    widens the refusal band; every other weapon returns 0 and keeps
    today's penalty semantics. The ONE read the gate, the range line,
    the HUD distance, and the card's HIT color share (ground specs
    carry no ``flight_speed`` — getattr keeps them at 0)."""
    return ws.min_range if getattr(ws, "flight_speed", 0) > 0 else 0


def merged_targets(state) -> list:
    """The merged targeting space over a state: alive enemies, then
    every live in-flight missile. One definition shared by the rules
    accessor, the loop's cycle/fire paths, and every frame renderer
    that paints the enemy block with ``target_idx`` (doc 57)."""
    return [e for e in state.enemy_insts if e.alive] + [
        m for m in state.in_flight if m.alive
    ]


@dataclass
class InFlightMissile:
    """One live crossing missile (doc 57 SETTLED 1/11).

    The field shape is EnemyInstance-compatible on every read the
    volley paths use (``name``/``pos``/``hull``/``max_hull``/
    ``shields``/``alive``/``cells_moved_this_turn``/
    ``pilot_piloting``/``weapons``), so ``hit_chance``, ``damage``,
    and the strip path work with no adapter layer. Dodge is 0 by
    construction (deterministic traveler), shields 0 (strip weapons
    do nothing by construction, not special case).
    """

    weapon_id: str
    pos: world.Position
    target: Any = None
    quality: int = 0
    side: str = "player"
    hull: int = 0                     # remaining missile_hp
    max_hull: int = 0
    fuel: int = 0                     # cells of travel left
    flight_speed: int = 0
    name: str = ""
    char: str = "*"
    fg: tuple[int, int, int] = HOSTILE_FG
    ent: world.Entity | None = None   # the render twin (non-blocking)
    shields: int = 0
    max_shields: int = 0
    alive: bool = True
    cells_moved_this_turn: int = 0
    pilot_piloting: int = 0
    weapons: tuple = ()


@dataclass(frozen=True)
class FlightStep:
    """One cell hop's pure result.

    ``path`` is the next track cell (empty when the missile cannot
    move); ``arrived`` when that cell is the target's;
    ``fuel_exhausted`` when the tank hits zero short of it.
    """

    path: tuple[tuple[int, int], ...]
    arrived: bool
    fuel_exhausted: bool


def advance_step(
    pos: world.Position, target_pos: world.Position,
    speed: int, fuel: int,
) -> FlightStep:
    """The hop math (pure): up to ``speed`` cells along the straight
    track toward the target's live position, capped by remaining fuel
    — re-vectoring happens per caller step because the caller passes
    the target's CURRENT position. Overshoot stops at the target,
    never past it."""
    from ._animations import _bresenham_line

    _cells = list(_bresenham_line(pos.x, pos.y, target_pos.x, target_pos.y))
    if not _cells:
        return FlightStep((), True, False)
    _hop = _cells[:max(0, min(speed, fuel))]
    if not _hop:
        return FlightStep((), False, True)
    _arrived = len(_hop) == len(_cells)
    _dry = fuel - len(_hop) <= 0 and not _arrived
    return FlightStep(tuple(_hop), _arrived, _dry)


def guidance_hit_chance(
    weapon_id: str, gunnery: int, target_dodge: int,
    hit_bonus: int = 0, *, weapon_quality: int = 0,
) -> int:
    """The arrival guidance roll (doc 57 SETTLED 5): quality-scaled
    launcher accuracy + the shooter's gunnery half-rate − the
    target's dodge-at-arrival, clamped 5-95. No range terms — range
    was paid at launch (the target sat inside [floor, max] when
    fired)."""
    _acc = effective_ship_weapon_spec(weapon_id, weapon_quality).accuracy
    return clamp_hit_chance(_acc + int(gunnery * 0.5) - target_dodge + hit_bonus)


def _half_speed(speed: int) -> int:
    """The launch move (SETTLED 11.3/5): half the normal move range,
    at least one cell."""
    return max(1, speed // _HALF_MOVE_DIVISOR)


def _occupied_by_missile(state, cell: world.Position) -> bool:
    return any(
        _m.alive and _m.pos.x == cell.x and _m.pos.y == cell.y
        for _m in state.in_flight
    )


def _nearest_free_cell(
    state, origin: world.Position, goal: world.Position,
) -> world.Position | None:
    """The free 8-neighbor of ``origin`` nearest ``goal`` (fixed tie
    order): walkable, ship-free, missile-free. ``None`` when boxed."""
    from ._ai import _STEP_DELTAS

    _best = None
    for _dx, _dy in _STEP_DELTAS:
        _cell = world.Position(origin.x + _dx, origin.y + _dy)
        if not state.game_map.is_walkable(_cell.x, _cell.y):
            continue
        if state.game_map.blocking_entity_at(_cell.x, _cell.y) is not None:
            continue
        if _occupied_by_missile(state, _cell):
            continue
        _dist = _distance(_cell, goal)
        if _best is None or _dist < _best[0]:
            _best = (_dist, _cell)
    return None if _best is None else _best[1]


def _spawn_cell(state, launch_pos: world.Position, target) -> world.Position:
    """Where the missile appears (SETTLED 11.2/4): a free cell near the
    shooter, nearest the target; the shooter's own cell when every
    neighbor is blocked (the show goes on — the half-move's first step
    usually clears it; the boxed corner rests one mini-turn against
    the hull, which the parking pre-check reads as contact)."""
    return _nearest_free_cell(state, launch_pos, target.pos) or launch_pos


def _same_shooter_missile_at(state, cell: world.Position, missile: InFlightMissile):
    """Another live missile OF THE SAME SHOOTER on ``cell`` (SETTLED
    11.6's avoidance trigger); cross-shooter missiles ignore each
    other."""
    for _m in state.in_flight:
        if _m is missile or not _m.alive:
            continue
        if _m.side == missile.side and _m.pos.x == cell.x and _m.pos.y == cell.y:
            return _m
    return None


def _sidestep(state, missile: InFlightMissile) -> world.Position | None:
    """The avoidance move (SETTLED 11.6): the free 8-neighbor nearest
    the target. ``None`` when boxed in (hold station, fuel intact)."""
    return _nearest_free_cell(state, missile.pos, missile.target.pos)


def _ship_at(state, cell: world.Position):
    """The ship standing at ``cell``: an alive enemy, the player, or
    None — missiles never count (SETTLED 11.6: they cannot collide
    with missiles)."""
    for _e in state.enemy_insts:
        if _e.alive and _e.pos.x == cell.x and _e.pos.y == cell.y:
            return _e
    _p = state.player_state["pos"]
    if _p.x == cell.x and _p.y == cell.y:
        return "player"
    return None


def _arrival_dodge(target) -> int:
    """The target's dodge-at-contact (doc 57 SETTLED 5): the existing
    ``_calc_dodge_bonus`` assembly over its latest-round movement."""
    return _calc_dodge_bonus(
        target.cells_moved_this_turn, int(target.pilot_piloting * 0.5),
    )


def _guided(state, ctx, missile: InFlightMissile, target_dodge: int) -> bool:
    """The guidance roll against a precomputed dodge (the ONE roll
    every contact site shares)."""
    from ..engine import RNG
    from ._rules_space import _player_hit_bonus

    _chance = guidance_hit_chance(
        missile.weapon_id, state.player_state["gunnery"], target_dodge,
        _player_hit_bonus(ctx, missile.weapon_id),
        weapon_quality=missile.quality,
    )
    return RNG.randint(1, 100) <= _chance


def _arrival_hits(state, ctx, missile: InFlightMissile, target) -> bool:
    """The guidance roll at contact: quality-scaled launcher accuracy
    against the struck ship's then-current dodge."""
    return _guided(state, ctx, missile, _arrival_dodge(target))


def _log_detonates_short(state) -> None:
    """The one harmless-detonation line (terrain, ship-miss,
    self-splash-miss — DRAFT vocabulary, checkpoint approval)."""
    from .. import message_log as _ml

    state.log.add_colored(
        "Missile detonates short.", _ml.COLOR_PLAYER_ACTION,
    )


def _apply_contact_damage(missile: InFlightMissile, target) -> tuple[int, int, int, bool]:
    """Resolve the impact through the normal damage path (doubled rack
    damage × quality × variance, shields first) and write the ship."""
    from ._actions import resolve_damage

    _dmg, _sdmg, _fh, _glancing = resolve_damage(
        missile.weapon_id, target.hull, target.shields,
        target_pilot_piloting=target.pilot_piloting,
        weapon_quality=missile.quality,
    )
    target.shields = max(0, target.shields - _sdmg)
    target.hull = _fh
    return _dmg, _sdmg, _fh, _glancing


def _remove_missile(state, game_map: world.GameMap, missile: InFlightMissile) -> None:
    """Take one missile off the map and out of the flight list."""
    missile.alive = False
    if missile.ent is not None and missile.ent in game_map.entities:
        game_map.entities.remove(missile.ent)
    if missile in state.in_flight:
        state.in_flight.remove(missile)


def sweep_flights(state, game_map: world.GameMap) -> None:
    """Clear every in-flight missile (entity + list) — the combat-end
    and abnormal-end cleanup (doc 57's save/load belt): missiles die
    with the fight, never gate the end, never serialize."""
    if state is None:
        return
    for _missile in list(state.in_flight):
        _remove_missile(state, game_map, _missile)


async def finish_intercept(
    state, ctx, game_map: world.GameMap, missile: InFlightMissile,
) -> None:
    """The flak intercept kill (doc 57): entity removed, explosion
    beat, one line — and NEVER ``rules.on_kill`` (no XP, loot, or
    reputation for shooting down ordnance)."""
    from .. import message_log as _ml
    from ._space_kills import _animate_kill_explosion

    _remove_missile(state, game_map, missile)
    await _animate_kill_explosion(state, ctx, game_map, missile)
    state.log.add_colored("Missile destroyed.", _ml.COLOR_COMBAT_EVENT)


async def _detonate_on_ship(
    state, ctx, game_map: world.GameMap, missile: InFlightMissile, ship,
) -> None:
    """Contact with ANY ship (SETTLED 11.7 — ruling: FULL DAMAGE ON
    CONTACT, target or not): the same guidance roll against the struck
    ship's dodge; a hit rides the normal damage path and any kill runs
    the FULL kill chain; a miss is the harmless detonation. Prose
    ruling 2026-10-01: contact hits speak the detonates form (the
    fire-form line stays the target arrival's)."""
    from .. import message_log as _ml
    from ._space_kills import on_kill as _kill_chain

    if not _arrival_hits(state, ctx, missile, ship):
        _log_detonates_short(state)
        return
    _dmg, _sdmg, _fh, _glancing = _apply_contact_damage(missile, ship)
    state.log.add_colored(
        f"Your {_find_weapon(missile.weapon_id).name} detonates on "
        f"{ship.name} for {_dmg} damage.",
        _ml.COLOR_PLAYER_ACTION,
    )
    if _fh > 0:
        return
    ship.alive = False
    state.log.add_colored(f"{ship.name} destroyed!", _ml.COLOR_COMBAT_EVENT)
    await _kill_chain(state, game_map, ship, ctx)


async def _detonate_on_player(state, ctx, missile: InFlightMissile) -> str | None:
    """Contact with the player's own hull (SETTLED 11.7 — self-splash
    is live): the same guidance roll; ``"DEFEAT"`` when the hull goes.
    DRAFT prose (checkpoint approval): the contact line."""
    _ps = state.player_state
    _dodge = _calc_dodge_bonus(
        _ps.get("cells_moved_this_turn", 0),
        int(_ps.get("piloting", 0) * 0.5),
    )
    if not _guided(state, ctx, missile, _dodge):
        _log_detonates_short(state)
        return None
    # A guided non-lethal hit already logged its contact line; only a
    # DEFEAT rides the return.
    return await _apply_player_contact(state, ctx, missile)


async def _apply_player_contact(state, ctx, missile: InFlightMissile) -> str | None:
    """Resolve a GUIDED self-splash hit onto the player state (the
    dict-shaped twin of :func:`_apply_contact_damage`); ``"DEFEAT"``
    when the hull reaches zero."""
    from .. import message_log as _ml
    from ._actions import resolve_damage

    _ps = state.player_state
    _ws = _find_weapon(missile.weapon_id)
    _dmg, _sdmg, _fh, _glancing = resolve_damage(
        missile.weapon_id, _ps["hull"], _ps["shields"],
        target_pilot_piloting=_ps.get("piloting", 0),
        weapon_quality=missile.quality,
    )
    _ps["shields"] = max(0, _ps["shields"] - _sdmg)
    _ps["hull"] = _fh
    if ctx is not None and hasattr(ctx, "player_counters"):
        ctx.player_counters.total_damage_taken += _dmg
    state.last_attacker = f"Your own {_ws.name}"
    state.log.add_colored(
        f"Your {_ws.name} detonates on your own hull for {_dmg} damage.",
        _ml.COLOR_COMBAT_EVENT,
    )
    if _fh > 0:
        return None
    await _present_player_death(state, _ps.get("piloting", 0) // 2)
    return "DEFEAT"


async def _present_player_death(state, evade: int) -> None:
    """The destruction beat on a self-splash kill (the shared
    death presentation)."""
    from ._ai import _present_ship_destruction
    from ._rules_space import _build_hit_chances, _calc_camera

    await _present_ship_destruction(
        state, evade_bonus=evade,
        hit_chances=_build_hit_chances(None), calc_cam=_calc_camera,
    )


async def _travel(
    state, ctx, game_map: world.GameMap, missile: InFlightMissile,
    allowance: int,
) -> str | None:
    """The movement executor (SETTLED 11.3-9): up to ``allowance``
    cells, one at a time, re-vectoring per cell, through the collision
    rules (see :func:`_advance_one_cell`). Returns ``"DEFEAT"`` when a
    missile kills the player."""
    from ._rules_space import _calc_camera

    _cam = _calc_camera()
    _moved = 0
    while _moved < allowance and missile.alive and missile.fuel > 0:
        _cell = _next_cell(state, missile)
        if _cell is None:
            break  # no track or boxed: hold station, fuel intact
        _outcome = await _advance_one_cell(
            state, ctx, game_map, missile, _cell, _cam,
        )
        if _outcome is not None:
            return _outcome  # warhead spent (DEFEAT only on the player)
        _moved += 1
    return None


def _next_cell(state, missile: InFlightMissile) -> world.Position | None:
    """The next cell this step: the track head, or the avoidance
    sidestep when a same-shooter missile holds it (SETTLED 11.6);
    ``None`` when there is no track or nowhere to sidestep."""
    _step = advance_step(missile.pos, missile.target.pos, 1, missile.fuel)
    if not _step.path:
        return None  # already on the target — hold
    _cell = world.Position(*_step.path[0])
    if _same_shooter_missile_at(state, _cell, missile) is None:
        return _cell
    return _sidestep(state, missile)


async def _advance_one_cell(
    state, ctx, game_map: world.GameMap, missile: InFlightMissile,
    cell: world.Position, cam: tuple[int, int],
) -> str | None:
    """Enter one checked cell: terrain detonates harmlessly
    (SETTLED 11.8), any ship contact detonates the warhead on it
    (SETTLED 11.7, full damage on contact), a dry tank exhausts.
    Returns ``"DEFEAT"`` only when the player's own hull went."""
    from .. import message_log as _ml

    if not game_map.is_walkable(cell.x, cell.y):
        _remove_missile(state, game_map, missile)
        _log_detonates_short(state)
        return None
    missile.pos = cell
    if missile.ent is not None:
        missile.ent.pos = cell
    missile.fuel -= 1
    await _render_hop_frame(state, cam)
    _ship = _ship_at(state, cell)
    if _ship is not None:
        _remove_missile(state, game_map, missile)
        if _ship == "player":
            return await _detonate_on_player(state, ctx, missile)
        await _detonate_on_ship(state, ctx, game_map, missile, _ship)
        return None
    if missile.fuel <= 0:
        state.log.add_colored(
            "Missile exhausts its fuel.", _ml.COLOR_PLAYER_ACTION,
        )
        _remove_missile(state, game_map, missile)
    return None


def _build_missile(
    state, weapon_id: str, target, side: str, quality: int,
    launch_pos: world.Position,
) -> InFlightMissile:
    """Construct the crossing missile + its non-blocking render twin
    at the deploy cell (no mounting — the caller appends)."""
    _ws = _find_weapon(weapon_id)
    _spawn = _spawn_cell(state, launch_pos, target)
    _missile = InFlightMissile(
        weapon_id=weapon_id, pos=_spawn, target=target,
        quality=quality, side=side,
        hull=_ws.missile_hp, max_hull=_ws.missile_hp,
        fuel=_ws.max_range, flight_speed=_ws.flight_speed,
        name=_ws.name,
        char=_GLYPH_BY_WEAPON.get(weapon_id, "*"),
        fg=PLAYER_FG if side == "player" else HOSTILE_FG,
    )
    _missile.ent = world.Entity(
        char=_missile.char, fg=_missile.fg, pos=_spawn,
        name=_ws.name, width=1, height=1, non_blocking=True,
    )
    return _missile


async def spawn_flight_missile(
    state, weapon_id: str, target, *, side: str, quality: int,
    launch_pos: world.Position,
) -> InFlightMissile:
    """Deploy one crossing missile (doc 57 SETTLED 11.2-5): it appears
    in a cell NEAR the shooter (never the shooter's own), reads the
    launch line, then makes its launch half-move — half the normal
    move range under the full collision rules. The volley's next
    member deploys after, seeing the previous missile's rest position
    (the stagger is the anti-stack)."""
    from .. import message_log as _ml

    _ws = _find_weapon(weapon_id)
    _missile = _build_missile(state, weapon_id, target, side, quality, launch_pos)
    state.game_map.entities.append(_missile.ent)
    state.in_flight.append(_missile)
    state.log.add_colored(
        f"{_ws.name[0]}{_ws.name[1:].lower()} away.",
        _ml.COLOR_PLAYER_ACTION,
    )
    # A launch-half-move self-splash kill is backstopped by the loop's
    # post-action hp gate (the volley's remaining slots still fire) —
    # reachable only when every progress-side neighbor is blocked.
    await _travel(
        state, state.ctx, state.game_map, _missile,
        _half_speed(_ws.flight_speed),
    )
    return _missile


async def _render_hop_frame(state, cam: tuple[int, int]) -> None:
    """One WAIT-mode frame of the crossing (the wordless dread beat),
    then its pacing sleep."""
    from .. import animation_timing
    from ._animations import _render_anim_frame, _responsive_sleep
    from ._rules_space import _build_hit_chances, _current_target

    _evade = _calc_dodge_bonus(
        state.player_state.get("cells_moved_this_turn", 0),
        int(state.player_state.get("piloting", 0) * 0.5),
    )
    _render_anim_frame(
        state.console, state.ctx, state.game_map,
        cam[0], cam[1], state.view_w, state.view_h,
        state.player_state, merged_targets(state), state.target_idx, state.log,
        weapon_list=tuple(state.weapons_list),
        active_weapons=state.active_weapons,
        evade_bonus=_evade,
        hit_chances=_build_hit_chances(_current_target()),
        player_mode="WAIT",
    )
    await _responsive_sleep(animation_timing.GROUND_STEP, state.ctx.context)


async def advance_flights(
    state, ctx, game_map: world.GameMap, side: str = "player",
) -> str | None:
    """The shooter's mini-turn (doc 57 SETTLED 11.9): at the start of
    the shooter's turn, ITS missiles (``side``) move ONE AT A TIME in
    launch order, full ``flight_speed``, through the collision rules.
    The player hook fires after enemy turns and reinforcements, before
    the player's AP; 57.2 mirrors it inside the enemy's own turn. A
    dead target at re-vector time dissipates its missile (fuel spent).
    Returns ``"DEFEAT"`` when a missile kills the player."""
    for _missile in list(state.in_flight):
        if _missile.side != side:
            continue
        if not _missile.alive:
            continue
        _target = _missile.target
        if _target is None or not getattr(_target, "alive", False):
            _remove_missile(state, game_map, _missile)
            continue
        # Contact reads on ENTRY only — except a ship that parked ON a
        # resting missile (they are non-blocking): that is contact.
        _parked = _ship_at(state, _missile.pos)
        if _parked is not None:
            _remove_missile(state, game_map, _missile)
            if _parked == "player":
                if await _detonate_on_player(state, ctx, _missile) == "DEFEAT":
                    return "DEFEAT"
            else:
                await _detonate_on_ship(state, ctx, game_map, _missile, _parked)
            continue
        _outcome = await _travel(
            state, ctx, game_map, _missile, _missile.flight_speed,
        )
        if _outcome == "DEFEAT":
            return "DEFEAT"
    return None
