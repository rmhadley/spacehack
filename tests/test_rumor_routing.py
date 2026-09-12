"""Determinism + legality of the INIT_SEED routing derivations
(doc 42 phase 3, SETTLED 7/14/15/17)."""

from spacehack import rumor
from spacehack.data.lore import list_rumors
from spacehack.data.lore.dealers import EXCLUSIVE_CANDIDATES
from spacehack.rumor_routing import (
    DARK_GROUP_SHARE,
    choose_dark_groups,
    live_holdings,
    live_routes,
)


def test_same_seed_same_routing() -> None:
    for seed in (0, 1, 42, 999_999):
        assert live_routes(seed) == live_routes(seed)
        assert live_holdings(seed) == live_holdings(seed)


def _holder_of(seed: int, rumor_id: str):
    """The (dealer, price) a seed picks as an exclusive's live holder."""
    for dealer, rows in live_holdings(seed).items():
        for row in rows:
            if row[0] == rumor_id:
                return (dealer, row[1])
    return None


def test_reroll_yields_a_different_legal_routing() -> None:
    # Across a spread of seeds the derivation is not constant — the
    # seed genuinely shuffles — while every draw stays legal.
    route_maps = {repr(live_routes(s)) for s in range(8)}
    assert len(route_maps) > 1
    holders = {_holder_of(s, "dark_berth_4") for s in range(8)}
    assert len(holders) > 1


def test_every_source_carried_entry_keeps_a_live_route() -> None:
    for seed in (0, 1, 42):
        routes = live_routes(seed)
        for entry in list_rumors():
            if not entry.sources:
                assert entry.id not in routes or routes[entry.id]
                continue
            live = routes[entry.id]
            assert live, entry.id  # SETTLED 14: never emptied
            pool = {(s[0], s[1]) for s in entry.sources}
            assert live <= pool, entry.id
            expected = len(pool) if entry.picks is None else entry.picks
            assert len(live) == expected, entry.id


def test_exactly_one_live_holder_per_exclusive() -> None:
    for seed in (0, 1, 42):
        for rumor_id, candidates in EXCLUSIVE_CANDIDATES.items():
            holder = _holder_of(seed, rumor_id)
            assert holder is not None, rumor_id
            assert holder in candidates, (seed, rumor_id, holder)


def test_dark_groups_guarantee_a_minimum() -> None:
    mids = [f"proc_npc_sol_pirate_raider_{i}" for i in range(9)]
    # count = max(1, groups // share) — one in four, at least one.
    for seed in (0, 7, 42):
        dark = choose_dark_groups(seed, "sol", mids)
        assert 1 <= len(dark) <= len(mids)
        assert len(dark) == max(1, len(mids) // DARK_GROUP_SHARE)
    assert choose_dark_groups(0, "sol", []) == frozenset()
    # Deterministic in (seed, system, ids).
    assert choose_dark_groups(3, "sol", mids) == choose_dark_groups(3, "sol", mids)


def test_host_resolvers_compose_with_the_live_map() -> None:
    routes = live_routes(42)
    live_pair = next(iter(routes["dark_berth_2"]))
    npc_id, planet_id = live_pair
    rows = rumor.askable_topics(
        ["dark_berth_1"], {}, frozenset(), npc_id, planet_id, live=routes,
    )
    assert rows == [("dark ports", "dark_berth_2")]
    # A candidate the seed did not pick stays silent even on its own
    # planet (the fixture-free integration of SETTLED 15 + 14).
    pool = {
        (s[0], s[1])
        for entry in list_rumors() if entry.id == "dark_berth_2"
        for s in entry.sources
    }
    dead = sorted(pool - set(routes["dark_berth_2"]))
    if dead:
        dead_npc, dead_planet = dead[0]
        assert rumor.askable_topics(
            ["dark_berth_1"], {}, frozenset(), dead_npc, dead_planet,
            live=routes,
        ) == []
