"""Dig-site data (doc 42 phase 4): the authored tables every RNG dig
site reads. Sites are derived per planet — nothing here is per-site
(SETTLED 25/26); a planet overrides through its spec's ``dig_*``
fields, and future planets inherit the defaults automatically.
"""

from dataclasses import dataclass as _dataclass

from ..dungeon_extensions import LandmarkVariant
from ..quality import DIG_QUALITY_RATES


@_dataclass(frozen=True)
class DigLootSpec:
    """The dig-cache loot config (SETTLED 30/35 + doc 47 phases 2/4):
    the planet's own ``produces`` goods, tier+floor-scaled — plus the
    phase-2 gear presence (a 1-in-``equipment_rate`` cache carries
    tier-banded equipment instead of goods, rolled at
    ``quality_rates``) and the phase-4 container fields: the
    ``legendary_bottom`` guarantee (one module randart on the deepest
    floor — the game's only legendary source) plus the lockbox
    rare-cache (1-in-``lockbox_rate``), off-world pool
    (1-in-``out_of_produce_rate``), and chip counts/values, whose
    spawners land with the phase-4 container steps (dormant until
    then). Per-planet overrides ride the ``dig_*`` spec fields;
    planets inherit these defaults."""
    cache_count: tuple[int, int] = (2, 3)
    base_qty: int = 2
    qty_per_tier: int = 1
    qty_per_floor: int = 2
    equipment_rate: int = 4
    quality_rates: tuple[int, int, int] = DIG_QUALITY_RATES
    legendary_bottom: bool = True
    # SETTLED 26 (doc 47.4): axis-count weights per dig band — T1
    # delves dish 2-stat randarts most of the time, band-3 delves
    # lean 4-stat. Weights index the (2, 3, 4) counts by band-1.
    legendary_axes_weights: tuple[tuple[int, int, int], ...] = (
        (70, 25, 5), (40, 40, 20), (15, 35, 50), (5, 25, 70),
    )
    lockbox_rate: int = 6
    out_of_produce_rate: int = 4
    chip_count: tuple[int, int] = (1, 2)
    chip_value: tuple[int, int] = (40, 120)
    lockbox_value: tuple[int, int] = (300, 900)


DIG_LOOT_SPEC = DigLootSpec()

# The off-world pool (doc 47 phase 4, SETTLED 23): ordinary market
# goods most planets don't produce — import flavor, better margins
# selling elsewhere. Story-bound goods (the act0 chain's power cells,
# escrow ore, sealed requisitions) stay out. Opening guess, tuned at
# playtest; the draw additionally excludes the planet's own produces.
OUT_OF_PRODUCE_GOODS: tuple[str, ...] = (
    "medical_supplies", "pharmaceuticals", "electronics",
    "luxury_goods", "machine_parts", "ship_components",
    "rare_earth_metals", "textiles",
)

# Phase-2 dig-cache gear (doc 47.2): an equipment cache rolls one
# entry from the site tier's pool. Pools draw from existing catalogs;
# opening guesses, tuned at playtest.
TIER_EQUIPMENT_POOLS: dict[int, tuple[tuple[str, str], ...]] = {
    1: (
        ("weapon", "kinetic_pistol"), ("weapon", "combat_knife"),
        ("weapon", "laser_pistol"), ("armor", "light_vest"),
        ("armor", "light_helmet"), ("armor", "tactical_gloves"),
    ),
    2: (
        ("weapon", "smg"), ("weapon", "shotgun"),
        ("weapon", "stun_baton"), ("armor", "medium_vest"),
        ("armor", "heavy_helmet"), ("armor", "reinforced_gauntlets"),
        ("armor", "armour_pads"),
    ),
    3: (
        ("weapon", "battle_rifle"), ("weapon", "plasma_pistol"),
        ("weapon", "vibroblade"), ("armor", "heavy_vest"),
        ("armor", "visor_helmet"), ("armor", "cybernetic_eyes"),
    ),
    4: (
        ("weapon", "railgun"), ("weapon", "plasma_caster"),
        ("weapon", "mono_blade"), ("weapon", "power_fist"),
        ("armor", "powered_vest"), ("armor", "assault_helmet"),
    ),
}

