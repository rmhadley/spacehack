"""Authored rumor chains (doc 42; content tracked in
docs/design/RUMORS.md).

The dark-ports chain: tier 1 arrives by experience — the dock /
dark-hail / pad triggers — never by asking; tier 2 rides the seeded
city carriers; tier 3 is the dark pirate's testimony on comms; tier
4 is the dealer exclusive (the name, the place, the passphrase).

The taking-ships opener is the deliberate exception to that
discovery model: ask-discovered gossip (RUMORS.md, settled
2026-09-27). All prose lives in ``data/text/08_rumors.json`` under
``rumor.<id>.*`` (user-authored).
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
    # --- Taking ships: the boarding-craft opener (RUMORS.md, settled
    # 2026-09-27). One entry, one lesson — the four conditions for
    # boarding in space combat, taught diegetically. Free to hear and
    # never sold: value 0 because the teller pool must seat the
    # dealers themselves (barkeep is the only T1 gossip seat), and a
    # co-teller refuses the buy anyway — common gossip is not
    # currency. Rarity is POOL COMPOSITION, not gates: rows per
    # planet scale with mission tier (T1: the barkeep only; T2: two
    # seats; T3/T4: up to three), and live_routes' uniform sample
    # turns pool share into per-port odds (~1-in-3 at a T1 port,
    # ~2-in-3 at a three-row frontier port).
    RumorEntry(
        id="taking_ships_1",
        chain="taking_ships",
        tier=1,
        value=0,
        picks=17,
        sources=(
            # T1 — one row each: the bar.
            ("barkeep", "earth", *_NO_GATE),
            ("barkeep", "mars", *_NO_GATE),
            ("barkeep", "venus", *_NO_GATE),
            ("barkeep", "mercury", *_NO_GATE),
            ("barkeep", "ac_planet_1", *_NO_GATE),
            # T2 — two rows where the seats exist.
            ("research_officer", "ac_planet_2", *_NO_GATE),
            ("guild_master", "ac_planet_2", *_NO_GATE),
            ("barkeep", "ac_planet_3", *_NO_GATE),
            ("bounty_master", "ac_planet_3", *_NO_GATE),
            ("barkeep", "ac_station", *_NO_GATE),
            ("depot_attendant", "ac_station", *_NO_GATE),
            ("barkeep", "barnards_b", *_NO_GATE),
            ("depot_attendant", "barnards_b", *_NO_GATE),
            ("barkeep", "barnards_c", *_NO_GATE),
            ("barkeep", "cygni_b", *_NO_GATE),
            ("militia_captain", "cygni_b", *_NO_GATE),
            ("depot_attendant", "depot", *_NO_GATE),
            ("barkeep", "eri_b", *_NO_GATE),
            ("militia_captain", "eri_b", *_NO_GATE),
            ("barkeep", "indi_b", *_NO_GATE),
            ("militia_captain", "indi_b", *_NO_GATE),
            ("barkeep", "proc_planet_1", *_NO_GATE),
            ("depot_attendant", "proc_planet_1", *_NO_GATE),
            ("depot_attendant", "proc_planet_2", *_NO_GATE),
            ("research_officer", "proc_planet_2", *_NO_GATE),
            ("research_officer", "sirius_station", *_NO_GATE),
            ("barkeep", "tc_b", *_NO_GATE),
            ("guild_master", "tc_b", *_NO_GATE),
            # T3 — three rows where the seats exist (wolf_b seats two).
            ("barkeep", "groom_b", *_NO_GATE),
            ("bounty_master", "groom_b", *_NO_GATE),
            ("depot_attendant", "groom_b", *_NO_GATE),
            ("barkeep", "vega_b", *_NO_GATE),
            ("depot_attendant", "vega_b", *_NO_GATE),
            ("guild_master", "vega_b", *_NO_GATE),
            ("wolf_barkeep", "wolf_b", *_NO_GATE),
            ("depot_attendant", "wolf_b", *_NO_GATE),
            # T4 — three rows where the seats exist (blockades seat two).
            ("blockade_officer", "blockade", *_NO_GATE),
            ("bounty_master", "blockade", *_NO_GATE),
            ("blockade_officer", "blockade_south", *_NO_GATE),
            ("bounty_master", "blockade_south", *_NO_GATE),
            ("barkeep", "lal_b", *_NO_GATE),
            ("deadfall_scrubber", "lal_b", *_NO_GATE),
            ("depot_attendant", "lal_b", *_NO_GATE),
            ("barkeep", "lal_c", *_NO_GATE),
            ("bounty_master", "lal_c", *_NO_GATE),
            ("guild_master", "lal_c", *_NO_GATE),
            ("barkeep", "ross_b", *_NO_GATE),
            ("bounty_master", "ross_b", *_NO_GATE),
            ("depot_attendant", "ross_b", *_NO_GATE),
            ("barkeep", "ross_c", *_NO_GATE),
            ("depot_attendant", "ross_c", *_NO_GATE),
            ("guild_master", "ross_c", *_NO_GATE),
        ),
    ),
)
