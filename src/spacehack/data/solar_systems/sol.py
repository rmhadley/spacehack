"""Sol — Earth's home system.

The player always starts here. Contains Sol (the central sun), the
eight classical planets, and (as of the multi-system iteration) a
Jump Point at the eastern edge that connects to Altair Gate at the
western edge of the Alpha Centauri system.

Bodies intentionally match the historical in-line SOL_BODIES
positions so existing screenshots + reference visualisations stay
consistent with the previous single-system version. Star sprinkle
positions are likewise carried over from the old in-line
``STARS`` so the void still reads as the same nebula the player
left from.

The Jump Point is at ``(193, 70)`` so it sits at the far east of
the 200x140 map, just past Neptune — far enough that you have to
fly out there but not blocked by any planet cell.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import EnemySpawn, JumpPoint, SolarSystem


# Anchor positions for Sol + the eight planets on the 200x140 map.
# Picked for visual balance (clear gaps between bodies, sun
# visually centred, planets read in distinct corners) rather than
# scientific orbital accuracy — the user said "rough
# representation, we'll iterate from there".
SUN_POS = world.Position(100, 70)
EARTH_POS = world.Position(140, 39)


_planets: tuple[solar_module.Planet, ...] = (
    # Sol: huge central star. 13x13 footprint dominates the camera
    # when the player bumps it (future iteration: star-bump warming).
    solar_module.Planet(
        id="sun", name="Sol", char="O", fg=(255, 230, 120),
        pos=SUN_POS, width=13, height=13, sun=True,
        description="The yellow dwarf star at the heart of the Sol system.",
    ),
    # Inner rocky planets: small footprints so the player can fit
    # Sol AND a few inner planets on screen at launch from Earth.
    solar_module.Planet(
        id="mercury", name="Mercury", char="m", fg=(180, 175, 165),
        pos=world.Position(75, 51), width=2, height=2,
        description="A scorched rocky world — closest orbit to Sol.",
    ),
    solar_module.Planet(
        id="venus", name="Venus", char="v", fg=(235, 215, 165),
        pos=world.Position(124, 94), width=3, height=3,
        description="A dense, cloud-shrouded planet — second from Sol.",
    ),
    solar_module.Planet(
        id="earth", name="Earth", char="o", fg=(130, 195, 230),
        pos=EARTH_POS, width=3, height=3,
        description="Your home — blue oceans, green continents, one moon.",
    ),
    solar_module.Planet(
        id="mars", name="Mars", char="M", fg=(200, 50, 50),
        pos=world.Position(60, 99), width=3, height=3,
        description="A red, dusty world — humanity's first off-world colony.",
    ),
    # Outer gas/ice giants: the largest non-Sol bodies so the scout
    # ship reads as visually tiny next to Jupiter/Saturn even at
    # 1 char per planet cell.
    solar_module.Planet(
        id="jupiter", name="Jupiter", char="J", fg=(210, 160, 110),
        pos=world.Position(164, 64), width=7, height=7,
        description="A massive gas giant with a famous red storm.",
    ),
    solar_module.Planet(
        id="saturn", name="Saturn", char="S", fg=(220, 200, 140),
        pos=world.Position(34, 89), width=7, height=7,
        description="A ringed gas giant — the second-largest in Sol.",
    ),
    solar_module.Planet(
        id="uranus", name="Uranus", char="U", fg=(160, 220, 235),
        pos=world.Position(20, 25), width=5, height=5,
        description="An ice giant tipped on its side, blue-green and cold.",
    ),
    solar_module.Planet(
        id="neptune", name="Neptune", char="N", fg=(95, 145, 230),
        pos=world.Position(179, 109), width=5, height=5,
        description="A deep-blue ice giant — the outermost classical planet.",
    ),
)


_jump_points: tuple[JumpPoint, ...] = (
    # The single Sol-side jump point, at the far east. 2x2 footprint
    # so it has enough visual weight to read as 'a gate', not just 'a
    # weird planet'. Warm gold fg so it pops next to the cooler
    # planet glyphs around it. Left-pointing chevron ('<') so the
    # glyph reads as "out toward the stars" rather than "in toward
    # Sol".
    JumpPoint(
        id="jump_alpha_centauri",
        name="Alpha Centauri Gate",
        char="<",
        fg=(245, 215, 110),
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(("alpha_centauri", "jump_sol"),),
        description="A humming FTL gate ringing the outer Sol system with starlight.",
    ),
    # Vega Gate: a SECOND gate from Sol so the player can reach
    # the Vega HUB directly from home without routing through
    # Alpha Centauri. Same warm-gold palette as the AC gate.
    # Positioned at (193, 100) so it sits south of the AC gate
    # in the south-east band — separate from the AC gate's row
    # so the player can visually distinguish two gates.
    JumpPoint(
        id="jump_vega",
        name="Vega Gate",
        char="<",
        fg=(245, 215, 110),
        pos=world.Position(193, 100),
        width=2, height=2,
        connects_to=(("vega", "jump_sol"),),
        description="A humming FTL gate facing Vega's hub system.",
    ),
    # Epsilon Eridani Gate: a THIRD gate from Sol, at the far
    # south-east (193, 128), sitting below Neptune's southern
    # footprint at y=113. Greenish-gold fg contrasts with the
    # AC/Vega gates' warm gold so the player sees a different
    # colour for a different route. This gate opens the deep-
    # space chain (Epsilon Eridani -> Procyon -> Tau Ceti ->
    # Wolf 359 -> Luyten's Star).
    JumpPoint(
        id="jump_epsilon_eridani",
        name="Epsilon Eridani Gate",
        char="<",
        fg=(180, 230, 180),                         # pale greenish — new route
        pos=world.Position(193, 128),
        width=2, height=2,
        connects_to=(("epsilon_eridani", "jump_sol"),),
        description="A humming FTL gate facing Epsilon Eridani — the deep-space corridor.",
    ),
    # 61 Cygni Gate: a FOURTH gate from Sol, opening the North Arm
    # (61 Cygni -> Epsilon Indi -> Groombridge 34). Positioned at the
    # far north edge (100, 5) so it reads as a separate direction from
    # the three east-edge gates. Amber-orange fg matches the K-type
    # palette of the arm's first star. Up-pointing chevron ('^')
    # signals a northward route.
    JumpPoint(
        id="jump_61_cygni",
        name="61 Cygni Gate",
        char="^",
        fg=(255, 180, 90),                          # amber-orange (K-type palette)
        pos=world.Position(100, 5),
        width=2, height=2,
        connects_to=(("cygni", "jump_sol"),),
        description="A humming FTL gate ringing the northern edge of Sol — the North Arm.",
    ),
)


# Star field generated procedurally — unique per system id so
# every system looks distinct. Density is tuned per-system (Sol
# is standard at 0.003).
_stars = solar_module.make_stars(200, 140, seed="sol")


SYSTEM: SolarSystem = SolarSystem(
    id="sol",
    name="Sol",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),                  # no stations near Sol yet (future: Earth Orbital Station)
    stars=_stars,
    enemies=(),
    npc_spawn_chance=0.7,
    npc_spawn_table=(("merchant_hauler", 0.9), ("pirate_scout", 0.4)),
    npc_density=2,
    patrol_density=(3, 4),
)