# Default two-part site-name pools (SETTLED 33) — a planet without
# authored pools draws its prefix and suffix from these. DRAFTS
# (prose gate: playtest checkpoint item 8).
DEFAULT_PREFIXES: tuple[str, ...] = (
    "Sunken", "Buried", "Silent", "Forgotten", "Rusted",
    "Hollow", "Shattered", "Deep", "Ashen", "Lost",
)
DEFAULT_SUFFIXES: tuple[str, ...] = (
    "Vault", "Warren", "Gallery", "Cistern", "Reliquary",
    "Foundry", "Terrace", "Annex", "Sublevel", "Cache",
)

# Tier-banded dig difficulty (SETTLED 26/38): the planet's mission_tier
# picks the pool and density; floors climb the band (tier + floor - 1).
# SETTLED 39 round 2 (user ruling): faction guards stand in the digs —
# the player's face decides whether a guard fights or steps aside
# (bump-to-swap), and pads flow from fighting across hostile lines.
# Doc 48 phase 2: the two consortium ids are DE-LISTED (SETTLED 12 —
# no procedurally-spawned consortium; authored content still pins raw
# ids). Their seats carry pirate weight so no band reads peaceful
# (SETTLED 16) — repetition IS weight under the uniform draws.
# Doc 48 SETTLED 49 amendment: the assault drone is T2 — its seat
# leaves bands 3-4 (hull_parasite takes it; bands 3-4 keep their
# humanoid droppers). Machine seats live at bands 1-2 only.
TIER_POOLS: dict[int, tuple[tuple[str, ...], float]] = {
    1: (("pirate_raider", "pirate_raider", "militia_trooper",
         "sentry_drone"), 1.0),
    2: (("pirate_raider", "pirate_rifleman", "pirate_rifleman",
         "assault_drone"), 1.4),
    3: (("pirate_rifleman", "pirate_rifleman", "pirate_brute",
         "hull_parasite"), 1.8),
    4: (("pirate_rifleman", "pirate_brute", "pirate_brute",
         "hull_parasite"), 2.2),
}

# Per-biome dig pools (doc 48 SETTLED 47/49): a planet declaring
# ``biome`` resolves its pool+density here, keyed by SITE band; floors
# still climb the stat band via the dig tier. ``TIER_POOLS`` stays the
# default read for every undescribed biome — a delve reads its planet's
# fauna, not pirates-by-default. Composition AND density are authored
# per biome per band (opening guesses, tuned at playtest); the density
# ladder is the SETTLED 35 rung set (1.0/1.4/1.8/2.2). Machine seats
# live at bands 1-2 only (sentry b1 / assault b2, desert/ice/scrap);
# bands 3-4 are fauna-pure, the strong face weighted up — deeper
# delves read WILDER, not more mechanized (SETTLED 49).
BIOME_POOLS: dict[str, dict[int, tuple[tuple[str, ...], float]]] = {
    "desert": {
        1: (("rock_scavenger", "rock_scavenger", "dust_prowler",
             "sentry_drone"), 1.0),
        2: (("dust_prowler", "dust_prowler", "rock_scavenger",
             "assault_drone"), 1.4),
        3: (("dust_prowler", "dust_prowler", "rock_scavenger",
             "rock_scavenger"), 1.8),
        4: (("dust_prowler", "dust_prowler", "dust_prowler",
             "rock_scavenger"), 2.2),
    },
    "ice": {
        1: (("ice_worm", "ice_worm", "frost_spitter",
             "sentry_drone"), 1.0),
        2: (("frost_spitter", "frost_spitter", "ice_worm",
             "assault_drone"), 1.4),
        3: (("frost_spitter", "frost_spitter", "ice_worm",
             "ice_worm"), 1.8),
        4: (("frost_spitter", "frost_spitter", "frost_spitter",
             "ice_worm"), 2.2),
    },
    # The four new-biome tables (doc 48 phase 10, the SETTLED 47 draft
    # approved verbatim with the brief): fauna-forward, no machine
    # seats (lush/volcanic/canyon read wild; scrap keeps the ruin-
    # security pair at bands 1-2), bands 3-4 fauna-pure with the
    # strong face weighted up.
    "lush": {
        1: (("vine_hound", "vine_hound", "vine_hound",
             "spore_spitter"), 1.0),
        2: (("spore_spitter", "spore_spitter", "vine_hound",
             "vine_hound"), 1.4),
        3: (("spore_spitter", "spore_spitter", "spore_spitter",
             "vine_hound"), 1.8),
        4: (("spore_spitter", "spore_spitter", "spore_spitter",
             "vine_hound", "vine_hound"), 2.2),
    },
    "volcanic": {
        1: (("ember_crawler", "ember_crawler", "ember_crawler",
             "magma_spitter"), 1.0),
        2: (("magma_spitter", "magma_spitter", "ember_crawler",
             "ember_crawler"), 1.4),
        3: (("magma_spitter", "magma_spitter", "magma_spitter",
             "ember_crawler"), 1.8),
        4: (("magma_spitter", "magma_spitter", "magma_spitter",
             "magma_spitter"), 2.2),
    },
    "scrap_ring": {
        1: (("scrap_hound", "scrap_hound", "rust_wasp",
             "sentry_drone"), 1.0),
        2: (("rust_wasp", "rust_wasp", "scrap_hound",
             "assault_drone"), 1.4),
        3: (("rust_wasp", "rust_wasp", "scrap_hound",
             "scrap_hound"), 1.8),
        4: (("rust_wasp", "rust_wasp", "rust_wasp",
             "scrap_hound"), 2.2),
    },
    "canyon": {
        1: (("canyon_viper", "canyon_viper", "crag_lurker"), 1.0),
        2: (("crag_lurker", "crag_lurker", "canyon_viper",
             "canyon_viper"), 1.4),
        3: (("canyon_viper", "canyon_viper", "crag_lurker",
             "crag_lurker"), 1.8),
        4: (("crag_lurker", "crag_lurker", "canyon_viper"), 2.2),
    },
}

