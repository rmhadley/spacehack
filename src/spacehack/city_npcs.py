"""Ambient city NPCs — placement, deterministic movement, and bump interaction.

Ambient NPCs are the streets' pedestrian layer (Phase 3 of the planet-city
expansion). Movement mirrors space NPC traffic: each citizen picks a walkable
pavement destination within its district radius, computes an A* path, and
walks it one cell per city tick — crossing blocks like ships crossing a
system, instead of pacing a tiny box around its anchor.

Design principles (matching the rest of the project):

* **Data-first** — every ambient NPC is a :class:`~spacehack.data.city_npcs.CityNpc`
  catalog entry; this module only places/moves/interacts with them.
* **Deterministic** — destinations come from ``engine.seeded_rng`` keyed on
  ``INIT_SEED`` + city + npc id, so save/load and re-entry never reshuffle
  routes; the current destination persists so a resumed save continues the
  same walk.
* **Reuse** — pathing reuses ``world.find_path`` (the same A* the space and
  ground NPC systems use); hostility reuses ``faction.spec_is_hostile`` via
  the NPC's ``npc_char_id``; direct-contact combat reuses the existing ground
  combat entry point.
* **One step per city tick** — called from the city move/wait handler exactly
  once per accepted action, mirroring ``ground_npcs.move_ground_npcs``.
"""

from __future__ import annotations

from . import world
from .engine import INIT_SEED, seeded_rng
from .data.npc_chars import find_npc_char as _find_npc_char
from .faction import spec_is_hostile as _spec_is_hostile


def is_hostile(ctx, entity: world.Entity) -> bool:
    """True if a city NPC's faction is hostile toward the player."""
    _charid = getattr(entity, "npc_char_id", "")
    if not _charid:
        return False
    try:
        _spec = _find_npc_char(_charid)
    except KeyError:
        return False
    return _spec_is_hostile(ctx, _spec)


def place_city_npcs(game_map: world.GameMap, population) -> None:
    """Place one ambient NPC entity per catalog entry at its anchor.

    Each NPC carries its ``city_npc_id`` and anchor metadata so the
    movement pass keeps it near its district and save/load can identify
    it across rebuilds.
    """
    for template in population:
        try:
            _cspec = _find_npc_char(template.npc_char_id)
        except KeyError:
            continue
        rng = seeded_rng(INIT_SEED, "city_npc", template.id)
        entity = world.Entity(
            char=_cspec.char,
            fg=_cspec.fg,
            pos=world.Position(*template.spawn),
            name=_cspec.name,
            city_npc_id=template.id,
            npc_char_id=template.npc_char_id,
            npc_id=template.npc_id,
            blocked_message=f"You bump into {_cspec.name}.",
        )
        entity.city_spawn = world.Position(*template.spawn)
        entity.city_wander_radius = template.wander_radius
        entity.city_move_chance = template.move_chance
        entity.city_rng = rng
        game_map.entities.append(entity)


_LANDMARK_KINDS = frozenset({
    "city_building_door", "city_plaza", "city_bridge", "landing_pad",
})


def _city_landmarks(
    game_map: world.GameMap,
) -> list[tuple[int, int]]:
    """Walkable landmark cells spread across the whole city.

    The city analogue of space's body goals: transit stops, building
    doors, plaza/bridge/landing-pad tiles. Citizens pick destinations
    from this whole-city set so they traverse between districts like
    ships traverse between planets, instead of circling one block.
    """
    cells: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for _e in game_map.entities:
        if getattr(_e, "transit_station_id", ""):
            _key = (_e.pos.x, _e.pos.y)
            if _key not in seen and game_map.tiles[_e.pos.y][_e.pos.x].walkable:
                seen.add(_key)
                cells.append(_key)
    for y in range(game_map.height):
        for x in range(game_map.width):
            if game_map.tiles[y][x].kind not in _LANDMARK_KINDS:
                continue
            if not game_map.tiles[y][x].walkable:
                continue
            if (x, y) in seen:
                continue
            seen.add((x, y))
            cells.append((x, y))
    return cells


def _pick_destination(
    entity: world.Entity,
    game_map: world.GameMap,
) -> tuple[int, int] | None:
    """Pick a landmark destination, preferring one far from the citizen.

    Mirrors space NPCs picking a body goal: draw from the whole-city
    landmark set (``_city_landmarks``) and prefer a landmark well away
    from the current cell so the walk visibly crosses the city — a ship
    doesn't loop the planet it's parked at, it heads somewhere else.
    ``wander_radius`` caps how far roamers may go from their anchor
    (small radii = district patrol; large radii = city-spanning roam).
    """
    cells = _city_landmarks(game_map)
    if not cells:
        return None
    rng = entity.city_rng
    if rng is None:
        return cells[0]
    _radius = entity.city_wander_radius
    if _radius <= 0:
        return rng.choice(cells)
    _sx, _sy = entity.city_spawn.x, entity.city_spawn.y
    _pool = [
        (x, y) for x, y in cells
        if abs(x - _sx) + abs(y - _sy) <= _radius
    ]
    if not _pool:
        # No landmark in range: fall back to the nearest one so small-
        # radius guards stay local instead of roaming the whole city.
        _pool = [min(cells, key=lambda c: abs(c[0] - _sx) + abs(c[1] - _sy))]
    _cx, _cy = entity.pos.x, entity.pos.y
    _far = [
        (x, y) for x, y in _pool
        if abs(x - _cx) + abs(y - _cy) >= 10
    ] or _pool
    return rng.choice(_far)


