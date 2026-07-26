"""In-space bodies, shared deep-space palette, and helpers that
operate on a :class:`spacehack.data.solar_systems.SolarSystem`.

This iteration ships two systems (Sol + Alpha Centauri) — see
:mod:`spacehack.data.solar_systems` for the per-system data
files. The :class:`Planet` dataclass lives here (not in
:mod:`spacehack.data.solar_systems`) because it's the shared
in-space body model that the renderer already depends on.

:attr:`current_solar_system_id` is module-level state — the
dispatcher sets it when the player jumps between systems. All
helpers default to looking up the current system but accept an
explicit ``system`` kwarg so test code + plot tools can exercise
any system without monkey-patching state.

Helpers exported:

  * :func:`find_planet` / :func:`find_jump_point` — id lookups.
  * :func:`planet_id_at` / :func:`jump_point_at` — footprint-
    aware id/object lookups by :class:`world.Position`.
  * :func:`make_solar_system` — build a :class:`world.GameMap`
    from a :class:`spacehack.data.solar_systems.SolarSystem`.
  * :func:`place_docked_ship` — canonical "ship in orbit west of
    this planet" :class:`world.Entity` for launch/land scenes.

Tiles used here have ``bg`` already baked in (same dark-starfield
bg across all bodies) so re-rendering with painted bodies via
:func:`world.render_world` still produces a coherent space
backdrop.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import world
from .data import solar_systems as systems_module


__all__ = [
    "DEEP_SPACE_BG", "STARFIELD", "STAR", "SUN",
    "Planet", "Station",
    "current_solar_system_id", "current_system",
    "set_current_solar_system",
    "find_planet", "find_jump_point", "find_station",
    "planet_id_at", "jump_point_at", "station_id_at",
    "make_stars", "make_solar_system", "place_docked_ship",
    "SOL_VIEW_W", "SOL_VIEW_H",
]


# Tile kinds used inside the solar system. ``STARFIELD`` is the
# dark void cell, ``STAR`` is the bright single-cell sprinkles
# for visual texture, ``SUN`` is the central star cell.
#
# Every kind uses the same near-black bg ``(8, 8, 22)`` so
# rendered bodies pop against a uniform backdrop. ``STARFIELD.
# char`` is a literal space so most cells read as 'the void'
# (just the bg shows); ``STAR.char`` is '*' so the occasional
# bright sprinkle reads as a star at a glance.
DEEP_SPACE_BG: tuple[int, int, int] = (8, 8, 22)
STARFIELD = world.Tile(
    kind="starfield", char=" ", walkable=True,
    fg=(40, 40, 70), bg=DEEP_SPACE_BG,
)
STAR = world.Tile(
    kind="star", char="*", walkable=True,
    fg=(220, 220, 230), bg=DEEP_SPACE_BG,
)
SUN = world.Tile(
    kind="sun", char="O", walkable=False,
    fg=(255, 230, 120),                                  # warm yellow glow
    bg=(140, 90, 30),                                    # ambient orange wash so the 'O' pops off the void
)


@dataclass(frozen=True)
class Station:
    """A stationary in-space structure with a city map attached.

    v1 ships one — Alpha Centauri's Science Port, near Proxima.
    Future iterations add more (Earth Orbital Station,
    Mars Orbital Station, gas-giant refueling platforms).

    Same footprint model as :class:`Planet` and
    :class:`systems_module.JumpPoint` (top-left ``pos`` + ``width`` +
    ``height``); ``walkable=False`` so the player ship bumps them
    rather than flying through. Like :class:`Planet` we render by
    filling the rectangular footprint with the same char/fg so the
    station reads as a multi-cell greyscale block at a glance.

    Distinction from :class:`Planet`: a planet has its own orbital
    body + sky/gravity (the v1 city interior lives on a planet's
    surface); a station is an orbital platform with no planetary
    body. They share the *landing* UX (planet-menu + land ops)
    but their city definitions come from a different registry
    entry (``city_planet_id`` -> ``data.planets.PlanetSpec``),
    not from the body's own ``id``.

    Attributes mirror :class:`Planet` + add ``city_planet_id``:
    """
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    pos: world.Position
    width: int = 1
    height: int = 1
    city_planet_id: str = ""
    description: str = ""

    def tile(self) -> world.Tile:
        """The :class:`world.Tile` rendered at this station's cells.

        ``kind=\"station\"`` so renderer / collision code can tag
        station cells distinctly from planets + jump-points.
        ``walkable=False`` because the player ship bumps them.
        """
        return world.Tile(
            kind="station",
            char=self.char,
            walkable=False,
            fg=self.fg,
            bg=DEEP_SPACE_BG,
        )


@dataclass(frozen=True)
class Planet:
    """One celestial body in a :class:`systems_module.SolarSystem`.

    ``pos`` is the body's TOP-LEFT cell on the system map.
    ``width`` and ``height`` define the rectangular footprint; a
    1x1 planet reads as a single glyph but the same data model
    scales to a 13x13 Sol so the player can SEE the size
    differential between the scout ship and Jupiter at a glance.
    ``sun`` signifies the central star (renders via :data:`SUN`);
    planets render as their own per-body :class:`world.Tile`
    filled across every cell of the footprint.
    """
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    pos: world.Position
    width: int = 1
    height: int = 1
    sun: bool = False
    description: str = ""

    def tile(self) -> world.Tile:
        """The ``world.Tile`` rendered at this body's center cell.

        ``SUN`` uses :data:`SUN` so the center star reads as one
        glyph; planets use their own char/fg with the dark
        starfield bg so they pop cleanly off the void.
        ``walkable=False`` so the player ship can't fly straight
        through a planet (they bump and can later 'land').
        """
        if self.sun:
            return SUN
        return world.Tile(
            kind="planet",
            char=self.char,
            walkable=False,
            fg=self.fg,
            bg=DEEP_SPACE_BG,
        )


# Module-level "current solar system" state. The dispatcher
# updates it when the player jumps between systems; the helpers
# below read it as the default when no explicit ``system`` is
# passed.
#
# Defaults to ``"sol"`` so any code that imports this module
# before the dispatcher sets state (test code, plot tools, etc.)
# still works.
DEFAULT_SOLAR_SYSTEM_ID: str = "sol"
current_solar_system_id: str = DEFAULT_SOLAR_SYSTEM_ID


def current_system() -> systems_module.SolarSystem:
    """Resolve the current solar system from module-level state.

    Equivalent to ``systems_module.find_solar_system(
    current_solar_system_id)`` but spelled out so call sites
    read naturally. Raises :class:`KeyError` if the configured
    id isn't in the registry (smoke test catches this).
    """
    return systems_module.find_solar_system(current_solar_system_id)


def set_current_solar_system(
    system_id: str,
) -> systems_module.SolarSystem:
    """Switch module-level current system; returns the resolved system.

    Called by the dispatcher after a successful jump so the
    helpers below pick up the new system on the next call.
    """
    global current_solar_system_id
    system = systems_module.find_solar_system(system_id)
    current_solar_system_id = system_id
    return system


def find_planet(
    planet_id: str,
    *,
    system: systems_module.SolarSystem | None = None,
) -> Planet:
    """Look up a :class:`Planet` by id in ``system``; raises
    :class:`KeyError` on miss.

    First scans :attr:`SolarSystem.stations` for any station whose
    :attr:`StationSpec.city_planet_id` matches ``planet_id`` and
    (if found) returns a synthesized :class:`Planet` whose
    footprint + colour match the station. This lets the planet-
    bump dispatcher flow unchanged when the player bumps a
    station: set ``pid = station.city_planet_id`` and the LAND
    branch treats it as a planet whose spec lives in
    :mod:`spacehack.data.planets`.

    ``system`` defaults to :func:`current_system`. Mirrors the
    look-up-by-id contract used by every other catalog module
    (:func:`spacehack.character.find_species`,
    :func:`spacehack.ship.find_ship`).
    """
    if system is None:
        system = current_system()
    # Station-by-city_planet_id fallback. Stations paint LAST in
    # make_solar_system so they visually overlap underlying bodies
    # - but the dispatcher routes them via planet-bump semantics
    # (LAND animation, scene swap, hangar dock). Synthesize a
    # Planet from the station spec so the existing planet-bump
    # code path works without bespoke station-branch duplication.
    for st in getattr(system, "stations", ()) or ():
        if st.city_planet_id == planet_id:
            # Synthetic for land dispatch only (planet-menu dialog,
            # LAND animation, scene-swap, hangar-dock). NOT painted
            # in space -- the station tile is what renders in
            # make_solar_system because the renderer iterates
            # system.planets + system.stations separately.
            return Planet(
                id=planet_id,
                name=st.name,
                char=st.char,
                fg=st.fg,
                pos=st.pos,
                width=st.width,
                height=st.height,
                sun=False,
                description=st.description,
            )
    for p in system.planets:
        if p.id == planet_id:
            return p
    raise KeyError(
        f"unknown planet id: {planet_id!r} in system {system.id!r}"
    )


def find_jump_point(
    jp_id: str,
    *,
    system: systems_module.SolarSystem | None = None,
) -> systems_module.JumpPoint:
    """Look up a :class:`systems_module.JumpPoint` by id; raises
    :class:`KeyError` on miss.

    ``system`` defaults to :func:`current_system`. Mirror of
    :func:`find_planet` for the jump-point catalog.
    """
    if system is None:
        system = current_system()
    for jp in system.jump_points:
        if jp.id == jp_id:
            return jp
    raise KeyError(
        f"unknown jump point id: {jp_id!r} in system {system.id!r}"
    )


def find_station(
    station_id: str,
    *,
    system: systems_module.SolarSystem | None = None,
) -> systems_module.Station:
    """Look up a :class:`systems_module.Station` by id; raises
    :class:`KeyError` on miss.

    ``system`` defaults to :func:`current_system`. Mirror of
    :func:`find_jump_point` for the station catalog. The station's
    :attr:`city_planet_id` field threads through the planet-menu's
    LAND dispatch so the dispatcher treats a station bump exactly
    like a planet bump (modulo the city id mapping).
    """
    if system is None:
        system = current_system()
    for st in system.stations:
        if st.id == station_id:
            return st
    raise KeyError(
        f"unknown station id: {station_id!r} in system {system.id!r}"
    )


def planet_id_at(
    x: int, y: int,
    *,
    system: systems_module.SolarSystem | None = None,
) -> str | None:
    """Return the planet id at ``(x, y)`` in ``system`` (default current).

    ``None`` for empty space / sun. Footprint-aware: any cell
    with ``p.pos.x <= x < p.pos.x + p.width`` AND
    ``p.pos.y <= y < p.pos.y + p.height`` resolves to
    ``p.id``. Without the footprint check, only the center cell
    of a multi-cell planet would resolve and the ship could fly
    "through" the perimeter without triggering a planet-bump
    dialog.

    Sol/the system's sun are excluded (the sun is its own kind
    and bumping it is a different future event; ``None`` cleanly
    separates 'no planet here' from 'planet sun here' without an
    enum).
    """
    if system is None:
        system = current_system()
    for p in system.planets:
        if p.sun:
            continue
        if (
            p.pos.x <= x < p.pos.x + p.width
            and p.pos.y <= y < p.pos.y + p.height
        ):
            return p.id
    return None


def jump_point_at(
    x: int, y: int,
    *,
    system: systems_module.SolarSystem | None = None,
) -> systems_module.JumpPoint | None:
    """Return the :class:`JumpPoint` at ``(x, y)`` in ``system``,
    or ``None``.

    Mirror of :func:`planet_id_at` for jump points. The
    dispatcher uses this to detect a jump-bump interaction when
    the player ship tries to fly INTO any cell of a JumpPoint's
    rectangular footprint. Returns the JumpPoint OBJECT (not
    just the id) so the caller can read ``jp.connects_to`` to
    drive the jump menu.
    """
    if system is None:
        system = current_system()
    for jp in system.jump_points:
        if (
            jp.pos.x <= x < jp.pos.x + jp.width
            and jp.pos.y <= y < jp.pos.y + jp.height
        ):
            return jp
    return None


def station_id_at(
    x: int, y: int,
    *,
    system: "systems_module.SolarSystem | None" = None,
) -> str | None:
    """Return the station id at ``(x, y)`` in ``system``, or ``None``.

    Mirror of :func:`planet_id_at` for station footprints. Used
    by the dispatcher in :mod:`spacehack.__main__` to detect a
    station-bump when the ship tries (and fails) to fly INTO any
    cell of a station's rectangular footprint. Returns the id
    string so the caller can look up its ``city_planet_id`` and
    pass it to the planet-menu's LAND dispatch (stations reuse
    the existing landing flow).
    """
    if system is None:
        system = current_system()
    for st in system.stations:
        if (
            st.pos.x <= x < st.pos.x + st.width
            and st.pos.y <= y < st.pos.y + st.height
        ):
            return st.id
    return None


# Solar system viewport (matches the city map viewport: left of
# HUD, above message log). Centralised here so the __main__
# dispatcher reads one source of truth instead of duplicating
# the math. Per-system TOTAL map size lives on each
# :class:`SolarSystem` record — viewport is system-agnostic.
SOL_VIEW_W: int = 80
SOL_VIEW_H: int = 54


def make_stars(
    width: int, height: int,
    *,
    density: float = 0.003,
    seed: int | str = 0,
) -> tuple[tuple[int, int], ...]:
    """Generate a deterministic star field for a system map.

    Uses the system id as the seed so the same system always
    produces the same star pattern. Default density (0.003)
    scatters ~84 stars on a 200x140 map, matching the hand-
    typed density typical of pre-refactor system modules.

    Pass a lower density (e.g. 0.002) for isolated / frontier
    systems, or a higher density for nebula-rich regions.
    """
    import hashlib
    import random as _random
    if isinstance(seed, str):
        seed = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
    rng = _random.Random(seed)
    coords = [
        (x, y)
        for x in range(width)
        for y in range(height)
        if rng.random() < density
    ]
    rng.shuffle(coords)
    return tuple(coords)


def make_solar_system(
    *,
    system: systems_module.SolarSystem | None = None,
) -> world.GameMap:
    """Build the :class:`world.GameMap` for ``system`` (default current).

    Painter-algorithm: STARFIELD across the whole map, then
    stars over the void, then planets over their footprints,
    then jump points LAST so a gate that happens to overlap a
    planet cell still shows as a gate (designer intent: jumps
    are MORE important than planets for navigation).

    ``width`` / ``height`` are read from the system record —
    the caller can't override them. A malformed system (w < 5
    or h < 5) raises ``ValueError`` early.
    """
    if system is None:
        system = current_system()
    width, height = system.width, system.height
    if width < 5 or height < 5:
        raise ValueError("solar system must be at least 5x5")

    tiles: list[list[world.Tile]] = [
        [STARFIELD for _ in range(width)] for _ in range(height)
    ]
    # Paint the static star sprinkle first so bodies overwrite
    # them at their cells (bodies win over stars, never the
    # other way around).
    for sx, sy in system.stars:
        if 0 <= sx < width and 0 <= sy < height:
            tiles[sy][sx] = STAR
    # Paint planets.
    for body in system.planets:
        tile = body.tile()
        for dy in range(body.height):
            for dx in range(body.width):
                cx = body.pos.x + dx
                cy = body.pos.y + dy
                if 0 <= cx < width and 0 <= cy < height:
                    tiles[cy][cx] = tile
    # Paint jump points so a gate that overlaps a planet cell
    # still shows as a gate (jumps win over planets for navigation).
    for jp in system.jump_points:
        tile = jp.tile()
        for dy in range(jp.height):
            for dx in range(jp.width):
                cx = jp.pos.x + dx
                cy = jp.pos.y + dy
                if 0 <= cx < width and 0 <= cy < height:
                    tiles[cy][cx] = tile
    # Paint stations LAST so a station overlapping a planet OR
    # a jump-point cell still shows as a station (station wins
    # over both; v1 has one station near Proxima so this only
    # matters when station footprints collide with JPs/planets).
    for st in system.stations:
        tile = st.tile()
        for dy in range(st.height):
            for dx in range(st.width):
                cx = st.pos.x + dx
                cy = st.pos.y + dy
                if 0 <= cx < width and 0 <= cy < height:
                    tiles[cy][cx] = tile

    # Build entity list: ships spawned from system.enemies
    entities: list[world.Entity] = []
    for _spawn in getattr(system, 'enemies', ()) or ():
        try:
            from .data.enemies import find_enemy as _find_enemy
            _espec = _find_enemy(_spawn.enemy_id)
        except (KeyError, ImportError):
            continue
        entities.append(world.Entity(
            char=_espec.char,
            fg=_espec.fg,
            pos=_spawn.pos,
            name=_espec.name,
            width=1,
            height=1,
        ))

    return world.GameMap(
        width=width, height=height, tiles=tiles, entities=entities,
    )


def place_docked_ship(ship_obj, planet_obj: Planet) -> world.Entity:
    """Build the player-ship :class:`world.Entity` docked at
    ``planet_obj``.

    The ship sits to the WEST of the planet, with one empty
    space between the ship's right edge and the planet's
    leftmost cell. Multi-cell planets (>1x1) widen the
    planet's left edge; the ship docks just west of that.
    Multi-cell ships (width > 1) extend further west; multi-row
    ships (height > 1) centre vertically on the planet's
    footprint.

    For a 1x1 ship docking at a 3x3 Earth whose leftmost cell
    is at (140, 39), the ship lands at (136, 40) — one cell
    west of Earth's left edge, centred (planet.height=3,
    ship.height=1, so y = 39 + (3-1)//2 = 40). For a 2x1
    Hauler at the same Earth, it lands at (134, 40) —
    extending further west.
    """
    return world.Entity(
        char=ship_obj.char,
        fg=ship_obj.fg,
        pos=world.Position(
            planet_obj.pos.x - 1 - ship_obj.width,
            planet_obj.pos.y
            + (planet_obj.height - ship_obj.height) // 2,
        ),
        name=f"Your Ship: {ship_obj.name}",
        ship_id=ship_obj.id,
        width=ship_obj.width,
        height=ship_obj.height,
        owned=True,
    )


def place_jumped_ship(
    ship_obj,
    jp_obj: systems_module.JumpPoint,
) -> world.Position:
    """Return the :class:`world.Position` where the player ship sits
    after JUMPING into a system, just east of ``jp_obj``.

    Mirror of :func:`place_docked_ship`'s "west of planet" rule
    but flipped to "east of gate" because the two gates face
    each other (Sol's gate sits at the eastern edge with a '<'
    pointing outward; Alpha Centauri's gate sits at the western
    edge with a '>' pointing toward Sol). On arrival the ship
    drifts in just east of the destination gate so the player
    is close enough to bump the gate again if they want to
    immediately jump back.
    """
    return world.Position(
        jp_obj.pos.x + jp_obj.width + 1,
        jp_obj.pos.y
        + (jp_obj.height - ship_obj.height) // 2,
    )
