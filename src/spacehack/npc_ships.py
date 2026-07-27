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

from . import engine as _engine
from . import message_log as _ml
from . import solar_system as _solar_module
from . import world
from .data.npc_ships import find_npc_ship as _find_npc_ship
from .game_context import GameContext, ProceduralSpawn

# Movement state keys stored on GameContext.
_NPC_TARGETS: str = "npc_targets"       # dict[str, tuple[int, int]]
_NPC_PATHS: str = "npc_paths"           # dict[str, list[tuple[int, int]]]


def spawn_npcs(
    ctx: GameContext,
    game_map: world.GameMap,
    system_id: str,
) -> None:
    """Roll for procedural NPC encounters in ``system_id``.

    Each jump / launch consumes a fresh roll from the game's seeded
    RNG. If the system's ``npc_spawn_chance`` hits, NPC groups are
    spawned according to the weighted ``npc_spawn_table`` and
    ``npc_density``.  Each NPC ship gets a ``npc_ship_id`` on the
    Entity (referencing :class:`data.npc_ships.NpcShipSpec`) so
    combat detection and loot generation can read per-type data.

    Uses ``ctx.procedural_spawns`` (keyed by system id) so combat
    detection can locate them.
    """
    from .data.solar_systems import find_solar_system as _fss
    try:
        _system = _fss(system_id)
    except KeyError:
        return
    if _system.npc_spawn_chance <= 0.0 or not _system.npc_spawn_table or _system.npc_density <= 0:
        return
    if _engine.RNG.random() >= _system.npc_spawn_chance:
        return

    # Build a set of blocked cells (planets, gates, stations, existing entities).
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
    for _e in game_map.entities:
        for _dy in range(_e.height):
            for _dx in range(_e.width):
                _blocked.add((_e.pos.x + _dx, _e.pos.y + _dy))

    def _pick_centre() -> tuple[int, int] | None:
        for _attempt in range(200):
            _cx = _engine.RNG.randint(10, _system.width - 10)
            _cy = _engine.RNG.randint(10, _system.height - 10)
            if (_cx, _cy) not in _blocked:
                return (_cx, _cy)
        return None

    # Roll which NPC types appear from the weighted table.
    # Each entry (npc_id, weight) is independently rolled.
    _active_types: list[str] = []
    for _npc_id, _weight in _system.npc_spawn_table:
        if _engine.RNG.random() < _weight:
            _active_types.append(_npc_id)
    if not _active_types:
        _active_types = [_system.npc_spawn_table[0][0]]

    # Build list of navigable body goals (x, y, type, name) for merchant spawns.
    _body_goals: list[tuple[int, int, str, str]] = []
    def _goal_for(body, kind: str, name: str) -> None:
        _gx = body.pos.x + body.width + 1
        _gy = body.pos.y + body.height // 2
        if 0 <= _gx < _system.width and 0 <= _gy < _system.height:
            _body_goals.append((_gx, _gy, kind, name))
    for _p in _system.planets:
        if getattr(_p, 'sun', False):
            continue
        _goal_for(_p, "planet", _p.name)
    for _jp in _system.jump_points:
        _goal_for(_jp, "gate", _jp.name)
    for _st in getattr(_system, 'stations', ()) or ():
        _goal_for(_st, "station", _st.name)

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
        if _is_merchant and len(_body_goals) >= 2:
            # Merchant: spawn at a body, en route to another.
            _origin_goal = _engine.RNG.choice(_body_goals)
            _dest_goal = _engine.RNG.choice([g for g in _body_goals if (g[0], g[1]) != (_origin_goal[0], _origin_goal[1])])
            _gcx, _gcy = _origin_goal[0], _origin_goal[1]
            _initial_target = (_dest_goal[0], _dest_goal[1])
            # Mark origin cell as blocked so we spawn near it, not on it.
            _blocked.add((_gcx, _gcy))
        else:
            # Pirate: random scatter.
            _centre = _pick_centre()
            if _centre is None:
                continue
            _gcx, _gcy = _centre

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
            game_map.entities.append(world.Entity(
                char=_spec.char, fg=_spec.fg, pos=_pos,
                name=_spec.name, width=1, height=1,
                npc_ship_id=_npc_id,
                procedural_squad_id=_movement_id,
            ))
            _group_positions.append(_pos)
            _all_procedural.append((_pos, _squad_id, _npc_id))
            _group_entities += 1
        _total_spawned += _group_entities

        # Pre-set initial target + path for merchants.
        if _is_merchant and _initial_target is not None and _group_positions:
            _leader_pos = _group_positions[0]
            ctx.npc_targets[_movement_id] = _initial_target
            _end_set: set[tuple[int, int]] = {_initial_target}
            _path = world.find_path(
                (_leader_pos.x, _leader_pos.y), _end_set, game_map,
            )
            ctx.npc_paths[_movement_id] = _path or []

    if _all_procedural:
        ctx.procedural_spawns[system_id] = [
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
            # Pick a random NPC type from the spawn table (simple random choice).
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
                    _tick_body_goals: list[tuple[int, int, str, str]] = []
                    def _tick_goal(body, kind: str, name: str) -> None:
                        _gx = body.pos.x + body.width + 1
                        _gy = body.pos.y + body.height // 2
                        if 0 <= _gx < _system.width and 0 <= _gy < _system.height:
                            _tick_body_goals.append((_gx, _gy, kind, name))
                    for _p in _system.planets:
                        if not getattr(_p, 'sun', False):
                            _tick_goal(_p, "planet", _p.name)
                    for _jp in _system.jump_points:
                        _tick_goal(_jp, "gate", _jp.name)
                    for _st in getattr(_system, 'stations', ()) or ():
                        _tick_goal(_st, "station", _st.name)

                    _tick_pos: world.Position | None = None
                    _tick_initial_target: tuple[int, int] | None = None
                    if _tick_is_merchant and len(_tick_body_goals) >= 2:
                        _origin = _engine.RNG.choice(_tick_body_goals)
                        _dest = _engine.RNG.choice([g for g in _tick_body_goals if (g[0], g[1]) != (_origin[0], _origin[1])])
                        _tick_pos = world.Position(_origin[0], _origin[1])
                        _tick_initial_target = (_dest[0], _dest[1])
                    else:
                        # Pirate: try random spot, with fewer attempts.
                        for _attempt in range(50):
                            _rx = _engine.RNG.randint(10, _system.width - 10)
                            _ry = _engine.RNG.randint(10, _system.height - 10)
                            if game_map.is_walkable(_rx, _ry) and game_map.entity_at(_rx, _ry) is None:
                                _tick_pos = world.Position(_rx, _ry)
                                break

                    if _tick_pos is not None:
                        game_map.entities.append(world.Entity(
                            char=_tick_spec.char, fg=_tick_spec.fg, pos=_tick_pos,
                            name=_tick_spec.name, width=1, height=1,
                            npc_ship_id=_tick_id,
                            procedural_squad_id=_tick_mid,
                        ))
                        if _tick_initial_target is not None:
                            ctx.npc_targets[_tick_mid] = _tick_initial_target
                            _end_set: set[tuple[int, int]] = {_tick_initial_target}
                            _path = world.find_path(
                                (_tick_pos.x, _tick_pos.y), _end_set, game_map,
                            )
                            ctx.npc_paths[_tick_mid] = _path or []
                        ctx.log.add_colored(
                            f"Sensor ping: 1 signal detected in the area ({_tick_spec.name}).",
                            _ml.COLOR_IMPORTANT_EVENT,
                        )

    # --- Build goal list with body type + name ---
    _goals: list[tuple[int, int, str, str]] = []  # (x, y, type, name)
    def _body_goal(body) -> tuple[int, int] | None:
        _gx = body.pos.x + body.width + 1
        _gy = body.pos.y + body.height // 2
        if 0 <= _gx < _system.width and 0 <= _gy < _system.height:
            return (_gx, _gy)
        return None
    for _p in _system.planets:
        if getattr(_p, 'sun', False):
            continue
        _g = _body_goal(_p)
        if _g is not None:
            _goals.append((_g[0], _g[1], "planet", _p.name))
    for _jp in _system.jump_points:
        _g = _body_goal(_jp)
        if _g is not None:
            _goals.append((_g[0], _g[1], "gate", _jp.name))
    for _st in getattr(_system, 'stations', ()) or ():
        _g = _body_goal(_st)
        if _g is not None:
            _goals.append((_g[0], _g[1], "station", _st.name))
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
                # Clean up procedural_spawns for this squad.
                _cur_sys_id = getattr(_system, 'id', '')
                if _cur_sys_id in ctx.procedural_spawns:
                    ctx.procedural_spawns[_cur_sys_id] = [
                        _ps for _ps in ctx.procedural_spawns[_cur_sys_id]
                        if _ps.squad_id != _sid
                    ]
                continue
            # Normal (pirate) or merchant with no current target: pick new.
            _candidates = [g for g in _goals if (g[0], g[1]) != _target]
            if not _candidates:
                _candidates = _goals
            _chosen = _engine.RNG.choice(_candidates)
            _target = (_chosen[0], _chosen[1])
            ctx.npc_targets[_sid] = _target
            _target_goal = _chosen
            _end_set: set[tuple[int, int]] = {_target}
            _path = world.find_path(
                (_lx, _ly), _end_set, game_map,
                exclude_entity=_leader,
            )
            ctx.npc_paths[_sid] = _path or []

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
        else:
            ctx.npc_paths.pop(_sid, None)
            ctx.npc_targets.pop(_sid, None)
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
