"""Missile flight — the crossing-entity domain (doc 57).

A launched flight missile is a live combat entity advancing
``flight_speed`` cells per combat round toward its target's live
position (homing, fuel-capped); every round on the map is an
intercept window. Pure advance math, the arrival guidance roll, and
the flight finishers live here; the state-holder seams (spawn on
fire, the round-boundary hook, the intercept kill) hang off
``SpaceCombatState.in_flight``.

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
from ._stats import _calc_dodge_bonus, clamp_hit_chance

# Family by shape, side by color (doc 57 SETTLED 10): the heavy's fat
# dense diamond reads as the flak-worthy crossing; the light's quick
# star as thin enough to maybe eat. Unknown racks fall back to the
# light read.
_GLYPH_BY_WEAPON: dict[str, str] = {"heavy_missile": "♦", "light_missile": "*"}

HOSTILE_FG: tuple[int, int, int] = (255, 80, 80)     # hot red — dread at a glance
PLAYER_FG: tuple[int, int, int] = (120, 225, 255)    # cyan friendly accent


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
    """One live crossing missile (doc 57 SETTLED 1).

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
    """One round-boundary hop's pure result.

    ``path`` are the cells entered this hop in order (empty when the
    missile cannot move); ``arrived`` when the hop's last cell is the
    target's; ``fuel_exhausted`` when the tank hits zero short of it.
    """

    path: tuple[tuple[int, int], ...]
    arrived: bool
    fuel_exhausted: bool


def advance_step(
    pos: world.Position, target_pos: world.Position,
    speed: int, fuel: int,
) -> FlightStep:
    """The round's hop math (pure): up to ``speed`` cells along the
    straight track toward the target's live position, capped by
    remaining fuel — re-vectoring happens per round because the
    caller passes the target's CURRENT position. Overshoot stops at
    the target (arrival), never past it."""
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


def spawn_flight_missile(
    state, weapon_id: str, target, *, side: str, quality: int,
    launch_pos: world.Position,
) -> InFlightMissile:
    """Build one crossing missile from its launcher spec and mount it
    on the map (spawned at the shooter's cell; the first hop lands at
    the next round boundary). The launch line reads here — the
    outcome lines belong to the arrival."""
    from .. import message_log as _ml

    _ws = _find_weapon(weapon_id)
    _missile = InFlightMissile(
        weapon_id=weapon_id, pos=launch_pos, target=target,
        quality=quality, side=side,
        hull=_ws.missile_hp, max_hull=_ws.missile_hp,
        fuel=_ws.max_range, flight_speed=_ws.flight_speed,
        name=_ws.name,
        char=_GLYPH_BY_WEAPON.get(weapon_id, "*"),
        fg=PLAYER_FG if side == "player" else HOSTILE_FG,
    )
    _missile.ent = world.Entity(
        char=_missile.char, fg=_missile.fg, pos=launch_pos,
        name=_ws.name, width=1, height=1, non_blocking=True,
    )
    state.game_map.entities.append(_missile.ent)
    state.in_flight.append(_missile)
    state.log.add_colored(
        f"{_ws.name[0]}{_ws.name[1:].lower()} away.",
        _ml.COLOR_PLAYER_ACTION,
    )
    return _missile


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
    """The intercept kill (doc 57): entity removed, explosion beat,
    one line — and NEVER ``rules.on_kill`` (no XP, loot, or
    reputation for shooting down ordnance)."""
    from .. import message_log as _ml
    from ._space_kills import _animate_kill_explosion

    _remove_missile(state, game_map, missile)
    await _animate_kill_explosion(state, ctx, game_map, missile)
    state.log.add_colored("Missile destroyed.", _ml.COLOR_COMBAT_EVENT)


def _arrival_dodge(target) -> int:
    """The target's dodge-at-arrival (doc 57 SETTLED 5): the existing
    ``_calc_dodge_bonus`` assembly over its latest-round movement."""
    return _calc_dodge_bonus(
        target.cells_moved_this_turn, int(target.pilot_piloting * 0.5),
    )


def _arrival_hits(state, ctx, missile: InFlightMissile, target) -> bool:
    """The guidance roll at impact: quality-scaled launcher accuracy
    against the target's then-current dodge."""
    from ..engine import RNG
    from ._rules_space import _player_hit_bonus

    _chance = guidance_hit_chance(
        missile.weapon_id, state.player_state["gunnery"], _arrival_dodge(target),
        _player_hit_bonus(ctx, missile.weapon_id),
        weapon_quality=missile.quality,
    )
    return RNG.randint(1, 100) <= _chance


