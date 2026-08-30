"""Generic data-driven city builder for every landable planet.

Phase 5 of the planet-city expansion: one builder path for all cities.
Design principles:

* **Data-first** — every knob lives on the :class:`PlanetSpec`.
* **One path** — :func:`load_planet` routes every planet through
  :func:`build_city`.
* **Layout as data** — ``city_layout_id`` maps to a (module, function)
  pair in a flat registry dict; any unknown id falls through to the
  generic grid layout.
"""

from __future__ import annotations

from . import city_transit, world
from .data.planets import PlanetSpec


# ----- Layout registry ------------------------------------------------

_LAYOUTS: dict[str, tuple[str, str]] = {
    "earth_river_coast":       ("earth_city",            "build_earth_layout"),
    "mercury_station":         ("mercury_city",          "build_mercury_layout"),
    "mars_colony":             ("mars_city",             "build_mars_layout"),
    "ac_ring_station":         ("ac_station_city",       "build_ac_ring_layout"),
    "eri_canyon_settlement":  ("epsilon_eridani_city",   "build_epsilon_eridani_layout"),
    "wolf_crater_settlement": ("wolf_city",             "build_wolf_layout"),
    "cygni_shipyard_colony":  ("cygni_city",            "build_cygni_layout"),
    "lal_wreck_colony":       ("lal_city",              "build_lal_layout"),
    "barnards_mine_colony":   ("barnards_city",         "build_barnards_layout"),
    "ross_volcanic_settlement": ("ross_city",            "build_ross_layout"),
    "groom_hardpan_boomtown": ("groom_city",            "build_groom_layout"),
    "tc_canopy_clearing":     ("tc_city",               "build_tc_layout"),
    "indi_farmland_grid":     ("indi_city",              "build_indi_layout"),
    "lalc_container_maze":     ("lalc_city",              "build_lalc_layout"),
    "barnards_c_atmo_deck":   ("barnards_c_city",       "build_barnards_c_layout"),
    "ross_c_scrap_ring":      ("ross_c_city",            "build_ross_c_layout"),
    "vega_beacon_station":    ("vega_b_city",            "build_vega_b_layout"),
    "proc_b_crossroads":      ("proc_b_city",            "build_proc_b_layout"),
    "proc_c_ice_campus":      ("proc_c_city",            "build_proc_c_layout"),
    "venus_cloudbreak":       ("venus_city",             "build_venus_layout"),
}


def _dispatch_layout(spec, resolve_ship, resolve_npc):
    """Resolve the layout-id to a builder function and call it."""
    pair = _LAYOUTS.get(spec.city_layout_id or "")
    if pair is None:
        return _build_grid_city(spec, resolve_npc, resolve_ship)
    import importlib
    mod = importlib.import_module(f".{pair[0]}", package="spacehack")
    return getattr(mod, pair[1])(spec, resolve_ship)


def build_city(spec: PlanetSpec, resolve_npc, resolve_ship) -> world.GameMap:
    """Build the outdoor city map for ``spec``."""
    game_map = _dispatch_layout(spec, resolve_ship, resolve_npc)
    _finalize_city(game_map, spec)
    return game_map


# ----- Generic grid layout (fallback) ---------------------------------

def _grid_theme(spec: PlanetSpec):
    from .data.planets import _readable_city_theme
    return _readable_city_theme(spec.theme or world.EARTH_THEME)


def _grid_tiles(width: int, height: int, theme) -> list[list[world.Tile]]:
    tiles = [[theme.floor for _ in range(width)] for _ in range(height)]
    for x in range(width):
        tiles[0][x] = world.WALL
        tiles[height - 1][x] = world.WALL
    for y in range(height):
        tiles[y][0] = world.WALL
        tiles[y][width - 1] = world.WALL
    return tiles


