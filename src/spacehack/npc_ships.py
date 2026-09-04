"""Procedural NPC ship spawning and movement.

Extracted from :mod:`__main__` so the dispatcher stays clean.
Replaces ``_spawn_procedural_pirates`` / ``_move_pirates`` with
a unified ``spawn_npcs`` / ``move_npcs`` that handles both pirates
and merchants from the single :class:`data.npc_ships.NpcShipSpec`
catalog.
"""

from __future__ import annotations
import math

from .framebuffer import FrameBuffer

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


def _spawn_consortium_squad(
    ctx: GameContext,
    game_map: world.GameMap,
    system_id: str,
    system,
    body_goals: list,
) -> bool:
    """Consortium squad near one body goal: pirate leader (aggro) +
    merchant front + escorts. True when anything spawned."""
    if not body_goals:
        return False
    try:
        _specs = dict(pirate=_find_npc_ship("pirate_scout"),
                      merchant=_find_npc_ship("merchant_hauler"))
    except KeyError:
        return False

    _origin = _engine.RNG.choice(body_goals)[:2]
    _mid = f"consortium_{system_id}_{_engine.RNG.randint(0, 99999)}"
    _squad = _SquadPlacement(
        game_map, system, *_origin, _occupied_cells(game_map), _mid,
    )
    # Leader first; escorts only join when the merchant front placed.
    if not _squad.place(_specs["pirate"]):
        return False
    if _squad.place(_specs["merchant"]):
        for _ in range(_engine.RNG.randint(1, 4)):
            _squad.place(_specs["pirate"])
    ctx.procedural_spawns.setdefault(system_id, []).extend(
        ProceduralSpawn(npc_id=_nid, pos=_ppos, squad_id=_mid)
        for _ppos, _nid in zip(_squad.positions, _squad.npc_ids)
    )
    _total = len(_squad.positions) - 1  # minus the merchant
    _escorts = "escort" if _total == 1 else "escorts"

    ctx.log.add_colored(
        f"Sensor ping: consortium operation detected - merchant hauler "
        f"with {_total} pirate {_escorts}.", _ml.COLOR_IMPORTANT_EVENT,
    )
    return True


class _SquadPlacement:
    """Places one squad's members near a shared goal cell, tracking
    occupied cells and the placed roster."""

    def __init__(self, game_map, system, gcx, gcy, blocked, mid):
        self.game_map = game_map
        self.system = system
        self.gcx = gcx
        self.gcy = gcy
        self.blocked = blocked
        self.mid = mid
        self.positions: list[world.Position] = []
        self.npc_ids: list[str] = []

    def place(self, spec) -> bool:
        """One member on a free cell within 4 of the goal (50 rolls)."""
        for _ in range(50):
            _x = self.gcx + _engine.RNG.randint(-4, 4)
            _y = self.gcy + _engine.RNG.randint(-4, 4)
            if not (0 <= _x < self.system.width and 0 <= _y < self.system.height):
                continue
            if (_x, _y) in self.blocked:
                continue
            self.blocked.add((_x, _y))
            _pos = world.Position(_x, _y)
            self.game_map.entities.append(_make_npc_entity(spec, _pos, self.mid))
            self.positions.append(_pos)
            self.npc_ids.append(spec.id)
            return True
        return False


def _occupied_cells(game_map) -> set[tuple[int, int]]:
    """Every cell covered by an existing entity (overlap guard)."""
    return {
        (_e.pos.x + _dx, _e.pos.y + _dy)
        for _e in game_map.entities
        for _dy in range(_e.height)
        for _dx in range(_e.width)
    }





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


def _derelict_position(system_id, system):
    """Where a derelict spawns this entry, or None (roll failed/full).

    Dev mode (SPACEHACK_DEV, Sol) forces one just east of Earth's
    dock so it is visible on launch; otherwise the system's
    derelict_spawn_chance rolls against open space far from bodies.
    """
    import os as _os
    if _os.environ.get("SPACEHACK_DEV") and system_id == "sol":
        return world.Position(150, 40)
    if getattr(system, 'derelict_spawn_chance', 0) <= 0:
        return None
    if _engine.RNG.random() >= system.derelict_spawn_chance:
        return None
    return _find_open_space(system, _derelict_blocked_near(system))


