"""Procedural NPC ship spawning and movement.

Extracted from :mod:`__main__` so the dispatcher stays clean.
Replaces ``_spawn_procedural_pirates`` / ``_move_pirates`` with
a unified ``spawn_npcs`` / ``move_npcs`` that handles both pirates
and merchants from the single :class:`data.npc_ships.NpcShipSpec`
catalog.
"""

from __future__ import annotations
import math
from typing import Any

import tcod.console

from . import engine as _engine
from . import main_quest as main_quest_module
from . import message_log as _ml
from . import solar_system as _solar_module
from . import world
from .data.npc_ships import find_npc_ship as _find_npc_ship
from .game_context import GameContext, ProceduralSpawn, NpcFlashEvent


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_body_goals(system) -> list[tuple[int, int, str, str]]:
    """Build navigable goal positions for all bodies in *system*.

    Returns ``[(x, y, kind, name), ...]`` where *kind* is
    ``"planet"`` / ``"gate"`` / ``"station"`` so callers can
    dispatch behaviour (despawn, dock, …) per body type.
    """
    _goals: list[tuple[int, int, str, str]] = []
    for _p in system.planets:
        if getattr(_p, 'sun', False):
            continue
        _gx = _p.pos.x + _p.width + 1
        _gy = _p.pos.y + _p.height // 2
        if 0 <= _gx < system.width and 0 <= _gy < system.height:
            _goals.append((_gx, _gy, "planet", _p.name))
    for _jp in system.jump_points:
        _gx = _jp.pos.x + _jp.width + 1
        _gy = _jp.pos.y + _jp.height // 2
        if 0 <= _gx < system.width and 0 <= _gy < system.height:
            _goals.append((_gx, _gy, "gate", _jp.name))
    for _st in getattr(system, 'stations', ()) or ():
        _gx = _st.pos.x + _st.width + 1
        _gy = _st.pos.y + _st.height // 2
        if 0 <= _gx < system.width and 0 <= _gy < system.height:
            _goals.append((_gx, _gy, "station", _st.name))
    return _goals


def _make_npc_entity(spec, pos: world.Position, movement_id: str) -> world.Entity:
    """Create a single NPC ship :class:`world.Entity` from its spec."""
    return world.Entity(
        char=spec.char, fg=spec.fg, pos=pos,
        name=spec.name, width=1, height=1,
        npc_ship_id=spec.id,
        procedural_squad_id=movement_id,
    )


def _set_npc_path(
    ctx: GameContext,
    movement_id: str,
    pos: world.Position,
    target: tuple[int, int],
    game_map: world.GameMap,
) -> None:
    """Compute and store an A* path from *pos* to *target*."""
    ctx.npc_targets[movement_id] = target
    _end_set: set[tuple[int, int]] = {target}
    _path = world.find_path((pos.x, pos.y), _end_set, game_map)
    ctx.npc_paths[movement_id] = _path or []


# ---------------------------------------------------------------------------
# Initial spawn (on jump / launch)
# ---------------------------------------------------------------------------

def _derelict_blocked_near(system, margin: int = 15) -> set[tuple[int, int]]:
    """Build a set of cells too close to any body in ``system``.

    Includes a ``margin``-cell buffer around every planet (non-sun),
    jump gate, and station. Used to ensure derelicts spawn in empty
    space, far from landmarks.
    """
    _blocked: set[tuple[int, int]] = set()
    for _p in system.planets:
        if getattr(_p, 'sun', False):
            continue
        for _dy in range(-margin, _p.height + margin):
            for _dx in range(-margin, _p.width + margin):
                _blocked.add((_p.pos.x + _dx, _p.pos.y + _dy))
    for _jp in system.jump_points:
        for _dy in range(-margin, _jp.height + margin):
            for _dx in range(-margin, _jp.width + margin):
                _blocked.add((_jp.pos.x + _dx, _jp.pos.y + _dy))
    for _st in getattr(system, 'stations', ()) or ():
        for _dy in range(-margin, _st.height + margin):
            for _dx in range(-margin, _st.width + margin):
                _blocked.add((_st.pos.x + _dx, _st.pos.y + _dy))
    return _blocked