def _grid_place_buildings(tiles, entities, spec, resolve_npc) -> None:
    for building in spec.buildings:
        occupant = resolve_npc(building.npc_id)
        changes, occupants = world.make_building(
            building.label,
            building.x_lo, building.x_hi,
            building.y_lo, building.y_hi,
            door_x=building.door_x,
            occupant=occupant,
            door_north=building.door_north,
        )
        for pos, tile in changes:
            tiles[pos.y][pos.x] = tile
        entities.extend(occupants)


def _grid_port_entities(spec, port, resolve_ship) -> list[world.Entity]:
    entities: list[world.Entity] = []
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(x=port.x_lo + off_x, y=port.y_lo + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))
    _term = world.Position(x=port.door_x + 2, y=port.y_hi + 1)
    entities.append(world.Entity(
        char="=", fg=(100, 220, 255), pos=_term,
        name="Trade Terminal", width=1, height=1, trade_terminal=True,
    ))
    _mech = world.Position(x=port.door_x - 2, y=port.y_hi + 1)
    entities.append(world.Entity(
        char="%", fg=(200, 220, 100), pos=_mech,
        name="Mechanic Terminal", width=1, height=1, mech_terminal=True,
    ))
    _armory = world.Position(x=port.door_x - 5, y=port.y_hi + 1)
    entities.append(world.Entity(
        char="A", fg=(255, 160, 80), pos=_armory,
        name="Armory Terminal", width=1, height=1, armory_terminal=True,
    ))
    return entities


def _grid_port_fixtures(entities, spec, resolve_ship) -> None:
    if spec.buildings:
        entities.extend(_grid_port_entities(spec, spec.buildings[0], resolve_ship))


def _grid_landing_pad(tiles, width, height, spec, theme) -> None:
    if not spec.buildings:
        return
    port = spec.buildings[0]
    if port.label != world.SPACEPORT_LABEL:
        return
    anchor = spec.hangar_anchor
    pad_x_lo = max(1, anchor.x - 3)
    pad_x_hi = min(width - 2, anchor.x + 3)
    pad_y_lo = port.y_hi + 1
    pad_y_hi = min(height - 2, anchor.y + 1)
    pad_tile = theme.landing_pad if theme else world.LANDING_PAD
    for py in range(pad_y_lo, pad_y_hi + 1):
        for px in range(pad_x_lo, pad_x_hi + 1):
            tiles[py][px] = pad_tile


def _grid_building_records(spec: PlanetSpec) -> dict:
    layout_by_label = dict(spec.interior_layouts)
    records = {}
    for building in spec.buildings:
        if building.door_north:
            entrance = (building.door_x, building.y_lo)
        else:
            entrance = (building.door_x, building.y_hi)
        records[building.label] = {
            "label": building.label,
            "display_name": building.label.replace("_", " "),
            "npc_id": building.npc_id,
            "interior_layout_id": layout_by_label.get(building.label, ""),
            "entrance": entrance,
            "cache_key": f"city:{spec.id}:{building.label}",
        }
    return records


def _set_grid_metadata(game_map, spec) -> None:
    game_map.city_layout_id = spec.city_layout_id or "grid"
    game_map.city_buildings = _grid_building_records(spec)


def _finalize_city(game_map, spec) -> None:
    city_transit.place_transit_stations(game_map, spec)
    from . import city_npcs
    city_npcs.place_city_npcs(game_map, spec.city_npc_population)


def _build_grid_city(spec, resolve_npc, resolve_ship) -> world.GameMap:
    width, height = spec.width, spec.height
    theme = _grid_theme(spec)
    tiles = _grid_tiles(width, height, theme)
    entities: list[world.Entity] = []
    _grid_place_buildings(tiles, entities, spec, resolve_npc)
    _grid_port_fixtures(entities, spec, resolve_ship)
    world._layout_outside(tiles, width, height, spec.buildings, theme=theme)
    _grid_landing_pad(tiles, width, height, spec, theme)
    game_map = world.GameMap(width=width, height=height,
                             tiles=tiles, entities=entities)
    _set_grid_metadata(game_map, spec)
    return game_map


__all__ = ["build_city"]