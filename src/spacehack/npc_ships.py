"""Procedural NPC ship spawning and movement.

Extracted from :mod:`__main__` so the dispatcher stays clean.
Replaces ``_spawn_procedural_pirates`` / ``_move_pirates`` with
a unified ``spawn_npcs`` / ``move_npcs`` that handles both pirates
and merchants from the single :class:`data.npc_ships.NpcShipSpec`
catalog.
"""

from __future__ import annotations

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

    _total_spawned = 0
    _all_procedural: list = []

    for _npc_id in _active_types:
        try:
            _spec = _find_npc_ship(_npc_id)
        except KeyError:
            continue

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
            _all_procedural.append((_pos, _squad_id, _npc_id))
            _group_entities += 1
        _total_spawned += _group_entities

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

    Called after the player moves in space mode. Each NPC squad
    (or solo) picks a planet, gate, or station and commits to
    moving toward it until within 2 cells, then picks a new
    target. Squad members use the A* path computed for the squad
    leader. Uses the same A*-based movement as the old pirate
    mover, but handles all NPC types (pirates + merchants) via
    ``npc_ship_id`` on the Entity.

    Movement state is stored on ``ctx.npc_targets`` and
    ``ctx.npc_paths`` (dicts keyed by ``procedural_squad_id``).
    """
    _system = _solar_module.current_system()
    if _system is None:
        return

    # Build goal list from the current system's bodies.
    _goals: list[tuple[int, int]] = []
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
            _goals.append(_g)
    for _jp in _system.jump_points:
        _g = _body_goal(_jp)
        if _g is not None:
            _goals.append(_g)
    for _st in getattr(_system, 'stations', ()) or ():
        _g = _body_goal(_st)
        if _g is not None:
            _goals.append(_g)
    if not _goals:
        _any_npcs = any(
            getattr(_e, 'procedural_squad_id', '') != ''
            for _e in game_map.entities
        )
        if _any_npcs:
            ctx.log.add("Sensor: NPC ships have no navigation targets nearby.")
        return

    _npcs = [
        _e for _e in game_map.entities
        if not getattr(_e, 'owned', False)
        and getattr(_e, 'procedural_squad_id', '') != ''
    ]
    _squad_map: dict[str, list] = {}
    for _e in _npcs:
        _squad_map.setdefault(_e.procedural_squad_id, []).append(_e)

    for _sid, _members in _squad_map.items():
        if len(_members) == 0:
            continue
        _is_squad = len(_members) > 1
        _leader = _members[0]
        _target = ctx.npc_targets.get(_sid)
        _lx, _ly = _leader.pos.x, _leader.pos.y
        _dist_to_target = (
            max(abs(_lx - _target[0]), abs(_ly - _target[1]))
            if _target is not None else 999
        )
        # Refresh target when None or within 2 cells.
        if _target is None or _dist_to_target <= 2:
            _candidates = [g for g in _goals if g != _target]
            if not _candidates:
                _candidates = _goals
            _target = _engine.RNG.choice(_candidates)
            ctx.npc_targets[_sid] = _target
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
                _slipped = False
                if _dx != 0 and _dy != 0:
                    for _sdx, _sdy in [(_dx, 0), (0, _dy)]:
                        _snx = _m.pos.x + _sdx
                        _sny = _m.pos.y + _sdy
                        if (game_map.is_walkable(_snx, _sny)
                                and game_map.entity_at(_snx, _sny, exclude=_m) is None):
                            _m.pos = world.Position(_snx, _sny)
                            _slipped = True
                            break
                elif _dx != 0:
                    for _sdx, _sdy in [(_dx, 1), (_dx, -1)]:
                        _snx = _m.pos.x + _sdx
                        _sny = _m.pos.y + _sdy
                        if (game_map.is_walkable(_snx, _sny)
                                and game_map.entity_at(_snx, _sny, exclude=_m) is None):
                            _m.pos = world.Position(_snx, _sny)
                            _slipped = True
                            break
                else:  # _dy != 0
                    for _sdx, _sdy in [(1, _dy), (-1, _dy)]:
                        _snx = _m.pos.x + _sdx
                        _sny = _m.pos.y + _sdy
                        if (game_map.is_walkable(_snx, _sny)
                                and game_map.entity_at(_snx, _sny, exclude=_m) is None):
                            _m.pos = world.Position(_snx, _sny)
                            _slipped = True
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
