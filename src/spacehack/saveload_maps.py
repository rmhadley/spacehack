"""Map (de)serialization helpers for the save/load system.

Houses the dungeon-map serialization (shared by the active dungeon and the
persistent ``ctx.interiors`` cache) plus the space/dungeon/city map rebuild
used when Continue reconstructs a run. Split out of :mod:`spacehack.saveload`
to keep that module within its architecture budget.
"""

from __future__ import annotations

from typing import NamedTuple

from . import ship as ship_module
from . import world

# Backward-compat fallback for old saves that stored kind strings.
_TILE_FROM_KIND: dict[str, world.Tile] = {
    "dungeon_wall": world.DUNGEON_WALL,
    "dungeon_floor": world.DUNGEON_FLOOR,
    "dungeon_door": world.DUNGEON_DOOR,
    "void": world.VOID,
    "airlock": world.AIRLOCK,
    "breach": world.BREACH,
    "cockpit": world.COCKPIT,
    "engine": world.ENGINE_TILE,
    "debris": world.DEBRIS,
    "exit": world.EXIT,
    "stairs_down": world.STAIRS_DOWN,
    "stairs_up": world.STAIRS_UP,
    "hull_wall": world.HULL_WALL,
}


class _RebuiltMap(NamedTuple):
    """Result of :func:`rebuild_game_map` for the active save mode."""

    game_map: world.GameMap
    player_ent: world.Entity
    mode: str
    city_id: str
    system_id: str
    space_map: world.GameMap | None
    space_player: world.Entity | None


def _coordinate_pair(raw) -> tuple[int, int] | None:
    """Return a valid integer coordinate pair, or ``None`` for bad data."""
    if hasattr(raw, "x") and hasattr(raw, "y"):
        _raw_pair = (raw.x, raw.y)
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        _raw_pair = (raw[0], raw[1])
    else:
        return None
    try:
        return int(_raw_pair[0]), int(_raw_pair[1])
    except (TypeError, ValueError):
        return None


def _position_list(value) -> list[int] | None:
    """Serialize a Position to ``[x, y]``, or ``None`` when absent/None."""
    if value is None:
        return None
    return [value.x, value.y]


def _entity_to_dict(e) -> dict:
    """Serialize one dungeon entity to a JSON-safe dict."""
    return {
        "char": e.char,
        "fg_r": e.fg[0], "fg_g": e.fg[1], "fg_b": e.fg[2],
        "x": e.pos.x, "y": e.pos.y,
        "name": e.name,
        "loot_data": e.loot_data,
        "computer_terminal": e.computer_terminal,
        "main_quest_console": bool(getattr(e, 'main_quest_console', False)),
        "npc_char_id": e.npc_char_id,
        "npc_id": getattr(e, 'npc_id', ''),
        "squad_id": getattr(e, 'squad_id', ''),
        "hp": getattr(e, 'hp', 0),
        "guard_post": _position_list(getattr(e, 'guard_post', None)),
        "heist_mission": bool(getattr(e, 'heist_mission', False)),
        "heist_mission_id": getattr(e, 'heist_mission_id', None),
        "main_quest_door": bool(getattr(e, 'main_quest_door', False)),
        # Quest cache / salvage loot (delve/salvage objectives): the
        # main-quest step id whose completion this loot triggers. Lives in
        # dungeon interiors (persisted here).
        "main_quest_step_id": getattr(e, 'main_quest_step_id', ''),
        "dungeon_interaction": getattr(e, 'dungeon_interaction', ''),
        "interaction_flavor": getattr(e, 'interaction_flavor', ''),
        "last_seen_pos": _position_list(getattr(e, 'last_seen_pos', None)),
        "last_seen_ticks": getattr(e, 'last_seen_ticks', 0),
        "blocked_message": getattr(e, 'blocked_message', "You bump into {name}."),
    }


def _anchor_positions(gm) -> dict:
    """Serialize the dungeon's spawn/stair anchor Positions."""
    return {
        "entry_spawn": _position_list(getattr(gm, "entry_spawn", None)),
        "up_stair_pos": _position_list(getattr(gm, "up_stair_pos", None)),
        "down_stair_pos": _position_list(getattr(gm, "down_stair_pos", None)),
        "mars_stairs_pos": _position_list(getattr(gm, "mars_stairs_pos", None)),
    }


