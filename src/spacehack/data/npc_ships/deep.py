"""Deep-space pirate specs for the uncharted tail systems.

Three new threat classes that only spawn in the systems past Sirius
(Ross 154) and past Groombridge (Lalande 21185) — or on T4 bounty /
bar-mission spawns elsewhere:

* ``pirate_hound`` — fast scout interceptor. High dodge, high
  piloting, moderate punch. Harasses at close range and is a pain
  to pin down; dies fast when caught but chews through shields
  while it dances.
* ``pirate_marauder`` — the T4 line soldier. A cruiser with a
  heavy mixed loadout, shield + armor kit, and nearly no surrender
  threshold. The meat of any deep-space squad.
* ``pirate_warlord`` — the end-of-arm boss. A frigate with the
  top-shelf arsenal, a recharger-backed shield, and a 0.02 flee
  threshold: it fights to the last hull point. Static warlord
  garrisons guard both deep systems.

All three keep ``comms_warning_range=0`` like the other random
pirates — they engage by proximity, not by hailing first.
"""

from . import NpcShipSpec


NPC_SHIPS: tuple[NpcShipSpec, ...] = (
    NpcShipSpec(
        id="pirate_hound",
        name="Pirate Hound",
        char="p",
        fg=(255, 90, 90),         # bright red — reads as fast / hot
        ship_id="scout",
        faction="pirate",
        weapons=("medium_laser", "light_laser"),
        modules=("compact_reactor", "gyro_stabilizer"),
        cargo_goods=("electronics", "fuel_cells", "machine_parts"),
        cargo_count=1,
        ai_aggressiveness=85,
        ai_preferred_range=3,
        ai_flee_threshold=0.15,
        ai_accuracy_bonus=10,
        ai_dodge_bonus=28,     # the whole point of a hound — hard to hit
        pilot_gunnery=28,
        pilot_piloting=38,
        pilot_engineering=12,
        min_power_gen=4,
        detect_radius=9,
        comms_warning_range=0,
        comms_lines=(
            "Not fast enough, hunter.",
            "I'll carve the paint off your hull.",
            "The pack doesn't stop for stragglers.",
        ),
    ),
    # --- T4 line soldier: heavy cruiser ---
    NpcShipSpec(
        id="pirate_marauder",
        name="Pirate Marauder",
        char="P",
        fg=(220, 60, 80),    # angry red — heavier than the scout red
        ship_id="cruiser",
        faction="pirate",
        weapons=("heavy_laser", "plasma_cannon", "heavy_missile"),
        modules=("shield_mk1", "shield_capacitor", "targeting_computer", "armor_plating"),
        cargo_goods=("weapons_blackmarket", "electronics", "luxury_goods", "rare_earth_metals"),
        cargo_count=3,
        ai_aggressiveness=80,
        ai_preferred_range=4,
        ai_flee_threshold=0.08,
        ai_accuracy_bonus=25,
        ai_dodge_bonus=5,
        pilot_gunnery=38,
        pilot_piloting=26,
        pilot_engineering=25,
        min_power_gen=6,
        detect_radius=12,
        comms_warning_range=0,
        comms_lines=(
            "This is marauder country. Pay the toll or feed the flares.",
            "You're hauling through MY belt, hunter.",
            "The Warlord sends his regards - take the message personally.",
        ),
    ),
    # --- T4 boss: end-of-arm frigate ---
    NpcShipSpec(
        id="pirate_warlord",
        name="Pirate Warlord",
        char="W",
        fg=(200, 30, 40),       # deep crimson — the boss palette
        ship_id="frigate",
        faction="pirate",
        weapons=("heavy_laser", "heavy_missile", "plasma_cannon", "light_laser"),
        modules=("shield_mk1", "shield_capacitor", "shield_recharger", "targeting_computer", "armor_plating"),
        cargo_goods=("weapons_blackmarket", "luxury_goods", "rare_earth_metals", "research_data"),
        cargo_count=4,
        ai_aggressiveness=90,
        ai_preferred_range=3,
        ai_flee_threshold=0.02,
        ai_accuracy_bonus=35,
        ai_dodge_bonus=10,
        pilot_gunnery=48,
        pilot_piloting=32,
        pilot_engineering=35,
        min_power_gen=8,
        detect_radius=14,
        comms_warning_range=0,
        comms_lines=(
            "Beyond this arm, I AM the authority.",
            "Every hunter who came for me is out there, drifting with the loot.",
            "You want the treasure? Take it from the wreck I'll make of you.",
        ),
    ),
)