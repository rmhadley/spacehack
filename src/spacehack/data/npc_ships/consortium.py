"""Consortium hunt ships (doc 48 phase 11, SETTLED 50/52/54).

Two silhouettes, unmistakable in the navy family color: the pursuit
CRUISER and the bold frigate ANCHOR. They exist ONLY inside the two
hunt beats — the q3 roaming squads and the q6 guarded wreck — never
in any system's ``npc_spawn_table`` (SETTLED 12's authored-only
exposure guard; pinned by test). Boarding one ships a consortium
deck through ``CREW_ROLES`` (SETTLED 51's exposure surface).

Flown gear floors at modded (``quality_floor=1``, SETTLED 52): what
you strip from a captured hunter is premium loot by construction.
"""

from . import NpcShipSpec


NPC_SHIPS: tuple[NpcShipSpec, ...] = (
    NpcShipSpec(
        id="consortium_hunter",
        name="Consortium Hunter",
        char="C",
        fg=(90, 120, 200),       # consortium family navy
        ship_id="cruiser",
        faction="consortium",
        band=2,
        # The pursuit read (SETTLED 52): piloting-biased like the
        # interceptors — they close and stay on you.
        skill_weights=(0.25, 0.50, 0.25),
        quality_floor=1,
        weapons=("heavy_laser", "light_missile"),
        # The military suite, existing ids only (SETTLED 52).
        modules=("shield_mk1", "shield_capacitor", "targeting_computer",
                 "gyro_stabilizer"),
        capture_layout_id="cruiser_crew",
        loot_budget=(600, 1800),
        ai_aggressiveness=70,
        # Doc 57 SETTLED 2: clears the rack floor (light_missile 4) by
        # >1.41 — 6 stops every approach outside the bench, so the rack
        # never sits out (the raider-never-fires lesson; the b2
        # raider/patrol precedent).
        ai_preferred_range=6,
        detect_radius=12,
        comms_warning_range=0,   # hunters never hail; they hunt
        comms_lines=(),          # dark corporate hulls answer nothing
    ),
    NpcShipSpec(
        id="consortium_dreadnought",
        name="Consortium Dreadnought",
        char="F",
        fg=(90, 120, 200),       # consortium family navy; the anchor = bold render
        ship_id="frigate",
        faction="consortium",
        elite=True,
        band=3,
        # Balanced flagship weights (SETTLED 52), the captain class.
        skill_weights=(0.34, 0.33, 0.33),
        quality_floor=1,
        weapons=("heavy_laser", "heavy_missile", "light_laser"),
        modules=("shield_mk1", "shield_capacitor", "targeting_computer",
                 "armor_plating", "shield_recharger"),
        capture_layout_id="frigate_crew",
        loot_budget=(800, 2400),
        ai_aggressiveness=70,
        # Doc 57 SETTLED 2: clears the heavy floor 5 by >1.41.
        ai_preferred_range=7,
        shield_regen_rate=2,     # the captain/patrol_heavy class (SETTLED 40)
        detect_radius=10,
        comms_warning_range=0,   # the set-piece guards in silence
        comms_lines=(),
    ),
)
