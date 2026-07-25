"""Pirate faction enemy ships — hostile NPCs that patrol solar systems.
"""

from . import AIProfile, EnemySpec

ENEMIES: tuple[EnemySpec, ...] = (
    EnemySpec(
        id="pirate_scout",
        name="Pirate Scout",
        char="p",
        fg=(255, 100, 100),
        ship_id="scout",
        weapons=("light_laser",),
        modules=("compact_reactor",),
        # Persona: cheap/loose scout. Lower accuracy_bonus
        # (positive but not enough to compensate for the +5
        # gunnery base below other AI) and a high dodge_bonus
        # so player shots against scouts miss often unless the
        # player charges in and forces a close shot. Feels
        # appropriately "nervous."
        ai=AIProfile(
            aggressiveness=60,
            preferred_range=3,
            flee_threshold=0.15,
            accuracy_bonus=5,
            dodge_bonus=20,
        ),
        detect_radius=8,
        min_power_gen=3,
        pilot_skills={"gunnery": 15, "piloting": 20, "engineering": 10},
    ),
    EnemySpec(
        id="pirate_raider",
        name="Pirate Raider",
        char="P",
        fg=(220, 60, 60),
        ship_id="cruiser",
        weapons=("light_laser", "light_missile"),
        modules=("compact_reactor", "shield_capacitor"),
        # Persona: premium/threatening. accuracy_bonus so the
        # raider lands hits even at long range; dodge_bonus
        # deliberately low so the player can take return shots
        # predictably. Combined with the cruiser hull (50 base
        # vs scout's 20), this should feel like a step-up
        # difficulty tier.
        ai=AIProfile(
            aggressiveness=75,
            preferred_range=4,
            flee_threshold=0.10,
            accuracy_bonus=15,
            dodge_bonus=0,
        ),
        detect_radius=10,
        min_power_gen=4,
        pilot_skills={"gunnery": 25, "piloting": 18, "engineering": 15},
    ),
)
