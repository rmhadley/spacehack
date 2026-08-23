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

from dataclasses import dataclass, replace

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
      quest_npc_spots:   ``(npc_id, building_label)`` pairs naming
                          where a quest-conditional NPC stands while
                          its step is live (added dynamically by
                          ``spawn_quest_npcs`` one tile EAST of the
                          named building's interior center — clear of
                          the regular occupant, who stands at the
                          center). Unlike ``npc_overrides`` these are
                          ADDITIVE — they never replace the building's
                          regular occupant.
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
    city_layout_id: str = ""
    interior_layouts: tuple[tuple[str, str], ...] = ()
    transit_stations: tuple[world.TransitStation, ...] = ()
    theme: world.PlanetTheme | None = None
    npc_overrides: tuple[tuple[str, npc_module.NPC], ...] = ()
    # (npc_id, building_label) — where quest-conditional NPCs stand.
    quest_npc_spots: tuple[tuple[str, str], ...] = ()
    produces: tuple[tuple[str, int], ...] = ()
    demands: tuple[tuple[str, int], ...] = ()
    # Mechanic terminal inventory — weapon/module IDs sold at this planet's
    # mechanic terminal. Empty tuples = use seeded RNG (see
    # :func:`resolve_mech_inventory`).
    mech_weapons: tuple[str, ...] = ()
    mech_modules: tuple[str, ...] = ()
    # Armory terminal inventory — ground weapon/armor IDs sold at this
    # planet's armory terminal. Empty tuples = use seeded RNG (see
    # :func:`resolve_armory_inventory`).
    armory_weapons: tuple[str, ...] = ()
    armory_armor: tuple[str, ...] = ()
    tech_level: int = 1               # max tech level stocked at this planet
    mission_tier: int = 1             # max mission tier offered at this planet's NPCs
    explorable_site_name: str = "Surface"  # label for the EXPLORE menu option (e.g. Mars = "signal")
    dungeon_params: object = None      # :class:`~spacehack.dungeon.DungeonParams` for procedural dungeons


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
        Integer credits price for one unit.
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


def list_planet_specs() -> list[PlanetSpec]:
    """Return every registered :class:`PlanetSpec` (registry order).

    Mirrors ``list_solar_systems`` / ``list_missions`` so integrity
    tooling can iterate the whole catalog.
    """
    return list(_registry().values())


def _filter_by_tech_level(items, level: int) -> list:
    """Return the items whose ``tech_level`` is at most ``level``."""
    return [item for item in items if item.tech_level <= level]


def _sample_stock(
    override: tuple[str, ...],
    items: list,
    level: int,
    count: int,
    rng,
    shop_filter: bool = False,
) -> tuple[str, ...]:
    """Return ``override`` verbatim, else a tier-gated RNG sample of ``items``."""
    if override:
        return override
    pool = _filter_by_tech_level(items, level)
    if shop_filter:
        pool = [item for item in pool if getattr(item, "shop_available", True)]
    if not pool:
        return ()
    pool.sort(key=lambda item: item.price)
    return tuple(item.id for item in rng.sample(pool, min(count, len(pool))))


def resolve_mech_inventory(
    planet_id: str,
    month: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(weapon_ids, module_ids)`` sold at ``planet_id``'s mechanic.

    Fixed per-planet overrides win; otherwise a deterministic subset of
tier-eligible items keyed on the run seed + planet + ``month``. Stock is
stable for a whole month and rolls over on the clock (like mission boards),
rather than re-rolling with every terminal interaction.
    """
    from ...engine import INIT_SEED, seeded_rng
    from ...data.modules import list_modules as _lm
    from ...data.weapons import list_weapons as _lw

    spec = find_planet_spec(planet_id)
    rng = seeded_rng(INIT_SEED, "mech", planet_id, month)
    _w_ids = _sample_stock(spec.mech_weapons, _lw(), spec.tech_level, 4, rng)
    _m_ids = _sample_stock(spec.mech_modules, _lm(), spec.tech_level, 6, rng)
    return _w_ids, _m_ids


def resolve_armory_inventory(
    planet_id: str,
    month: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(weapon_ids, armor_ids)`` sold at ``planet_id``'s armory.

    Mirrors :func:`resolve_mech_inventory` for ground gear: fixed
per-planet overrides win, else a deterministic subset of tier-eligible
shop items keyed on the run seed + planet + ``month``.
    """
    from ...engine import INIT_SEED, seeded_rng
    from ...data.ground_armor import list_ground_armor as _lga
    from ...data.ground_weapons import list_ground_weapons as _lgw

    spec = find_planet_spec(planet_id)
    rng = seeded_rng(INIT_SEED, "armory", planet_id, month)
    _w_ids = _sample_stock(
        spec.armory_weapons, _lgw(), spec.tech_level, 4, rng, shop_filter=True,
    )
    _a_ids = _sample_stock(spec.armory_armor, _lga(), spec.tech_level, 6, rng)
    return _w_ids, _a_ids


def has_explorable_sites(planet_id: str) -> list[str]:
    """Return a list of explorable site names for ``planet_id``, or
    empty list if the planet has no surface dungeon configured.

    The site name comes from :attr:`PlanetSpec.explorable_site_name`
    so the menu option can be themed per planet (e.g. Mars offers
    "Explore signal" instead of "Explore Surface").
    """
    try:
        spec = find_planet_spec(planet_id)
        if getattr(spec, 'dungeon_params', None) is not None:
            return [spec.explorable_site_name]
    except KeyError:
        pass
    return []


def has_militia_presence(planet_id: str) -> bool:
    """Return True iff ``planet_id`` has a building labeled ``"militia"``.

    Militia checkpoints run cargo scans on landing (see
    :func:`spacehack.navigation._run_cargo_scan`). Used by the
    planet-bump dialog to warn the player before they commit to
    landing, and by the scan itself. Returns False for unknown ids.
    """
    try:
        spec = find_planet_spec(planet_id)
    except KeyError:
        return False
    return any(b.label == "militia" for b in spec.buildings)


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


_CITY_THEME_FIELDS = (
    "floor", "grass", "grass_accent", "plaza", "sidewalk",
    "road_surface", "road_ns", "road_ew", "landing_pad", "neon",
    "tree", "decor",
)
_CITY_BG_MIN_LUMA = 60.0
_CITY_BG_MIN_CHANNEL = 28


def _city_bg_luma(color: tuple[int, int, int]) -> float:
    """Return perceptual brightness for one city tile background."""
    return 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]