def _find_open_space(system, blocked: set[tuple[int, int]]) -> world.Position | None:
    """Return a random open-space position in ``system`` not in ``blocked``.

    Tries up to 100 random cells. Returns ``None`` if all attempts
    land in the blocked set (extremely rare on a 200x140 map).
    """
    for _ in range(100):
        _tx = _engine.RNG.randint(5, system.width - 5)
        _ty = _engine.RNG.randint(5, system.height - 5)
        if (_tx, _ty) not in blocked:
            return world.Position(_tx, _ty)
    return None


def _spawn_derelict(
    ctx: GameContext,
    game_map: world.GameMap,
    system_id: str,
    system,
) -> bool:
    """Roll for a derelict ship in ``system``.

    Separate from the normal NPC spawn roll — derelicts use their
    own ``derelict_spawn_chance`` field. If the roll hits, spawns
    a single derelict_scout in empty space far from any body.

    When ``SPACEHACK_DEV`` is set and in the Sol system, bypasses
    the RNG roll and spawns a derelict near Earth for easy testing.

    Returns ``True`` if a derelict was spawned.
    """
    import os as _os
    _is_dev = bool(_os.environ.get("SPACEHACK_DEV"))

    # --- Determine spawn position ---
    if _is_dev and system_id == "sol":
        # Dev mode: force a derelict outside Earth's docking position.
        # Earth is at (140, 39), 3x3. The player docks just east of
        # Earth at (143, 40). Place the derelict a few cells east so
        # the player sees it immediately on launch.
        _pos = world.Position(150, 40)
    else:
        # Normal: roll RNG + find open space far from bodies.
        if getattr(system, 'derelict_spawn_chance', 0) <= 0:
            return False
        if _engine.RNG.random() >= system.derelict_spawn_chance:
            return False
        _pos = _find_open_space(system, _derelict_blocked_near(system))
        if _pos is None:
            return False

    # --- Build entity + register spawn ---
    try:
        _spec = _find_npc_ship("derelict_scout")
    except KeyError:
        return False

    _derelict_ent = world.Entity(
        char=_spec.char, fg=_spec.fg, pos=_pos,
        name=_spec.name, width=1, height=1,
        npc_ship_id=_spec.id,
    )
    game_map.entities.append(_derelict_ent)

    _spawn_id = f"derelict_{system_id}_{_pos.x}_{_pos.y}"
    if system_id not in ctx.procedural_spawns:
        ctx.procedural_spawns[system_id] = []
    ctx.procedural_spawns[system_id].append(
        ProceduralSpawn(npc_id=_spec.id, pos=_pos, squad_id=_spawn_id)
    )

    ctx.log.add_colored(
        f"Sensor ping: faint derelict signal detected "
        f"near ({_pos.x}, {_pos.y}).",
        _ml.COLOR_IMPORTANT_EVENT,
    )
    return True


# Radius (cells) around the player's arrival body to exclude from
# initial NPC placement. NPCs spawned from other bodies will be
# placed outside this radius.
SPAWN_EXCLUSION_RADIUS: int = 12


