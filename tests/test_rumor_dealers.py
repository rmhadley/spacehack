"""Dealer-spec integrity + the favor exchange (doc 42 phases 2-3).

The exchange is data-defined, so the data test is the enforcement:
dealers seat real NPCs, exclusive candidates price real rumors with
real dealers, and exclusives are never free-asked (empty sources,
ruling 12). The resolvers are ctx-free; the wrappers are pinned on
constructed ledgers.
"""

from types import SimpleNamespace

import pytest

from spacehack import rumor
from spacehack.data.lore import find_rumor
from spacehack.data.lore.dealers import (
    DEALERS,
    EXCLUSIVE_CANDIDATES,
    find_dealer,
    is_dealer,
)
from spacehack.data.npcs import find_npc


def test_dealers_seat_real_npcs() -> None:
    for spec in DEALERS:
        find_npc(spec.dealer_npc_id)


def test_dealer_ids_unique() -> None:
    ids = [spec.dealer_npc_id for spec in DEALERS]
    assert len(ids) == len(set(ids))


def test_exclusive_candidates_are_well_formed() -> None:
    for rumor_id, candidates in EXCLUSIVE_CANDIDATES.items():
        find_rumor(rumor_id)
        assert len(candidates) >= 2, rumor_id  # a real scatter choice
        for dealer_id, price in candidates:
            assert is_dealer(dealer_id), dealer_id
            assert isinstance(price, int) and price > 0, (rumor_id, dealer_id)


def test_exclusives_are_never_free_asked() -> None:
    for rumor_id in EXCLUSIVE_CANDIDATES:
        assert find_rumor(rumor_id).sources == (), rumor_id
        assert not find_rumor(rumor_id).triggers, rumor_id


def test_registry_lookup() -> None:
    assert is_dealer("wolf_barkeep")
    assert not is_dealer("guild_master")
    with pytest.raises(KeyError):
        find_dealer("guild_master")


# --- the exchange resolvers (pure) -----------------------------------------


def test_favor_for_defaults_to_zero() -> None:
    assert rumor.favor_for({}, "wolf_barkeep") == 0
    assert rumor.favor_for(
        {"wolf_barkeep": {"favor": 3, "earned": []}}, "wolf_barkeep",
    ) == 3


def test_offerable_lists_heard_unsold_valued_rumors() -> None:
    # research_officer is a tier-2 carrier, but tiers 1 and 3 have no
    # sources — those they buy.
    ledgers = {"research_officer": {"favor": 0, "earned": ["dark_berth_1"]}}
    rows = rumor.offerable_rumors(
        ["dark_berth_1", "dark_berth_3"], ledgers, "research_officer",
    )
    assert rows == [("dark_berth_3", 3)]


def test_dealer_wont_buy_back_their_own_telling() -> None:
    # Round-1 ruling: no selling back. Every dealer seats as a tier-2
    # carrier this phase — the tier they told, they won't buy.
    for dealer_id in ("wolf_barkeep", "research_officer", "barkeep"):
        assert rumor.offerable_rumors(
            ["dark_berth_2"], {}, dealer_id,
        ) == [], dealer_id


def test_co_teller_refuses_too() -> None:
    # Knowledge, not transaction history: the scrubber and the tech
    # carry tier 2 — they already know it whoever told you.
    assert rumor.offerable_rumors(
        ["dark_berth_2"], {}, "deadfall_scrubber",
    ) == []
    assert rumor.offerable_rumors(["dark_berth_2"], {}, "ember_tech") == []


def test_dealer_buys_tiers_nobody_carries() -> None:
    # Tiers 1, 3, 4 are trigger/exclusive-delivered — no dealer is an
    # authored source, so every book buys them. The chain walk funds
    # the exclusive exactly: tier 1 + tier 3 = 4 favor.
    rows = rumor.offerable_rumors(
        ["dark_berth_1", "dark_berth_3"], {}, "wolf_barkeep",
    )
    assert rows == [("dark_berth_1", 1), ("dark_berth_3", 3)]


def test_offerable_is_per_dealer() -> None:
    # Sold to the wolf; the barkeep, another book, still pays
    # (ruling 9 — one book per dealer).
    ledgers = {"wolf_barkeep": {"favor": 1, "earned": ["dark_berth_1"]}}
    assert rumor.offerable_rumors(
        ["dark_berth_1"], ledgers, "barkeep",
    ) == [("dark_berth_1", 1)]
    assert rumor.offerable_rumors(["dark_berth_1"], ledgers, "wolf_barkeep") == []


def test_offerable_skips_stale_ids() -> None:
    # derelict_line_1 retired with the one-chain ruling.
    assert rumor.offerable_rumors(["derelict_line_1"], {}, "barkeep") == []


def test_exclusive_offers_gate_on_requires_unheard_and_affordability() -> None:
    known = ["dark_berth_1", "dark_berth_2", "dark_berth_3"]
    ledgers = {"wolf_barkeep": {"favor": 4, "earned": []}}
    assert rumor.exclusive_offers(
        known, ledgers, "wolf_barkeep", (("dark_berth_4", 4),),
    ) == [("dark_berth_4", 4)]


