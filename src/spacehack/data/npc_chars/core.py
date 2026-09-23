"""NPC character catalog — pirate raiders and city pedestrians.

Derelict-boarder raiders scavenge ruined ships, tied to the
``pirate`` faction so their hostility is driven by faction reputation
rather than a hardcoded flag. The civilian/militia templates anchor the
Earth ambient population (``data/city_npcs.py``) — they are non-hostile
by default and fight only as the faction rules dictate.

Additional NPC char types (mercenaries, colonists) can be added as new
entries in the ``NPC_CHARS`` tuple.
"""

from . import NpcCharSpec, six_weights


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
        weapon_families=("melee", "pistols"),
        stat_weights=six_weights(0.25, 0.40, 0.20),
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
        weapon_families=("pistols",),
        stat_weights=six_weights(0.45, 0.15, 0.25),
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
        weapon_families=("melee", "pistols"),
        stat_weights=six_weights(0.2834, 0.2833, 0.2833),  # even (SETTLED 35)
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
        weapon_families=("rifles",),   # a real rifleman under the ladder (SETTLED 13)
        stat_weights=six_weights(0.45, 0.15, 0.25),
        tier=2,
        loot_pool=("fuel_cells", "machine_parts", "electronics"),
        # No rifle entries: the family ladder already wields them
        # (wielded weapons drop via the kit path — doc 47.1).
        equipment_loot_pool=(
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
        # The band-3/4 heavy face (SETTLED 13/35): slow, explosive,
        # strength/stamina-heavy and reflexes-poor — the slow-heavy-
        # hunter matrix cell. Bold `R`: the family's serious case,
        # elite-flagged (SETTLED 34/35).
        id="pirate_brute",
        name="Pirate Brute",
        char="R",
        fg=(220, 120, 80),       # pirate family rust (bold serious case)
        faction="pirate",
        hp=34,
        weapon_families=("explosive",),  # grenade -> rocket as bands climb
        stat_weights=six_weights(0.10, 0.50, 0.25),
        behavior="hunter",       # it comes to you, ponderously
        squad_size=(1, 2),
        elite=True,
        tier=3,
        armor=2,
        loot_pool=("machine_parts", "fuel_cells", "scrap_metal"),
        equipment_loot_pool=(
            ("armor", "heavy_vest"),
            ("armor", "visor_helmet"),
        ),
        field_item_loot_pool=(
            ("ammo", "rockets"),
            ("consumable", "stim"),
        ),
        loot_count=(1, 2),
        xp_reward=45,
        ap=3,
    ),
    NpcCharSpec(
        # The strike-crew face (SETTLED 10/13): organized, well
        # equipped, fights as a unit — squad_size carries the pack
        # feel until the tactics wave (phase 5).
        id="militia_marine",
        name="Militia Marine",
        char="M",                # militia family serious case
        fg=(100, 200, 255),      # militia family blue (matches the fleet)
        faction="militia",
        hp=28,
        weapon_families=("rifles", "pistols"),
        stat_weights=six_weights(0.35, 0.30, 0.20),
        behavior="hunter",
        squad_size=(2, 3),
        tier=2,
        armor=1,
        loot_pool=("machine_parts",),
        equipment_loot_pool=(
            ("armor", "reinforced_gauntlets"),
            ("weapon", "stun_baton"),
        ),
        field_item_loot_pool=(
            ("ammo", "rifle_rounds"),
            ("consumable", "med_pack"),
        ),
        loot_count=(1, 1),
        xp_reward=30,
    ),
    NpcCharSpec(
        # The heavy-hitting precision row (SETTLED 10/18): a perched
        # guard that holds sightlines — precision, not the pirate
        # heavy's explosive profile. Bold `M`; rifles PINNED to the
        # window's top (SETTLED 35: the railgun at band 4 is the
        # precision payoff).
        id="militia_sniper",
        name="Militia Sniper",
        char="M",
        fg=(100, 200, 255),      # militia family blue (bold serious case)
        faction="militia",
        hp=24,
        weapon_families=("rifles",),
        pin_window_top=True,
        stat_weights=six_weights(0.60, 0.10, 0.15),
        behavior="guard",        # perched — holds the sightline, no chase
        squad_size=(1, 1),
        elite=True,
        tier=4,
        armor=1,
        loot_pool=("machine_parts", "electronics"),
        field_item_loot_pool=(
            ("ammo", "rifle_rounds"),
        ),
        loot_count=(1, 1),
        xp_reward=40,
    ),
    NpcCharSpec(
        # The honest working crew (doc 48 SETTLED 5/7/38): everyday
        # joes — light gear, band-exempt, no difficulty axis. A deck's
        # defense is its droid complement (the CREW_ROLES dial), never
        # these hands.
        id="merchant",
        name="Merchant",
        char="h",                # merchant family letter (SETTLED 38)
        fg=(100, 220, 140),      # merchant family green (matches the fleet)
        faction="merchant",
        hp=16,
        weapons=("kinetic_pistol", "combat_knife"),  # fixed light gear — no ladder
        stat_weights=six_weights(0.0, 0.0, 0.0),  # band-exempt
        tier=1,
        loot_pool=("food_rations", "textiles"),
        loot_count=(1, 1),
        xp_reward=12,
    ),
    NpcCharSpec(
        id="civilian_bystander",
        name="Civilian Bystander",
        char="c",
        fg=(235, 215, 175),       # warm civilian clothing
        faction="civilian",
        hp=15,
        weapon_families=("melee",),
        stat_weights=six_weights(0.0, 0.0, 0.0),  # band-exempt (SETTLED 14)
        tier=1,
        loot_pool=("food_rations",),
        loot_count=(1, 1),
        xp_reward=8,
    ),
    NpcCharSpec(
        id="militia_trooper",
        name="Militia Trooper",
        char="m",                # militia family common case (SETTLED 34/35)
        fg=(100, 200, 255),      # militia family blue (matches the fleet)
        faction="militia",
        hp=26,
        weapon_families=("pistols", "melee"),
        stat_weights=six_weights(0.30, 0.25, 0.30),
        tier=1,
        armor=1,
        loot_pool=("machine_parts",),
        loot_count=(1, 1),
        xp_reward=18,
    ),
)