def _landmark_interaction_cells(gm) -> list[list[int]]:
    """Serialize landmark interaction cells as integer pairs."""
    cells = []
    for cell in getattr(gm, "landmark_interaction_cells", ()):
        pair = _coordinate_pair(cell)
        if pair is not None:
            cells.append([pair[0], pair[1]])
    return cells


def _tiles_to_dict(gm) -> list:
    """Serialize the dungeon tile grid."""
    return [[{
        "kind": c.kind, "char": c.char, "walkable": c.walkable,
        "fg": list(c.fg), "bg": list(c.bg), "bg_override": c.bg_override,
        "blocked_message": c.blocked_message,
    } for c in row] for row in gm.tiles]


def _activation_positions_to_dict(gm) -> dict:
    """Serialize activation positions (event_id -> [x, y])."""
    return {
        str(event_id): [point.x, point.y]
        for event_id, point in getattr(gm, 'activation_positions', {}).items()
    }


def _autoexplore_memory_to_dict(gm) -> list[list[int]]:
    """Serialize remembered auto-explore cells in stable map order."""
    return [
        [int(_x), int(_y)]
        for _x, _y in sorted(getattr(gm, "autoexplore_ignored", set()))
    ]


def _optional_map_fields(gm) -> dict:
    """Serialize optional dungeon, landmark, and city-interior metadata."""
    return {
        "wreck_spawn_id": getattr(gm, 'wreck_spawn_id', None),
        "extension_id": getattr(gm, 'extension_id', ''),
        "extension_floor": getattr(gm, 'extension_floor', 0),
        "feature_theme": getattr(gm, 'feature_theme', ''),
        "activation_positions": _activation_positions_to_dict(gm),
        "autoexplore_ignored": _autoexplore_memory_to_dict(gm),
        "extension_entry_id": getattr(gm, 'extension_entry_id', ''),
        "interior_cache_key": getattr(gm, 'interior_cache_key', ''),
        "city_interior_id": getattr(gm, 'city_interior_id', ''),
        "city_building_label": getattr(gm, 'city_building_label', ''),
        "city_parent_door": list(getattr(gm, 'city_parent_door', ()) or ()),
        "landmark_footprint": [
            [int(x), int(y)] for x, y in getattr(gm, 'landmark_footprint', set())
        ],
        "landmark_interaction_cells": _landmark_interaction_cells(gm),
        "landmark_variant_id": getattr(gm, 'landmark_variant_id', ''),
    }


def _dungeon_to_dict(gm, space_player_pos: tuple[int, int] | None) -> dict:
    """Serialize a dungeon :class:`world.GameMap` to a JSON-safe dict."""
    return {
        "width": gm.width,
        "height": gm.height,
        "tiles": _tiles_to_dict(gm),
        "entities": [
            _entity_to_dict(e) for e in gm.entities if e.char != '@'
        ],
        "seen": gm.seen,
        "sight_radius": gm.sight_radius,
        "power_restored": getattr(gm, 'power_restored', False),
        "space_player_x": space_player_pos[0] if space_player_pos else 0,
        "space_player_y": space_player_pos[1] if space_player_pos else 0,
        "location_name": getattr(gm, 'location_name', ''),
        **_optional_map_fields(gm),
        **_anchor_positions(gm),
    }


def _tile_from_dict(t) -> world.Tile:
    """Rebuild one dungeon tile from a kind string or full tile dict."""
    if isinstance(t, str):
        return _TILE_FROM_KIND.get(t, world.VOID)
    return world.Tile(
        kind=t.get("kind", "void"),
        char=t.get("char", " "),
        walkable=t.get("walkable", False),
        fg=tuple(t.get("fg", [0, 0, 0])),
        bg=tuple(t.get("bg", [0, 0, 0])),
        bg_override=t.get("bg_override", False),
        blocked_message=t.get("blocked_message", "A wall blocks your path."),
    )