def test_exclusive_hidden_until_affordable() -> None:
    # Ruling 11: the priced row exists only once favor covers it.
    known = ["dark_berth_1", "dark_berth_2", "dark_berth_3"]
    ledgers = {"wolf_barkeep": {"favor": 3, "earned": []}}
    assert rumor.exclusive_offers(
        known, ledgers, "wolf_barkeep", (("dark_berth_4", 4),),
    ) == []


def test_exclusive_hidden_until_requires_met() -> None:
    # Favor to burn, but tier 3 unheard: nothing to buy (checklist 4).
    ledgers = {"wolf_barkeep": {"favor": 9, "earned": []}}
    assert rumor.exclusive_offers(
        ["dark_berth_1"], ledgers, "wolf_barkeep", (("dark_berth_4", 4),),
    ) == []


def test_exclusive_gone_once_heard() -> None:
    known = ["dark_berth_1", "dark_berth_2", "dark_berth_3", "dark_berth_4"]
    ledgers = {"wolf_barkeep": {"favor": 9, "earned": []}}
    assert rumor.exclusive_offers(
        known, ledgers, "wolf_barkeep", (("dark_berth_4", 4),),
    ) == []


def test_holding_is_an_explicit_input_the_routing_seam() -> None:
    # research_officer is an authored CANDIDATE holder, yet the
    # resolver prices the exclusive against the holding the host
    # hands in — phase-3 scatter composes, no rewrite (requires met
    # by the keyring, favor from the book).
    known = ["dark_berth_1", "dark_berth_2", "dark_berth_3"]
    ledgers = {"research_officer": {"favor": 4, "earned": []}}
    assert rumor.exclusive_offers(
        known, ledgers, "research_officer", (("dark_berth_4", 4),),
    ) == [("dark_berth_4", 4)]
    assert rumor.exclusive_offers(
        known, ledgers, "research_officer", (),
    ) == []


# --- the exchange mutations -------------------------------------------------


def test_offer_pays_value_once_per_dealer() -> None:
    ctx = SimpleNamespace(known_rumors=["dark_berth_1"], rumor_favor={})
    assert rumor.offer_rumor(ctx, "research_officer", "dark_berth_1") == 1
    assert ctx.rumor_favor == {
        "research_officer": {"favor": 1, "earned": ["dark_berth_1"]},
    }
    assert rumor.offer_rumor(ctx, "research_officer", "dark_berth_1") == 0
    assert ctx.rumor_favor["research_officer"]["favor"] == 1


def test_buy_spends_then_hears() -> None:
    ctx = SimpleNamespace(
        known_rumors=["dark_berth_1", "dark_berth_2", "dark_berth_3"],
        rumor_favor={"wolf_barkeep": {"favor": 4, "earned": ["dark_berth_1"]}},
    )
    assert rumor.buy_exclusive(ctx, "wolf_barkeep", "dark_berth_4", 4) is True
    assert ctx.rumor_favor["wolf_barkeep"]["favor"] == 0
    assert ctx.known_rumors[-1] == "dark_berth_4"
    # The earned set is offer-history, not purchase-history — a buy
    # spends favor without touching it (ruling 13).
    assert ctx.rumor_favor["wolf_barkeep"]["earned"] == ["dark_berth_1"]


def test_buy_never_goes_below_zero_and_refusal_touches_nothing() -> None:
    ctx = SimpleNamespace(known_rumors=[], rumor_favor={})
    assert rumor.buy_exclusive(ctx, "barkeep", "dark_berth_4", 4) is False
    assert ctx.rumor_favor == {}
    assert ctx.known_rumors == []


def test_buy_refuses_known_rumors() -> None:
    ctx = SimpleNamespace(
        known_rumors=["dark_berth_4"],
        rumor_favor={"barkeep": {"favor": 9, "earned": []}},
    )
    assert rumor.buy_exclusive(ctx, "barkeep", "dark_berth_4", 4) is False
    assert ctx.rumor_favor["barkeep"]["favor"] == 9


def test_knowledge_gates_reference_real_npcs_and_rumors() -> None:
    from spacehack.identity import KNOWLEDGE_GATES

    for npc_id, rumor_id in KNOWLEDGE_GATES.items():
        find_npc(npc_id)
        find_rumor(rumor_id)


def test_offer_refuses_unheard_rumors() -> None:
    # The mutation boundary is self-defending (reviewer round): a
    # future host can't pay out for knowledge off the keyring.
    ctx = SimpleNamespace(known_rumors=[], rumor_favor={})
    assert rumor.offer_rumor(ctx, "barkeep", "dark_berth_1") == 0
    assert ctx.rumor_favor == {}


def test_offer_refuses_rumors_the_dealer_knows() -> None:
    # Same boundary, round-1 ruling side: no selling back to a
    # teller, whatever a host might render.
    ctx = SimpleNamespace(known_rumors=["dark_berth_2"], rumor_favor={})
    assert rumor.offer_rumor(ctx, "wolf_barkeep", "dark_berth_2") == 0
    assert ctx.rumor_favor == {}