def spawn_npcs(
    ctx: GameContext,
    game_map: world.GameMap,
    system_id: str,
    *,
    player_spawn_exclusion: set[tuple[int, int]] | None = None,
) -> None:
    """Roll for procedural NPC encounters in ``system_id``.

    Each jump / launch consumes a fresh roll from the game's seeded
    RNG. If the system's ``npc_spawn_chance`` hits, NPC groups are
    spawned according to the weighted ``npc_spawn_table`` and
    ``npc_density``.  Each NPC ship gets a ``npc_ship_id`` on the
    Entity (referencing :class:`data.npc_ships.NpcShipSpec`) so
    combat detection and loot generation can read per-type data.

    All NPC types spawn from a planet / gate / station position
    (arriving from the body) rather than appearing at a random point
    in empty space.

    Also rolls for derelict ship spawning via the system's
    ``derelict_spawn_chance`` field (separate roll from NPC table).

    ``player_spawn_exclusion`` — cells that should be blocked from
    NPC placement, typically a radius around the player's arrival
    point (jump gate or planet) so the player isn't immediately
    surrounded after a jump or launch.

    Uses ``ctx.procedural_spawns`` (keyed by system id) so combat
    detection can locate them.
    """
    from .data.solar_systems import find_solar_system as _fss
    try:
        _system = _fss(system_id)
    except KeyError:
        return

    # Separate derelict spawn roll (independent of NPC chance)
    _spawn_derelict(ctx, game_map, system_id, _system)

    # Build a set of blocked cells (planets, gates, stations) — shared
    # by militia spawn and regular NPC spawn so neither places ships
    # inside celestial bodies.
    _blocked: set[tuple[int, int]] = set()
    for _p in _system.planets:
        for _dy in range(_p.height):
            for _dx in range(_p.width):
                _blocked.add((_p.pos.x + _dx, _p.pos.y + _dy))
    for _jp in _system.jump_points:
        for _dy in range(_jp.height):
            for _dx in range(_jp.width):
                _blocked.add((_jp.pos.x + _dx, _jp.pos.y + _dy))
    for _st in getattr(_system, 'stations', ()) or ():
        for _dy in range(_st.height):
            for _dx in range(_st.width):
                _blocked.add((_st.pos.x + _dx, _st.pos.y + _dy))

    # --- Militia patrol spawn (separate from NPC table, uses patrol_density) ---
    _patrol_min, _patrol_max = _system.patrol_density
    _all_militia: list = []
    if _patrol_max > 0:
        _body_goals = _build_body_goals(_system)
        # Exclude the arrival body so militia don't spawn on top of the player.
        if player_spawn_exclusion:
            _body_goals = [
                g for g in _body_goals
                if (g[0], g[1]) not in player_spawn_exclusion
            ]
        if _body_goals:
            _patrol_count = _engine.RNG.randint(_patrol_min, _patrol_max)
            # Derive ship type from max density.
            _patrol_ship = (
                "militia_patrol_heavy" if _patrol_max >= 5 else
                "militia_patrol" if _patrol_max >= 3 else
                "militia_patrol_light"
            )
            try:
                _patrol_spec = _find_npc_ship(_patrol_ship)
            except KeyError:
                _patrol_spec = None
            if _patrol_spec is not None:
                for _pi in range(_patrol_count):
                    _origin = _engine.RNG.choice(_body_goals)
                    _gcx, _gcy = _origin[0], _origin[1]
                    _mid = f"patrol_{system_id}_{_pi}_{_engine.RNG.randint(0, 99999)}"
                    for _attempt in range(50):
                        _x = _gcx + _engine.RNG.randint(-4, 4)
                        _y = _gcy + _engine.RNG.randint(-4, 4)
                        if (0 <= _x < _system.width and 0 <= _y < _system.height
                                and (_x, _y) not in _blocked):
                            break
                    else:
                        continue
                    _pos = world.Position(_x, _y)
                    _blocked.add((_x, _y))
                    game_map.entities.append(_make_npc_entity(_patrol_spec, _pos, _mid))
                    _all_militia.append((_pos, _mid, _patrol_ship))
                # Register militia spawns.
                if _all_militia:
                    if system_id not in ctx.procedural_spawns:
                        ctx.procedural_spawns[system_id] = []
                    ctx.procedural_spawns[system_id].extend([
                        ProceduralSpawn(npc_id=npc_id, pos=pos, squad_id=sid)
                        for pos, sid, npc_id in _all_militia
                    ])
                    ctx.log.add_colored(
                        f"Sensor ping: {len(_all_militia)} militia patrol(s) "
                        f"active in the area.",
                        _ml.COLOR_IMPORTANT_EVENT,
                    )

    if _system.npc_spawn_chance <= 0.0 or not _system.npc_spawn_table or _system.npc_density <= 0:
        return
    if _engine.RNG.random() >= _system.npc_spawn_chance:
        return

    # Add existing entities to the blocked set so NPCs don't spawn on them.
    for _e in game_map.entities:
        for _dy in range(_e.height):
            for _dx in range(_e.width):
                _blocked.add((_e.pos.x + _dx, _e.pos.y + _dy))

    # Exclude the player's arrival zone so they aren't immediately
    # surrounded after a jump or launch.
    if player_spawn_exclusion:
        _blocked.update(player_spawn_exclusion)

    # Build body goals once, shared by all active NPC types.
    _body_goals = _build_body_goals(_system)

    # Exclude the arrival body's goal from NPC spawn origins so
    # NPC groups can't originate from the exact body the player
    # just arrived at. The arrival body's goal cell is the same
    # position as the player's ship — if the exclusion zone didn't
    # filter it out during the randint(-4,4) spread, this prevents
    # it from being chosen at all.
    if player_spawn_exclusion:
        _body_goals = [
            g for g in _body_goals
            if (g[0], g[1]) not in player_spawn_exclusion
        ]

    # Roll which NPC types appear from the weighted table.
    _active_types: list[str] = []
    for _npc_id, _weight in _system.npc_spawn_table:
        if _engine.RNG.random() < _weight:
            _active_types.append(_npc_id)
    if not _active_types:
        _active_types = [_system.npc_spawn_table[0][0]]

    _total_spawned = 0
    _all_procedural: list = []

    for _npc_id in _active_types:
        try:
            _spec = _find_npc_ship(_npc_id)
        except KeyError:
            continue

        _is_merchant = getattr(_spec, 'faction', 'pirate') == 'merchant'

        # Determine spawn centre and initial destination.
        _initial_target: tuple[int, int] | None = None
        if _body_goals:
            # All NPC types spawn from a body (no more random scatter).
            _origin_goal = _engine.RNG.choice(_body_goals)
            _gcx, _gcy = _origin_goal[0], _origin_goal[1]
            _blocked.add((_gcx, _gcy))
            if _is_merchant and len(_body_goals) >= 2:
                _dest_goal = _engine.RNG.choice(
                    [g for g in _body_goals if (g[0], g[1]) != (_origin_goal[0], _origin_goal[1])]
                )
                _initial_target = (_dest_goal[0], _dest_goal[1])
        else:
            # No bodies in system — skip this NPC type.
            continue

        # Squad id for groups > 1.
        _is_squad = _system.npc_density > 1 and _engine.RNG.random() < 0.5
        _squad_id: str | None = (
            f"proc_npc_{system_id}_{_npc_id}_{_engine.RNG.randint(0, 99999)}"
            if _is_squad else None
        )
        _movement_id: str = _squad_id or f"proc_solo_{system_id}_{_npc_id}_{_engine.RNG.randint(0, 99999)}"

        # Group size: 1 for solo, 2-4 for squad based on density.
        _g_size = _engine.RNG.randint(1, min(_system.npc_density, 4))

        _group_entities = 0
        _group_positions: list[world.Position] = []
        for _i in range(_g_size):
            _x = _y = -1
            for _attempt in range(50):
                _x = _gcx + _engine.RNG.randint(-4, 4)
                _y = _gcy + _engine.RNG.randint(-4, 4)
                if (_x, _y) not in _blocked and 0 <= _x < _system.width and 0 <= _y < _system.height:
                    break
            else:
                continue
            _pos = world.Position(_x, _y)
            _blocked.add((_x, _y))
            game_map.entities.append(_make_npc_entity(_spec, _pos, _movement_id))
            _group_positions.append(_pos)
            _all_procedural.append((_pos, _movement_id, _npc_id))
            _group_entities += 1
        _total_spawned += _group_entities

        # Pre-set initial target + path for merchants.
        if _is_merchant and _initial_target is not None and _group_positions:
            _set_npc_path(ctx, _movement_id, _group_positions[0], _initial_target, game_map)

    if _all_procedural:
        # Preserve existing spawn entries whose npc_id wasn't just
        # spawned by this call (e.g. derelicts from _spawn_derelict).
        _spawned_npc_ids = {npc_id for _, _, npc_id in _all_procedural}
        _existing = ctx.procedural_spawns.get(system_id, [])
        _preserved = [_ps for _ps in _existing
                      if _ps.npc_id not in _spawned_npc_ids]
        ctx.procedural_spawns[system_id] = _preserved + [
            ProceduralSpawn(npc_id=npc_id, pos=pos, squad_id=sid)
            for pos, sid, npc_id in _all_procedural
        ]
        _faction_names = set()
        for _pos, _sid, _npc_id in _all_procedural:
            try:
                _spec = _find_npc_ship(_npc_id)
                _faction_names.add(_spec.name)
            except KeyError:
                _faction_names.add("unknown contact")
        _contacts = ", ".join(sorted(_faction_names))
        ctx.log.add_colored(
            f"Sensor ping: {_total_spawned} signal{('s' if _total_spawned != 1 else '')}"
            f" detected in the area ({_contacts}).",
            _ml.COLOR_IMPORTANT_EVENT,
        )


