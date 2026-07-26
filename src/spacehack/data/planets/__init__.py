"""Planet specs + a single loader entry point.

Each planet (Earth, Mars, future Jupiter/Saturn etc.) lives in its
own module exporting a :class:`PlanetSpec` instance. The dispatcher in
:mod:`spacehack.__main__` reads a planet id per scene (the
``current_city_id`` slot) and calls :func:`load_planet` to build the
:class:`spacehack.world.GameMap` for that planet.

Per-planet data lives in:

  * :mod:`spacehack.data.planets.earth` (the player's home city)
  * :mod:`spacehack.data.planets.mars`  (humanity's first off-world colony)

Extending to a new planet is a single new module + one entry in
:data:`_PLANETS` - no dispatcher / engine / render code rewrites.
"""
from __future__ import annotations

from dataclasses import dataclass

from ... import world
from ...data import npcs as npc_module


@dataclass(frozen=True)
class PlanetSpec:
    """Static data describing one planet's on-surface city.

    Mirror fields chosen so today's Earth city code can be expressed
    as a literal Python value plus a single loader. New planets get
    a new module exporting their own :class:`PlanetSpec` instance.

    Attributes:
      id:                registry key, e.g. ``"earth"``.
      name:              display name shown to the player.
      char:              glyph rendered on the in-space planet tile.
      fg:                foreground colour for that tile.
      description:       one-line flavour text for the planet menu.
      width / height:    GameMap dimensions (Earth + Mars are both 60x40).
      hangar_anchor:      Position where the player's owned ship docks
                          on this planet (just south of the spaceport).
      buildings:         tuple of :class:`spacehack.world.CityBuilding`.
                          ``npc_id`` per building refers to either the
                          planet-local override map or the global
                          :class:`spacehack.data.npcs.NPCS` catalog.
      showroom_ships:    ``(ship_id, offset_x, offset_y)`` triples
                          placed inside the FIRST building (the
                          spaceport) using the same offsets Earth uses.
      npc_overrides:     ``(npc_id, NPC)`` pairs that REPLACE the
                          global NPC entry on this planet only.
                          Missing ids fall through to the global
                          :data:`spacehack.data.npcs.NPCS` catalog.
    """
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    description: str
    width: int
    height: int
    hangar_anchor: world.Position
    buildings: tuple[world.CityBuilding, ...]
    showroom_ships: tuple[tuple[str, int, int], ...]
    theme: world.PlanetTheme | None = None
    npc_overrides: tuple[tuple[str, npc_module.NPC], ...] = ()


_BY_ID: dict[str, PlanetSpec] | None = None


def _build_registry() -> dict[str, PlanetSpec]:
    from . import earth as earth_module
    from . import mars as mars_module
    from . import ac_station as ac_station_module
    from . import depot as depot_module
    from . import blockade as blockade_module
    return {
        earth_module.SPEC.id: earth_module.SPEC,
        mars_module.SPEC.id: mars_module.SPEC,
        ac_station_module.SPEC.id: ac_station_module.SPEC,
        depot_module.SPEC.id: depot_module.SPEC,
        blockade_module.SPEC.id: blockade_module.SPEC,
    }


