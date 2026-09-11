"""Dealer-spec integrity (doc 42 phase 2).

The favor exchange is data-defined, so the data test is the
enforcement: dealers seat real NPCs, exclusives price real rumors,
and exclusives are never free-asked (empty sources, ruling 12).
"""

import pytest

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
