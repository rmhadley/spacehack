"""Pure INIT_SEED derivations for the rumor system (doc 42 phase 3).

Everything here is a pure function of the run's INIT_SEED and stable
catalog keys — nothing serializes (SETTLED 7): CONTINUE regenerates
identical routing, SPACEHACK_SEED pins it for playtests, and a
Shift+S reroll yields a different but equally legal routing. The seed
never gates a chain (SETTLED 14): every source-carried entry keeps at
least one live route, and the dark-hull choice guarantees a minimum.
"""

from __future__ import annotations

from .engine import seeded_rng
from .data.lore.dealers import EXCLUSIVE_CANDIDATES

# One ambient pirate group in N flies dark this run (doc 42 phase
# 2.5 — the authored share; tunable at playtest).
DARK_GROUP_SHARE = 4


def live_routes(seed: int) -> dict[str, frozenset[tuple[str, str]]]:
    """Per-entry live ``(npc, planet)`` candidates (SETTLED 15).

    Each source-carried entry's derivation picks ``picks`` live
    candidates from its pool (every candidate when ``picks`` is
    None). At least one live route always survives — the derivation
    can never empty an entry's pool. The catalog is read through the
    ``rumor`` facade so test registries compose."""
    from . import rumor

    routes: dict[str, frozenset[tuple[str, str]]] = {}
    for entry in rumor.list_rumors():
        if not entry.sources:
            continue
        pool = sorted({(source[0], source[1]) for source in entry.sources})
        if entry.picks is None or entry.picks >= len(pool):
            routes[entry.id] = frozenset(pool)
            continue
        rng = seeded_rng(seed, "rumor_route", entry.id)
        routes[entry.id] = frozenset(rng.sample(pool, entry.picks))
    return routes


def live_holdings(seed: int) -> dict[str, tuple[tuple[str, int], ...]]:
    """Per-dealer exclusive holdings (SETTLED 17): the seed picks
    exactly one live holder per exclusive among the authored
    ``(dealer, price)`` candidates."""
    holdings: dict[str, list[tuple[str, int]]] = {}
    for rumor_id, candidates in EXCLUSIVE_CANDIDATES.items():
        rng = seeded_rng(seed, "rumor_holding", rumor_id)
        dealer_id, price = rng.choice(sorted(candidates))
        holdings.setdefault(dealer_id, []).append((rumor_id, price))
    return {dealer: tuple(rows) for dealer, rows in holdings.items()}


def choose_dark_groups(
    seed: int, system_id: str, movement_ids
) -> frozenset[str]:
    """Which ambient pirate groups fly dark this run (doc 42 phase
    2.5): ``max(1, groups // DARK_GROUP_SHARE)`` seeded picks — a
    guaranteed minimum live, never seed-blocked (SETTLED 14)."""
    groups = sorted(set(movement_ids))
    if not groups:
        return frozenset()
    count = min(len(groups), max(1, len(groups) // DARK_GROUP_SHARE))
    rng = seeded_rng(seed, "rumor_dark", system_id, *groups)
    return frozenset(rng.sample(groups, count))
