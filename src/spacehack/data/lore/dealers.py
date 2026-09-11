"""Info dealers (doc 42 phase 2): the seats that trade in favors.

A dealer is an authored NPC seat that buys heard rumors at the
rumor's authored value and may hold exclusives — rumors with empty
sources, never free-asked, sold at a per-rumor price against that
dealer's ledger. Rows are structural; the book itself lives on ctx
(``rumor_favor``, ruling 13).

The ledger keys the ROLE id, so any seat of that id honors the same
book — uniform with every other npc-id-keyed table (ruling 9).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DealerSpec:
    """One info dealer: an existing NPC seat plus what they hold.

    Attributes:
        dealer_npc_id: the role id keying the ledger (``rumor_favor``
            uses this id as its key).
        exclusives: ``(rumor_id, price)`` pairs this dealer sells;
            empty for buy-side-only dealers.
    """

    dealer_npc_id: str
    exclusives: tuple[tuple[str, int], ...] = ()


DEALERS: tuple[DealerSpec, ...] = (
    DealerSpec(dealer_npc_id="barkeep"),
    DealerSpec(
        dealer_npc_id="wolf_barkeep",
        exclusives=(("dark_berth_4", 4),),
    ),
    DealerSpec(dealer_npc_id="research_officer"),
)

_BY_ID: dict[str, DealerSpec] = {
    spec.dealer_npc_id: spec for spec in DEALERS
}


def find_dealer(npc_id: str) -> DealerSpec:
    """Look up a dealer by NPC id; raises ``KeyError``."""
    try:
        return _BY_ID[npc_id]
    except KeyError:
        raise KeyError(f"not a dealer: {npc_id!r}") from None


def is_dealer(npc_id: str) -> bool:
    """Whether this NPC id seats a dealer."""
    return npc_id in _BY_ID