def _registry() -> dict[str, PlanetSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_planet_spec(planet_id: str) -> PlanetSpec:
    """Look up a :class:`PlanetSpec` by id; raises :class:`KeyError` on miss.

    Mirrors the look-up-by-id contract used by every other catalog
    so call sites don't have to special-case missing bodies.
    """
    try:
        return _registry()[planet_id]
    except KeyError:
        raise KeyError(f"unknown planet id: {planet_id!r}") from None


def has_landable_port(planet_id: str) -> bool:
    """Return True iff ``planet_id`` resolves to a :class:`PlanetSpec`
    whose :attr:`PlanetSpec.buildings` includes a spaceport-labeled
    building.

    Used by the planet-bump dialog (:func:`spacehack.__main__._run_planet_menu`)
    to decide whether to expose the ``Land`` option, and by the
    cross-planet LAND dispatch in :mod:`spacehack.__main__` to defend
    against a :class:`KeyError` crash if a future code path emits a
    :attr:`PlanetMenuOutcome.LAND` outcome for a planet the registry
    doesn't know about.

    Returns False for:
      - unknown planet ids (catches :class:`KeyError` from
        :func:`find_planet_spec` internally so callers don't have to),
      - known planets whose spec has no spaceport building (Mercury,
        Venus, Jupiter, Saturn, Uranus, Neptune in the current system).

    Returns True when the planet is in the registry AND its
    :attr:`PlanetSpec.buildings` tuple contains at least one entry
    whose :attr:`CityBuilding.label` is :attr:`world.SPACEPORT_LABEL`.
    This is data-driven: any future planet that ships with a
    ``spaceport`` building in its spec automatically gets a True
    return without needing a schema field flip.
    """
    try:
        spec = find_planet_spec(planet_id)
    except KeyError:
        return False
    return any(b.label == world.SPACEPORT_LABEL for b in spec.buildings)


def hangar_anchor(planet_id: str) -> world.Position:
    """Return the position where the player's owned ship docks on ``planet_id``."""
    return find_planet_spec(planet_id).hangar_anchor


def load_planet(planet_id: str) -> world.GameMap:
    """Build the :class:`world.GameMap` for the named planet's on-surface city.

    Shared decorative code (perimeter walls + 4 doors + roads + plaza +
    sidewalks + grass patch) lives in :func:`world.make_city`; this
    loader composes the skeleton with the planet-specific building
    layout, showroom ships, and NPC overrides from the spec.
    """
    spec = find_planet_spec(planet_id)
    width, height = spec.width, spec.height

    theme = spec.theme or world.EARTH_THEME
    tiles: list[list[world.Tile]] = [
        [theme.floor for _ in range(width)] for _ in range(height)
    ]
    # Perimeter walls (all WALL — the 4 perimeter "door" tiles were
    # a traditional-roguelike holdover that served no purpose here).
    for x in range(width):
        tiles[0][x] = world.WALL
        tiles[height - 1][x] = world.WALL
    for y in range(height):
        tiles[y][0] = world.WALL
        tiles[y][width - 1] = world.WALL

    entities: list[world.Entity] = []

    # Per-planet buildings + their NPC occupants (planet-local
    # override or global catalog fallback).
    for building in spec.buildings:
        occupant = _resolve_npc_entity(building.npc_id, spec)
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

    # Showroom ships inside the FIRST building (the spaceport).
    if spec.buildings:
        port = spec.buildings[0]
        for ship_id, off_x, off_y in spec.showroom_ships:
            ship_obj = _resolve_ship(ship_id)
            entities.append(world.Entity(
                char=ship_obj.char,
                fg=ship_obj.fg,
                pos=world.Position(x=port.x_lo + off_x, y=port.y_lo + off_y),
                name=f"Ship: {ship_obj.name}",
                ship_id=ship_obj.id,
                width=ship_obj.width,
                height=ship_obj.height,
            ))

    # Shared decoration: roads, plaza, sidewalks, grass patch.
    world._layout_outside(tiles, width, height, spec.buildings, theme=theme)

    return world.GameMap(
        width=width, height=height,
        tiles=tiles, entities=entities,
    )


def _resolve_npc_entity(
    npc_id: str, spec: PlanetSpec,
) -> world.Entity | None:
    """Resolve an NPC id to a placeholder :class:`world.Entity`.

    Checks planet-local overrides (:attr:`PlanetSpec.npc_overrides`)
    first, then falls through to the global NPCS catalog. Both
    branches return ``None`` for an empty id (no occupant). The
    returned entity's ``pos`` is a placeholder: :func:`world.make_building`
    re-anchors it to the building interior before splicing.
    """
    if not npc_id:
        return None
    # Planet-local override first.
    for oid, npc_obj in spec.npc_overrides:
        if oid == npc_id:
            return world.Entity(
                char=npc_obj.char, fg=npc_obj.fg,
                pos=world.Position(0, 0),
                name=npc_obj.name,
                npc_id=npc_obj.id,
                width=1, height=1,
            )
    # Fall through to the global catalog.
    global_npc = npc_module.find_npc(npc_id)
    return world.Entity(
        char=global_npc.char, fg=global_npc.fg,
        pos=world.Position(0, 0),
        name=global_npc.name,
        npc_id=global_npc.id,
        width=1, height=1,
    )


def _resolve_ship(ship_id: str):
    from ... import ship as ship_module
    return ship_module.find_ship(ship_id)


__all__ = ["PlanetSpec", "load_planet", "find_planet_spec", "hangar_anchor"]
