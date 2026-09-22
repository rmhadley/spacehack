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
        # The merchants chain's antagonist: the consortium's claims
        # enforcement crews (ground side of the heat system's squads).
        # faction="consortium" since doc 48 phase 2 — the hidden axis
        # (start −100) keeps them hostile on sight exactly as the old
        # pirate tag read; the hired-pirate fiction retires in phase 11.
        id="consortium_enforcer",
        name="Consortium Enforcer",
        char="E",
        fg=(90, 120, 200),       # consortium family navy (serious case)
        faction="consortium",
        hp=22,
        weapon_pick=("combat_knife", "kinetic_pistol"),
        reflexes=12,
        strength=16,
        stamina=14,
        detect_radius=5,
        behavior="hunter",
        tier=1,
        loot_pool=("electronics", "machine_parts", "scrap_metal"),
        equipment_loot_pool=(
            ("armor", "light_helmet"),
        ),
        field_item_loot_pool=(
            ("ammo", "pistol_rounds"),
            ("consumable", "med_pack"),
        ),
        loot_count=(1, 2),
        xp_reward=22,
    ),
    NpcCharSpec(
        # Ranged guard: HOLDS the room it spawns in and fires at range
        # — the artillery cell of the behavior matrix (doc 34), arrived
        # via content. Counter-play: break LOS or fight inside its blind
        # arc; it will not chase.
        id="consortium_gunner",
        name="Consortium Gunner",
        char="e",
        fg=(90, 120, 200),       # consortium family navy (common case)
        faction="consortium",
        hp=28,
        weapons=("kinetic_pistol",),
        reflexes=14,
        strength=12,
        stamina=16,
        detect_radius=6,
        behavior="guard",
        tier=2,
        loot_pool=("electronics", "machine_parts", "fuel_cells"),
        equipment_loot_pool=(
            ("weapon", "kinetic_rifle"),
            ("armor", "reinforced_gauntlets"),
        ),
        field_item_loot_pool=(
            ("ammo", "rifle_rounds"),
            ("consumable", "stim"),
        ),
        loot_count=(1, 2),
        xp_reward=38,
    ),
    NpcCharSpec(
        id="pirate_raider",
        name="Pirate Raider",
        char="r",
        fg=(220, 120, 80),       # pirate family rust (common case)
        faction="pirate",
        hp=20,
        weapon_pick=("combat_knife", "kinetic_pistol"),  # 50/50 melee vs ranged
        reflexes=12,
        strength=16,
        stamina=14,
        detect_radius=4,
        tier=1,
        loot_pool=("food_rations", "fuel_cells", "scrap_metal"),
        # wielded weapons arrive as kit drops (doc 47.1) — pool is
        # beyond-the-weapon extras only
        equipment_loot_pool=(
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
        fg=(220, 120, 80),       # pirate family rust (serious case)
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
        id="civilian_bystander",
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
        char="M",                # re-cases to `m` at phase 4 with the marine
        fg=(100, 200, 255),      # militia family blue (matches the fleet)
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
