"""Dig-site data (doc 42 phase 4): the authored tables every RNG dig
site reads. Sites are derived per planet — nothing here is per-site
(SETTLED 25/26); a planet overrides through its spec's ``dig_*``
fields, and future planets inherit the defaults automatically.
"""

from ..dungeon_extensions import LandmarkVariant

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
