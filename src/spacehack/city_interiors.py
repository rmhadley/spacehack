"""Entry and exit transitions for authored city interiors."""

from __future__ import annotations

from . import city_landmarks, world


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
        and game_map.tiles[y][x].kind != "exit"
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

    parent_position = getattr(interior, "city_parent_door", None)
    if parent_position is None and record is not None:
        parent_position = record.get("entrance")
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
    state.log.add("You step back outside.")
    return "HANDLED"
