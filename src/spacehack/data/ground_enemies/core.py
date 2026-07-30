"""Ground enemy catalog — derelict scavengers and guards.

Two starter enemies for the derelict scout. Used by dungeon layouts
via ENEMY: directives.
"""

from . import GroundEnemySpec


WARES: tuple[GroundEnemySpec, ...] = (
    GroundEnemySpec(
        id="derelict_scavenger",
        name="Derelict Scavenger",
        char="s",
        fg=(200, 150, 100),       # warm amber — reads as feral/ferrous
        hp=20,
        weapon_pick=("combat_knife", "kinetic_pistol"),   # 50/50 melee vs ranged
        reflexes=8,
        strength=12,
        stamina=10,
        detect_radius=4,
        loot_pool=("food_rations", "fuel_cells", "scrap_metal"),
        loot_count=(1, 2),
        xp_reward=20,
    ),
    GroundEnemySpec(
        id="derelict_guard",
        name="Derelict Guard",
        char="g",
        fg=(150, 200, 150),       # muted green — faded uniform
        hp=30,
        weapons=("kinetic_pistol",),
        reflexes=10,
        strength=10,
        stamina=12,
        detect_radius=5,
        loot_pool=("fuel_cells", "machine_parts", "electronics"),
        loot_count=(1, 2),
        xp_reward=35,
    ),
)