def _apply_arrival_damage(missile: InFlightMissile, target) -> tuple[int, int, int, bool]:
    """Resolve the impact through the normal damage path (doubled rack
    damage × quality × variance, shields first) and write the target."""
    from ._actions import resolve_damage

    _dmg, _sdmg, _fh, _glancing = resolve_damage(
        missile.weapon_id, target.hull, target.shields,
        target_pilot_piloting=target.pilot_piloting,
        weapon_quality=missile.quality,
    )
    target.shields = max(0, target.shields - _sdmg)
    target.hull = _fh
    return _dmg, _sdmg, _fh, _glancing


async def _finish_arrival(
    state, ctx, game_map: world.GameMap, missile: InFlightMissile,
) -> None:
    """Resolve one missile's arrival (doc 57 SETTLED 5): guidance roll
    against the target's then-current dodge; a hit rides the normal
    resolve path and a kill runs the FULL kill chain exactly like a
    volley kill (minus the Momentum refund — volley-time mechanics
    never reach delayed kills). A miss is a harmless detonation. An
    arrival at another crossing MISSILE takes the intercept
    bookkeeping — ordnance destroyed, never the ship kill chain."""
    from .. import message_log as _ml
    from ..ship import weapon_display_name
    from ._messages import player_attack_line
    from ._space_kills import on_kill as _kill_chain

    _remove_missile(state, game_map, missile)
    _target = missile.target
    if isinstance(_target, InFlightMissile):
        await _arrive_at_missile(state, ctx, game_map, missile, _target)
        return
    if not _arrival_hits(state, ctx, missile, _target):
        state.log.add_colored(
            "Missile detonates short.", _ml.COLOR_PLAYER_ACTION,
        )
        return
    _dmg, _sdmg, _fh, _glancing = _apply_arrival_damage(missile, _target)
    _line = player_attack_line(
        missile.weapon_id,
        weapon_display_name(missile.weapon_id, missile.quality),
        _target.name, hit=True, hull_dmg=_dmg, shield_dmg=_sdmg,
        is_glancing=_glancing, quality=missile.quality,
    )
    state.log.add_colored(_line, _ml.COLOR_PLAYER_ACTION, runs=_line.runs)
    if _fh > 0:
        return
    _target.alive = False
    state.log.add_colored(f"{_target.name} destroyed!", _ml.COLOR_COMBAT_EVENT)
    await _kill_chain(state, game_map, _target, ctx)


async def _arrive_at_missile(
    state, ctx, game_map: world.GameMap,
    missile: InFlightMissile, target: InFlightMissile,
) -> None:
    """A flight rack arriving at another crossing missile: the same
    guidance roll, damage onto ``missile_hp``, and the INTERCEPT kill
    branch on destruction (entity removed, explosion beat, one line —
    never ``rules.on_kill``). The interceptor detonates on impact
    either way; the caller already removed it."""
    from .. import message_log as _ml

    if _arrival_hits(state, ctx, missile, target):
        _dmg, _sdmg, _fh, _glancing = _apply_arrival_damage(missile, target)
        if _fh <= 0:
            target.alive = False
            await finish_intercept(state, ctx, game_map, target)
            return
    state.log.add_colored(
        "Missile detonates short.", _ml.COLOR_PLAYER_ACTION,
    )


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


async def advance_flights(state, ctx, game_map: world.GameMap) -> None:
    """The round-boundary advance (doc 57 SETTLED 1): every live
    missile makes its hop — each cell rendering — then arrivals
    resolve. A dead target at re-vector time dissipates its missile
    (fuel spent); an empty tank short of the target exhausts it."""
    from .. import message_log as _ml
    from ._rules_space import _calc_camera

    _cam = _calc_camera()
    for _missile in list(state.in_flight):
        if not _missile.alive:
            continue
        _target = _missile.target
        if _target is None or not getattr(_target, "alive", False):
            _remove_missile(state, game_map, _missile)
            continue
        _step = advance_step(
            _missile.pos, _target.pos, _missile.flight_speed, _missile.fuel,
        )
        for _cx, _cy in _step.path:
            _missile.pos = world.Position(_cx, _cy)
            if _missile.ent is not None:
                _missile.ent.pos = _missile.pos
            await _render_hop_frame(state, _cam)
        _missile.fuel -= len(_step.path)
        if _step.arrived:
            await _finish_arrival(state, ctx, game_map, _missile)
        elif _step.fuel_exhausted or _missile.fuel <= 0:
            state.log.add_colored(
                "Missile exhausts its fuel.", _ml.COLOR_PLAYER_ACTION,
            )
            _remove_missile(state, game_map, _missile)