def _parse_dungeon_tiles(dd: dict) -> list[list[world.Tile]]:
    """Rebuild the dungeon tile grid from serialized rows."""
    return [
        [_tile_from_dict(t) for t in row]
        for row in dd.get("tiles", [["void"]])
    ]


def _build_entity_base(ed: dict) -> world.Entity:
    """Build the core :class:`world.Entity` from a serialized dict."""
    return world.Entity(
        char=ed.get("char", "?"),
        fg=(ed.get("fg_r", 255), ed.get("fg_g", 255), ed.get("fg_b", 255)),
        pos=world.Position(ed.get("x", 0), ed.get("y", 0)),
        name=ed.get("name", ""),
        width=1, height=1,
        loot_data=ed.get("loot_data"),
        computer_terminal=ed.get("computer_terminal", False),
        main_quest_console=ed.get("main_quest_console", False),
        npc_char_id=ed.get("npc_char_id", ""),
        npc_id=ed.get("npc_id", ""),
        squad_id=ed.get("squad_id", ""),
        hp=ed.get("hp", 0),
        blocked_message=ed.get("blocked_message", "You bump into {name}."),
    )


def _entity_from_dict(ed: dict) -> world.Entity:
    """Rebuild one dungeon entity, restoring its optional flags."""
    e = _build_entity_base(ed)
    _gp = ed.get("guard_post")
    if isinstance(_gp, (list, tuple)) and len(_gp) >= 2:
        # Guard leash anchor (LOS aggro): preserved across save/load so a
        # guard re-engaging after Continue defends its ORIGINAL post.
        e.guard_post = world.Position(int(_gp[0]), int(_gp[1]))
    if ed.get("heist_mission", False):
        e.heist_mission = True
    _hmid = ed.get("heist_mission_id")
    if _hmid:
        e.heist_mission_id = _hmid
    if ed.get("main_quest_door", False):
        e.main_quest_door = True
    _qsid = ed.get("main_quest_step_id")
    if _qsid:
        e.main_quest_step_id = _qsid
    _interaction = ed.get("dungeon_interaction", "")
    if _interaction:
        e.dungeon_interaction = str(_interaction)
    _flavor = ed.get("interaction_flavor", "")
    if _flavor:
        e.interaction_flavor = str(_flavor)
    _last_seen = ed.get("last_seen_pos")
    _last_seen_pair = _coordinate_pair(_last_seen)
    try:
        _last_seen_ticks = max(0, int(ed.get("last_seen_ticks", 0)))
    except (TypeError, ValueError):
        _last_seen_ticks = 0
    if _last_seen_pair is not None and _last_seen_ticks > 0:
        e.last_seen_pos = world.Position(*_last_seen_pair)
        e.last_seen_ticks = _last_seen_ticks
    return e


def _set_position_attr(dungeon_map: world.GameMap, dd: dict, key: str, attr: str) -> None:
    """Set a Position attribute from a ``[x, y]`` list, when present."""
    raw = dd.get(key)
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        setattr(dungeon_map, attr, world.Position(int(raw[0]), int(raw[1])))


def _apply_extension_attributes(dungeon_map: world.GameMap, dd: dict) -> None:
    """Restore extension/landmark attributes from a serialized dict."""
    _extension_id = dd.get("extension_id", "")
    if _extension_id:
        dungeon_map.extension_id = _extension_id
    _extension_floor = dd.get("extension_floor", 0)
    if _extension_floor:
        dungeon_map.extension_floor = int(_extension_floor)
    _feature_theme = dd.get("feature_theme", "")
    if _feature_theme:
        dungeon_map.feature_theme = str(_feature_theme)
    _activation_positions = dd.get("activation_positions", {}) or {}
    if _activation_positions:
        dungeon_map.activation_positions = {
            str(_event_id): world.Position(int(_point[0]), int(_point[1]))
            for _event_id, _point in _activation_positions.items()
            if isinstance(_point, (list, tuple)) and len(_point) >= 2
        }
    _extension_entry_id = dd.get("extension_entry_id", "")
    if _extension_entry_id:
        dungeon_map.extension_entry_id = str(_extension_entry_id)
    _interior_cache_key = dd.get("interior_cache_key", "")
    if _interior_cache_key:
        dungeon_map.interior_cache_key = str(_interior_cache_key)
    _city_interior_id = dd.get("city_interior_id", "")
    if _city_interior_id:
        dungeon_map.city_interior_id = str(_city_interior_id)
        dungeon_map.city_building_label = str(dd.get("city_building_label", ""))
        _parent_door = dd.get("city_parent_door", [])
        if isinstance(_parent_door, (list, tuple)) and len(_parent_door) >= 2:
            dungeon_map.city_parent_door = (int(_parent_door[0]), int(_parent_door[1]))
    _restore_landmark_fields(dungeon_map, dd)