# ---------------------------------------------------------------------------
# Per-tick movement (and occasional per-tick spawn)
# ---------------------------------------------------------------------------

def move_npcs(ctx: GameContext, game_map: world.GameMap) -> None:
    """Patrol procedural NPC entities toward planets/gates/stations.

    Called after the player moves in space mode. Behaviour varies
    by NPC faction (from NpcShipSpec):

      * **pirates** — patrol loop: pick a planet/gate/station,
        move toward it, pick a new target on arrival.
      * **merchants** — move toward a planet/gate/station.
        When within 2 cells of a gate: despawn ("jumps to next
        system").  When in range of a planet/station: despawn
        ("docks at port").  Flee from nearby pirates.

    ``_FLEE_RANGE`` controls how close a pirate must be before a
    merchant attempts to flee (in cells).  Squad members use the
    A* path computed for the squad leader.
    """
    _system = _solar_module.current_system()
    if _system is None:
        return

    # --- Per-tick NPC spawn (continuous traffic) ---
    # Roll a small chance each tick to spawn a new ship, scaled from
    # the system's base spawn chance so busier systems stay busy.
    # Capped at npc_density * 3 to avoid overcrowding.
    _PER_TICK_CHANCE_MULTIPLIER = 0.05
    _current_npc_count = sum(
        1 for _e in game_map.entities
        if not getattr(_e, 'owned', False)
        and getattr(_e, 'procedural_squad_id', '') != ''
    )
    if _current_npc_count < _system.npc_density * 3:
        if _engine.RNG.random() < _system.npc_spawn_chance * _PER_TICK_CHANCE_MULTIPLIER:
            _tick_types = [
                _tid for _tid, _tw in _system.npc_spawn_table
                if _engine.RNG.random() < _tw
            ]
            if _tick_types:
                _tick_id = _engine.RNG.choice(_tick_types)
                try:
                    _tick_spec = _find_npc_ship(_tick_id)
                except KeyError:
                    pass
                else:
                    _tick_is_merchant = getattr(_tick_spec, 'faction', 'pirate') == 'merchant'
                    _tick_mid = f"tick_npc_{getattr(_system, 'id', '')}_{_tick_id}_{_engine.RNG.randint(0, 99999)}"
                    _tick_body_goals = _build_body_goals(_system)

                    _tick_pos: world.Position | None = None
                    _tick_initial_target: tuple[int, int] | None = None
                    if _tick_body_goals:
                        _origin = _engine.RNG.choice(_tick_body_goals)
                        _tick_pos = world.Position(_origin[0], _origin[1])
                        if _tick_is_merchant and len(_tick_body_goals) >= 2:
                            _dest = _engine.RNG.choice(
                                [g for g in _tick_body_goals if (g[0], g[1]) != (_origin[0], _origin[1])]
                            )
                            _tick_initial_target = (_dest[0], _dest[1])

                    if _tick_pos is not None:
                        game_map.entities.append(
                            _make_npc_entity(_tick_spec, _tick_pos, _tick_mid)
                        )
                        # Register in procedural_spawns so save/load can find it.
                        # squad_id = movement_id so per-kill combat cleanup
                        # can match spawn → entity 1:1.
                        _cur_sys_id = getattr(_system, 'id', '')
                        if _cur_sys_id not in ctx.procedural_spawns:
                            ctx.procedural_spawns[_cur_sys_id] = []
                        ctx.procedural_spawns[_cur_sys_id].append(
                            ProceduralSpawn(
                                npc_id=_tick_id,
                                pos=_tick_pos,
                                squad_id=_tick_mid,
                            )
                        )
                        if _tick_initial_target is not None:
                            _set_npc_path(ctx, _tick_mid, _tick_pos, _tick_initial_target, game_map)
                        ctx.log.add_colored(
                            f"Sensor ping: 1 signal detected in the area ({_tick_spec.name}).",
                            _ml.COLOR_IMPORTANT_EVENT,
                        )

    # --- Build goal list with body type + name ---
    _goals = _build_body_goals(_system)
    if not _goals:
        _any_npcs = any(
            getattr(_e, 'procedural_squad_id', '') != ''
            for _e in game_map.entities
        )
        if _any_npcs:
            ctx.log.add("Sensor: NPC ships have no navigation targets nearby.")
        return

    # Helpers: resolve NPC spec from entity, check faction
    _MERCHANT_FLEE_RANGE = 10  # cells

    def _npc_spec_of(_e) -> Any | None:
        _pid = getattr(_e, 'npc_ship_id', '')
        if not _pid:
            return None
        try:
            return _find_npc_ship(_pid)
        except (KeyError, ImportError):
            return None

    def _faction_of(_e) -> str:
        _s = _npc_spec_of(_e)
        return getattr(_s, 'faction', 'pirate') if _s else 'pirate'

    # Cache pirate positions for flee detection (once per tick).
    _pirate_positions: list[tuple[int, int, int]] = []  # (x, y, dist_penalty later)
    for _e in game_map.entities:
        if getattr(_e, 'owned', False) or getattr(_e, 'procedural_squad_id', '') == '':
            continue
        if _faction_of(_e) == 'pirate':
            _pirate_positions.append((_e.pos.x, _e.pos.y))

    _npcs = [
        _e for _e in game_map.entities
        if not getattr(_e, 'owned', False)
        and getattr(_e, 'procedural_squad_id', '') != ''
    ]
    _squad_map: dict[str, list] = {}
    for _e in _npcs:
        _squad_map.setdefault(_e.procedural_squad_id, []).append(_e)

    for _sid, _members in list(_squad_map.items()):
        if len(_members) == 0:
            continue
        # Determine faction for this squad (read from the leader's spec).
        _faction = _faction_of(_members[0])

        # No global aggro — NPCs do not chase the player based on
        # reputation alone. Combat triggers only when the player
        # gets within ``detect_radius`` (handled by
        # ``_detect_combat_encounter``) or bumps an NPC and chooses
        # Attack via comms.
        _is_squad = len(_members) > 1
        _leader = _members[0]
        _lx, _ly = _leader.pos.x, _leader.pos.y
        _target = ctx.npc_targets.get(_sid)
        _target_goal = None  # will hold the full (x, y, type, name) tuple

        # --- Merchant flee check: detect nearby pirates ---
        if _faction == 'merchant' and _pirate_positions:
            _nearest_pirate_dist = min(
                math.hypot(_lx - _px, _ly - _py)
                for _px, _py in _pirate_positions
            )
            if _nearest_pirate_dist < _MERCHANT_FLEE_RANGE:
                # Move away from the nearest pirate instead of toward dest.
                _nearest_px, _nearest_py = min(
                    _pirate_positions,
                    key=lambda p: math.hypot(_lx - p[0], _ly - p[1]),
                )
                _flee_dx = _lx - _nearest_px
                _flee_dy = _ly - _nearest_py
                _flee_dx = max(-1, min(1, _flee_dx or _engine.RNG.randint(-1, 1)))
                _flee_dy = max(-1, min(1, _flee_dy or _engine.RNG.randint(-1, 1)))
                for _m in _members:
                    _nx = _m.pos.x + _flee_dx
                    _ny = _m.pos.y + _flee_dy
                    if (game_map.is_walkable(_nx, _ny)
                            and game_map.entity_at(_nx, _ny, exclude=_m) is None):
                        _m.pos = world.Position(_nx, _ny)
                # Skip normal movement for this tick after fleeing.
                continue

        # --- Check distance to current target ---
        if _target is not None:
            _tx, _ty = _target[0], _target[1]
            _dist_to_target = max(abs(_lx - _tx), abs(_ly - _ty))
            # Find the matching goal for the current target.
            for _g in _goals:
                if _g[0] == _tx and _g[1] == _ty:
                    _target_goal = _g
                    break
        else:
            _dist_to_target = 999

        # --- Refresh target when None or within 2 cells (merchant: despawn) ---
        if _target is None or _dist_to_target <= 2:
            if _faction == 'merchant' and _target_goal is not None:
                # Merchant reached destination — despawn.
                _body_type, _body_name = _target_goal[2], _target_goal[3]
                _spec = _npc_spec_of(_leader)
                _ship_name = getattr(_spec, 'name', 'Merchant') if _spec else 'Merchant'
                if _body_type == 'gate':
                    ctx.log.add(f"{_ship_name} jumps through {_body_name}.")
                    # Push a flash event at the despawn position for the
                    # space-mode render loop. Only visible in the viewport.
                    ctx.npc_flash_events.append(
                        NpcFlashEvent(pos=world.Position(_lx, _ly), lifetime=4)
                    )
                else:
                    ctx.log.add(f"{_ship_name} docks at {_body_name}.")
                # Remove all members from the map.
                for _m in _members:
                    try:
                        game_map.entities.remove(_m)
                    except ValueError:
                        pass
                ctx.npc_targets.pop(_sid, None)
                ctx.npc_paths.pop(_sid, None)
                # Clean up procedural_spawns for the despawned entities.
                # Match by both NPC type and position so we don't
                # accidentally remove a different NPC type at the same spot.
                _cur_sys_id = getattr(_system, 'id', '')
                _leader_npc = getattr(_leader, 'npc_ship_id', '')
                _despawned_positions = {(m.pos.x, m.pos.y) for m in _members}
                if _cur_sys_id in ctx.procedural_spawns:
                    ctx.procedural_spawns[_cur_sys_id] = [
                        _ps for _ps in ctx.procedural_spawns[_cur_sys_id]
                        if not (_ps.npc_id == _leader_npc
                                and (_ps.pos.x, _ps.pos.y) in _despawned_positions)
                    ]
                continue
            # Charged cell aggro: militia in Sol hunt the player.
            # Override ANY current target — drop patrol routes instantly.
            if (main_quest_module.charged_cell_in_sol(
                    ctx, getattr(_system, 'id', ''))
                    and _faction_of(_leader) == 'militia'):
                _target = (ctx.player.pos.x, ctx.player.pos.y)
                _target_goal = None
            elif _target is not None:
                # NPC still has a current patrol target — keep it.
                pass
            else:
                # Normal (pirate) or merchant with no current target: pick new.
                _candidates = [g for g in _goals if (g[0], g[1]) != _target]
                if not _candidates:
                    _candidates = _goals
                _chosen = _engine.RNG.choice(_candidates)
                _target = (_chosen[0], _chosen[1])
                _target_goal = _chosen
            ctx.npc_targets[_sid] = _target
            _end_set: set[tuple[int, int]] = {_target}
            _path = world.find_path(
                (_lx, _ly), _end_set, game_map,
                exclude_entity=_leader,
            )
            ctx.npc_paths[_sid] = _path or []
            # Aggro militia: force a fresh path every tick so they
            # constantly adjust to the player's movement.
            if _target_goal is None:
                ctx.npc_targets.pop(_sid, None)  # force repick next tick

        # Move most ticks for consistent progress (80% chance).
        if _engine.RNG.random() >= 0.8:
            continue
        _path = ctx.npc_paths.get(_sid)
        if not _path:
            ctx.npc_targets.pop(_sid, None)
            continue
        _next = _path[0]
        _dx = _next[0] - _lx
        _dy = _next[1] - _ly
        if abs(_dx) > 1 or abs(_dy) > 1:
            ctx.npc_paths[_sid] = []
            continue
        # Try the squad direction for each member.
        _leader_moved = False
        for _m in _members:
            _nx = _m.pos.x + _dx
            _ny = _m.pos.y + _dy
            if (game_map.is_walkable(_nx, _ny)
                    and game_map.entity_at(_nx, _ny, exclude=_m) is None):
                _m.pos = world.Position(_nx, _ny)
                if _m is _leader:
                    _leader_moved = True
            else:
                # Blocked — try perpendicular slip-around.
                if _dx != 0 and _dy != 0:
                    for _sdx, _sdy in [(_dx, 0), (0, _dy)]:
                        _snx = _m.pos.x + _sdx
                        _sny = _m.pos.y + _sdy
                        if (game_map.is_walkable(_snx, _sny)
                                and game_map.entity_at(_snx, _sny, exclude=_m) is None):
                            _m.pos = world.Position(_snx, _sny)
                            break
                elif _dx != 0:
                    for _sdx, _sdy in [(_dx, 1), (_dx, -1)]:
                        _snx = _m.pos.x + _sdx
                        _sny = _m.pos.y + _sdy
                        if (game_map.is_walkable(_snx, _sny)
                                and game_map.entity_at(_snx, _sny, exclude=_m) is None):
                            _m.pos = world.Position(_snx, _sny)
                            break
                else:  # _dy != 0
                    for _sdx, _sdy in [(1, _dy), (-1, _dy)]:
                        _snx = _m.pos.x + _sdx
                        _sny = _m.pos.y + _sdy
                        if (game_map.is_walkable(_snx, _sny)
                                and game_map.entity_at(_snx, _sny, exclude=_m) is None):
                            _m.pos = world.Position(_snx, _sny)
                            break
        if _leader_moved:
            ctx.npc_paths[_sid].pop(0)
        # On collision, preserve the path so the leader retries the same
        # step next tick. Don't recompute A* just because a cell was
        # temporarily occupied — the path is still valid.
        # Squad cohesion: pull stragglers toward centre
        if _is_squad:
            _cx = sum(m.pos.x for m in _members) // len(_members)
            _cy = sum(m.pos.y for m in _members) // len(_members)
            for _m in _members:
                if max(abs(_m.pos.x - _cx), abs(_m.pos.y - _cy)) > 4:
                    _pull_x = _cx + (1 if _m.pos.x < _cx else -1 if _m.pos.x > _cx else 0)
                    _pull_y = _cy + (1 if _m.pos.y < _cy else -1 if _m.pos.y > _cy else 0)
                    if (game_map.is_walkable(_pull_x, _pull_y)
                        and game_map.entity_at(_pull_x, _pull_y, exclude=_m) is None):
                        _m.pos = world.Position(_pull_x, _pull_y)


