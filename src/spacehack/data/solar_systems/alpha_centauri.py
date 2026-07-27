"""Alpha Centauri — humanity's second-out system, reachable from Sol.

The user asked for Alpha Centauri as the first non-Sol system, so
v1 ships the real-world triple: Alpha Centauri A + B (the binary
stars) and Proxima Centauri (the red dwarf third star). Bodies
are NOT landable in v1 (no :class:`spacehack.data.planets.PlanetSpec`
entries yet) — they're for visual flavour + the Jump Point back
to Sol, which is the required behaviour.

A single Jump Point at the western edge of the map connects to
:data:`spacehack.data.solar_systems.sol`'s Jump Point at its
eastern edge. The two gates mirror each other across the jump
so the player's mental model of the connection is symmetric.

Map dims intentionally MATCH Sol's 200x140 footprint so the two
systems feel like the same size class. Future iterations can
scale per-system if Alpha Centauri ends up being a tighter
cluster than Sol.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem, StationSpec


# Anchor positions for Alpha Centauri's three stars + planets,
# picked for visual balance (binary pair centered, Proxima distant,
# planets in middle band, jump point at far west edge).
AC_A_POS = world.Position(80, 55)
AC_B_POS = world.Position(120, 85)
PROXIMA_POS = world.Position(170, 30)


_planets: tuple[solar_module.Planet, ...] = (
    # Alpha Centauri A — close analogue to Sol, yellow-white. 11x11
    # so it's a hair smaller than Sol's 13x13 (Sol is G2, AC-A is
    # G2-V but slightly smaller and hotter, IRL).
    solar_module.Planet(
        id="ac_a", name="Alpha Centauri A", char="O", fg=(255, 240, 180),
        pos=AC_A_POS, width=11, height=11, sun=True,
        description="A yellow-white star — close twin to Sol.",
    ),
    # Alpha Centauri B — orange K1 companion, 7x7 footprint so it
    # reads as smaller + warmer than AC-A at a glance.
    solar_module.Planet(
        id="ac_b", name="Alpha Centauri B", char="O", fg=(255, 170, 100),
        pos=AC_B_POS, width=7, height=7, sun=True,
        description="An orange companion — the binary's smaller twin.",
    ),
    # Proxima Centauri — small red dwarf, far from the binary.
    # Tiny 3x3 footprint so the size differential to AC-A reads as
    # 'this star is much smaller'.
    solar_module.Planet(
        id="proxima", name="Proxima Centauri", char="o", fg=(230, 80, 50),
        pos=PROXIMA_POS, width=3, height=3, sun=True,
        description="A small red dwarf — distant third member of the system.",
    ),
    # A few non-landable flavour planets (no planet-spec entries) —
    # gives the system some visual depth beyond the three stars.
    # Same warm/gas-giant palette as Sol's outer planets so the
    # two systems feel related (Mars-like rusty, ringed Saturn-
    # like, cool Uranus-like).
    solar_module.Planet(
        id="ac_planet_1", name="AC-I", char="p", fg=(180, 165, 130),
        pos=world.Position(45, 110), width=2, height=2,
        description="A scorched rocky world orbiting Alpha Centauri A.",
    ),
    solar_module.Planet(
        id="ac_planet_2", name="AC-II", char="p", fg=(190, 200, 220),
        pos=world.Position(140, 50), width=3, height=3,
        description="An icy body on the outer rim of the binary.",
    ),
    solar_module.Planet(
        id="ac_planet_3", name="AC-III", char="P", fg=(210, 145, 100),
        pos=world.Position(30, 30), width=5, height=5,
        description="A ringed gas giant in the system's middle orbit.",
    ),
)


# Science Port --- a research station in close orbit of Proxima
# Centauri. We pick a 3x3 footprint so it reads as a built
# structure against the starfields (matches the multi-cell planet
# scheme). Positioned just below + right of Proxima so it's
# visually paired with the red dwarf it studies but doesn't
# overlap any of Proxima's 3x3 footprint.
_stations: tuple[StationSpec, ...] = (
    StationSpec(
        id="ac_station_science_port",
        name="Science Port",
        char="#",
        fg=(150, 200, 220),                # cool steel-blue so it pops off warm AC stars.
        pos=world.Position(185, 24),       # east of Proxima (170, 30), 3x3 footprint.
        width=3, height=3,
        city_planet_id="ac_station",       # lands on the science-port city spec.
        description=(
            "A close-orbit research outpost round Proxima Centauri --- long-baseline"
            " stellar studies and a quiet dock for science crews."
            ),
    ),
)

_jump_points: tuple[JumpPoint, ...] = (
    # Mirrors Sol's jump point at the eastern edge — placed at the
    # far west so the two gates face each other across the jump.
    # Right-pointing chevron ('>') because the glyph should read as
    # "forward toward Sol" (the direction the player originally
    # came from). Same warm-gold palette so the two gates feel like
    # the same architecture.
    JumpPoint(
        id="jump_sol",
        name="Sol Gate",
        char=">",
        fg=(245, 215, 110),
        pos=world.Position(2, 70),
        width=2, height=2,
        connects_to=(("sol", "jump_alpha_centauri"),),
        description="A humming FTL gate ringing the outer Alpha Centauri system with starlight.",
    ),
    # Barnard's Star Gate: a SECOND gate from AC so
    # the player can route through AC -> Barnard's Star
    # -> Vega/Sirius. Warm-red palette matches
    # Barnard's Star's red-dwarf glow so the gate reads
    # as 'leads to a red star system'. Positioned at
    # (193, 70) east edge so it pairs visually with
    # the Sol gate (west edge).
    JumpPoint(
        id="jump_barnards_star",
        name="Barnard's Star Gate",
        char="<",
        fg=(245, 100, 70),
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(("barnards_star", "jump_alpha_centauri"),),
        description="A humming FTL gate facing Barnard's Star.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="alpha_centauri")


SYSTEM: SolarSystem = SolarSystem(
    id="alpha_centauri",
    name="Alpha Centauri",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=_stations,
    stars=_stars,
    npc_spawn_chance=0.6,
    npc_spawn_table=(("merchant_hauler", 0.7), ("pirate_scout", 0.5)),
    npc_density=2,
)
