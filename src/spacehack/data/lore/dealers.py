"""Info dealers (doc 42 phase 2): the seats that trade in favors.

A dealer is an authored NPC seat that buys heard rumors at the
rumor's authored value. Exclusive holdings — rumors with empty
sources, never free-asked, sold at a per-rumor price against that
dealer's ledger — live in :data:`EXCLUSIVE_CANDIDATES` (doc 42
phase 3, SETTLED 17): each exclusive authors candidate
``(dealer, price)`` pairs and the run's seed picks the live holder
via ``rumor_routing.live_holdings``. Rows are structural; the book
itself lives on ctx (``rumor_favor``, ruling 13).

The ledger keys the ROLE id, so any seat of that id honors the same
book — uniform with every other npc-id-keyed table (ruling 9).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DealerSpec:
    """One info dealer: an existing NPC seat that trades in favors."""

    dealer_npc_id: str


DEALERS: tuple[DealerSpec, ...] = (
    DealerSpec(dealer_npc_id="barkeep"),
    DealerSpec(dealer_npc_id="wolf_barkeep"),
    DealerSpec(dealer_npc_id="research_officer"),
)

# Authored exclusive candidates (SETTLED 17): rumor id → the dealers
# that may hold it this run, each with their price. The seed picks
# exactly one live holder per run (rumor_routing.live_holdings).
EXCLUSIVE_CANDIDATES: dict[str, tuple[tuple[str, int], ...]] = {
    "dark_berth_4": (
        ("barkeep", 4),
        ("wolf_barkeep", 4),
        ("research_officer", 4),
    ),
}

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
