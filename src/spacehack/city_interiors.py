"""Entry and exit transitions for authored city interiors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import city_landmarks, world

if TYPE_CHECKING:
    from .saveload_maps import _RebuiltMap


def _building_record(game_map: world.GameMap, position: world.Position) -> dict | None:
    """Return the building record whose exterior door is ``position``."""
    for record in getattr(game_map, "city_buildings", {}).values():
        if record.get("entrance") == (position.x, position.y):
            return record
    return None


def _first_interior_npc(game_map: world.GameMap, spawn: world.Position) -> world.Position | None:
    """Choose a clear walkable interior cell for the resident NPC."""
    occupied = {(entity.pos.x, entity.pos.y) for entity in game_map.entities}
    candidates = [
        world.Position(x, y)
        for y in range(1, game_map.height - 1)
        for x in range(1, game_map.width - 1)
        if game_map.tiles[y][x].walkable
        and (x, y) not in occupied
        and (x, y) != (spawn.x, spawn.y)
        and game_map.tiles[y][x].kind not in ("exit", "showroom_berth")
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda point: abs(point.x - game_map.width // 2)
        + abs(point.y - game_map.height // 2),
    )


def _seat_building_npc(game_map: world.GameMap, record: dict) -> None:
    """Place the building's service NPC inside its authored interior."""
    npc_id = record.get("npc_id", "")
    if not npc_id:
        return
    override = record.get("npc_override")
    if override is not None:
        npc = override
    else:
        from .data.npcs import find_npc
        npc = find_npc(npc_id)
    spawn = getattr(game_map, "entry_spawn", None)
    position = _first_interior_npc(game_map, spawn) if spawn is not None else None
    if position is None:
        return
    game_map.entities.append(world.Entity(
        char=npc.char, fg=npc.fg, pos=position,
        name=npc.name, npc_id=npc.id, width=1, height=1,
    ))


def _seat_service_npcs(ctx, game_map: world.GameMap, record: dict) -> None:
    """Seat the building's always-on service NPCs (doc 40 phase 5).

    The unconditional sibling of the quest seater: additive beside the
    resident, idempotent on cache hits, data-driven by the planet's
    ``service_npc_spots``."""
    from .data.npcs import find_npc
    from .data.planets import find_planet_spec

    label = record.get("label", "")
    planet_id = getattr(ctx, "current_city_id", "")
    if not planet_id or not label:
        return
    try:
        spec = find_planet_spec(planet_id)
    except KeyError:
        return
    for npc_id, spot_label in getattr(spec, "service_npc_spots", ()):
        if spot_label != label:
            continue
        if any(getattr(_e, "npc_id", "") == npc_id for _e in game_map.entities):
            continue
        spawn = getattr(game_map, "entry_spawn", None)
        position = _first_interior_npc(game_map, spawn) if spawn is not None else None
        if position is None:
            ctx.log.add(f"[SERVICE NPC] {npc_id} has no clear cell in {label}.")
            continue
        npc = find_npc(npc_id)
        game_map.entities.append(world.Entity(
            char=npc.char, fg=npc.fg, pos=position,
            name=npc.name, npc_id=npc.id, width=1, height=1,
        ))


def _seat_showroom_displays(ctx, game_map: world.GameMap) -> None:
    """Seat the city's showroom displays on every interior entry (doc 45).

    The kit helper owns the seating; this adapter resolves the current
    city's spec and the ownership filter. Berth presence gates the
    helper, so non-spaceport interiors are a no-op.
    """
    from .city_kit import seat_showroom_ships
    from .data.planets import find_planet_spec

    planet_id = getattr(ctx, "current_city_id", "")
    if not planet_id:
        return
    try:
        spec = find_planet_spec(planet_id)
    except KeyError:
        return
    owned = getattr(ctx, "player_owned_ship", None)
    seat_showroom_ships(
        game_map, spec, owned.ship_id if owned is not None else None,
    )


def _remove_player(game_map: world.GameMap) -> None:
    """Remove transient player entities before reusing a cached map."""
    game_map.entities[:] = [entity for entity in game_map.entities if entity.char != "@"]


def _interior_for_record(ctx, record: dict) -> tuple[world.GameMap, world.Position]:
    """Load or retrieve one cached authored interior."""
    cache_key = record["cache_key"]
    game_map = ctx.interiors.get(cache_key)
    if game_map is None:
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        game_map = asset.game_map
        game_map.city_interior_id = cache_key
        game_map.interior_cache_key = cache_key
        game_map.city_building_label = record["label"]
        game_map.city_parent_door = record["entrance"]
        game_map.location_name = record["display_name"]
        ctx.interiors[cache_key] = game_map
        _seat_building_npc(game_map, record)
    # Live quest NPCs stand beside the resident (idempotent on cache hits;
    # interiors are deterministic-authored, so completed steps stop seating).
    from .main_quest import seat_quest_npcs_in_interior as _seat_quest
    _seat_quest(ctx, game_map, record)
    _seat_service_npcs(ctx, game_map, record)
    # Showroom displays re-seat on EVERY entry: ownership can change
    # between visits, and the helper strips before seating (idempotent).
    _seat_showroom_displays(ctx, game_map)
    spawn = getattr(game_map, "entry_spawn", None)
    if spawn is None:
        raise ValueError(f"City interior {cache_key!r} has no entry spawn")
    _remove_player(game_map)
    return game_map, spawn


