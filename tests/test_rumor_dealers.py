"""Dealer-spec integrity + the favor exchange (doc 42 phase 2).

The exchange is data-defined, so the data test is the enforcement:
dealers seat real NPCs, exclusives price real rumors, and exclusives
are never free-asked (empty sources, ruling 12). The resolvers are
ctx-free; the wrappers are pinned on constructed ledgers.
"""

from types import SimpleNamespace

import pytest

from spacehack import rumor
from spacehack.data.lore import find_rumor
from spacehack.data.lore.dealers import DEALERS, find_dealer, is_dealer
from spacehack.data.npcs import find_npc


def test_dealers_seat_real_npcs() -> None:
    for spec in DEALERS:
        find_npc(spec.dealer_npc_id)


def test_dealer_ids_unique() -> None:
    ids = [spec.dealer_npc_id for spec in DEALERS]
    assert len(ids) == len(set(ids))


def test_exclusives_price_real_rumors() -> None:
    for spec in DEALERS:
        for rumor_id, price in spec.exclusives:
            find_rumor(rumor_id)
            assert isinstance(price, int), (spec.dealer_npc_id, rumor_id)
            assert price > 0, (spec.dealer_npc_id, rumor_id)


def test_exclusives_are_never_free_asked() -> None:
    for spec in DEALERS:
        for rumor_id, _price in spec.exclusives:
            assert find_rumor(rumor_id).sources == (), rumor_id


def test_registry_lookup() -> None:
    assert is_dealer("wolf_barkeep")
    assert not is_dealer("guild_master")
    assert find_dealer("wolf_barkeep").exclusives == (("dark_berth_4", 4),)
    with pytest.raises(KeyError):
        find_dealer("guild_master")


# --- the exchange resolvers (pure) -----------------------------------------


def test_favor_for_defaults_to_zero() -> None:
    assert rumor.favor_for({}, "wolf_barkeep") == 0
    assert rumor.favor_for(
        {"wolf_barkeep": {"favor": 3, "earned": []}}, "wolf_barkeep",
    ) == 3


def test_offerable_lists_heard_unsold_valued_rumors() -> None:
    # research_officer holds no sources — they buy anything heard.
    ledgers = {"research_officer": {"favor": 0, "earned": ["thin_month_1"]}}
    rows = rumor.offerable_rumors(
        ["thin_month_1", "derelict_line_1"], ledgers, "research_officer",
    )
    assert rows == [("derelict_line_1", 1)]


def test_dealer_wont_buy_back_their_own_telling() -> None:
    # Round-1 ruling: no selling back. The barkeep is an authored
    # source of both openers — neither shows a Sell row at his book.
    assert rumor.offerable_rumors(
        ["thin_month_1", "derelict_line_1"], {}, "barkeep",
    ) == []


def test_co_teller_refuses_too() -> None:
    # Knowledge, not transaction history: dark_berth_1 heard from the
    # wolf — deadfall (co-source) already knows it too.
    assert rumor.offerable_rumors(
        ["dark_berth_1"], {}, "deadfall_scrubber",
    ) == []


def test_dealer_buys_tiers_they_dont_hold() -> None:
    # The wolf told you dark_berth_1 but holds no thin-month sources
    # — that entry he buys.
    rows = rumor.offerable_rumors(
        ["dark_berth_1", "thin_month_1"], {}, "wolf_barkeep",
    )
    assert rows == [("thin_month_1", 1)]


def test_offerable_is_per_dealer() -> None:
    # Sold to the wolf (who holds no thin-month sources);
    # research_officer still pays — two books, one per dealer
    # (ruling 9).
    ledgers = {"wolf_barkeep": {"favor": 1, "earned": ["thin_month_1"]}}
    assert rumor.offerable_rumors(
        ["thin_month_1"], ledgers, "research_officer",
    ) == [("thin_month_1", 1)]
    assert rumor.offerable_rumors(["thin_month_1"], ledgers, "wolf_barkeep") == []


def test_offerable_skips_stale_ids() -> None:
    assert rumor.offerable_rumors(["retired_rumor"], {}, "barkeep") == []


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
    # research_officer holds nothing in DEALERS, yet the resolver
    # prices the exclusive against the holding the host hands in —
    # phase-3 scatter composes, no rewrite (requires met by the
    # keyring, favor from the book).
    known = ["dark_berth_1", "dark_berth_2", "dark_berth_3"]
    ledgers = {"research_officer": {"favor": 4, "earned": []}}
    assert rumor.exclusive_offers(
        known, ledgers, "research_officer", (("dark_berth_4", 4),),
    ) == [("dark_berth_4", 4)]
    assert rumor.exclusive_offers(
        known, ledgers, "research_officer", find_dealer("research_officer").exclusives,
    ) == []


# --- the exchange mutations -------------------------------------------------


def test_offer_pays_value_once_per_dealer() -> None:
    ctx = SimpleNamespace(known_rumors=["thin_month_1"], rumor_favor={})
    assert rumor.offer_rumor(ctx, "research_officer", "thin_month_1") == 1
    assert ctx.rumor_favor == {
        "research_officer": {"favor": 1, "earned": ["thin_month_1"]},
    }
    assert rumor.offer_rumor(ctx, "research_officer", "thin_month_1") == 0
    assert ctx.rumor_favor["research_officer"]["favor"] == 1


def test_buy_spends_then_hears() -> None:
    ctx = SimpleNamespace(
        known_rumors=["dark_berth_1", "dark_berth_2", "dark_berth_3"],
        rumor_favor={"wolf_barkeep": {"favor": 4, "earned": ["thin_month_1"]}},
    )
    assert rumor.buy_exclusive(ctx, "wolf_barkeep", "dark_berth_4", 4) is True
    assert ctx.rumor_favor["wolf_barkeep"]["favor"] == 0
    assert ctx.known_rumors[-1] == "dark_berth_4"
    # The earned set is offer-history, not purchase-history — a buy
    # spends favor without touching it (ruling 13).
    assert ctx.rumor_favor["wolf_barkeep"]["earned"] == ["thin_month_1"]


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
    assert rumor.offer_rumor(ctx, "barkeep", "thin_month_1") == 0
    assert ctx.rumor_favor == {}


def test_offer_refuses_rumors_the_dealer_knows() -> None:
    # Same boundary, round-1 ruling side: no selling back to a
    # teller, whatever a host might render.
    ctx = SimpleNamespace(known_rumors=["thin_month_1"], rumor_favor={})
    assert rumor.offer_rumor(ctx, "barkeep", "thin_month_1") == 0
    assert ctx.rumor_favor == {}
