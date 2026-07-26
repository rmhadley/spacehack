"""Solar systems catalog + per-system data files.

Mirrors the :mod:`spacehack.data.planets` pattern: each solar
system (Sol, future Alpha Centauri etc.) lives in its own module
exporting a :class:`SolarSystem` instance. Adding a system is a
single new module + one entry in :data:`_SYSTEMS` + one
``connects_to`` target pair on the relevant JumpPoints — no
dispatcher / engine / render code rewrites.

The :class:`spacehack.solar_system.Planet` dataclass lives in
:mod:`spacehack.solar_system` (not here) because it's the shared
in-space body model the renderer already depends on. The
:class:`JumpPoint` + :class:`SolarSystem` dataclasses live here
because they're data-driven (mirroring :class:`PlanetSpec` in
:mod:`spacehack.data.planets`).
"""
from __future__ import annotations

from dataclasses import dataclass

from spacehack import solar_system as solar_module
from spacehack import world


__all__ = [
    "EnemySpawn", "JumpPoint", "SolarSystem", "StationSpec",
    "find_solar_system", "list_solar_systems",
]


@dataclass(frozen=True)
class EnemySpawn:
    """One enemy ship placement in a solar system.

    Attributes:
        enemy_id: references EnemySpec.id (e.g. "pirate_scout").
        pos: starting position on the system map.
        patrol_radius: cells around spawn point it can wander.
        squad_id: optional grouping key. Spawns sharing a non-empty
            ``squad_id`` form a logical squad: when ANY alive squad
            member is detected by the player, ALL alive members of
            the squad join the same combat encounter (even if some
            members are beyond the player's detect radius from the
            triggering position). ``None`` (default) marks a
            standalone spawn that engages by proximity only.
    """
    enemy_id: str
    pos: world.Position
    patrol_radius: int = 5
    squad_id: str | None = None


@dataclass(frozen=True)
class JumpPoint:
    """One jump point within a :class:`SolarSystem`.

    Like :class:`solar_module.Planet`, a JumpPoint has a
    rectangular footprint on the system map; bumping any cell of
    that footprint opens the jump menu (mirror of the planet-bump
    menu in :mod:`spacehack.__main__`).

    Attributes:
      id: registry key, e.g. ``"jump_alpha_centauri"``.
      name: display name shown in the jump menu title.
      char / fg: glyph + foreground color for the JumpPoint tile.
        Picked to read at a glance as 'a gate' distinct from the
        planet glyphs that surround it (different fg + a chevron
        or bracket char).
      pos / width / height: rectangular footprint on the system
        map. 1x1 places a single glyph; 2x2 gives the gate enough
        visual weight to read as 'monument-scale'.
      connects_to: tuple of ``(target_system_id, target_jp_id)``
        pairs that this jump point can connect to. The single-hop
        Sol <-> Alpha Centauri setup ships one entry per gate; a
        future hub-and-spoke gate at a nexus station would carry
        multiple entries.
      description: one-line flavour text for the jump menu.
    """
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    pos: world.Position
    width: int = 1
    height: int = 1
    connects_to: tuple[tuple[str, str], ...] = ()
    description: str = ""

    def tile(self) -> world.Tile:
        """The :class:`world.Tile` rendered at this JumpPoint's footprint.

        ``kind="jump_point"`` so rendering / collision code can
        distinguish a jump-point cell from a planet cell at a
        glance. ``walkable=False`` because the player ship bumps
        into jump points — it doesn't fly through them.
        """
        return world.Tile(
            kind="jump_point",
            char=self.char,
            walkable=False,
            fg=self.fg,
            bg=(8, 8, 22),                       # matches DEEP_SPACE_BG
        )