def _restore_landmark_fields(dungeon_map: world.GameMap, dd: dict) -> None:
    """Restore landmark footprint, interaction cells, and variant id."""
    footprint = dd.get("landmark_footprint", []) or []
    if footprint:
        dungeon_map.landmark_footprint = {
            (int(point[0]), int(point[1]))
            for point in footprint
            if isinstance(point, (list, tuple)) and len(point) >= 2
        }
    interaction_cells = set()
    for point in dd.get("landmark_interaction_cells", []) or []:
        pair = _coordinate_pair(point)
        if pair is not None:
            interaction_cells.add(pair)
    if interaction_cells:
        dungeon_map.landmark_interaction_cells = interaction_cells
    variant_id = dd.get("landmark_variant_id", "")
    if variant_id:
        dungeon_map.landmark_variant_id = str(variant_id)


def _restore_autoexplore_memory(dungeon_map: world.GameMap, dd: dict) -> None:
    """Restore valid remembered auto-explore coordinates from a save."""
    _memory = set()
    for _point in dd.get("autoexplore_ignored", []) or []:
        if not isinstance(_point, (list, tuple)) or len(_point) < 2:
            continue
        try:
            _x, _y = int(_point[0]), int(_point[1])
        except (TypeError, ValueError):
            continue
        if dungeon_map.in_bounds(_x, _y):
            _memory.add((_x, _y))
    dungeon_map.autoexplore_ignored = _memory


def _apply_dungeon_attributes(dungeon_map: world.GameMap, dd: dict) -> None:
    """Restore optional dungeon-map attributes from a serialized dict."""
    dungeon_map.seen = dd.get("seen")
    dungeon_map.sight_radius = dd.get("sight_radius", 8)
    _restore_autoexplore_memory(dungeon_map, dd)
    dungeon_map.location_name = dd.get("location_name", "")
    if dd.get("power_restored", False):
        dungeon_map.power_restored = True
    _wsid = dd.get("wreck_spawn_id")
    if _wsid:
        dungeon_map.wreck_spawn_id = _wsid
    _set_position_attr(dungeon_map, dd, "entry_spawn", "entry_spawn")
    _set_position_attr(dungeon_map, dd, "up_stair_pos", "up_stair_pos")
    _set_position_attr(dungeon_map, dd, "down_stair_pos", "down_stair_pos")
    _set_position_attr(dungeon_map, dd, "mars_stairs_pos", "mars_stairs_pos")
    _apply_extension_attributes(dungeon_map, dd)


def _dungeon_from_dict(dd: dict) -> tuple:
    """Rebuild a dungeon :class:`world.GameMap` from a serialized dict.

    Returns ``(game_map, space_player_pos)``. The player entity is NOT
    included (the caller appends a fresh ``@`` at the saved position).
    """
    dungeon_map = world.GameMap(
        width=dd.get("width", 1),
        height=dd.get("height", 1),
        tiles=_parse_dungeon_tiles(dd),
        entities=[_entity_from_dict(ed) for ed in dd.get("entities", [])],
    )
    _apply_dungeon_attributes(dungeon_map, dd)
    space_pos = (dd.get("space_player_x", 0), dd.get("space_player_y", 0))
    return dungeon_map, space_pos


# ---------------------------------------------------------------------------
# Map rebuild (used by saveload.load_game)
# ---------------------------------------------------------------------------


