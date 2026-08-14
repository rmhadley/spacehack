"""Dungeon monster catalog — non-sentient hostile fauna and drones.

Every monster sets ``always_hostile=True`` and ``faction=""`` so it
fights on sight regardless of faction reputation and killing one
changes no reputation score (``_COMBAT_KILL_DELTAS.get("", {})`` is
a no-op). Behavior + squad size drive out-of-combat movement and
procedural dungeon population. ``tier`` gates equipment drops and
``armor`` is flat DR the player must punch through (plasma halves it).

Design doc: ``docs/design/in_progress/11_DESIGN_DUNGEON_MONSTERS.md``
"""

from . import NpcCharSpec

NPC_CHARS: tuple[NpcCharSpec, ...] = (
    NpcCharSpec(
        id="rock_scavenger",
        name="Rock Scavenger",
        char="s",
        fg=(205, 170, 120),       # sandy rock-grey — desert/rock fauna
        faction="",
        hp=14,
        weapons=("monster_claws",),
        reflexes=10,
        strength=12,
        stamina=10,
        detect_radius=4,
        behavior="hunter",
        squad_size=(3, 5),        # swarmer — always hunts in packs
        always_hostile=True,
        tier=1,
        loot_pool=("scrap_metal",),
        equipment_loot_pool=(
            ("weapon", "survival_axe"),
            ("weapon", "combat_knife"),
            ("armor", "tactical_gloves"),
        ),
        loot_count=(1, 2),
        xp_reward=10,
    ),
    NpcCharSpec(
        id="sentry_drone",
        name="Sentry Drone",
        char="d",
        fg=(150, 185, 255),       # cold blue-white — security lighting
        faction="",
        hp=18,
        weapons=("drone_laser",),
        reflexes=14,
        strength=10,
        stamina=12,
        detect_radius=6,
        behavior="guard",         # holds position, fires at range
        squad_size=(1, 1),
        always_hostile=True,
        tier=2,
        armor=1,
        loot_pool=("electronics", "machine_parts"),
        equipment_loot_pool=(
            ("armor", "light_helmet"),
            ("armor", "heavy_helmet"),
            ("armor", "reinforced_gauntlets"),
            ("weapon", "smg"),
        ),
        field_item_loot_pool=(
            ("ammo", "energy_cells"),
            ("consumable", "med_pack"),
        ),
        loot_count=(1, 2),
        xp_reward=25,
    ),
    NpcCharSpec(
        id="ice_worm",
        name="Ice Worm",
        char="w",
        fg=(185, 220, 245),       # pale ice-blue — cold-cave ambusher
        faction="",
        hp=26,
        weapons=("monster_claws",),
        reflexes=12,
        strength=32,              # claws 3 + 3 = 6 per hit
        stamina=14,
        detect_radius=5,
        behavior="ambusher",      # holds still, bursts out on approach
        squad_size=(1, 2),
        always_hostile=True,
        tier=1,
        loot_pool=("scrap_metal", "research_data"),
        loot_count=(1, 1),
        xp_reward=20,
    ),
    NpcCharSpec(
        id="dust_prowler",
        name="Dust Prowler",
        char="p",
        fg=(215, 130, 90),        # red-brown — fast desert predator
        faction="",
        hp=22,
        weapons=("monster_claws",),
        reflexes=13,
        strength=18,
        stamina=12,
        detect_radius=5,
        behavior="hunter",        # fast, aggressive single/duo hunter
        squad_size=(1, 2),
        always_hostile=True,
        tier=1,
        loot_pool=("scrap_metal", "food_rations"),
        loot_count=(1, 2),
        xp_reward=18,
    ),
    NpcCharSpec(
        id="assault_drone",
        name="Assault Drone",
        char="D",
        fg=(200, 170, 110),       # bronze armor — heavy security frame
        faction="",
        hp=34,
        weapons=("monster_claws",),
        reflexes=10,
        strength=25,              # slow but hits hard (claws 3 + 2 = 5)
        stamina=16,
        detect_radius=5,
        behavior="guard",         # armored bruiser — holds its post
        squad_size=(1, 1),
        always_hostile=True,
        tier=3,
        armor=3,
        loot_pool=("electronics", "machine_parts", "ship_components"),
        equipment_loot_pool=(
            ("armor", "heavy_vest"),
            ("armor", "visor_helmet"),
            ("armor", "powered_gloves"),
            ("weapon", "vibroblade"),
        ),
        field_item_loot_pool=(
            ("ammo", "energy_cells"),
            ("consumable", "stim"),
        ),
        loot_count=(1, 2),
        xp_reward=30,
    ),
    NpcCharSpec(
        id="frost_spitter",
        name="Frost Spitter",
        char="f",
        fg=(170, 210, 250),       # pale frost blue — ice-cave harasser
        faction="",
        hp=20,
        weapons=("frost_bolt",),
        reflexes=13,
        strength=10,
        stamina=12,
        field_item_loot_pool=(
            ("ammo", "energy_cells"),
            ("consumable", "med_pack"),
        ),
        detect_radius=6,
        behavior="hunter",        # ranged harasser, hunts in pairs/trios
        squad_size=(2, 3),
        always_hostile=True,
        tier=2,
        loot_pool=("research_data", "electronics"),
        loot_count=(1, 2),
        xp_reward=25,
    ),
    NpcCharSpec(
        id="hull_parasite",
        name="Hull Parasite",
        char="m",
        fg=(175, 140, 190),       # sickly mauve — alien stowaway
        faction="",
        hp=16,
        weapons=("parasite_mandibles",),
        reflexes=12,
        strength=12,
        stamina=10,
        detect_radius=4,
        behavior="ambusher",      # lurks in derelicts, bursts out on approach
        squad_size=(2, 4),
        always_hostile=True,
        tier=1,
        loot_pool=("scrap_metal", "research_data"),
        loot_count=(1, 1),
        xp_reward=15,
    ),
)