def _spawn_derelict(
    ctx: GameContext,
    game_map: world.GameMap,
    system_id: str,
    system,
) -> bool:
    """Spawn a derelict_scout in ``system`` if the roll hits
    (see _derelict_position); ``True`` when one spawned."""
    _pos = _derelict_position(system_id, system)
    if _pos is None:
        return False
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
    ctx.procedural_spawns.setdefault(system_id, []).append(
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
    """Roll procedural NPC encounters in ``system_id``.

    Phases in RNG-draw order (do not reorder): derelict, militia
    patrols, consortium heat, npc_spawn_table groups.
    """
    _system = _system_or_none(system_id)
    if _system is None:
        return
    _spawn_derelict(ctx, game_map, system_id, _system)
    _blocked = _celestial_blocked_cells(_system)
    _spawn_militia_patrols(
        ctx, game_map, system_id, _system, _blocked, player_spawn_exclusion,
    )
    if main_quest_module.consortium_heat_active(ctx):
        _body_goals = _spawn_body_goals(_system, player_spawn_exclusion)
        for _ in range(_engine.RNG.randint(1, 2)):
            _spawn_consortium_squad(ctx, game_map, system_id, _system, _body_goals)

    if (_system.npc_spawn_chance <= 0.0
            or not _system.npc_spawn_table or _system.npc_density <= 0
            or _engine.RNG.random() >= _system.npc_spawn_chance):
        return

    _blocked |= _occupied_cells(game_map)
    if player_spawn_exclusion:
        _blocked.update(player_spawn_exclusion)
    _total, _all = _spawn_table_groups(
        ctx, game_map, system_id, _system, _blocked,
        _spawn_body_goals(_system, player_spawn_exclusion),
    )
    _register_table_batch(ctx, system_id, _all, _total)


def _system_or_none(system_id):
    """The system spec, or None for an unknown id."""
    from .data.solar_systems import find_solar_system as _fss
    try:
        return _fss(system_id)
    except KeyError:
        return None


def _celestial_blocked_cells(system) -> set[tuple[int, int]]:
    """Every cell covered by a planet, gate, or station footprint."""
    _blocked: set[tuple[int, int]] = set()
    _groups = (
        list(system.planets) + list(system.jump_points)
        + list(getattr(system, 'stations', ()) or ())
    )
    for _body in _groups:
        for _dy in range(_body.height):
            for _dx in range(_body.width):
                _blocked.add((_body.pos.x + _dx, _body.pos.y + _dy))
    return _blocked


def _spawn_body_goals(system, exclusion) -> list:
    """Body-goal cells for spawn origins, minus the arrival body."""
    _goals = _build_body_goals(system)
    if not exclusion:
        return _goals
    return [g for g in _goals if (g[0], g[1]) not in exclusion]


def _free_cell_near(gcx, gcy, system, blocked) -> tuple[int, int] | None:
    """One in-bounds unblocked cell within 4 of the goal (50 rolls)."""
    for _ in range(50):
        _x = gcx + _engine.RNG.randint(-4, 4)
        _y = gcy + _engine.RNG.randint(-4, 4)
        if (0 <= _x < system.width and 0 <= _y < system.height
                and (_x, _y) not in blocked):
            return _x, _y
    return None


def _spawn_militia_patrols(
    ctx, game_map, system_id, system, blocked, exclusion,
) -> None:
    """Patrol ships per patrol_density, heavier classes at density 3+."""
    _patrol_min, _patrol_max = system.patrol_density
    if _patrol_max <= 0:
        return
    _body_goals = _spawn_body_goals(system, exclusion)
    if not _body_goals:
        return
    _patrol_ship = (
        "militia_patrol_heavy" if _patrol_max >= 5 else
        "militia_patrol" if _patrol_max >= 3 else
        "militia_patrol_light"
    )
    try:
        _patrol_spec = _find_npc_ship(_patrol_ship)
    except KeyError:
        return
    _militia: list = []
    for _pi in range(_engine.RNG.randint(_patrol_min, _patrol_max)):
        _gcx, _gcy = _engine.RNG.choice(_body_goals)[:2]
        _cell = _free_cell_near(_gcx, _gcy, system, blocked)
        if _cell is None:
            continue
        blocked.add(_cell)
        _mid = f"patrol_{system_id}_{_pi}_{_engine.RNG.randint(0, 99999)}"
        _pos = world.Position(*_cell)
        game_map.entities.append(_make_npc_entity(_patrol_spec, _pos, _mid))
        _militia.append((_pos, _mid, _patrol_ship))
    if not _militia:
        return
    ctx.procedural_spawns.setdefault(system_id, []).extend(
        ProceduralSpawn(npc_id=_npc_id, pos=_pos, squad_id=_sid)
        for _pos, _sid, _npc_id in _militia
    )
    ctx.log.add_colored(
        f"Sensor ping: {len(_militia)} militia patrol(s) active in the area.",
        _ml.COLOR_IMPORTANT_EVENT,
    )


def _spawn_table_groups(
    ctx, game_map, system_id, system, blocked, body_goals,
) -> tuple[int, list]:
    """Spawn the weighted npc_spawn_table groups.

    Returns ``(total_spawned, [(pos, movement_id, npc_id), ...])``.
    """
    _active: list[str] = [
        _npc_id for _npc_id, _weight in system.npc_spawn_table
        if _engine.RNG.random() < _weight
    ]
    if not _active:
        _active = [system.npc_spawn_table[0][0]]

    _total = 0
    _all: list = []
    for _npc_id in _active:
        try:
            _spec = _find_npc_ship(_npc_id)
        except KeyError:
            continue
        if not body_goals:
            continue
        _total += _spawn_one_type(
            ctx, game_map, system_id, system, blocked, body_goals,
            _npc_id, _spec, _all,
        )
    return _total, _all


def _spawn_one_type(
    ctx, game_map, system_id, system, blocked, body_goals,
    npc_id, spec, all_procedural,
) -> int:
    """One NPC type's group near one origin goal (merchants get a
    destination body); returns the count placed."""
    _is_merchant = getattr(spec, 'faction', 'pirate') == 'merchant'
    _origin = _engine.RNG.choice(body_goals)
    _gcx, _gcy = _origin[0], _origin[1]
    blocked.add((_gcx, _gcy))
    _initial_target = None
    if _is_merchant and len(body_goals) >= 2:
        _dest = _engine.RNG.choice(
            [g for g in body_goals if (g[0], g[1]) != (_gcx, _gcy)]
        )
        _initial_target = (_dest[0], _dest[1])

    _is_squad = system.npc_density > 1 and _engine.RNG.random() < 0.5
    _squad_id = (
        f"proc_npc_{system_id}_{npc_id}_{_engine.RNG.randint(0, 99999)}"
        if _is_squad else None
    )
    _movement_id = _squad_id or (
        f"proc_solo_{system_id}_{npc_id}_{_engine.RNG.randint(0, 99999)}"
    )

    _group: list[world.Position] = []
    for _ in range(_engine.RNG.randint(1, min(system.npc_density, 4))):
        _cell = _free_cell_near(_gcx, _gcy, system, blocked)
        if _cell is None:
            continue
        blocked.add(_cell)
        _pos = world.Position(*_cell)
        game_map.entities.append(_make_npc_entity(spec, _pos, _movement_id))
        _group.append(_pos)
        all_procedural.append((_pos, _movement_id, npc_id))
    if _is_merchant and _initial_target and _group:
        _set_npc_path(ctx, _movement_id, _group[0], _initial_target, game_map)
    return len(_group)


def _register_table_batch(ctx, system_id, all_procedural, total) -> None:
    """Swap in the fresh table batch, preserving other npc_id entries
    (e.g. derelicts), and log the sensor ping."""
    if not all_procedural:
        return
    _spawned_ids = {npc_id for _, _, npc_id in all_procedural}
    _preserved = [
        _ps for _ps in ctx.procedural_spawns.get(system_id, [])
        if _ps.npc_id not in _spawned_ids
    ]
    ctx.procedural_spawns[system_id] = _preserved + [
        ProceduralSpawn(npc_id=npc_id, pos=pos, squad_id=sid)
        for pos, sid, npc_id in all_procedural
    ]
    _names = set()
    for _, _, _npc_id in all_procedural:
        try:
            _names.add(_find_npc_ship(_npc_id).name)
        except KeyError:
            _names.add("unknown contact")
    _signals = "signal" if total == 1 else "signals"
    ctx.log.add_colored(
        f"Sensor ping: {total} {_signals} detected in the area "
        f"({', '.join(sorted(_names))}).", _ml.COLOR_IMPORTANT_EVENT,
    )
# ---------------------------------------------------------------------------
# Per-tick movement (and occasional per-tick spawn)
# ---------------------------------------------------------------------------

def move_npcs(ctx: GameContext, game_map: world.GameMap) -> None:
    """Patrol procedural NPC entities toward bodies, once per tick.

    Pirates loop body to body; merchants head for a body and despawn
    on arrival (gate = jump, planet/station = dock), fleeing nearby
    pirates. Aggro militia/consortium squads chase the player instead.
    Squad members follow the leader's A* path with cohesion stepping.
    """
    _system = _solar_module.current_system()
    if _system is None:
        return

    _tick_spawn_npc(ctx, game_map, _system)
    _tick_consortium_squads(ctx, game_map, _system)

    _goals = _build_body_goals(_system)
    if not _goals:
        if any(getattr(_e, 'procedural_squad_id', '') for _e in game_map.entities):
            ctx.log.add("Sensor: NPC ships have no navigation targets nearby.")
        return

    _pirates = _pirate_positions(game_map)
    for _sid, _members in _squad_groups(game_map).items():
        _move_one_squad(
            ctx, game_map, _system, _goals, _sid, _members, _pirates,
        )


def _spec_of_entity(entity):
    """The entity's NpcShipSpec, or None when unresolvable."""
    _pid = getattr(entity, 'npc_ship_id', '')
    if not _pid:
        return None
    try:
        return _find_npc_ship(_pid)
    except (KeyError, ImportError):
        return None


def _faction_of_entity(entity) -> str:
    _spec = _spec_of_entity(entity)
    return getattr(_spec, 'faction', 'pirate') if _spec else 'pirate'


def _pirate_positions(game_map) -> list[tuple[int, int]]:
    """Cached pirate cells for merchant flee checks (once per tick)."""
    return [
        (_e.pos.x, _e.pos.y)
        for _e in game_map.entities
        if not getattr(_e, 'owned', False)
        and getattr(_e, 'procedural_squad_id', '') != ''
        and _faction_of_entity(_e) == 'pirate'
    ]


def _squad_groups(game_map) -> dict[str, list]:
    """Patrollable NPCs grouped by squad id (combat participants stay
    locked out so they neither patrol nor despawn mid-fight)."""
    _squads: dict[str, list] = {}
    for _e in game_map.entities:
        if getattr(_e, 'owned', False):
            continue
        _sid = getattr(_e, 'procedural_squad_id', '')
        if not _sid or getattr(_e, 'combat_locked', False):
            continue
        _squads.setdefault(_sid, []).append(_e)
    return _squads


def _live_npc_count(game_map) -> int:
    """Unowned, procedurally-spawned entities on the map."""
    return sum(
        1 for _e in game_map.entities
        if not getattr(_e, 'owned', False)
        and getattr(_e, 'procedural_squad_id', '') != ''
    )


def _origin_and_destination(goals, is_merchant):
    """(origin_position, merchant_destination | None) from body goals."""
    if not goals:
        return None, None
    _origin = _engine.RNG.choice(goals)
    _pos = world.Position(_origin[0], _origin[1])
    _target = None
    if is_merchant and len(goals) >= 2:
        _dest = _engine.RNG.choice(
            [g for g in goals if (g[0], g[1]) != (_origin[0], _origin[1])]
        )
        _target = (_dest[0], _dest[1])
    return _pos, _target


def _tick_spawn_npc(ctx, game_map, system) -> None:
    """One-per-tick traffic spawn: a scaled-down roll from the
    system's base chance and weighted table, capped at density x 3."""
    _PER_TICK_CHANCE_MULTIPLIER = 0.05
    if _live_npc_count(game_map) >= system.npc_density * 3:
        return
    if _engine.RNG.random() >= system.npc_spawn_chance * _PER_TICK_CHANCE_MULTIPLIER:
        return
    _types = [
        _tid for _tid, _tw in system.npc_spawn_table
        if _engine.RNG.random() < _tw
    ]
    if not _types:
        return
    _tick_id = _engine.RNG.choice(_types)
    try:
        _tick_spec = _find_npc_ship(_tick_id)
    except KeyError:
        return
    _is_merchant = getattr(_tick_spec, 'faction', 'pirate') == 'merchant'
    _mid = f"tick_npc_{getattr(system, 'id', '')}_{_tick_id}_{_engine.RNG.randint(0, 99999)}"
    _pos, _initial_target = _origin_and_destination(
        _build_body_goals(system), _is_merchant,
    )
    if _pos is None:
        return

    game_map.entities.append(_make_npc_entity(_tick_spec, _pos, _mid))
    # squad_id = movement_id so per-kill combat cleanup matches 1:1.
    ctx.procedural_spawns.setdefault(getattr(system, 'id', ''), []).append(
        ProceduralSpawn(npc_id=_tick_id, pos=_pos, squad_id=_mid)
    )
    if _initial_target is not None:
        _set_npc_path(ctx, _mid, _pos, _initial_target, game_map)
    ctx.log.add_colored(
        f"Sensor ping: 1 signal detected in the area ({_tick_spec.name}).",
        _ml.COLOR_IMPORTANT_EVENT,
    )


def _tick_consortium_squads(ctx, game_map, system) -> None:
    """~2%-per-tick consortium squad while quest heat is live, capped
    at density x 2 live NPCs."""
    if not main_quest_module.consortium_heat_active(ctx):
        return
    _live = sum(
        1 for _e in game_map.entities
        if not getattr(_e, 'owned', False)
        and getattr(_e, 'procedural_squad_id', '') != ''
    )
    if _live < system.npc_density * 2 and _engine.RNG.random() < 0.02:
        _spawn_consortium_squad(
            ctx, game_map, getattr(system, 'id', ''),
            system, _build_body_goals(system),
        )


def _move_one_squad(ctx, game_map, system, goals, sid, members, pirates) -> None:
    """One squad's tick: flee or refresh target, maybe despawn,
    store path, then step (aggro squads chase the player)."""
    _faction = _faction_of_entity(members[0])
    _leader = members[0]
    _lx, _ly = _leader.pos.x, _leader.pos.y
    _target = ctx.npc_targets.get(sid)
    _target_goal = _matching_goal(goals, _target)

    if _faction == 'merchant' and pirates:
        if _merchant_flees(game_map, _leader, members, pirates):
            return

    _dist = (
        max(abs(_lx - _target[0]), abs(_ly - _target[1]))
        if _target is not None else 999
    )

    # Aggro state once per squad, shared by target + movement.
    _aggro = _squad_aggro(ctx, system, _leader)
    if _aggro:
        _target = (ctx.player.pos.x, ctx.player.pos.y)
        _target_goal = None
    elif _target is None or _dist <= 2:
        if _faction == 'merchant' and _target_goal is not None:
            _despawn_merchant(ctx, game_map, system, _leader, members, _target_goal)
            return
        if _target is None:
            _target, _target_goal = _new_patrol_target(goals)

    if _target is not None:
        _store_target_path(ctx, game_map, sid, _leader, _target, _aggro)
    _step_squad(ctx, game_map, sid, members, _aggro)


def _squad_aggro(ctx, system, leader) -> bool:
    """Charged-cell militia or consortium-heat pirates chase the player."""
    _faction = _faction_of_entity(leader)
    return (
        main_quest_module.charged_cell_in_sol(ctx, getattr(system, 'id', ''))
        and _faction == 'militia'
    ) or (
        main_quest_module.consortium_heat_active(ctx)
        and _faction == 'pirate'
    )


def _new_patrol_target(goals):
    """A fresh body goal (full tuple), preferring an unvisited one."""
    _chosen = _engine.RNG.choice(goals)
    return (_chosen[0], _chosen[1]), _chosen


def _matching_goal(goals, target):
    """The full (x, y, type, name) goal tuple for a stored target."""
    if target is None:
        return None
    return next(
        (_g for _g in goals if _g[0] == target[0] and _g[1] == target[1]),
        None,
    )


def _merchant_flees(game_map, leader, members, pirates) -> bool:
    """Flee step away from the nearest pirate (10 cells); True when
    the squad fled and should skip normal movement this tick."""
    _MERCHANT_FLEE_RANGE = 10
    _lx, _ly = leader.pos.x, leader.pos.y
    _nearest = min(
        math.hypot(_lx - _px, _ly - _py) for _px, _py in pirates
    )
    if _nearest >= _MERCHANT_FLEE_RANGE:
        return False
    _px, _py = min(
        pirates, key=lambda p: math.hypot(_lx - p[0], _ly - p[1]),
    )
    _dx = max(-1, min(1, _lx - _px or _engine.RNG.randint(-1, 1)))
    _dy = max(-1, min(1, _ly - _py or _engine.RNG.randint(-1, 1)))
    for _m in members:
        _nx = _m.pos.x + _dx
        _ny = _m.pos.y + _dy
        if (game_map.is_walkable(_nx, _ny)
                and game_map.blocking_entity_at(_nx, _ny, exclude=_m) is None):
            _m.pos = world.Position(_nx, _ny)
    return True


def _despawn_merchant(ctx, game_map, system, leader, members, target_goal) -> None:
    """Merchant arrival: log jump/dock, flash, remove entities and
    the spawn records."""
    _body_type, _body_name = target_goal[2], target_goal[3]
    _spec = _spec_of_entity(leader)
    _ship_name = getattr(_spec, 'name', 'Merchant') if _spec else 'Merchant'
    if _body_type == 'gate':
        ctx.log.add(f"{_ship_name} jumps through {_body_name}.")
        ctx.npc_flash_events.append(
            NpcFlashEvent(pos=world.Position(leader.pos.x, leader.pos.y), lifetime=4)
        )
    else:
        ctx.log.add(f"{_ship_name} docks at {_body_name}.")
    for _m in members:
        try:
            game_map.entities.remove(_m)
        except ValueError:
            pass
    _sid = leader.procedural_squad_id
    ctx.npc_targets.pop(_sid, None)
    ctx.npc_paths.pop(_sid, None)
    _sys_id = getattr(system, 'id', '')
    _leader_npc = getattr(leader, 'npc_ship_id', '')
    _positions = {(m.pos.x, m.pos.y) for m in members}
    if _sys_id in ctx.procedural_spawns:
        ctx.procedural_spawns[_sys_id] = [
            _ps for _ps in ctx.procedural_spawns[_sys_id]
            if not (_ps.npc_id == _leader_npc
                    and (_ps.pos.x, _ps.pos.y) in _positions)
        ]


def _store_target_path(ctx, game_map, sid, leader, target, aggro) -> None:
    """Remember the target and (re)compute the A* path: aggro squads
    throttle — far ships drift, near ships recompute ~33%/tick."""
    ctx.npc_targets[sid] = target
    _lx, _ly = leader.pos.x, leader.pos.y
    if aggro:
        _dist = math.hypot(
            _lx - ctx.player.pos.x, _ly - ctx.player.pos.y,
        )
        if _dist > 50:
            ctx.npc_paths[sid] = []  # drift mode
        elif _engine.RNG.random() < 0.33:
            ctx.npc_paths[sid] = world.find_path(
                (_lx, _ly), {target}, game_map, exclude_entity=leader,
            ) or []
    elif ctx.npc_paths.get(sid) is None:
        ctx.npc_paths[sid] = world.find_path(
            (_lx, _ly), {target}, game_map, exclude_entity=leader,
        ) or []


def _step_squad(ctx, game_map, sid, members, aggro) -> None:
    """The squad's movement for this tick (80% chance): follow the
    stored path, drift when aggro has no path, keep cohesion."""
    _leader = members[0]
    _lx, _ly = _leader.pos.x, _leader.pos.y
    if _engine.RNG.random() >= 0.8:
        return
    _path = ctx.npc_paths.get(sid)
    if (not _path and aggro and ctx.npc_targets.get(sid) is not None):
        _drift_leader_toward(ctx, game_map, _leader, ctx.npc_targets[sid])
        return
    if not _path:
        ctx.npc_targets.pop(sid, None)
        ctx.npc_paths.pop(sid, None)
        return
    _next = _path[0]
    _dx = _next[0] - _lx
    _dy = _next[1] - _ly
    if abs(_dx) > 1 or abs(_dy) > 1:
        ctx.npc_paths.pop(sid, None)
        return
    _leader_moved = False
    _start = {id(_m): _m.pos for _m in members}
    for _m in members:
        _direct = world.try_step_with_slip(_m, game_map, _dx, _dy)
        if _m is _leader and _direct:
            _leader_moved = True
    if _leader_moved:
        ctx.npc_paths[sid].pop(0)
    # On collision the path is kept so the leader retries the same
    # step next tick — a temporarily occupied cell doesn't invalidate
    # the A* result.
    if len(members) > 1:
        _regroup_stragglers(game_map, members, _start)


def _drift_leader_toward(ctx, game_map, leader, target) -> None:
    """One-axis step toward the target (aggro ships with no path)."""
    _lx, _ly = leader.pos.x, leader.pos.y
    _dx = 1 if _lx < target[0] else -1 if _lx > target[0] else 0
    _dy = 1 if _ly < target[1] else -1 if _ly > target[1] else 0
    if _dx != 0 and _dy != 0:
        if _engine.RNG.random() < 0.5:
            _dy = 0
        else:
            _dx = 0
    _nx = _lx + _dx
    _ny = _ly + _dy
    if (game_map.is_walkable(_nx, _ny)
            and game_map.blocking_entity_at(_nx, _ny, exclude=leader) is None):
        leader.pos = world.Position(_nx, _ny)


def _regroup_stragglers(game_map, members, start_positions) -> None:
    """Cohesion: one-cell step toward the squad centre for stuck
    members only. Never yank a member that just moved — that fights
    the patrol and freezes the whole pack (the tau_ceti save bug)."""
    _cx = sum(m.pos.x for m in members) // len(members)
    _cy = sum(m.pos.y for m in members) // len(members)
    for _m in members:
        if (_m.pos == start_positions[id(_m)]
                and max(abs(_m.pos.x - _cx), abs(_m.pos.y - _cy)) > 4):
            _dx = 1 if _m.pos.x < _cx else -1 if _m.pos.x > _cx else 0
            _dy = 1 if _m.pos.y < _cy else -1 if _m.pos.y > _cy else 0
            world.try_step_with_slip(_m, game_map, _dx, _dy)

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
    console: FrameBuffer,
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
        # Lifetime decays every frame regardless of viewport; events
        # off-screen just aren't drawn (they may scroll into view).
        _ev.lifetime -= 1
        if _ev.lifetime <= 0:
            continue
        _sx = _ev.pos.x - cam_x
        _sy = _ev.pos.y - cam_y
        if 0 <= _sx < view_w and 0 <= _sy < view_h:
            _paint_flash_rings(console, _sx, _sy, _ev, view_w, view_h)
        _active.append(_ev)

    ctx.npc_flash_events = _active


def _paint_flash_rings(console, sx, sy, ev, view_w, view_h) -> None:
    """Expanding diamond rings: lifetime counts down (4→1), so more
    rings draw as the flash ages."""
    _rings_to_draw = len(_NPC_FLASH_RINGS) - ev.lifetime + 1
    for _ri in range(_rings_to_draw):
        _r_char, _r_fg = _NPC_FLASH_RINGS[_ri]
        _dist = _ri + 1
        for _dy in range(-_dist, _dist + 1):
            for _dx in range(-_dist, _dist + 1):
                if abs(_dx) + abs(_dy) != _dist:
                    continue
                _px = sx + _dx
                _py = sy + _dy
                if 0 <= _px < view_w and 0 <= _py < view_h:
                    console.print(x=_px, y=_py, string=_r_char, fg=_r_fg)
