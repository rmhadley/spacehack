"""Lore catalog: authored rumor chains (doc 42).

Each :class:`RumorEntry` is a frozen dataclass row in a sibling
module (``chains.py``) — the ``data/missions`` shape. Adding a rumor
is one row plus its prose keys in ``data/text/08_rumors.json``.

Rows are STRUCTURAL. All prose lives in the JSON overlay under keys
derived from the id — the catalog never stores text:

    rumor.<id>.topic              short askable label (sub-menu row)
    rumor.<id>.text               canonical text (readout + ledger)
    rumor.<id>.witness.<npc_id>   per-source delivery override
                                  (conversation flavor only)

Chain linkage is internal to the catalog (``chain`` + ``tier`` +
``requires``) — the main-quest machinery is not involved.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RumorEntry:
    """One rumor in an authored chain.

    Attributes:
        id: registry key; also the JSON prose key path
            (``rumor.<id>.*``).
        chain: authored chain id shared by the tiered entries.
        tier: 1-based depth within the chain; tier 1 needs no
            ``requires``.
        requires: rumor ids that must already be known before this
            entry can surface.
        sources: who can deliver this entry — tuples of
            ``(npc_id, faction | None, min_standing | None,
            trait | None)`` in the shipped ``talk_gate`` shape. The
            floor reads the RESOLVED sheet's standing for ``faction``
            (``None`` = no floor); ``trait`` demands a quest perk or
            trait when set.
    """

    id: str
    chain: str
    tier: int
    requires: tuple[str, ...] = ()
    sources: tuple[tuple[str, str | None, int | None, str | None], ...] = ()


def _build_registry() -> dict[str, RumorEntry]:
    from . import chains as chains_module

    return {entry.id: entry for entry in chains_module.CHAINS}


_BY_ID: dict[str, RumorEntry] | None = None


def _registry() -> dict[str, RumorEntry]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_rumor(rumor_id: str) -> RumorEntry:
    """Look up a :class:`RumorEntry` by id; raises ``KeyError``."""
    try:
        return _registry()[rumor_id]
    except KeyError:
        raise KeyError(f"unknown rumor id: {rumor_id!r}") from None


def list_rumors() -> tuple[RumorEntry, ...]:
    """All registered rumors (undefined order)."""
    return tuple(_registry().values())
