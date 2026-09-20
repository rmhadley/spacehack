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
    lockbox_rate: int = 6
    out_of_produce_rate: int = 4
    chip_count: tuple[int, int] = (1, 2)
    chip_value: tuple[int, int] = (40, 120)
    lockbox_value: tuple[int, int] = (300, 900)


DIG_LOOT_SPEC = DigLootSpec()

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
TIER_POOLS: dict[int, tuple[tuple[str, ...], float]] = {
    1: (("pirate_raider", "consortium_gunner", "militia_trooper",
         "sentry_drone"), 1.0),
    2: (("pirate_raider", "pirate_rifleman", "consortium_enforcer",
         "assault_drone"), 1.4),
    3: (("pirate_rifleman", "consortium_enforcer", "assault_drone",
         "hull_parasite"), 1.8),
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

# Door 1's droppers (SETTLED 27): humanoid combatant NpcCharSpec ids.
# civillian_bystander is deliberately absent — bystanders are not a
# loot source.
HUMANOID_PAD_DROPPERS: tuple[str, ...] = (
    "pirate_raider",
    "pirate_rifleman",
    "consortium_enforcer",
    "consortium_gunner",
    "militia_trooper",
)