def _make_ship_entity(owned_ship, pos: world.Position) -> world.Entity:
    """Build the player's owned-ship entity at ``pos``."""
    ship_spec = ship_module.find_ship(owned_ship.ship_id)
    return world.Entity(
        char=ship_spec.char, fg=ship_spec.fg,
        pos=pos,
        name=f"Your Ship: {ship_module.ship_display_name(owned_ship)}",
        ship_id=owned_ship.ship_id, owned=True,
    )


def _make_walker_entity(pos: world.Position) -> world.Entity:
    """Build the bare on-foot player entity at ``pos``."""
    return world.Entity(
        char='@', fg=(255, 255, 255),
        pos=pos, name='Player',
    )


def _add_bounty_npcs(game_map, spawns, find_npc) -> None:
    """Place saved bounty NPCs onto ``game_map``, restoring combat linkage."""
    for bs in spawns:
        try:
            espec = find_npc(bs.enemy_id)
        except (KeyError, ImportError):
            continue
        display_name = bs.bounty_target_name or espec.name
        ent = world.Entity(
            char=espec.char, fg=espec.fg,
            pos=bs.pos, name=display_name,
            width=1, height=1,
            npc_ship_id=bs.enemy_id,
        )
        if bs.salvage_wreck:
            # Non-combatant mission wreck: boardable, persists until the
            # component is secured. No bounty_spawn_id (never auto-completes).
            ent.salvage_wreck_spawn_id = bs.spawn_id
            game_map.entities.append(ent)
            continue
        if not bs.squad_group_id:
            ent.bounty_spawn_id = bs.spawn_id
            # Restore intercept linkage so on_kill still drops the mission
            # loot after a save/quit/continue (mirrors navigation.py).
            if bs.heist_spawn_id is not None:
                ent.heist_spawn_id = bs.heist_spawn_id
        # Squad linkage for comms Attack (mirrors navigation.py).
        ent.bounty_squad_id = bs.squad_group_id or bs.spawn_id
        # Restore auto-hail range on all members too (mirrors navigation.py).
        ent.bounty_comms_range = bs.comms_warning_range
        game_map.entities.append(ent)


def _add_procedural_npcs(game_map, spawns, system_id, mid_map, find_npc) -> None:
    """Place saved procedural NPCs, restoring their movement IDs."""
    for i, ps in enumerate(spawns):
        try:
            espec = find_npc(ps.npc_id)
        except (KeyError, ImportError):
            continue
        saved_mids = mid_map.get(system_id, [])
        mid = (saved_mids[i] if i < len(saved_mids) and saved_mids[i]
               else ps.squad_id
               or f"proc_loaded_{system_id}_{ps.npc_id}_{i}")
        ent = world.Entity(
            char=espec.char, fg=espec.fg,
            pos=ps.pos, name=espec.name,
            width=1, height=1,
            npc_ship_id=ps.npc_id,
        )
        # Stationary ships (base_speed=0, e.g. derelicts) don't get
        # procedural_squad_id so move_npcs ignores them.
        if getattr(espec, 'base_speed', 0) > 0:
            ent.procedural_squad_id = mid
        game_map.entities.append(ent)


def _build_space_map(
    system_id, log, owned_ship, bounty_spawns, proc_spawns, proc_mid_map,
    pos_x, pos_y,
):
    """Build the space map with NPCs and the player entity, or None."""
    from . import solar_system as solar_system_module
    from .data.npc_ships import find_npc_ship as _find_npc
    from .data.solar_systems import find_solar_system as _find_sys

    try:
        sys_spec = _find_sys(system_id)
    except KeyError:
        log.add(f"Save references unknown system '{system_id}' - loading Earth city.")
        return None
    game_map = solar_system_module.make_solar_system(system=sys_spec)
    solar_system_module.current_solar_system_id = system_id
    _add_bounty_npcs(game_map, bounty_spawns.get(system_id, []), _find_npc)
    _add_procedural_npcs(
        game_map, proc_spawns.get(system_id, []), system_id, proc_mid_map, _find_npc,
    )
    pos = world.Position(pos_x, pos_y)
    player_ent = (
        _make_ship_entity(owned_ship, pos)
        if owned_ship is not None else _make_walker_entity(pos)
    )
    game_map.entities.append(player_ent)
    return game_map, player_ent