def _readable_city_bg(color: tuple[int, int, int]) -> tuple[int, int, int]:
    """Lift only near-black city backgrounds while preserving their hue."""
    lifted = tuple(max(_CITY_BG_MIN_CHANNEL, channel) for channel in color)
    luma = _city_bg_luma(lifted)
    if luma < _CITY_BG_MIN_LUMA:
        scale = _CITY_BG_MIN_LUMA / max(1.0, luma)
        lifted = tuple(
            min(255, max(_CITY_BG_MIN_CHANNEL, round(channel * scale) + 1))
            for channel in lifted
        )
    return lifted


def _readable_city_theme(theme: world.PlanetTheme) -> world.PlanetTheme:
    """Return ``theme`` with readable backgrounds and sparse base surfaces."""
    changes = {}
    for field in _CITY_THEME_FIELDS:
        tile = getattr(theme, field)
        bg = _readable_city_bg(tile.bg)
        char = "." if field in {"floor", "landing_pad"} else tile.char
        if bg != tile.bg or char != tile.char:
            changes[field] = replace(tile, bg=bg, char=char)
    return replace(theme, **changes) if changes else theme


def load_planet(planet_id: str) -> world.GameMap:
    """Build the :class:`world.GameMap` for the named planet's city."""
    spec = find_planet_spec(planet_id)
    if spec.city_layout_id == "earth_river_coast":
        from ...earth_city import build_earth_city
        return build_earth_city(
            spec,
            lambda npc_id: _resolve_npc_entity(npc_id, spec),
            _resolve_ship,
        )
    width, height = spec.width, spec.height
    theme = _readable_city_theme(spec.theme or world.EARTH_THEME)
    tiles = _city_tiles(width, height, theme)
    entities: list[world.Entity] = []
    _place_buildings(spec, tiles, entities)
    _place_port_fixtures(spec, entities)
    world._layout_outside(tiles, width, height, spec.buildings, theme=theme)
    _paint_landing_pad(spec, tiles, width, height, theme)
    return world.GameMap(
        width=width, height=height,
        tiles=tiles, entities=entities,
    )


def _city_tiles(width: int, height: int, theme) -> list[list[world.Tile]]:
    """Build the floor grid with perimeter walls for one city map."""
    tiles: list[list[world.Tile]] = [
        [theme.floor for _ in range(width)] for _ in range(height)
    ]
    for x in range(width):
        tiles[0][x] = world.WALL
        tiles[height - 1][x] = world.WALL
    for y in range(height):
        tiles[y][0] = world.WALL
        tiles[y][width - 1] = world.WALL
    return tiles


def _place_buildings(spec: PlanetSpec, tiles, entities) -> None:
    """Place per-planet buildings and their NPC occupants onto ``tiles``."""
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


def _port_entities(spec: PlanetSpec, port) -> list[world.Entity]:
    """Showroom ships + trade/mech/armory terminals outside the spaceport."""
    entities: list[world.Entity] = []
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


def _place_port_fixtures(spec: PlanetSpec, entities) -> None:
    """Place showroom ships + terminals if the spec has a spaceport."""
    if spec.buildings:
        entities.extend(_port_entities(spec, spec.buildings[0]))


def _paint_landing_pad(spec: PlanetSpec, tiles, width, height, theme) -> None:
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


__all__ = ["PlanetSpec", "load_planet", "find_planet_spec", "list_planet_specs", "hangar_anchor", "has_explorable_sites", "has_landable_port", "has_militia_presence"]
