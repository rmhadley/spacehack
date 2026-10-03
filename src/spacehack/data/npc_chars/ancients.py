"""Ancient machines — the alien prison's guardians (doc 48 SETTLED 29/42/45).

Three ``always_hostile`` rows, prison-exclusive FOR NOW (the doc-43
inhabitants handoff is deferred, not retired). The family unifies by
COLOR, not letter (SETTLED 45): three distinct glyphs in one cold
violet — Watcher ``O``, Shredder ``S``, Warden bold ``W``. Mechanics
dials ride the row as authored data (:class:`MachineMechanics`).

No usable drops (SETTLED 29): every loot pool empty, ``loot_count``
zero — the sites pay in alien tech, the machines are not a farmable
source. Band resolution is FLAT 4 (``fixed_band``): the site's
floor-band stamp never dilutes them (SETTLED 42, T4 provisional).
"""

from . import NpcCharSpec, six_weights, MachineMechanics

# The family's one color (SETTLED 45, approved with the brief).
ANCIENT_VIOLET: tuple[int, int, int] = (170, 140, 250)

NPC_CHARS: tuple[NpcCharSpec, ...] = (
    NpcCharSpec(
        id="watcher",
        name="Watcher",
        char="O",
        fg=ANCIENT_VIOLET,
        faction="",
        hp=16,                     # + stamina //3 -> 19: TTK 1 by intent
        weapons=(),                # weaponless — the stare is its attack
        stat_weights=six_weights(0.85, 0.0, 0.0),  # authored REF ~100 at band 4
        elite=False,
        ap=4,
        ai_aggressiveness=15,      # the drift: low dial, high dodge dance
        loot_pool=(),
        loot_count=(0, 0),
        xp_reward=40,
        always_hostile=True,
        behavior="guard",          # the sentinel cell
        squad_size=(1, 1),
        tier=4,
        armor=0,                   # fragile by intent — the lens on a hover field
        fixed_band=4,
        mechanics=MachineMechanics(
            stare_core=36,         # pre-soak; the ring reads half (SETTLED 42)
            shriek_radius=32,      # the loud one: 25-40 dial band
        ),
    ),
    NpcCharSpec(
        id="shredder",
        name="Shredder",
        char="S",
        fg=ANCIENT_VIOLET,
        faction="",
        hp=80,                     # + stamina //3 -> ~97: eats the opening shot
        weapons=("ancient_claws",),
        stat_weights=six_weights(0.10, 0.45, 0.30),
        elite=False,
        ap=6,                      # three 2-AP claw strikes in a full unload
        ai_aggressiveness=70,      # presses the melee — hesitation is its food
        loot_pool=(),
        loot_count=(0, 0),
        xp_reward=60,
        always_hostile=True,
        behavior="ambusher",       # the cell-block bursts-out verb (SETTLED 42)
        squad_size=(1, 1),
        tier=4,
        armor=10,                  # rugged mass — everything can hurt it, it doesn't care
        fixed_band=4,
        mechanics=MachineMechanics(
            mend_rate=5,           # in-combat start-of-turn mend lean (SETTLED 42)
        ),
    ),
    NpcCharSpec(
        id="warden",
        name="Warden",
        char="W",
        fg=ANCIENT_VIOLET,
        faction="",
        hp=65,                     # + stamina //3 -> ~85: TTK 2 on both reference sheets
        weapons=("ancient_warden_shot",),
        melee_weapons=("ancient_slam",),
        stat_weights=six_weights(0.15, 0.35, 0.35),
        elite=True,                # bold W — the unique's emphasis callout (SETTLED 45)
        ap=3,                      # firing IS the round (SETTLED 44 lean)
        ai_aggressiveness=80,      # holds ground and shoots
        loot_pool=(),
        loot_count=(0, 0),
        xp_reward=90,
        always_hostile=True,
        behavior="guard",          # holds ground (the deep-cell anchor)
        squad_size=(1, 1),
        tier=4,
        armor=12,
        fixed_band=4,
        mechanics=MachineMechanics(
            field_tile_hp=30,      # one railgun shot per tile (SETTLED 42 lean)
            field_regen=10,        # +10/turn minimum — space-shield symmetry
        ),
    ),
)