def _rebuild_space(
    system_id, log, owned_ship, bounty_spawns, proc_spawns, proc_mid_map,
    pos_x, pos_y, city_id,
):
    """Rebuild the space map; returns None when the system id is unknown."""
    built = _build_space_map(
        system_id, log, owned_ship, bounty_spawns, proc_spawns, proc_mid_map,
        pos_x, pos_y,
    )
    if built is None:
        return None
    game_map, player_ent = built
    return _RebuiltMap(game_map, player_ent, "space", city_id, system_id, None, None)


def _rebuild_dungeon(
    data, system_id, log, owned_ship, bounty_spawns, proc_spawns, proc_mid_map,
    pos_x, pos_y, city_id,
):
    """Rebuild the space map + dungeon; returns None when unusable."""
    dd = data.get("dungeon", {})
    if not dd:
        log.add("Dungeon save data missing - loading Earth city.")
        return None
    built = _build_space_map(
        system_id, log, owned_ship, bounty_spawns, proc_spawns, proc_mid_map,
        dd.get("space_player_x", pos_x), dd.get("space_player_y", pos_y),
    )
    if built is None:
        return None
    space_map, space_player = built
    dungeon_map, _ = _dungeon_from_dict(dd)
    dungeon_player = _make_walker_entity(world.Position(pos_x, pos_y))
    dungeon_map.entities.append(dungeon_player)
    return _RebuiltMap(
        dungeon_map, dungeon_player, "dungeon", city_id, system_id,
        space_map, space_player,
    )


def _rebuild_city(system_id, log, owned_ship, pos_x, pos_y, city_id):
    """Rebuild the planet city map for the saved city id."""
    from . import solar_system as solar_system_module
    from .data.planets import hangar_anchor as _planet_anchor
    from .data.planets import load_planet as planets_load_planet
    from .data.solar_systems import find_solar_system as _find_sys

    # Restore module-level current-system state (save/load contract — the
    # space and dungeon branches both restore it; without this a city save on
    # a non-Sol planet would rebuild the WRONG system on launch). Fall back to
    # Earth city on an unknown system, mirroring the other branches.
    try:
        _find_sys(system_id)
    except KeyError:
        log.add(f"Save references unknown system '{system_id}' - loading Earth city.")
        city_id = "earth"
        system_id = "sol"
    solar_system_module.current_solar_system_id = system_id

    game_map = planets_load_planet(city_id)
    player_ent = _make_walker_entity(world.Position(pos_x, pos_y))
    game_map.entities.append(player_ent)
    if owned_ship is not None:
        hangar = _make_ship_entity(owned_ship, _planet_anchor(city_id))
        game_map.entities.append(hangar)
    return _RebuiltMap(game_map, player_ent, "city", city_id, system_id, None, None)


def rebuild_game_map(
    data,
    *,
    owned_ship,
    log,
    pos_x,
    pos_y,
    mode,
    city_id,
    system_id,
    bounty_spawns,
    proc_spawns,
    proc_mid_map,
) -> _RebuiltMap:
    """Rebuild the active map for the saved mode.

    Falls back to Earth city when the saved system id or dungeon data is
    unusable (matching the log messages the legacy inline code emitted).
    """
    if mode == "space":
        result = _rebuild_space(
            system_id, log, owned_ship, bounty_spawns, proc_spawns, proc_mid_map,
            pos_x, pos_y, city_id,
        )
        if result is not None:
            return result
        city_id = "earth"
    elif mode == "dungeon":
        result = _rebuild_dungeon(
            data, system_id, log, owned_ship, bounty_spawns, proc_spawns,
            proc_mid_map, pos_x, pos_y, city_id,
        )
        if result is not None:
            return result
        city_id = "earth"
    return _rebuild_city(system_id, log, owned_ship, pos_x, pos_y, city_id)
