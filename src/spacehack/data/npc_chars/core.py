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
        id="pirate_raider",
        name="Pirate Raider",
        char="r",
        fg=(220, 120, 80),       # pirate family rust (common case)
        faction="pirate",
        hp=20,
        weapon_families=("melee", "pistols"),
        melee_families=("melee",),
        stat_weights=six_weights(0.2834, 0.2833, 0.2833),  # even (SETTLED 35)
        # Doc 48 SETTLED 55/56: light gear — head+hands at the
        # band's fill chance; goods are chance-rolled pocket change.
        worn_armor_slots=("head", "hands"),
        loot_pool=("food_rations", "fuel_cells", "scrap_metal"),
        field_item_loot_pool=(
            ("ammo", "pistol_rounds"),
            ("consumable", "med_pack"),
        ),
        loot_count=(0, 1),
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
        melee_families=("melee",),
        stat_weights=six_weights(0.45, 0.15, 0.25),
        worn_armor_slots=("hands",),  # the shooter's grip (doc 48 SETTLED 55)
        loot_pool=("fuel_cells", "machine_parts", "electronics"),
        # No rifle entries: the family ladder already wields them
        # (wielded weapons drop via the kit path — doc 47.1).
        field_item_loot_pool=(
            ("ammo", "rifle_rounds"),
            ("consumable", "stim"),
        ),
        loot_count=(0, 1),
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
        melee_families=("melee",),
        stat_weights=six_weights(0.10, 0.50, 0.25),
        behavior="hunter",       # it comes to you, ponderously
        squad_size=(1, 2),
        elite=True,
        # Doc 48 SETTLED 55: authored armor 0 — the slab IS the worn
        # body+head set the band rolls for it.
        worn_armor_slots=("body", "head"),
        loot_pool=("machine_parts", "fuel_cells", "scrap_metal"),
        field_item_loot_pool=(
            ("ammo", "rockets"),
            ("consumable", "stim"),
        ),
        loot_count=(0, 1),
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
        melee_families=("melee",),
        stat_weights=six_weights(0.35, 0.30, 0.20),
        behavior="hunter",
        squad_size=(2, 3),
        worn_armor_slots=("body", "hands"),  # the strike kit (doc 48 SETTLED 55)
        loot_pool=("machine_parts",),
        field_item_loot_pool=(
            ("ammo", "rifle_rounds"),
            ("consumable", "med_pack"),
        ),
        loot_count=(0, 1),
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
        melee_families=("melee",),
        stat_weights=six_weights(0.60, 0.10, 0.15),
        behavior="guard",        # perched — holds the sightline, no chase
        squad_size=(1, 1),
        elite=True,
        worn_armor_slots=("head",),  # the scope, nothing else (doc 48 SETTLED 55)
        loot_pool=("machine_parts", "electronics"),
        field_item_loot_pool=(
            ("ammo", "rifle_rounds"),
        ),
        loot_count=(0, 1),
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
        weapons=("kinetic_pistol",),  # fixed light gear — no ladder
        melee_weapons=("combat_knife",),  # the knife it always carried, now its own set
        stat_weights=six_weights(0.0, 0.0, 0.0),  # band-exempt
        # Doc 48 SETTLED 55/56: honest workers — maybe a vest, almost
        # never (the row's low fill mod); their GUARANTEED one good is
        # the outlaw-route incentive.
        worn_armor_slots=("body",),
        worn_fill_mod=0.15,
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
        # Doc 48 SETTLED 56: never a loot source — the bystander is
        # ambient dressing; harming it is crime, not farming.
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
        melee_families=("melee",),
        stat_weights=six_weights(0.30, 0.25, 0.30),
        worn_armor_slots=("body",),  # the vest, maybe (doc 48 SETTLED 55)
        loot_pool=("machine_parts",),
        loot_count=(0, 1),
        xp_reward=18,
    ),
)