# ---------------------------------------------------------------------------
# NPC flash events — one-shot ring animations on the space map
# ---------------------------------------------------------------------------

_NPC_FLASH_RINGS: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("*", (200, 220, 255)),   # inner — pale blue-white (jump energy)
    ("+", (180, 200, 255)),   # ring 1 — blue-white
    ("o", (150, 180, 255)),   # ring 2 — dimmer blue
    ("#", (120, 150, 220)),   # ring 3 — faint blue edge
)
# The number of entries (4) must match NpcFlashEvent's default lifetime (4).
# If you add or remove a ring, update NpcFlashEvent.pos lifetime default too.


def render_npc_flash_events(
    console: tcod.console.Console,
    ctx: GameContext,
    cam_x: int, cam_y: int,
    view_w: int, view_h: int,
) -> None:
    """Paint expanding rings for active flash events in the viewport.

    Called from the space-mode render loop after the world view is
    drawn but before the HUD. Each event with a position inside
    the current viewport gets its rings painted; events outside
    the viewport decay silently. Expired events are removed.
    """
    if not ctx.npc_flash_events:
        return

    _active: list[NpcFlashEvent] = []
    for _ev in ctx.npc_flash_events:
        # Decrement lifetime every frame, regardless of viewport.
        # Events outside the viewport decay silently and are not
        # drawn — the continue below skips drawing but not the
        # decrement above the check.
        _ev.lifetime -= 1
        if _ev.lifetime <= 0:
            continue  # expired, discard

        _sx = _ev.pos.x - cam_x
        _sy = _ev.pos.y - cam_y

        # Only draw rings when the event is inside the viewport.
        # Events outside the viewport still decay naturally and
        # become visible if the camera moves toward them.
        if 0 <= _sx < view_w and 0 <= _sy < view_h:
            # Draw expanding rings: lifetime counts DOWN (4 → 1),
            # so the number of rings drawn INCREASES as lifetime
            # decreases, creating an expanding-outward flash.
            _rings_to_draw = len(_NPC_FLASH_RINGS) - _ev.lifetime + 1
            for _ri in range(_rings_to_draw):
                _r_char, _r_fg = _NPC_FLASH_RINGS[_ri]
                _dist = _ri + 1
                for _dy in range(-_dist, _dist + 1):
                    for _dx in range(-_dist, _dist + 1):
                        if abs(_dx) + abs(_dy) != _dist:
                            continue
                        _px = _sx + _dx
                        _py = _sy + _dy
                        if 0 <= _px < view_w and 0 <= _py < view_h:
                            console.print(x=_px, y=_py, string=_r_char, fg=_r_fg)

        # Keep alive (regardless of viewport) so the event decays
        # naturally over its full lifetime.
        _active.append(_ev)

    ctx.npc_flash_events = _active
