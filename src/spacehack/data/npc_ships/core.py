"""NPC ship catalog — the single source for all non-player ships.

Identity doctrine (doc 48 SETTLED 33): glyph = the hull flown (the
player shipyard alphabet — scout `s`, hauler `h`, cruiser `C`,
frigate `F`, freighter `H`; the h/H case pair is the cargo family
(small hauler / big freighter), color = the faction's ONE family color —
pirate red (220,60,60), militia blue (100,200,255), merchant green
(100,220,140); derelicts keep amber/brass. Class twins render
identical by design — weight reads from the hull glyph, faction from
the color, elites from the bold flag.

Pirates migrated from ``data/enemies/pirates.py`` (which is now deleted).
Merchant and civilian specs added alongside them.
"""

from . import NpcShipSpec


NPC_SHIPS: tuple[NpcShipSpec, ...] = (
    # --- Derelicts (boardable, no crew, no movement) ---
    NpcShipSpec(
        id="derelict_scout",
        name="Derelict Scout",
        char="s",
        fg=(200, 160, 80),    # warm amber — visible against dark starfield, distinct from pirate reds/merchant greens
        ship_id="scout",
        faction="neutral",
        is_boardable=True,
        weapons=(),
        modules=(),
        cargo_goods=("food_rations", "fuel_cells"),
        cargo_count=1,
        ai_aggressiveness=0,
        ai_preferred_range=0,
        ai_accuracy_bonus=0,
        ai_dodge_bonus=0,
        detect_radius=0,
        base_speed=0,
        comms_lines=(
            "[DISTRESS BEACON] - Scout ship 'Event Horizon' - hull breach - ",
            "[DISTRESS BEACON] - life support failing - any vessel please respond - ",
            "[DISTRESS BEACON] - automated message - crew status: unknown - ",
        ),
        comms_trigger_viewport=True,   # hail on viewport entry, not at a fixed distance
        comms_warning_range=0,         # no distance-based hail for derelicts
        loot_budget=(400, 1600),
    ),
    NpcShipSpec(
        id="derelict_freighter",
        name="Derelict Freighter",
        char="H",
        fg=(190, 140, 60),    # dull brass — the neutral family's wreck tones (amber/brass)
        ship_id="freighter",
        faction="neutral",
        is_boardable=True,
        weapons=(),
        modules=(),
        cargo_goods=("machine_parts", "fuel_cells", "electronics"),
        cargo_count=2,
        ai_aggressiveness=0,
        ai_preferred_range=0,
        ai_accuracy_bonus=0,
        ai_dodge_bonus=0,
        detect_radius=0,
        base_speed=0,
        comms_lines=(
            "[DISTRESS BEACON] - Freighter 'Goliath' - multiple hull breaches - ",
            "[DISTRESS BEACON] - life support failing - any vessel please respond - ",
            "[DISTRESS BEACON] - automated message - crew status: unknown - ",
        ),
        comms_trigger_viewport=True,   # hail on viewport entry, not at a fixed distance
        comms_warning_range=0,         # no distance-based hail for derelicts
        loot_budget=(1400, 4200),
    ),
    # --- Pirates (migrated from data/enemies/) ---
    NpcShipSpec(
        id="pirate_scout",
        name="Pirate Scout",
        char="s",
        fg=(220, 60, 60),      # pirate family red
        ship_id="scout",
        faction="pirate",
        weapons=("light_laser",),
        modules=("compact_reactor",),
        # Cheap/loose scout: low accuracy, moderate dodge (dodge bonus
        # cut 20 -> 10 so the tutorial bounty / tier-1 scouts read as an
        # easy first kill instead of a kiter; also lowers the glancing
        # threshold via pilot_piloting).
        cargo_goods=("food_rations", "fuel_cells"),
        cargo_count=1,
        band=1,
        skill_weights=(0.25, 0.50, 0.25),
        ai_aggressiveness=60,
        ai_preferred_range=3,
        ai_accuracy_bonus=5,
        ai_dodge_bonus=10,
        capture_layout_id="scout_crew",
        loot_budget=(250, 800),
        detect_radius=8,
        comms_warning_range=0,    # random pirates don't auto-hail — only zone defenders do
        comms_lines=(
            "You're making a mistake, hunter.",
            "I ain't worth the bounty, pal.",
            "Back off or be boarded!",
        ),
    ),
    NpcShipSpec(
        id="pirate_raider",
        name="Pirate Raider",
        char="C",
        fg=(220, 60, 60),      # pirate family red
        ship_id="cruiser",
        faction="pirate",
        weapons=("light_laser", "light_missile"),
        modules=("compact_reactor", "shield_capacitor"),
        # Premium threat: high accuracy, low dodge
        cargo_goods=("electronics", "luxury_goods", "weapons_blackmarket"),
        cargo_count=2,
        band=2,
        skill_weights=(0.50, 0.25, 0.25),
        ai_aggressiveness=75,
        ai_preferred_range=4,
        ai_accuracy_bonus=15,
        ai_dodge_bonus=0,
        detect_radius=10,
        comms_warning_range=0,    # random pirates don't auto-hail — only zone defenders do
        comms_lines=(
            "You've got guts coming after me, hunter.",
            "Name your price. Everyone has one.",
            "Hand over your cargo or we'll take it!",
            "You're in raider space now!",
        ),
        capture_layout_id="cruiser_crew",
        loot_budget=(600, 1800),
    ),
    # --- Militia ---
    NpcShipSpec(
        id="militia_blockade",
        name="Militia Blockade",
        char="C",
        fg=(100, 200, 255),                    # militia family blue
        ship_id="cruiser",
        faction="militia",
        weapons=("light_laser", "light_laser"),
        modules=("shield_mk1", "shield_capacitor", "targeting_computer", "armor_plating"),
        cargo_goods=("food_rations", "fuel_cells", "electronics"),
        cargo_count=2,
        band=2,
        skill_weights=(0.50, 0.25, 0.25),
        capture_layout_id="cruiser_crew",
        loot_budget=(600, 1800),
        ai_aggressiveness=70,
        ai_preferred_range=4,
        # Doc 41 phase 3 tuning (the 30-floor harness): pickets are
        # LIGHT cutters — one is a threat to a normal hauler, ten
        # converging are the level-30 gate. See test_line_tuning.py.
        ai_accuracy_bonus=0,
        ai_dodge_bonus=10,
        detect_radius=7,                         # narrower than comms_warning_range so warning fires first
        comms_warning_range=18,                   # auto-hail at longer range — player can turn back
        comms_lines=(
            "You are entering restricted space. Halt your vessel immediately.",
            "This sector is under federation blockade. Turn back now.",
        ),
        challenge_lines=(
            "Blockade control: a dark transponder is a violation. Identify or be fired upon.",
        ),
    ),
    # --- Pirate Captain (Tier 4 bounty target) ---
    NpcShipSpec(
        id="pirate_captain",
        name="Pirate Captain",
        char="F",
        fg=(220, 60, 60),      # pirate family red; flagship = bold render (elite)
        ship_id="frigate",
        faction="pirate",
        elite=True,
        weapons=("heavy_laser", "heavy_missile", "light_laser"),
        modules=("shield_mk1", "shield_capacitor", "targeting_computer", "armor_plating", "smuggler_hold"),
        cargo_goods=("weapons_blackmarket", "luxury_goods", "electronics"),
        cargo_count=3,
        band=3,
        skill_weights=(0.34, 0.33, 0.33),
        capture_layout_id="frigate_crew",
        loot_budget=(800, 2400),
        # Boss-level threat: high accuracy, moderate dodge
        ai_aggressiveness=85,
        ai_preferred_range=3,
        ai_accuracy_bonus=25,
        ai_dodge_bonus=10,
        detect_radius=12,
        comms_warning_range=0,    # random pirates don't auto-hail — only zone defenders do
        comms_lines=(
            "They sent YOU? I'm insulted.",
            "I am the price on your head, hunter.",
            "I've crushed better ships than yours.",
            "Name your price. Everyone has one.",
        ),
    ),
    # --- Militia Patrols (procedural, system-entry spawn) ---
    NpcShipSpec(
        id="militia_patrol_light",
        name="Militia Scout",
        char="s",
        fg=(100, 200, 255),    # militia family blue — weight reads from the hull glyph
        ship_id="scout",
        faction="militia",
        weapons=("light_laser",),
        modules=("targeting_computer",),
        cargo_goods=("food_rations", "fuel_cells"),
        cargo_count=1,
        band=1,
        skill_weights=(0.25, 0.50, 0.25),
        capture_layout_id="scout_crew",
        loot_budget=(200, 700),
        ai_aggressiveness=60,
        ai_preferred_range=4,
        ai_accuracy_bonus=10,
        ai_dodge_bonus=15,
        detect_radius=6,
        comms_warning_range=15,   # auto-hail window for cargo scans
        comms_lines=(
            "Routine patrol. Hold your course, pilot.",
            "Militia scout on sector sweep. Identify yourself.",
        ),
        challenge_lines=(
            "Unknown contact: your transponder is dark. Identify or be treated as hostile.",
        ),
    ),
    NpcShipSpec(
        id="militia_patrol",
        name="Militia Patrol",
        char="C",
        fg=(100, 200, 255),    # militia family blue
        ship_id="cruiser",
        faction="militia",
        weapons=("heavy_laser", "light_missile"),
        modules=("shield_mk1", "shield_capacitor"),
        cargo_goods=("food_rations", "fuel_cells", "electronics"),
        cargo_count=2,
        band=2,
        skill_weights=(0.50, 0.25, 0.25),
        capture_layout_id="cruiser_crew",
        ai_aggressiveness=70,
        ai_preferred_range=4,
        ai_accuracy_bonus=20,
        ai_dodge_bonus=10,
        detect_radius=7,
        comms_warning_range=18,
        comms_lines=(
            "Militia patrol. Prepare for cargo inspection.",
            "You are entering patrolled space. Halt for scan.",
        ),
        challenge_lines=(
            "Militia patrol to unregistered hull: identify yourself or we open fire.",
        ),
    ),
    NpcShipSpec(
        id="militia_patrol_heavy",
        name="Militia Enforcer",
        char="F",
        fg=(100, 200, 255),    # militia family blue — weight reads from the hull glyph
        ship_id="frigate",
        faction="militia",
        weapons=("heavy_laser", "heavy_missile", "plasma_cannon"),
        modules=("shield_mk1", "shield_capacitor", "targeting_computer", "armor_plating"),
        cargo_goods=("weapons_blackmarket", "electronics", "luxury_goods"),
        cargo_count=2,
        band=3,
        skill_weights=(0.34, 0.33, 0.33),
        capture_layout_id="frigate_crew",
        loot_budget=(600, 1800),
        ai_aggressiveness=80,
        ai_preferred_range=3,
        ai_accuracy_bonus=30,
        ai_dodge_bonus=15,
        detect_radius=8,
        comms_warning_range=20,
        comms_lines=(
            "Enforcer vessel. Halt immediately for deep scan.",
            "High-security zone. Full cargo manifest required.",
        ),
        challenge_lines=(
            "Enforcer to dark contact: identify, or we open fire.",
        ),
    ),
    # --- Merchants ---
    NpcShipSpec(
        id="merchant_hauler",
        name="Merchant Hauler",
        char="h",
        fg=(100, 220, 140),   # merchant family green
        ship_id="hauler",
        faction="merchant",
        weapons=(),
        modules=("expanded_cargo",),
        cargo_goods=("electronics", "machine_parts", "food_rations", "textiles"),
        cargo_count=3,
        band=1,
        skill_weights=(0.20, 0.10, 0.70),
        capture_layout_id="hauler_crew",
        security_drones=0.5,      # the wealth dial (SETTLED 7/38): a lean crew's deck
        loot_budget=(400, 1200),
        # Merchants are non-combat
        ai_aggressiveness=10,
        ai_preferred_range=6,
        ai_accuracy_bonus=0,
        ai_dodge_bonus=0,
        detect_radius=0,
        comms_lines=(
            "Greetings, pilot. Just passing through.",
            "Fair skies and good trading!",
        ),
    ),
    NpcShipSpec(
        id="merchant_freighter",
        name="Merchant Freighter",
        char="H",
        fg=(100, 220, 140),   # merchant family green
        ship_id="freighter",
        faction="merchant",
        weapons=("light_laser", "light_laser"),
        modules=("expanded_cargo", "shield_mk1", "compact_reactor"),
        cargo_goods=("luxury_goods", "electronics", "machine_parts", "food_rations"),
        cargo_count=4,
        band=2,
        skill_weights=(0.20, 0.10, 0.70),
        capture_layout_id="freightliner_crew",
        security_drones=1.0,      # the wealth dial's midpoint (SETTLED 7/38)
        loot_budget=(600, 1800),
        ai_aggressiveness=15,
        ai_preferred_range=5,
        ai_accuracy_bonus=5,
        ai_dodge_bonus=0,
        detect_radius=0,
        comms_lines=(
            "Keep your distance, stranger.",
            "We don't want any trouble.",
        ),
    ),
    NpcShipSpec(
        id="merchant_caravan",
        name="Merchant Caravan",
        char="H",
        fg=(100, 220, 140),   # merchant family green — wealth reads in the hull + droid dial, not color
        ship_id="freighter",
        faction="merchant",
        weapons=("light_laser", "light_laser", "heavy_laser"),
        modules=("expanded_cargo", "shield_mk1", "shield_recharger", "compact_reactor"),
        cargo_goods=("luxury_goods", "electronics", "weapons_blackmarket", "research_data"),
        cargo_count=5,
        band=3,
        skill_weights=(0.20, 0.10, 0.70),
        capture_layout_id="freightliner_crew",
        security_drones=1.5,      # the wealth dial (SETTLED 7/38): a rich convoy runs a dronier deck
        loot_budget=(700, 2100),
        ai_aggressiveness=20,
        ai_preferred_range=5,
        ai_accuracy_bonus=10,
        ai_dodge_bonus=0,
        detect_radius=0,
        comms_lines=(
            "We're armed. Don't try anything.",
            "This cargo is worth more than your ship.",
        ),
    ),
)
