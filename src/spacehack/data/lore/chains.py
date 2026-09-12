"""Authored rumor chains (doc 42 phase 2.5 — the dark-ports chain).

One chain (the 2026-09-11 one-chain ruling). Tier 1 arrives by
experience — the dock / dark-hail / pad triggers — never by asking;
tier 2 rides the seeded city carriers; tier 3 is the dark pirate's
testimony on comms; tier 4 is the dealer exclusive (the name, the
place, the passphrase). All prose lives in
``data/text/08_rumors.json`` under ``rumor.<id>.*`` (user-authored,
doc 42 phase 2.5).
"""

from . import RumorEntry

# Source tuple: (npc_id, planet, faction | None, min_standing | None,
# trait | None) — the talk_gate shape, planet-scoped (SETTLED 15).
_NO_GATE = (None, None, None)

CHAINS: tuple[RumorEntry, ...] = (
    # --- The dark ports: the ports that don't check, and the hulls
    # that use them (doc 42 phase 2.5).
    RumorEntry(
        id="dark_berth_1",
        chain="dark_berth",
        tier=1,
        value=1,
        triggers=("dock_dark_port", "dark_hail"),
    ),
    RumorEntry(
        id="dark_berth_2",
        chain="dark_berth",
        tier=2,
        requires=("dark_berth_1",),
        value=2,
        picks=2,
        sources=(
            ("wolf_barkeep", "wolf_b", *_NO_GATE),
            ("deadfall_scrubber", "lal_b", *_NO_GATE),
            ("ember_tech", "ross_b", *_NO_GATE),
            ("research_officer", "mercury", *_NO_GATE),
            ("barkeep", "lal_c", *_NO_GATE),
        ),
    ),
    RumorEntry(
        id="dark_berth_3",
        chain="dark_berth",
        tier=3,
        requires=("dark_berth_2",),
        value=3,
        triggers=("dark_hail",),
    ),
    # Tier 4: never free-asked (empty sources) — the live dealer
    # holds it this run (dealers.EXCLUSIVE_CANDIDATES; ruling 12,
    # SETTLED 17).
    RumorEntry(
        id="dark_berth_4",
        chain="dark_berth",
        tier=4,
        requires=("dark_berth_3",),
        value=2,
    ),
)
