"""Authored rumor chains (doc 42).

One chain — the 2026-09-11 one-chain ruling retired ``derelict_line``
and ``thin_month`` so refinement concentrates on the dark berths.
Tier 1 lists every teller who opens the chain; deeper tiers narrow to
the witness who holds the next piece. All prose lives in
``data/text/08_rumors.json`` under ``rumor.<id>.*``.
"""

from . import RumorEntry

# Source tuple: (npc_id, faction | None, min_standing | None,
# trait | None) — the talk_gate shape, minus the refusal line.
_NO_GATE = (None, None, None)

CHAINS: tuple[RumorEntry, ...] = (
    # --- The dark berths: who pays for the ports that don't ask.
    RumorEntry(
        id="dark_berth_1",
        chain="dark_berth",
        tier=1,
        value=1,
        sources=(
            ("wolf_barkeep", *_NO_GATE),
            ("deadfall_scrubber", *_NO_GATE),
        ),
    ),
    RumorEntry(
        id="dark_berth_2",
        chain="dark_berth",
        tier=2,
        requires=("dark_berth_1",),
        value=2,
        sources=(("deadfall_scrubber", *_NO_GATE),),
    ),
    RumorEntry(
        id="dark_berth_3",
        chain="dark_berth",
        tier=3,
        requires=("dark_berth_2",),
        value=3,
        sources=(("ember_tech", *_NO_GATE),),
    ),
    # Tier 4: never free-asked (empty sources) — wolf_barkeep sells it
    # as his exclusive (dealers.py; ruling 12).
    RumorEntry(
        id="dark_berth_4",
        chain="dark_berth",
        tier=4,
        requires=("dark_berth_3",),
        value=2,
        sources=(),
    ),
)
