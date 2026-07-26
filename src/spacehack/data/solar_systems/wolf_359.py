"""Wolf 359 — a dim red dwarf system on the frontier of charted
space. Dangerous. Pirates patrol the dark between the sparse
planets. The last gate before Luyten's Star.

Wolf 359 is one of the faintest stars in Earth's night sky at
~7.8 ly distance. In this universe it marks the boundary between
the relative safety of the inner federation systems and the
uncharted deep beyond Luyten's Star.

The star is a small dim red dwarf (7x7 footprint). Only a few
barren rocky worlds orbit here. The system's main feature is its
pirate presence — a well-armed squad patrols near the jump gates,
ambushing traders on the Tau Ceti / Luyten's Star run.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import EnemySpawn, JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Wolf 359 — dim red dwarf, 7x7 footprint. Small, faint,
    # menacing palette.
    solar_module.Planet(
        id="sun", name="Wolf 359",
        char="O", fg=(255, 80, 50),                  # deep cool red
        pos=world.Position(100, 70), width=7, height=7,
        sun=True,
        description="A dim red dwarf — one of the faintest stars in the sky.",
    ),
    # A single barren rocky world — dark, airless.
    solar_module.Planet(
        id="wolf_b", name="Wolf 359 b",
        char="p", fg=(80, 60, 50),                   # very dim brown
        pos=world.Position(55, 55), width=2, height=2,
        description="A dark, airless rock barely reflecting the star's dim glow.",
    ),
)


# Two Jump Points — west to Tau Ceti, east to Luyten's Star.
_jump_points: tuple[JumpPoint, ...] = (
    JumpPoint(
        id="jump_tau_ceti",
        name="Tau Ceti Gate",
        char=">",
        fg=(255, 235, 140),                          # golden-yellow (Tau Ceti palette)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(( "tau_ceti", "jump_wolf_359"),),
        description="A humming FTL gate facing Tau Ceti.",
    ),
    JumpPoint(
        id="jump_luyten_star",
        name="Luyten's Star Gate",
        char="<",
        fg=(220, 180, 130),                          # warm brownish (dim star palette)
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(( "luyten_star", "jump_wolf_359"),),
        description="A humming FTL gate facing Luyten's Star.",
    ),
)


# Pirate presence — two raider ships patrolling the corridor
# between the gates, so the player can't simply hug one gate
# to avoid detection entirely. A third scout roams near the
# Luyten's Star gate.
_enemies: tuple[EnemySpawn, ...] = (
    EnemySpawn(
        enemy_id="pirate_scout",
        pos=world.Position(60, 55),                  # near the rocky planet
        patrol_radius=8,
        squad_id="wolf_pirate_patrol_1",
    ),
    EnemySpawn(
        enemy_id="pirate_scout",
        pos=world.Position(140, 85),                 # mid-point between gates
        patrol_radius=8,
        squad_id="wolf_pirate_patrol_1",
    ),
    EnemySpawn(
        enemy_id="pirate_scout",
        pos=world.Position(175, 60),                 # near Luyten's gate
        patrol_radius=6,
        squad_id="wolf_pirate_patrol_2",
    ),
)


_stars: tuple[tuple[int, int], ...] = (
    # Sparser stars than inner systems — Wolf 359 is a dim
    # star in a dim neighbourhood. Fewer stars make it feel
    # isolated and dangerous.
    # North edge
    (15, 8), (35, 12), (55, 6), (75, 11),
    (110, 5), (135, 7), (160, 10), (185, 12),
    # South edge
    (20, 130), (45, 125), (70, 135), (95, 132),
    (120, 138), (150, 130), (175, 128),
    # Side gutters
    (5, 35), (5, 55), (5, 95), (5, 110),
    (190, 35), (190, 55), (190, 95), (190, 110),
    # Sparse mid-system
    (25, 40), (85, 25), (155, 30),
    (35, 105), (95, 105), (155, 100),
    (50, 80), (120, 45), (165, 80),
    # Gate vicinity
    (8, 65), (8, 78), (4, 73), (15, 60), (15, 80),
    (188, 65), (188, 78), (195, 73), (193, 60), (193, 80),
)


SYSTEM: SolarSystem = SolarSystem(
    id="wolf_359",
    name="Wolf 359",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),
    stars=_stars,
    enemies=_enemies,
)
