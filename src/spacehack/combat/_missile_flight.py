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
the intercept kill) hang off ``SpaceCombatState.in_flight``. Doc
57.2: BOTH sides fly — enemy missiles spawn wordless, home on the
player through :class:`PlayerHomingTarget`, resolve their mini-turns
per shooter (plus the dead-shooter orphan sweep), arrive through the
shared enemy-hit tail, and clip fellow hostiles as uncredited
fratricide.

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
    shooter: Any = None               # the launching ship (None = the player)
    gunnery: int = 0                  # enemy launch snapshot: shooter pilot_gunnery
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


@dataclass
class PlayerHomingTarget:
    """The player as a flight target (doc 57.2): live ``pos``/``alive``
    reads over the combat player_state — the dict's Position entry is
    REPLACED on every move, so enemy missiles home through this
    adapter, never a snapshot. Contact detection stays on
    :func:`_ship_at` (the dict read)."""

    state: Any

    @property
    def pos(self) -> world.Position:
        return self.state.player_state["pos"]

    @property
    def alive(self) -> bool:
        return self.state.player_state.get("hull", 1) > 0


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
    other — shooter IDENTITY is the key (doc 57.2: several enemy
    launchers share a side), and the player's single shooter reads
    ``shooter=None`` uniformly."""
    for _m in state.in_flight:
        if _m is missile or not _m.alive:
            continue
        if _m.shooter is missile.shooter and _m.pos.x == cell.x and _m.pos.y == cell.y:
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
    every contact site shares). Player-owned racks roll the player's
    LIVE reads (the Pirate opener window can close mid-flight); enemy
    ordnance rolls its launch-time gunnery snapshot and none of the
    player's perks (doc 57.2)."""
    from ..engine import RNG

    if missile.side == "enemy":
        _chance = guidance_hit_chance(
            missile.weapon_id, missile.gunnery, target_dodge,
            weapon_quality=missile.quality,
        )
        return RNG.randint(1, 100) <= _chance
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
    ruling 2026-10-01: PLAYER-owned contact hits speak the detonates
    form. ENEMY ordnance clipping a fellow hostile is fratricide (doc
    57.2): identical physics, no player credit."""
    if missile.side == "enemy":
        await _fratricide_contact(state, ctx, game_map, missile, ship)
        return
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


def _shooter_name(missile: InFlightMissile) -> str:
    """The launching ship's name for enemy-owned lines (``Hostile``
    fallback for a hand-mounted round)."""
    _shooter = missile.shooter
    return _shooter.name if _shooter is not None else "Hostile"


async def _fratricide_contact(
    state, ctx, game_map: world.GameMap, missile: InFlightMissile, ship,
) -> None:
    """An enemy missile detonating on a fellow hostile (doc 57.2,
    DRAFT line — checkpoint approval): the same guidance roll and
    damage path (rule 7 verbatim: ANY ship), but the kill records
    NOTHING for the player — no ``on_kill``, no XP, loot, bounty, rep,
    or defeat records (ordnance deaths the player did not cause book
    like intercepts, not kills); the victim's entity still leaves the
    map, no ghost hull."""
    from .. import message_log as _ml
    from ._space_kills import _animate_kill_explosion, pop_dead_entity

    if not _arrival_hits(state, ctx, missile, ship):
        _log_detonates_short(state)
        return
    _dmg, _sdmg, _fh, _glancing = _apply_contact_damage(missile, ship)
    state.log.add_colored(
        f"{_shooter_name(missile)}'s {_find_weapon(missile.weapon_id).name} "
        f"detonates on {ship.name} for {_dmg} damage.",
        _ml.COLOR_ENEMY_ACTION,
    )
    if _fh > 0:
        return
    ship.alive = False
    state.log.add_colored(f"{ship.name} destroyed!", _ml.COLOR_COMBAT_EVENT)
    pop_dead_entity(state, game_map, ship)
    await _animate_kill_explosion(state, ctx, game_map, ship)


async def _detonate_on_player(state, ctx, missile: InFlightMissile) -> str | None:
    """Contact with the player's hull: an ENEMY missile's arrival (doc
    57.2 — the attack line lands with the warhead; ``"DEFEAT"`` rides
    the return) or the player's own self-splash (SETTLED 11.7 — live
    by ruling, DRAFT prose as pinned)."""
    if missile.side == "enemy":
        return await _enemy_arrival_on_player(state, ctx, missile)
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


async def _apply_guided_arrival(
    state, ctx, missile: InFlightMissile, _dodge: int,
) -> str | None:
    """Resolve a GUIDED enemy arrival onto the player through the
    shared enemy-hit tail verbatim — attack line, damage counters,
    ``last_attacker``, DEFEAT presentation. ``"DEFEAT"`` rides the
    return."""
    from ._actions import resolve_damage
    from ._ai import _apply_enemy_hit
    from ._rules_space import _build_hit_chances, _calc_camera

    _ps = state.player_state
    _ws = _find_weapon(missile.weapon_id)
    _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
        missile.weapon_id, _ps["hull"], _ps["shields"],
        target_pilot_piloting=_ps.get("piloting", 0),
        weapon_quality=missile.quality,
    )
    return await _apply_enemy_hit(
        state, missile.shooter, missile.weapon_id, _ws,
        _dmg, _sdmg, _fh, False, _is_glancing,
        hit_chances=_build_hit_chances(None), evade_bonus=_dodge,
        calc_cam=_calc_camera, ctx=ctx,
    )


async def _enemy_arrival_on_player(
    state, ctx, missile: InFlightMissile,
) -> str | None:
    """An enemy missile arriving on the player (doc 57.2): the enemy
    guidance roll — the shooter's snapshot gunnery against the
    player's dodge-at-contact, with the Bounty Hunter's +5 evade as a
    resolution-only read (the ``_resolve_enemy_shot`` mirror) — then
    the shared guided-arrival tail. The launch was wordless; the line
    lands with the warhead."""
    from .. import message_log as _ml
    from ..xp import bounty_hunter_evade_bonus
    from ._messages import enemy_attack_line

    _ps = state.player_state
    _ws = _find_weapon(missile.weapon_id)
    _dodge = _calc_dodge_bonus(
        _ps.get("cells_moved_this_turn", 0),
        int(_ps.get("piloting", 0) * 0.5),
    ) + bounty_hunter_evade_bonus(ctx if ctx is not None else state.ctx)
    if not _guided(state, ctx, missile, _dodge):
        state.log.add_colored(
            enemy_attack_line(
                _shooter_name(missile), missile.weapon_id, _ws.name,
                hit=False, quality=missile.quality,
            ),
            _ml.COLOR_ENEMY_ACTION,
        )
        return None
    return await _apply_guided_arrival(state, ctx, missile, _dodge)


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
    launch_pos: world.Position, shooter, gunnery: int,
) -> InFlightMissile:
    """Construct the crossing missile + its non-blocking render twin
    at the deploy cell (no mounting — the caller appends)."""
    _ws = _find_weapon(weapon_id)
    _spawn = _spawn_cell(state, launch_pos, target)
    _missile = InFlightMissile(
        weapon_id=weapon_id, pos=_spawn, target=target,
        quality=quality, side=side, shooter=shooter, gunnery=gunnery,
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
    launch_pos: world.Position, shooter=None, gunnery: int = 0,
) -> InFlightMissile:
    """Deploy one crossing missile (doc 57 SETTLED 11.2-5): it appears
    in a cell NEAR the shooter (never the shooter's own), then makes
    its launch half-move — half the normal move range under the full
    collision rules. The volley's next member deploys after, seeing
    the previous missile's rest position (the stagger is the
    anti-stack). The PLAYER's launch reads the away line; an enemy
    launch is WORDLESS (doc 57.2: the glyph crossing is the notice —
    the attack line lands with the warhead at arrival)."""
    from .. import message_log as _ml

    _ws = _find_weapon(weapon_id)
    _missile = _build_missile(
        state, weapon_id, target, side, quality, launch_pos, shooter, gunnery,
    )
    state.game_map.entities.append(_missile.ent)
    state.in_flight.append(_missile)
    if side == "player":
        state.log.add_colored(
            f"{_ws.name[0]}{_ws.name[1:].lower()} away.",
            _ml.COLOR_PLAYER_ACTION,
        )
    # A launch-half-move self-splash kill is backstopped by the loop's
    # post-action hp gate (the volley's remaining slots still fire) —
    # reachable only when every progress-side neighbor is blocked. The
    # ENEMY mirror is different geometry: Euclidean floors pass at
    # diagonal standoffs a light's half-move can cross, so the enemy
    # seam reads the hp seam as its DEFEAT (doc 57.2, ADVISE 1).
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


def _owns_flight(missile: InFlightMissile, side: str, shooter) -> bool:
    """Whether ``missile`` resolves its mini-turn at ``shooter``'s turn
    (doc 57.2): side plus shooter identity — the per-shooter timing
    several enemy launchers need. The player hook passes
    ``shooter=None`` and owns every player missile (one shooter by
    construction)."""
    if missile.side != side:
        return False
    return shooter is None or missile.shooter is shooter


async def _mini_turn(
    state, ctx, game_map: world.GameMap, missile: InFlightMissile,
) -> str | None:
    """One missile's mini-turn body (doc 57 SETTLED 11.9): a dead
    target at re-vector time dissipates it (fuel spent); a ship
    parked on a resting missile (they are non-blocking) is contact;
    else the full-``flight_speed`` travel through the collision
    rules. Returns ``"DEFEAT"`` when it kills the player."""
    _target = missile.target
    if _target is None or not getattr(_target, "alive", False):
        _remove_missile(state, game_map, missile)
        return None
    _parked = _ship_at(state, missile.pos)
    if _parked is not None:
        _remove_missile(state, game_map, missile)
        if _parked == "player":
            return await _detonate_on_player(state, ctx, missile)
        await _detonate_on_ship(state, ctx, game_map, missile, _parked)
        return None
    return await _travel(state, ctx, game_map, missile, missile.flight_speed)


async def advance_flights(
    state, ctx, game_map: world.GameMap, side: str = "player",
    shooter=None,
) -> str | None:
    """The shooter's mini-turn (doc 57 SETTLED 11.9): at the start of
    the shooter's turn, ITS missiles (``side``; ``shooter`` narrows to
    one launcher — the enemy mirror, doc 57.2) move ONE AT A TIME in
    launch order, full ``flight_speed``, through the collision rules.
    The player hook fires after enemy turns and reinforcements, before
    the player's AP; the enemy hook at the top of ``_take_enemy_turn``.
    Returns ``"DEFEAT"`` when a missile kills the player."""
    for _missile in list(state.in_flight):
        if not _missile.alive or not _owns_flight(_missile, side, shooter):
            continue
        if await _mini_turn(state, ctx, game_map, _missile) == "DEFEAT":
            return "DEFEAT"
    return None


async def advance_orphan_flights(
    state, ctx, game_map: world.GameMap, side: str = "enemy",
) -> str | None:
    """The orphan sweep (doc 57.2): a dead shooter never recalls its
    launch, so its missiles fly their mini-turn at the START of the
    enemy phase, ahead of the live shooters' turns — at most one move
    per missile per round, never both paths (a shooter dying mid-phase
    after its own turn has already moved them; one killed between the
    sweep and its turn leaves its missiles stationary that round and
    they resume here next round). Returns ``"DEFEAT"`` when a missile
    kills the player."""
    for _missile in list(state.in_flight):
        if not _missile.alive or _missile.side != side:
            continue
        if getattr(_missile.shooter, "alive", False):
            continue  # a live shooter's own turn moves it
        if await _mini_turn(state, ctx, game_map, _missile) == "DEFEAT":
            return "DEFEAT"
    return None
