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
)


# Static star sprinkle positions for Sol.  Same set as the
# historical in-line ``STARS`` so we preserve the look the player
# is used to. New rows added near the eastern Jump Point so the
# gate isn't sitting in pure void.
_stars: tuple[tuple[int, int], ...] = (
    # North edge
    (5, 5), (15, 8), (25, 3), (35, 9), (45, 2), (55, 7), (65, 4), (75, 9),
    # South edge
    (8, 45), (18, 50), (32, 41), (38, 47), (52, 39), (58, 44), (68, 49), (78, 41),
    # Side gutters
    (2, 15), (2, 32), (72, 15), (72, 38), (78, 22),
    # Scattered middle
    (10, 11), (24, 49), (54, 49), (60, 11),
    (7, 23), (73, 23), (7, 35), (73, 35),
    (45, 42), (35, 51), (45, 51),
    (20, 25), (60, 25), (10, 5), (50, 7),
    (38, 14), (42, 38), (22, 14), (55, 16),
    # Far edges on the wider 200x140 regions (the map
    # grew ~2.5x larger when planets went multi-cell). The original
    # still fit; this block fills the new far-east / far-west /
    # far-south bands so the void doesn't read as empty away from
    # the launch planet. Planet cells overwrite any accidental
    # overlap in :func:`make_solar_system`.
    (85, 4), (95, 9), (110, 3), (122, 8), (138, 4), (152, 7),
    (175, 3), (188, 8), (195, 9),
    (5, 60), (12, 75), (24, 88), (38, 110), (52, 128), (66, 132),
    (74, 138), (88, 125), (102, 130), (118, 122), (134, 138),
    (150, 130), (165, 132), (180, 125), (192, 135),
    (90, 65), (105, 78), (88, 88), (102, 95), (118, 108),
    (122, 65), (138, 85), (155, 88), (148, 110), (175, 115),
    (180, 80), (190, 60), (195, 95), (188, 30), (192, 50),
    (8, 18), (8, 28), (188, 18), (188, 28),
    (50, 70), (75, 70), (95, 115), (165, 50), (40, 60),
    (110, 50), (130, 60), (50, 18), (80, 85),
    # A few sparkle stars near the Jump Point so the gate isn't in
    # a black void.
    (188, 65), (188, 78), (195, 73), (193, 60), (193, 80),
)


SYSTEM: SolarSystem = SolarSystem(
    id="sol",
    name="Sol",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),                  # no stations near Sol yet (future: Earth Orbital Station)
    stars=_stars,
    # Two pirate ships between Earth (140, 39) and Mars (60, 99)
    # grouped as a single squad via ``squad_id`` so the player
    # faces both in a single combat encounter whenever either is
    # detected (the squad is a logical unit, not a per-spawn
    # proximity check). Without the shared ``squad_id`` only
    # whichever scout is within detect_radius on the trigger
    # frame would engage, leaving the other stranded.
    enemies=(
        EnemySpawn(
            enemy_id="pirate_scout",
            pos=world.Position(100, 69),
            patrol_radius=4,
            squad_id="sol_pirate_patrol_1",
        ),
        EnemySpawn(
            enemy_id="pirate_scout",
            pos=world.Position(105, 66),
            patrol_radius=4,
            squad_id="sol_pirate_patrol_1",
        ),
    ),
)
