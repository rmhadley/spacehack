"""Dig-site data (doc 42 phase 4): the authored tables every RNG dig
site reads. Sites are derived per planet — nothing here is per-site
(SETTLED 25/26); a planet overrides through its spec's ``dig_*``
fields, and future planets inherit the defaults automatically.
"""

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
