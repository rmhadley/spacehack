"""Consortium ground rungs (doc 48 phase 11, SETTLED 51/54).

The augmentation ladder realized as SETTLED 34's case/bold variants
of family letter ``e``: Gunner `e` is the LIGHT rung (eyes/arms-class
augments), Enforcer `E` the MID rung (arms/legs), Executor bold-`E`
the HIGH rung (the full set — the heaviest augmentation). Each rung
carries a FIXED band (the ancients' ``fixed_band`` precedent) —
authored encounter difficulty decides which rung you meet (SETTLED
12), and a rung reads identical wherever it appears.

Names are user-ruled VERBATIM (SETTLED 54). Worn pieces are the
EXISTING armor cybernetics (SETTLED 11); their bonus fields go live
on the wearer through the standard modifier math (SETTLED 27) and
drop via the kit path at stamped qualities — premium loot by the
quality floor (never base; the Executor floors at overclocked).
"""

from . import NpcCharSpec, six_weights


NPC_CHARS: tuple[NpcCharSpec, ...] = (
    NpcCharSpec(
        # The LIGHT rung: ranged guard, HOLDS its room and fires — the
        # artillery cell. Eyes-class aim augment + arm-class wiring.
        id="consortium_gunner",
        name="Consortium Gunner",
        char="e",
        fg=(90, 120, 200),       # consortium family navy (common case)
        faction="consortium",
        hp=28,
        weapon_families=("pistols",),
        melee_families=("melee",),
        stat_weights=six_weights(0.45, 0.15, 0.25),
        behavior="guard",
        fixed_band=2,
        worn_armor=("cybernetic_eyes", "cybernetic_arms"),
        quality_floor=1,
        loot_pool=("electronics", "machine_parts", "fuel_cells"),
        field_item_loot_pool=(
            # rifle_rounds retired (doc 48 SETTLED 56): no authored
            # family feeds it — the pistols draw kinetic_pistol.
            ("consumable", "stim"),
        ),
        loot_count=(0, 1),
        xp_reward=38,
    ),
    NpcCharSpec(
        # The MID rung: the claims-enforcement hunter — closes, melee-
        # capable. Arms + legs: the speed-and-grip augmentation class.
        id="consortium_enforcer",
        name="Consortium Enforcer",
        char="E",
        fg=(90, 120, 200),       # consortium family navy (serious case)
        faction="consortium",
        hp=30,
        weapon_families=("melee", "pistols"),
        melee_families=("melee",),
        stat_weights=six_weights(0.25, 0.40, 0.20),
        behavior="hunter",
        fixed_band=3,
        worn_armor=("cybernetic_arms", "cybernetic_legs"),
        quality_floor=1,
        loot_pool=("electronics", "machine_parts", "scrap_metal"),
        field_item_loot_pool=(
            ("ammo", "pistol_rounds"),
            ("consumable", "med_pack"),
        ),
        loot_count=(0, 1),
        xp_reward=45,
    ),
    NpcCharSpec(
        # The HIGH rung (SETTLED 54 name, user verbatim): the full
        # set — eyes/torso/arms/legs, the heaviest augmentation. The
        # deck-clearing heavy: strength/stamina-loaded, rifle-armed at
        # the fixed band-4 window, quality floored at OVERCLOCKED so
        # every drop reads prototype-class corporate gear.
        id="consortium_executor",
        name="Consortium Executor",
        char="E",
        fg=(90, 120, 200),       # consortium family navy; the rung = bold render
        faction="consortium",
        elite=True,
        hp=40,
        weapon_families=("rifles",),
        melee_families=("melee",),
        stat_weights=six_weights(0.20, 0.35, 0.30),
        behavior="hunter",
        fixed_band=4,
        worn_armor=(
            "cybernetic_eyes", "cybernetic_torso",
            "cybernetic_arms", "cybernetic_legs",
        ),
        quality_floor=2,
        loot_pool=("electronics", "machine_parts", "research_data"),
        field_item_loot_pool=(
            ("ammo", "rifle_rounds"),
            ("consumable", "stim"),
        ),
        loot_count=(0, 1),
        xp_reward=90,
    ),
)
