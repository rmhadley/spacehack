"""Authored rumor chains (doc 42, phase 1).

Three chains across the bar and city talk hosts. Tier 1 entries list
every teller who opens the chain; deeper tiers narrow to the witness
who holds the next piece. All prose lives in
``data/text/08_rumors.json`` under ``rumor.<id>.*``.
"""

from . import RumorEntry

# Source tuple: (npc_id, faction | None, min_standing | None,
# trait | None) — the talk_gate shape, minus the refusal line.
_NO_GATE = (None, None, None)

CHAINS: tuple[RumorEntry, ...] = (
    # --- The derelict line: what the wrecks are telling the charts.
    RumorEntry(
        id="derelict_line_1",
        chain="derelict_line",
        tier=1,
        value=1,
        sources=(
            ("barkeep", *_NO_GATE),
            ("depot_attendant", *_NO_GATE),
        ),
    ),
    RumorEntry(
        id="derelict_line_2",
        chain="derelict_line",
        tier=2,
        requires=("derelict_line_1",),
        value=2,
        sources=(("depot_attendant", *_NO_GATE),),
    ),
    RumorEntry(
        id="derelict_line_3",
        chain="derelict_line",
        tier=3,
        requires=("derelict_line_2",),
        value=3,
        sources=(("wolf_barkeep", *_NO_GATE),),
    ),
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
    # --- The thin month: the blockade's maintenance watch.
    RumorEntry(
        id="thin_month_1",
        chain="thin_month",
        tier=1,
        value=1,
        sources=(
            ("barkeep", *_NO_GATE),
            ("blockade_officer", "militia", 0, None),
        ),
    ),
    RumorEntry(
        id="thin_month_2",
        chain="thin_month",
        tier=2,
        requires=("thin_month_1",),
        value=2,
        sources=(("blockade_officer", "militia", 0, None),),
    ),
    RumorEntry(
        id="thin_month_3",
        chain="thin_month",
        tier=3,
        requires=("thin_month_2",),
        value=3,
        sources=(("militia_captain", "militia", 26, "warrant_license"),),
    ),
)
