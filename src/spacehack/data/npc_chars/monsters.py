"""Dungeon monster catalog — non-sentient hostile fauna and drones.

Every monster sets ``always_hostile=True`` and ``faction=""`` so it
fights on sight regardless of faction reputation and killing one
changes no reputation score (``_COMBAT_KILL_DELTAS.get("", {})`` is
a no-op). Behavior + squad size drive out-of-combat movement and
procedural dungeon population. ``armor`` is flat DR the player must
punch through (plasma halves it). Corpses pay by the carried-loot
doctrine (doc 48 SETTLED 56/58): fauna nothing, machines their own
substance, apexes the trophy good.

Design doc: ``docs/design/in_progress/11_DESIGN_DUNGEON_MONSTERS.md``
"""

from . import NpcCharSpec, six_weights

NPC_CHARS: tuple[NpcCharSpec, ...] = (
    NpcCharSpec(
        id="rock_scavenger",
        name="Rock Scavenger",
        char="s",
        fg=(205, 170, 120),       # sandy rock-grey — desert/rock fauna
        faction="",
        hp=14,
        weapons=("monster_claws",),
        stat_weights=six_weights(0.30, 0.25, 0.30),
        behavior="hunter",
        squad_size=(3, 5),        # swarmer — always hunts in packs
        always_hostile=True,
        xp_reward=10,
        ap=5,
    ),
    NpcCharSpec(
        id="sentry_drone",
        name="Sentry Drone",
        char="d",
        fg=(200, 180, 110),       # machine family bronze (common case)
        faction="",
        hp=18,
        weapons=("drone_laser",),
        stat_weights=six_weights(0.40, 0.10, 0.35),
        behavior="guard",         # holds position, fires at range
        squad_size=(1, 1),
        always_hostile=True,
        armor=1,
        loot_pool=("scrap_metal",),
        loot_count=(0, 1),
        # Doc 48 SETTLED 56/58: the machine's own substance — 0-1
        # scrap, energy cells (its ammunition); no consumables (a
        # drone's self-repair is its chassis).
        field_item_loot_pool=(
            ("ammo", "energy_cells"),
        ),
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
        stat_weights=six_weights(0.10, 0.55, 0.20),
        behavior="ambusher",      # holds still, bursts out on approach
        squad_size=(1, 2),
        always_hostile=True,
        xp_reward=20,
        ap=5,
    ),
    NpcCharSpec(
        id="dust_prowler",
        name="Dust Prowler",
        char="p",
        fg=(215, 130, 90),        # red-brown — fast desert predator
        faction="",
        hp=22,
        weapons=("monster_claws",),
        stat_weights=six_weights(0.35, 0.30, 0.20),
        behavior="hunter",        # fast, aggressive single/duo hunter
        squad_size=(1, 2),
        always_hostile=True,
        xp_reward=18,
        ap=6,
    ),
    NpcCharSpec(
        id="assault_drone",
        name="Assault Drone",
        char="D",
        fg=(200, 180, 110),       # machine family bronze (serious case)
        faction="",
        hp=34,
        weapons=("monster_claws",),
        stat_weights=six_weights(0.10, 0.50, 0.25),
        behavior="guard",         # armored bruiser — holds its post
        squad_size=(1, 1),
        always_hostile=True,
        # SETTLED 49 (doc 48): classified T2 — the machine family
        # reads as ruin-security T2 uniformly, the sentry's class
        # (drops since re-authored by SETTLED 56/58: substance only).
        armor=3,
        loot_pool=("scrap_metal",),
        loot_count=(0, 1),
        field_item_loot_pool=(
            ("ammo", "energy_cells"),
        ),
        xp_reward=30,
        ap=3,
    ),
    NpcCharSpec(
        id="frost_spitter",
        name="Frost Spitter",
        char="f",
        fg=(170, 210, 250),       # pale frost blue — ice-cave harasser
        faction="",
        hp=20,
        weapons=("frost_bolt",),
        stat_weights=six_weights(0.45, 0.10, 0.30),
        behavior="hunter",        # ranged harasser, hunts in pairs/trios
        squad_size=(2, 3),
        always_hostile=True,
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
        stat_weights=six_weights(0.35, 0.30, 0.20),
        behavior="ambusher",      # lurks in derelicts, bursts out on approach
        squad_size=(2, 4),
        always_hostile=True,
        xp_reward=15,
        ap=5,
    ),
    # --- biome fauna (doc 48 phase 10, SETTLED 47/48): two faces per
    # new biome, every row a DISTINCT behavior-attack cell — matrix
    # cells, never stat walls. Species glyphs in biome palettes (not
    # identity families, SETTLED 34); fixed organic weapons (never
    # weapon_families, SETTLED 35 law); numbers lean on the rows above.
    NpcCharSpec(
        id="vine_hound",
        name="Vine Hound",
        char="v",
        fg=(110, 200, 90),        # lush green — the undergrowth pack
        faction="",
        hp=14,
        weapons=("monster_claws",),   # hounds keep claws
        stat_weights=six_weights(0.35, 0.15, 0.35),
        behavior="hunter",        # AP-6 closer pack: pressure you
        squad_size=(2, 2),        # can't out-walk — pairs
        always_hostile=True,
        xp_reward=15,
        ap=6,
    ),
    NpcCharSpec(
        id="spore_spitter",
        name="Spore Spitter",
        char="i",
        fg=(190, 210, 120),       # pale spore yellow-green
        faction="",
        hp=16,
        weapons=("spore_burst",),
        melee_weapons=("monster_claws",),  # the sting set — the FIRST
        stat_weights=six_weights(0.45, 0.10, 0.30),  # two-set fauna:
        behavior="guard",         # rushing the nest triggers the
        squad_size=(1, 2),        # cornered-switch (SETTLED 43)
        always_hostile=True,
        xp_reward=15,
    ),
    NpcCharSpec(
        id="ember_crawler",
        name="Ember Crawler",
        char="x",
        fg=(235, 150, 70),        # ember orange — the volcanic swarm
        faction="",
        hp=12,
        weapons=("monster_claws",),
        stat_weights=six_weights(0.20, 0.30, 0.35),
        behavior="hunter",        # ARMORED swarm: armor on volume —
        squad_size=(4, 6),        # plasma/AoE bait, kinetic starves
        always_hostile=True,
        armor=2,
        xp_reward=10,
    ),
    NpcCharSpec(
        id="magma_spitter",
        name="Magma Spitter",
        char="g",
        fg=(250, 80, 60),         # magma red — the brawler-caster
        faction="",
        hp=22,
        weapons=("magma_bolt",),  # heavy hits at max 4 — the inverse
        stat_weights=six_weights(0.35, 0.25, 0.25),  # of frost's kite
        behavior="hunter",
        squad_size=(1, 2),
        always_hostile=True,
        armor=1,
        xp_reward=25,
    ),
    NpcCharSpec(
        id="scrap_hound",
        name="Scrap Hound",
        char="k",
        fg=(190, 175, 140),       # weathered steel-tan
        faction="",
        hp=18,
        weapons=("monster_claws",),   # hounds keep claws
        stat_weights=six_weights(0.40, 0.20, 0.25),
        behavior="hunter",        # fast ARMORED skirmisher — out-races
        squad_size=(2, 2),        # you; pin and trade
        always_hostile=True,
        armor=2,
        xp_reward=20,
        ap=6,
    ),
    NpcCharSpec(
        id="rust_wasp",
        name="Rust Wasp",
        char="y",
        fg=(230, 210, 90),        # wasp yellow
        faction="",
        hp=12,
        weapons=("rust_spines",),
        stat_weights=six_weights(0.45, 0.05, 0.35),
        behavior="hunter",        # the RANGED swarm: volume of
        squad_size=(3, 5),        # incoming fire at short range
        always_hostile=True,
        xp_reward=12,
        ap=6,
    ),
    NpcCharSpec(
        id="crag_lurker",
        name="Crag Lurker",
        char="l",
        fg=(160, 150, 135),       # stone grey-brown
        faction="",
        hp=24,
        weapons=("monster_claws",),
        stat_weights=six_weights(0.10, 0.45, 0.30),
        behavior="ambusher",      # the ARMORED burst-out — the
        squad_size=(1, 2),        # surprise wall
        always_hostile=True,
        armor=3,
        xp_reward=25,
    ),
    NpcCharSpec(
        id="canyon_viper",
        name="Canyon Viper",
        char="n",
        fg=(180, 230, 130),       # viper green-yellow
        faction="",
        hp=10,
        weapons=("venom_fangs",),
        stat_weights=six_weights(0.60, 0.05, 0.20),  # max reflexes —
        behavior="hunter",        # the can't-hit-it problem; melee/
        squad_size=(1, 2),        # accurate/AoE are the answers
        always_hostile=True,
        xp_reward=15,
        ap=6,
    ),
    # --- the biome apexes (doc 48 phase 10, SETTLED 47/48): one per
    # biome incl. DESERT/ICE, each guarding DIFFERENTLY — data-only
    # rows (no mechanic machinery): FLAT bases, the band stamp does
    # the scaling; bold glyphs (elite), solo (squad 1,1) unless the
    # row authors a pack; knockback/armor_bypass ride the WEAPON
    # fields. The kill pays: big XP + the trophy good (SETTLED 57).
    NpcCharSpec(
        id="dune_behemoth",
        name="Dune Behemoth",
        char="B",
        fg=(230, 190, 120),       # dune sand-gold
        faction="",
        hp=65,
        weapons=("behemoth_maul",),   # knockback 2 — the anchor
        stat_weights=six_weights(0.10, 0.40, 0.35),  # ejects its
        behavior="guard",         # victim along the attack vector
        squad_size=(1, 1),
        always_hostile=True,
        elite=True,
        armor=5,
        loot_pool=("behemoth_hide",),
        loot_count=(1, 1),  # the GUARANTEED trophy (SETTLED 57)
        xp_reward=120,
        ap=3,
    ),
    NpcCharSpec(
        id="glacier_wyrm",
        name="Glacier Wyrm",
        char="G",
        fg=(200, 235, 255),       # glacier white-blue
        faction="",
        hp=60,
        weapons=("wyrm_breath",),     # armor_bypass — the
        melee_weapons=("monster_claws",),  # soak-breaker: dodge
        stat_weights=six_weights(0.40, 0.10, 0.35),  # answers what
        behavior="hunter",            # soak can't
        squad_size=(1, 1),
        always_hostile=True,
        elite=True,
        armor=4,
        loot_pool=("glacier_fang",),
        loot_count=(1, 1),  # the GUARANTEED trophy (SETTLED 57)
        xp_reward=120,
    ),
    NpcCharSpec(
        id="caldera_tyrant",
        name="Caldera Tyrant",
        char="T",
        fg=(255, 120, 60),        # caldera fire-orange
        faction="",
        hp=55,
        weapons=("siege_bolt",),      # long heavy — the bombardier
        melee_weapons=("monster_claws",),  # holds at range, weak
        stat_weights=six_weights(0.45, 0.05, 0.35),  # melee; close
        behavior="guard",             # inside its band
        squad_size=(1, 1),
        always_hostile=True,
        elite=True,
        armor=3,
        loot_pool=("tyrant_scale",),
        loot_count=(1, 1),  # the GUARANTEED trophy (SETTLED 57)
        xp_reward=110,
    ),
    NpcCharSpec(
        id="canopy_maw",
        name="Canopy Maw",
        char="A",
        fg=(90, 180, 80),         # canopy deep green
        faction="",
        hp=70,
        weapons=("behemoth_maul",),   # knockback 2 — the ambush
        stat_weights=six_weights(0.15, 0.40, 0.30),  # apex: waits
        behavior="ambusher",      # beside the cache, bursts out —
        squad_size=(1, 1),        # approach the legendary from range
        always_hostile=True,
        elite=True,
        armor=3,
        loot_pool=("maw_sinew",),
        loot_count=(1, 1),  # the GUARANTEED trophy (SETTLED 57)
        xp_reward=120,
    ),
    NpcCharSpec(
        id="scrap_colossus",
        name="Scrap Colossus",
        char="Z",
        fg=(210, 190, 150),       # weathered steel
        faction="",
        hp=75,                        # the highest HP — the
        weapons=("rust_spines",),     # immovable object: both
        melee_weapons=("behemoth_maul",),  # weapon sets, no weak
        stat_weights=six_weights(0.10, 0.35, 0.40),  # band; you pay
        behavior="guard",             # at the range you choose
        squad_size=(1, 1),
        always_hostile=True,
        elite=True,
        armor=4,
        loot_pool=("colossus_core",),
        loot_count=(1, 1),  # the GUARANTEED trophy (SETTLED 57)
        xp_reward=130,
        ap=2,
    ),
    NpcCharSpec(
        id="mesa_mauler",
        name="Mesa Mauler",
        char="U",
        fg=(225, 150, 90),        # mesa ochre
        faction="",
        hp=60,
        weapons=("monster_claws",),
        stat_weights=six_weights(0.40, 0.20, 0.25),
        behavior="hunter",        # THE PACK APEX (SETTLED 48): roams
        squad_size=(1, 1),        # the bottom with its viper pack —
        pack_pool=("canyon_viper",),   # thin the pack, then duel
        pack_size=(2, 4),              # the mauler
        always_hostile=True,
        elite=True,
        armor=3,
        loot_pool=("mauler_pelt",),
        loot_count=(1, 1),  # the GUARANTEED trophy (SETTLED 57)
        xp_reward=120,
        ap=5,
    ),
)