def _take_one_step(entity: world.Entity, game_map: world.GameMap) -> None:
    """Move ``entity`` one cell along its current destination path.

    When the citizen has no destination (or reached it), pick a fresh one
    and compute an A* path — exactly how space NPCs pick a new body goal
    on arrival. Walk the cached path one cell; if the next cell is blocked
    the step is skipped and the path is retried next tick (no recompute),
    mirroring the space patrol loop.
    """
    dest = entity.city_dest
    if dest is None:
        dest = _pick_destination(entity, game_map)
        entity.city_dest = dest
    if dest is None:
        return
    path = entity.city_path
    if not path:
        path = world.find_path(
            (entity.pos.x, entity.pos.y), {dest}, game_map,
            exclude_entity=entity,
        ) or []
        entity.city_path = path
    if not path:
        # Unreachable this tick — clear so we repick next tick.
        entity.city_dest = None
        return
    nx, ny = path[0]
    dx, dy = nx - entity.pos.x, ny - entity.pos.y
    if abs(dx) > 1 or abs(dy) > 1:
        entity.city_path = None
        return
    if world.try_step_with_slip(entity, game_map, dx, dy):
        entity.city_path = path[1:]
    if (entity.pos.x, entity.pos.y) == (dest[0], dest[1]):
        entity.city_dest = None
        entity.city_path = None

def run_city_fight(ctx, console, game_map: world.GameMap, hostiles) -> None:
    """Run a direct-contact ground fight vs the engaged hostile citizens.

    Wired from the occupied (bump) dispatch when the player walks into a
    faction-enemy citizen. Reuses the shared ground-combat runtime so the
    encounter plays out with the exact same combat AI as a dungeon fight.
    Hands defeat over to the shared defeat-presentation flow.
    """
    from . import tutorial as _tutorial
    from .combat import _rules_ground as _rg
    from .combat._loop import run_combat as _run_combat
    from .game_flow import _apply_ground_combat_rep as _apply_rep
    _tutorial.maybe_ground_combat_intro(ctx)
    _rg.init(ctx, hostiles, game_map, console=console)
    _result = _run_combat(console, ctx, game_map, _rg)
    _apply_rep(ctx, _result)
    _tutorial.notify_ground_combat_ended(ctx)
    if _result is not None and _result.outcome == 'DEFEAT':
        raise SystemExit()


def save_city_npc_positions(ctx) -> dict:
    """Serialize current ambient city NPC positions by ``city_npc_id``.

    City maps rebuild deterministically on load, so NPC identity and seed
    persist for free; only their in-progress positions and destinations
    need saving (the Phase 3 persistence contract). Called from
    ``saveload.save_game``; the reverse
    (``saveload_maps._restore_city_npc_positions``) reapplies them onto
    the rebuilt city map.
    """
    _positions: dict = {}
    _map = getattr(ctx, "game_map", None)
    if _map is None:
        return _positions
    for _e in getattr(_map, "entities", ()):
        _cid = getattr(_e, "city_npc_id", "")
        if _cid:
            _dest = _e.city_dest
            _positions[_cid] = {
                "pos": [_e.pos.x, _e.pos.y],
                "dest": list(_dest) if _dest is not None else None,
            }
    return _positions


def move_city_npcs(ctx, game_map: world.GameMap) -> None:
    """Advance ambient city NPCs one step (each rolls its move chance once).

    Called once per accepted city action (movement or wait). Each NPC uses
    its own seeded RNG so route choice is deterministic per run. NPCs in an
    active combat encounter (``combat_locked``) are skipped so the combat AI
    owns their position.
    """
    for entity in game_map.entities:
        if not getattr(entity, "city_npc_id", ""):
            continue
        if getattr(entity, "combat_locked", False):
            continue
        if getattr(entity, "city_move_chance", 0) <= 0:
            continue
        rng = entity.city_rng
        if rng.random() >= entity.city_move_chance:
            continue
        _take_one_step(entity, game_map)


__all__ = [
    "place_city_npcs", "move_city_npcs", "is_hostile", "run_city_fight",
    "save_city_npc_positions",
]