# The authored-room sprinkle (SETTLED 25/32): a seeded minority of
# floors carry one; the pieces are agent-drafted (prose gate, playtest
# checkpoint item 8) and iterated with the user.
LANDMARK_CHANCE = 0.25
LANDMARK_VARIANTS: tuple[LandmarkVariant, ...] = (
    LandmarkVariant("dig_reliquary", 1.0),
    LandmarkVariant("dry_workshop", 1.0),
    LandmarkVariant("dig_cistern", 1.0),
)

# SETTLED 36: the three RNG-rare discovery doors as one rates table
# (1-in-N, opening guesses — tuned at playtest). None is guaranteed.
DOOR_RATES: dict[str, int] = {
    "humanoid_pad": 12,
    "derelict_pad": 8,
    "terminal": 6,
}

# The delve-bottom apex (doc 48 SETTLED 47-as-amended/48): every dig's
# deepest floor spawns its biome's apex beside the legendary cache,
# band-stamped at that floor's dig tier — EVERY means every: default
# biomes BORROW the nearest biome's apex through APEX_BORROW (opening
# guesses, tunable), everything unlisted falls back to the default
# biome. No unguarded legendaries anywhere.
BIOME_APEX: dict[str, str] = {
    "desert": "dune_behemoth",
    "ice": "glacier_wyrm",
    "lush": "canopy_maw",
    "volcanic": "caldera_tyrant",
    "scrap_ring": "scrap_colossus",
    "canyon": "mesa_mauler",
}
APEX_BORROW: dict[str, str] = {
    "wolf_b": "ice", "lal_c": "ice",
    "mars": "desert",
    "venus": "lush", "vega_b": "lush", "ac_planet_3": "lush",
    "indi_b": "lush",
}
DEFAULT_APEX_BIOME: str = "desert"

# Door 1's droppers (SETTLED 27): humanoid combatant NpcCharSpec ids.
# civilian_bystander is deliberately absent — bystanders are not a
# loot source.
HUMANOID_PAD_DROPPERS: tuple[str, ...] = (
    "pirate_raider",
    "pirate_rifleman",
    "pirate_brute",
    "consortium_enforcer",
    "consortium_gunner",
    "militia_trooper",
    "militia_marine",
    "militia_sniper",
)
