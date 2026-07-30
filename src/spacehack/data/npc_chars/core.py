"""NPC character catalog — pirate raiders for derelict boarding.

These are hostile NPCs that scavenge derelict ships, tied to the
``pirate`` faction so their hostility is driven by faction reputation
rather than a hardcoded flag.

Additional NPC char types (militia troops, mercenaries, colonists)
can be added as new entries in the ``NPC_CHARS`` tuple.
"""

from . import NpcCharSpec


NPC_CHARS: tuple[NpcCharSpec, ...] = (
    NpcCharSpec(
        id="pirate_raider",
        name="Pirate Raider",
        char="r",
        fg=(220, 120, 80),       # rust-orange — salvager gear
        faction="pirate",
        hp=20,
        weapon_pick=("combat_knife", "kinetic_pistol"),  # 50/50 melee vs ranged
        reflexes=8,
        strength=12,
        stamina=10,
        detect_radius=4,
        loot_pool=("food_rations", "fuel_cells", "scrap_metal"),
        loot_count=(1, 2),
        xp_reward=20,
    ),
    NpcCharSpec(
        id="pirate_rifleman",
        name="Pirate Rifleman",
        char="R",
        fg=(200, 80, 80),         # faded red — hardened fighter
        faction="pirate",
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