@dataclass(frozen=True)
class StationSpec:
    """Static data describing one in-space station (e.g. a science port).

    Mirrors :class:`solar_module.Planet`'s shape (rectangular footprint,
    id, char/fg, pos/width/height) but stations retrieve their landing
    city via :attr:`city_planet_id` rather than their own :attr:`id`
    because the city definition lives in :mod:`spacehack.data.planets`
    --- a single city spec can back multiple stations in future
    iterations (e.g. an Earth Orbital Station AND a Mars Orbital Station
    both routing to the same generic spacestation city plan).

    Attributes:
      id: registry key (unique inside the parent system).
      name: display name, e.g. "Science Port".
      char / fg: glyph + foreground color painted at each footprint
        cell. ``'#'`` + greyscale reads as 'a built structure' even
        in the starfield.
      pos / width / height: rectangular footprint on the system map.
      city_planet_id: the :class:`spacehack.data.planets.PlanetSpec`
        id whose city map is loaded when the player lands. Stop-gap:
        the city spec is reused (an orbital station can use Earth's
        spec for layout prototyping).
      description: one-line flavour text shown in the
        Areas-of-Interest panel + bump menu.
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
        """The :class:`world.Tile` rendered at this station's footprint.

        ``kind="station"`` so rendering / collision code can
        distinguish a station cell from a planet/jump-point.
        ``walkable=False`` because the player ship bumps into
        stations --- it doesn't fly through them. Stations paint
        LAST in :func:`make_solar_system` (highest Z priority) so
        they overwrite any planet/jump-point that happens to
        overlap.
        """
        return world.Tile(
            kind="station",
            char=self.char,
            walkable=False,
            fg=self.fg,
            bg=(8, 8, 22),                       # matches DEEP_SPACE_BG
        )


@dataclass(frozen=True)
class SolarSystem:
    """Static data describing one star system's map + bodies.

    Attributes:
      id: registry key, e.g. ``"sol"`` or ``"alpha_centauri"``.
      name: display name, e.g. ``"Sol"`` (shown in map title).
      width / height: the system map's total size in cells. Must
        be larger than :data:`spacehack.solar_system.SOL_VIEW_W/H`
        so the viewport is scrollable (the visual payoff for
        'space feels bigger').
      planets: tuple of :class:`solar_module.Planet` for planets
        AND the system's central sun (the :attr:`Planet.sun` flag
        distinguishes them). The Sun lives in this tuple alongside
        the planets because the render code paints them all as
        rectangular footprints of starfield cells.
      jump_points: tuple of :class:`JumpPoint`.
      stations: tuple of :class:`StationSpec` for in-space
        stations (orbital platforms; future science ports,
        refueling depots, etc.). Optional, defaults to empty so
        Sol can ship stations=() for systems that have none.
      stars: tuple of ``(x, y)`` static star sprinkle positions.
      enemies: tuple of :class:`EnemySpawn` for hostile ships.
    """
    id: str
    name: str
    width: int
    height: int
    planets: tuple[solar_module.Planet, ...]
    jump_points: tuple[JumpPoint, ...]
    stars: tuple[tuple[int, int], ...]
    stations: tuple[StationSpec, ...] = ()
    enemies: tuple[EnemySpawn, ...] = ()


_BY_ID: dict[str, SolarSystem] | None = None


def _build_registry() -> dict[str, SolarSystem]:
    """Build the system-id -> SolarSystem mapping.

    Import every per-system module and index its ``SYSTEM``
    module-level instance. Mirrors :func:`spacehack.data.planets.
    _build_registry` so the two catalog namespaces share the same
    shape — easier to grep + reason about.
    """
    from . import sol as sol_module
    from . import alpha_centauri as ac_module
    from . import barnards_star as barnards_module
    from . import sirius as sirius_module
    from . import vega as vega_module
    from . import epsilon_eridani as ee_module
    from . import procyon as procyon_module
    from . import tau_ceti as tc_module
    from . import wolf_359 as wolf_module
    from . import luyten_star as ls_module
    return {
        sol_module.SYSTEM.id: sol_module.SYSTEM,
        ac_module.SYSTEM.id: ac_module.SYSTEM,
        barnards_module.SYSTEM.id: barnards_module.SYSTEM,
        sirius_module.SYSTEM.id: sirius_module.SYSTEM,
        vega_module.SYSTEM.id: vega_module.SYSTEM,
        ee_module.SYSTEM.id: ee_module.SYSTEM,
        procyon_module.SYSTEM.id: procyon_module.SYSTEM,
        tc_module.SYSTEM.id: tc_module.SYSTEM,
        wolf_module.SYSTEM.id: wolf_module.SYSTEM,
        ls_module.SYSTEM.id: ls_module.SYSTEM,
    }


def _registry() -> dict[str, SolarSystem]:
    """Lazy-init wrapper around :data:`_BY_ID`."""
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_solar_system(system_id: str) -> SolarSystem:
    """Look up a :class:`SolarSystem` by id; raises :class:`KeyError` on miss.

    Mirrors the look-up-by-id contract used by every other catalog
    module (:func:`spacehack.data.planets.find_planet_spec`,
    :func:`spacehack.character.find_species`) so callers don't
    have to special-case missing bodies.
    """
    try:
        return _registry()[system_id]
    except KeyError:
        raise KeyError(f"unknown solar system id: {system_id!r}") from None


def list_solar_systems() -> tuple[SolarSystem, ...]:
    """All registered solar systems, in registry order."""
    return tuple(_registry().values())


def reachable_system_ids(
    from_id: str,
    max_hops: int = 10,
) -> dict[str, int]:
    """BFS-walk the jump-point graph from ``from_id``.

    Returns a mapping ``{target_system_id: hop_count}`` of every
    OTHER system reachable in ``<= max_hops`` hops via the
    connect-graph encoded in :attr:`JumpPoint.connects_to`.
    ``from_id`` itself is NOT in the returned mapping (you are
    not 'reachable' from yourself).

    ``max_hops`` bounds the search depth so a future connected
    graph can't blow up the caller's render surface (the Map
    modal paints every reachable system in the AoI panel; an
    unreasonable depth would overflow the screen).

    Used by:
      * :func:`spacehack.__main__._render_aoi_panel` to list
        neighbour systems in the Map modal so the player can
        see how many jumps are needed to reach them.
      * Smoke @checks to confirm the universe graph is fully
        connected (every registered system is reachable from
        Sol in a finite number of hops).

    A system with no ``connects_to`` pair reachable in
    ``max_hops`` jumps is simply absent from the result — the
    smoke @checks per clause mean we don't need to handle that
    edge case today.
    """
    from collections import deque
    seen: dict[str, int] = {from_id: 0}
    queue: deque[tuple[str, int]] = deque([(from_id, 0)])
    while queue:
        curr_id, hops = queue.popleft()
        if hops >= max_hops:
            continue
        try:
            curr = find_solar_system(curr_id)
        except KeyError:
            continue
        for jp in curr.jump_points:
            for target_sys_id, _target_jp_id in jp.connects_to:
                if target_sys_id == from_id:
                    continue
                new_hops = hops + 1
                if new_hops > max_hops:
                    continue
                if target_sys_id not in seen or new_hops < seen[target_sys_id]:
                    seen[target_sys_id] = new_hops
                    queue.append((target_sys_id, new_hops))
    seen.pop(from_id, None)
    return seen
