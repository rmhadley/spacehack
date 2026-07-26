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
    produces: tuple[tuple[str, int], ...] = ()
    demands: tuple[tuple[str, int], ...] = ()
    trade_npc_id: str = ""


# ---------------------------------------------------------------------------
# Economy helpers
# ---------------------------------------------------------------------------


def trade_price(base_price: int, current_stock: int, target_stock: int) -> int:
    """Calculate the buy/sell price given current vs target stock levels.

    Uses a linear curve:
      Stock ratio = 0%   (shortage)  → 2.0\u00d7 base price
      Stock ratio = 50%  (equilibrium) → 1.0\u00d7 base price
      Stock ratio = 100% (surplus)    → 0.6\u00d7 base price

    This is the SINGLE pricing function for both the terminal and
    the NPC trader — no separate markup constants. The NPC trader
    simply offers access to a different stock pool (better prices
    because the stock levels are different).

    Args:
        base_price:  The :attr:`TradeGood.base_price` value.
        current_stock: How many units the planet currently holds.
        target_stock:  The equilibrium stock level (``target``
                       in the ``produces`` / ``demands`` tuple).

    Returns:
        Integer gold price for one unit.
    """
    target = max(1, target_stock)
    ratio = current_stock / target
    if ratio < 0.5:
        # Shortage zone: 2.0\u00d7 linearly down to 1.0\u00d7 at 50%.
        return int(base_price * (2.0 - ratio * 2.0))
    else:
        # Surplus zone: 1.0\u00d7 linearly down to 0.6\u00d7 at 100%.
        return int(base_price * (1.0 - (ratio - 0.5) * 0.8))


_BY_ID: dict[str, PlanetSpec] | None = None


def _build_registry() -> dict[str, PlanetSpec]:
    """Build the planet-spec id -> PlanetSpec mapping.

    Auto-discovers every module under this package that exports
    a ``SPEC`` attribute — no manual import list needed when
    adding a new planet. Just drop a new ``.py`` file in
    ``data/planets/``, export ``SPEC``, and it's registered.
    """
    import importlib, pkgutil
    spec_map: dict[str, PlanetSpec] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if hasattr(mod, "SPEC"):
            spec_map[mod.SPEC.id] = mod.SPEC
    return spec_map


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
        # Trade terminal: auto-placed outside every spaceport.
        # Every planet gets one — neutral goods from the full catalog
        # are available even when ``produces``/``demands`` are empty.
        _term_x = port.door_x + 2
        _term_y = port.y_hi + 1  # just outside the south-wall door
        entities.append(world.Entity(
            char="=",
            fg=(100, 220, 255),
            pos=world.Position(x=_term_x, y=_term_y),
            name="Trade Terminal",
            width=1, height=1,
            trade_terminal=True,
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


__all__ = ["PlanetSpec", "load_planet", "find_planet_spec", "hangar_anchor", "trade_price"]