def _install_interior_state(state, parent_map, interior, spawn, record):
    """Install the player and parent-map links for an active room."""
    parent_player = state.player
    if parent_player in parent_map.entities:
        parent_map.entities.remove(parent_player)
    interior_player = world.Entity("@", parent_player.fg, spawn, name="Player")
    interior.entities.append(interior_player)
    interior.city_parent_map = parent_map
    interior.city_parent_player = parent_player
    state.city_game_map = parent_map
    state.city_player = parent_player
    state.game_map = interior
    state.player = interior_player
    state.current_mode = "dungeon"
    state.ctx.game_map = interior
    state.ctx.player = interior_player


def enter_city_interior(state) -> str:
    """Enter the city building at the player's current exterior door."""
    parent_map = state.game_map
    record = _building_record(parent_map, state.player.pos)
    if record is None or not record.get("interior_layout_id"):
        return "NOT_ENTERED"
    try:
        interior, spawn = _interior_for_record(state.ctx, record)
    except (FileNotFoundError, ValueError):
        state.log.add("The building's interior is not available.")
        return "CONTINUE"
    _install_interior_state(state, parent_map, interior, spawn, record)
    state.log.add(f"You enter the {record['display_name']}.")
    return "ENTERED"


def restore_city_interior_parent(ctx, rebuilt) -> None:
    """Rebuild and attach the exterior city while resuming indoors."""
    interior = rebuilt.game_map
    if not getattr(interior, "city_interior_id", ""):
        return
    from . import ship as ship_module
    from .data.planets import hangar_anchor as _planet_anchor
    from .data.planets import load_planet as _load_planet
    parent = _load_planet(rebuilt.city_id)
    label = getattr(interior, "city_building_label", "")
    record = getattr(parent, "city_buildings", {}).get(label)
    if record is None:
        return
    door = record.get("entrance") or getattr(interior, "city_parent_door", None)
    if door is None:
        return
    parent_player = world.Entity("@", (255, 255, 255), world.Position(*door), name="Player")
    parent.entities.append(parent_player)
    if ctx.player_owned_ship is not None:
        ship_spec = ship_module.find_ship(ctx.player_owned_ship.ship_id)
        parent.entities.append(world.Entity(
            ship_spec.char, ship_spec.fg, _planet_anchor(rebuilt.city_id),
            name=f"Your Ship: {ship_module.ship_display_name(ctx.player_owned_ship)}",
            ship_id=ship_spec.id, owned=True,
        ))
    interior.city_parent_map = parent
    interior.city_parent_player = parent_player
    interior.city_parent_door = tuple(door)


def _ensure_gated_population(state, parent_map) -> None:
    """The gated city population re-check on interior exit (doc 42
    phase 2.5) — the shady tech appears once the chain names him."""
    from .city_npcs import ensure_gated_npcs
    from .data.planets import find_planet_spec
    try:
        ensure_gated_npcs(
            state.ctx, parent_map,
            find_planet_spec(getattr(state, "current_city_id", "")),
        )
    except KeyError:
        pass  # no planet spec — nothing gated to place


def exit_city_interior(state) -> str:
    """Return from a city interior to its exterior entrance."""
    interior = state.game_map
    parent_map = getattr(interior, "city_parent_map", None) or state.city_game_map
    parent_player = getattr(interior, "city_parent_player", None) or state.city_player
    if parent_map is None or parent_player is None:
        return "CONTINUE"

    record = getattr(parent_map, "city_buildings", {}).get(
        getattr(interior, "city_building_label", ""),
    )
    _remove_player(interior)

    parent_position = None
    if record is not None:
        parent_position = record.get("entrance")
    if parent_position is None:
        parent_position = getattr(interior, "city_parent_door", None)
    if parent_position is None:
        parent_position = (parent_player.pos.x, parent_player.pos.y)
    parent_player.pos = world.Position(*parent_position)
    parent_map.entities.append(parent_player)

    state.game_map = parent_map
    state.player = parent_player
    state.city_game_map = parent_map
    state.city_player = parent_player
    state.current_mode = "city"
    state.ctx.game_map = parent_map
    state.ctx.player = parent_player
    _ensure_gated_population(state, parent_map)
    state.log.add("You step back outside.")
    return "HANDLED"


def is_city_interior_key(key) -> bool:
    """True when an interior cache key belongs to a deterministic city room."""
    return str(key).startswith("city:")


def rebuild_active_city_interior(ctx, rebuilt) -> "_RebuiltMap":
    """Swap a serialized city interior for the current authored room.

    City rooms are deterministic assets with no persistent mutable state
    (the seated service NPC re-seats on cache miss), so resuming indoors
    must never pin stale tiles or a stale entry spawn from an older
    save. The player re-enters through the door at the room's current
    entry spawn; a saved in-room position is ephemeral by design
    (exiting already repositions the player at the exterior door).
    """
    from .data.planets import load_planet

    label = getattr(rebuilt.game_map, "city_building_label", "")
    parent = load_planet(rebuilt.city_id)
    record = getattr(parent, "city_buildings", {}).get(label)
    if record is None or not record.get("interior_layout_id"):
        return rebuilt
    interior, spawn = _interior_for_record(ctx, record)
    player = rebuilt.player_ent
    player.pos = world.Position(spawn.x, spawn.y)
    interior.entities.append(player)
    ctx.game_map = interior
    ctx.player = player
    return rebuilt._replace(game_map=interior, player_ent=player)
