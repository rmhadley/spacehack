"""NPC character catalog — pirate raiders and city pedestrians.

Derelict-boarder raiders scavenge ruined ships, tied to the
``pirate`` faction so their hostility is driven by faction reputation
rather than a hardcoded flag. The civilian/militia templates anchor the
Earth ambient population (``data/city_npcs.py``) — they are non-hostile
by default and fight only as the faction rules dictate.

Additional NPC char types (mercenaries, colonists) can be added as new
entries in the ``NPC_CHARS`` tuple.
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
        reflexes=12,
        strength=16,
        stamina=14,
        detect_radius=4,
        tier=1,
        loot_pool=("food_rations", "fuel_cells", "scrap_metal"),
        equipment_loot_pool=(
            ("weapon", "combat_knife"),
            ("weapon", "kinetic_pistol"),
            ("armor", "light_helmet"),
        ),
        field_item_loot_pool=(
            ("ammo", "pistol_rounds"),
            ("consumable", "med_pack"),
        ),
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
        reflexes=14,
        strength=12,
        stamina=16,
        detect_radius=5,
        tier=2,
        loot_pool=("fuel_cells", "machine_parts", "electronics"),
        equipment_loot_pool=(
            ("weapon", "kinetic_rifle"),
            ("weapon", "stun_baton"),
            ("armor", "reinforced_gauntlets"),
        ),
        field_item_loot_pool=(
            ("ammo", "rifle_rounds"),
            ("consumable", "stim"),
        ),
        loot_count=(1, 2),
        xp_reward=35,
    ),
    NpcCharSpec(
        id="civillian_bystander",
        name="Civilian Bystander",
        char="c",
        fg=(235, 215, 175),       # warm civilian clothing
        faction="civilian",
        hp=15,
        weapon_pick=("combat_knife",),  # can defend if forced
        reflexes=8,
        strength=8,
        stamina=10,
        detect_radius=3,
        tier=1,
        loot_pool=("food_rations",),
        loot_count=(1, 1),
        xp_reward=8,
    ),
    NpcCharSpec(
        id="militia_trooper",
        name="Militia Trooper",
        char="M",
        fg=(120, 200, 255),       # security blue fatigues
        faction="militia",
        hp=26,
        weapon_pick=("kinetic_pistol", "combat_knife"),
        reflexes=13,
        strength=12,
        stamina=14,
        detect_radius=4,
        tier=1,
        armor=1,
        loot_pool=("machine_parts",),
        loot_count=(1, 1),
        xp_reward=18,
    ),
)
