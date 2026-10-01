"""Deep-space pirate specs for the uncharted tail systems.

Three new threat classes that only spawn in the systems past Sirius
(Ross 154) and past Groombridge (Lalande 21185) — or on T4 bounty /
bar-mission spawns elsewhere:

* ``pirate_hound`` — fast scout interceptor. High dodge, high
  piloting, moderate punch. Harasses at close range and is a pain
  to pin down; dies fast when caught but chews through shields
  while it dances.
* ``pirate_marauder`` — the T4 line soldier. A cruiser with a
  heavy mixed loadout and a shield + armor kit. The meat of any
  deep-space squad.
* ``pirate_warlord`` — the end-of-arm boss. A frigate with the
  top-shelf arsenal and a recharger-backed shield: it fights to the
  last hull point. Static warlord garrisons guard both deep systems.

All three keep ``comms_warning_range=0`` like the other random
pirates — they engage by proximity, not by hailing first.
"""

from . import NpcShipSpec


NPC_SHIPS: tuple[NpcShipSpec, ...] = (
    NpcShipSpec(
        id="pirate_hound",
        name="Pirate Hound",
        char="s",
        fg=(220, 60, 60),        # pirate family red
        ship_id="scout",
        faction="pirate",
        weapons=("medium_laser", "light_laser"),
        modules=("compact_reactor", "gyro_stabilizer"),
        cargo_goods=("electronics", "fuel_cells", "machine_parts"),
        cargo_count=1,
        band=2,
        skill_weights=(0.25, 0.50, 0.25),
        capture_layout_id="scout_crew",
        loot_budget=(250, 800),
        ai_aggressiveness=85,
        ai_preferred_range=3,
        ai_accuracy_bonus=10,
        ai_dodge_bonus=28,     # the whole point of a hound — hard to hit
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
        char="C",
        fg=(220, 60, 60),      # pirate family red
        ship_id="cruiser",
        faction="pirate",
        weapons=("heavy_laser", "plasma_cannon", "heavy_missile"),
        modules=("shield_mk1", "shield_capacitor", "targeting_computer", "armor_plating"),
        cargo_goods=("weapons_blackmarket", "electronics", "luxury_goods", "rare_earth_metals"),
        cargo_count=3,
        band=3,
        skill_weights=(0.50, 0.25, 0.25),
        capture_layout_id="cruiser_crew",
        loot_budget=(700, 2100),
        ai_aggressiveness=80,
        # Doc 57.2 playtest fix: clears the heavy floor 5 by >1.41.
        ai_preferred_range=7,
        ai_accuracy_bonus=25,
        ai_dodge_bonus=5,
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
        char="F",
        fg=(220, 60, 60),       # pirate family red; flagship = bold render (elite)
        ship_id="frigate",
        faction="pirate",
        elite=True,
        weapons=("heavy_laser", "heavy_missile", "plasma_cannon", "light_laser"),
        # SETTLED 22 (doc 56): the smuggler hold is the cut that makes
        # the kit fit — with it the loadout is 32 cells on the frigate's
        # 30; without it 23/30 and zero combat-math change.
        modules=("shield_mk1", "shield_capacitor", "shield_recharger", "targeting_computer", "armor_plating"),
        cargo_goods=("weapons_blackmarket", "luxury_goods", "rare_earth_metals", "research_data"),
        cargo_count=4,
        band=4,
        skill_weights=(0.34, 0.33, 0.33),
        capture_layout_id="frigate_crew",
        loot_budget=(1400, 4200),
        ai_aggressiveness=90,
        # Doc 57.2 playtest fix: clears the heavy floor 5 by >1.41.
        ai_preferred_range=7,
        ai_accuracy_bonus=35,
        ai_dodge_bonus=10,
        shield_regen_rate=3,    # paid divert below half shields (doc 48 SETTLED 40)
        detect_radius=14,
        comms_warning_range=0,
        comms_lines=(
            "Beyond this arm, I AM the authority.",
            "Every hunter who came for me is out there, drifting with the loot.",
            "You want the treasure? Take it from the wreck I'll make of you.",
        ),
    ),
)