"""NPC ship catalog — the single source for all non-player ships.

Pirates migrated from ``data/enemies/pirates.py`` (which is now deleted).
Merchant and civilian specs added alongside them.
"""

from . import NpcShipSpec


NPC_SHIPS: tuple[NpcShipSpec, ...] = (
    # --- Pirates (migrated from data/enemies/) ---
    NpcShipSpec(
        id="pirate_scout",
        name="Pirate Scout",
        char="p",
        fg=(255, 100, 100),
        ship_id="scout",
        faction="pirate",
        weapons=("light_laser",),
        modules=("compact_reactor",),
        # Cheap/loose scout: low accuracy, high dodge
        cargo_goods=("food_rations", "fuel_cells"),
        cargo_count=1,
        ai_aggressiveness=60,
        ai_preferred_range=3,
        ai_flee_threshold=0.15,
        ai_accuracy_bonus=5,
        ai_dodge_bonus=20,
        pilot_gunnery=15,
        pilot_piloting=20,
        pilot_engineering=10,
        min_power_gen=3,
        detect_radius=8,
        comms_lines=(
            "Back off or be boarded!",
            "This is our space, pilot!",
        ),
    ),
    NpcShipSpec(
        id="pirate_raider",
        name="Pirate Raider",
        char="P",
        fg=(220, 60, 60),
        ship_id="cruiser",
        faction="pirate",
        weapons=("light_laser", "light_missile"),
        modules=("compact_reactor", "shield_capacitor"),
        # Premium threat: high accuracy, low dodge
        cargo_goods=("electronics", "luxury_goods", "weapons_blackmarket"),
        cargo_count=2,
        ai_aggressiveness=75,
        ai_preferred_range=4,
        ai_flee_threshold=0.10,
        ai_accuracy_bonus=15,
        ai_dodge_bonus=0,
        pilot_gunnery=25,
        pilot_piloting=18,
        pilot_engineering=15,
        min_power_gen=4,
        detect_radius=10,
        comms_lines=(
            "Hand over your cargo or we'll take it!",
            "You're in raider space now!",
        ),
    ),
    # --- Militia ---
    NpcShipSpec(
        id="militia_blockade",
        name="Militia Blockade",
        char="B",
        fg=(130, 230, 220),                    # teal — distinct from pirate red/merchant green
        ship_id="cruiser",
        faction="militia",
        weapons=("heavy_laser", "light_missile"),
        modules=("shield_mk1", "shield_capacitor", "targeting_computer", "armor_plating"),
        cargo_goods=("food_rations", "fuel_cells", "electronics"),
        cargo_count=2,
        ai_aggressiveness=70,
        ai_preferred_range=4,
        ai_flee_threshold=0.05,                 # militia fights to nearly the end
        ai_accuracy_bonus=20,
        ai_dodge_bonus=10,
        pilot_gunnery=35,
        pilot_piloting=25,
        pilot_engineering=25,
        min_power_gen=5,
        detect_radius=7,                         # narrower than comms_warning_range so warning fires first
        comms_warning_range=18,                   # auto-hail at longer range — player can turn back
        comms_lines=(
            "You are entering restricted space. Halt your vessel immediately.",
            "This sector is under federation blockade. Turn back now.",
        ),
    ),
    # --- Merchants ---
    NpcShipSpec(
        id="merchant_hauler",
        name="Merchant Hauler",
        char="M",
        fg=(100, 220, 140),
        ship_id="hauler",
        faction="merchant",
        weapons=(),
        modules=(),
        cargo_goods=("electronics", "machine_parts", "food_rations", "textiles"),
        cargo_count=3,
        # Merchants are non-combat — flee threshold at 0.8
        ai_aggressiveness=10,
        ai_preferred_range=6,
        ai_flee_threshold=0.80,
        ai_accuracy_bonus=0,
        ai_dodge_bonus=0,
        pilot_gunnery=10,
        pilot_piloting=15,
        pilot_engineering=10,
        min_power_gen=3,
        detect_radius=0,
        comms_lines=(
            "Greetings, pilot. Just passing through.",
            "Fair skies and good trading!",
        ),
    ),
)
