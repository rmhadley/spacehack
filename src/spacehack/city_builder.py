"""Generic data-driven city builder for every landable planet.

Phase 5 of the planet-city expansion: one builder path for all cities.
The terrain (river/coast, grid, station, ...) is a layout generator
selected by ``PlanetSpec.city_layout_id`` from data; everything else —
buildings, service entities, interior records, transit stations, and
ambient NPCs — is driven by the spec fields and shared across planets.
Earth's authored river-coast layout is one generator
(``earth_city.build_earth_layout``); every other planet flows through
the generic grid layout below (the former ``load_planet`` fallback,
plus the Phase 2/3 city systems).

Design principles (matching the rest of the project):

* **Data-first** — every knob lives on the :class:`PlanetSpec`: theme,
  buildings, ``transit_stations``, ``interior_layouts``,
  ``city_npc_population``, showroom ships. A desolate moon base and a
  research station operate identically while reading as clearly
  different worlds.
* **One path** — :func:`load_planet` routes every planet through
  :func:`build_city`; there is no per-planet fork in the loader.
* **Layout as data** — ``city_layout_id`` selects the terrain generator;
  the river/coast shape is Earth's authored choice, not a hardcoded
  loader branch.
"""

from __future__ import annotations

from . import city_transit, world
from .data.planets import PlanetSpec


def build_city(spec: PlanetSpec, resolve_npc, resolve_ship) -> world.GameMap:
    """Build the outdoor city for ``spec`` from data + authored assets.

    Dispatches terrain generation by ``spec.city_layout_id``:
    ``\"earth_river_coast\"`` uses Earth's authored river/coast generator
    (``earth_city.build_earth_layout``); any other id (or empty) uses
    the generic grid layout. Every layout then runs the same shared
    tail — transit stations and ambient NPCs — so all landable cities
    operate identically.
    """
    if spec.city_layout_id == "earth_river_coast":
        from .earth_city import build_earth_layout

        game_map = build_earth_layout(spec, resolve_ship)
    else:
        game_map = _build_grid_city(spec, resolve_npc, resolve_ship)
    _finalize_city(game_map, spec)
    return game_map


# ---------------------------------------------------------------------------
# Generic grid layout (the default for non-Earth planets)
# ---------------------------------------------------------------------------


def _grid_theme(spec: PlanetSpec):
    """Return the planet theme, readability-adjusted like the loader does."""
    from .data.planets import _readable_city_theme

    return _readable_city_theme(spec.theme or world.EARTH_THEME)


def _grid_tiles(width: int, height: int, theme) -> list[list[world.Tile]]:
    """Floor grid with perimeter walls (mirrors the legacy loader path)."""
    tiles = [
        [theme.floor for _ in range(width)] for _ in range(height)
    ]
    for x in range(width):
        tiles[0][x] = world.WALL
        tiles[height - 1][x] = world.WALL
    for y in range(height):
        tiles[y][0] = world.WALL
        tiles[y][width - 1] = world.WALL
    return tiles


def _grid_place_buildings(tiles, entities, spec, resolve_npc) -> None:
    """Place every spec building + its occupant via ``world.make_building``."""
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
    """Showroom ships + trade/mech/armory terminals outside the spaceport."""
    entities: list[world.Entity] = []
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        entities.append(world.Entity(
            char=ship_obj.char,
            fg=ship_obj.fg,
            pos=world.Position(x=port.x_lo + off_x, y=port.y_lo + off_y),
            name=f"Ship: {ship_obj.name}",
            ship_id=ship_obj.id,
            width=ship_obj.width,
            height=ship_obj.height,
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
    """Place showroom ships + terminals if the spec has a spaceport."""
    if spec.buildings:
        entities.extend(_grid_port_entities(spec, spec.buildings[0], resolve_ship))


def _grid_landing_pad(tiles, width, height, spec, theme) -> None:
    """Paint landing-pad tiles south of the spaceport for every planet."""
    if not spec.buildings or spec.buildings[0].label != world.SPACEPORT_LABEL:
        return
    port = spec.buildings[0]
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
    """Data-driven building records so interiors work on any planet.

    Mirrors Earth's ``_city_building_records`` shape: one record per
    spec building keyed by label, with the interior layout id from
    ``spec.interior_layouts`` and an entrance on the building's door
    cell (the south wall, or the north wall when ``door_north``).
    """
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
    """Attach the metadata city systems need (transit, interiors)."""
    game_map.city_layout_id = spec.city_layout_id or "grid"
    game_map.city_buildings = _grid_building_records(spec)


def _finalize_city(game_map, spec) -> None:
    """Run the shared tail for every layout: transit stations + citizens."""
    city_transit.place_transit_stations(game_map, spec)
    from . import city_npcs

    city_npcs.place_city_npcs(game_map, spec.city_npc_population)


def _build_grid_city(spec: PlanetSpec, resolve_npc, resolve_ship) -> world.GameMap:
    """Build a generic data-driven grid city for ``spec``.

    This is the former ``load_planet`` fallback (floor grid, buildings,
    port fixtures, legacy outside layout, landing pad) plus the Phase
    2/3 additions: interior building records, transit, and NPCs.
    """
    width, height = spec.width, spec.height
    theme = _grid_theme(spec)
    tiles = _grid_tiles(width, height, theme)
    entities: list[world.Entity] = []
    _grid_place_buildings(tiles, entities, spec, resolve_npc)
    _grid_port_fixtures(entities, spec, resolve_ship)
    world._layout_outside(tiles, width, height, spec.buildings, theme=theme)
    _grid_landing_pad(tiles, width, height, spec, theme)
    game_map = world.GameMap(
        width=width, height=height,
        tiles=tiles, entities=entities,
    )
    _set_grid_metadata(game_map, spec)
    return game_map


__all__ = ["build_city"]
