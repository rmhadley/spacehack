"""The rumor domain (doc 42): resolvers over the lore catalog and the
player's keyring, plus the favor exchange (phase 2).

Pure computation lives here; the hosts (``npc`` talk rows and the
quest-log ledger) call these — they never resolve ``rumor.*`` text
keys or read the catalog directly. Floors read the RESOLVED sheet the
host passes in (``identity.effective_reputation`` — dark → {} reads
neutral), so every function stays deterministic and ctx-free except
the three mutation wrappers (``hear``, ``offer_rumor``,
``buy_exclusive``).
"""

from __future__ import annotations

from typing import Callable

from .data.lore import RumorEntry, find_rumor, list_rumors
from .data.lore.dealers import find_dealer, is_dealer
from .text import get as _text_get


def routing_all(rumor_id: str) -> bool:
    """Phase-1 routing: every authored chain is live this run."""
    return True


def _source_passes(
    source: tuple[str, str | None, int | None, str | None],
    resolved_rep: dict[str, int],
    player_traits,
) -> bool:
    """The talk-gate comparison: resolved standing meets the floor,
    and a trait-gated source demands the trait."""
    _, faction, min_standing, trait = source
    if faction is not None and resolved_rep.get(faction, 0) < (min_standing or 0):
        return False
    if trait is not None and trait not in (player_traits or ()):
        return False
    return True


def _delivers(
    entry: RumorEntry,
    npc_id: str,
    resolved_rep: dict[str, int],
    player_traits,
) -> bool:
    return any(
        source[0] == npc_id
        and _source_passes(source, resolved_rep, player_traits)
        for source in entry.sources
    )


def _chain_entries(chain: str) -> list[RumorEntry]:
    return sorted(
        (entry for entry in list_rumors() if entry.chain == chain),
        key=lambda entry: entry.tier,
    )


def _next_entry(entry: RumorEntry) -> RumorEntry | None:
    for candidate in _chain_entries(entry.chain):
        if candidate.tier == entry.tier + 1:
            return candidate
    return None


def _requirements_met(entry: RumorEntry, known_set: set[str]) -> bool:
    return all(required in known_set for required in entry.requires)


def topic_label(rumor_id: str) -> str:
    """The short askable label (``rumor.<id>.topic``)."""
    return _text_get(f"rumor.{rumor_id}.topic", rumor_id.replace("_", " "))


def entry_text(rumor_id: str) -> str:
    """The canonical entry text — what the ledger records."""
    return _text_get(f"rumor.{rumor_id}.text", "")


def witness_text(rumor_id: str, npc_id: str) -> str:
    """The text as this NPC delivers it — the witness override when
    one is authored, else the canonical entry text."""
    return (
        _text_get(f"rumor.{rumor_id}.witness.{npc_id}", "")
        or entry_text(rumor_id)
    )


def askable_topics(
    known: list[str],
    resolved_rep: dict[str, int],
    player_traits,
    npc_id: str,
    *,
    routing: Callable[[str], bool] = routing_all,
) -> list[tuple[str, str]]:
    """``(topic, rumor_id)`` rows for everything this NPC can tell
    you: unheard chain openers they can deliver, plus the next tier
    of any heard chain they can extend. The ONE ask surface — the
    main talk menu carries a single Ask around row when this is
    non-empty (user ruling, 2026-09-11)."""
    known_set = set(known)
    rows: list[tuple[str, str]] = []
    for entry in list_rumors():
        if entry.tier != 1 or entry.id in known_set:
            continue
        if not routing(entry.id):
            continue
        if not _delivers(entry, npc_id, resolved_rep, player_traits):
            continue
        rows.append((topic_label(entry.id), entry.id))
    for rumor_id in known:
        try:
            heard = find_rumor(rumor_id)
        except KeyError:
            continue  # stale id from an older save — the ledger forgets it
        nxt = _next_entry(heard)
        if (
            nxt is None
            or nxt.id in known_set
            or not _requirements_met(nxt, known_set)
            or not routing(nxt.id)
            or not _delivers(nxt, npc_id, resolved_rep, player_traits)
        ):
            continue
        rows.append((topic_label(rumor_id), nxt.id))
    return rows


def known_entries(known: list[str]) -> list[RumorEntry]:
    """Heard entries in heard order — the ledger's content. Stale ids
    from older saves are skipped, never raised: knowledge can fade,
    the game must not crash on it."""
    entries = []
    for rumor_id in known:
        try:
            entries.append(find_rumor(rumor_id))
        except KeyError:
            continue
    return entries


# --- the favor exchange (phase 2): pure resolvers -------------------------


def favor_for(ledgers: dict, dealer_id: str) -> int:
    """The player's favor with one dealer (0 for an unopened book)."""
    return int((ledgers.get(dealer_id) or {}).get("favor", 0))


def _earned(ledgers: dict, dealer_id: str) -> set[str]:
    return set((ledgers.get(dealer_id) or {}).get("earned", ()) or ())


def offerable_rumors(
    known: list[str], ledgers: dict, dealer_id: str,
) -> list[tuple[str, int]]:
    """``(rumor_id, value)`` for everything this dealer will buy:
    heard, never sold to THEM, and worth something (ruling 10's
    uniform buy side)."""
    earned = _earned(ledgers, dealer_id)
    rows: list[tuple[str, int]] = []
    for rumor_id in known:
        if rumor_id in earned:
            continue
        try:
            value = find_rumor(rumor_id).value
        except KeyError:
            continue  # stale id from an older save — nothing to sell
        if value > 0:
            rows.append((rumor_id, value))
    return rows


def exclusive_offers(
    known: list[str],
    ledgers: dict,
    dealer_id: str,
    holdings: tuple[tuple[str, int], ...],
) -> list[tuple[str, int]]:
    """``(rumor_id, price)`` for the dealer's exclusives you may buy:
    requires met, unheard, and favor ≥ price — hidden until
    affordable (ruling 11). ``holdings`` is the dealer's exclusive
    set as an explicit input: the phase-3 routing seam."""
    known_set = set(known)
    favor = favor_for(ledgers, dealer_id)
    rows: list[tuple[str, int]] = []
    for rumor_id, price in holdings:
        if rumor_id in known_set:
            continue
        if not _requirements_met(find_rumor(rumor_id), known_set):
            continue
        if favor < price:
            continue
        rows.append((rumor_id, price))
    return rows


def hear(ctx, rumor_id: str) -> bool:
    """Record a heard rumor on the keyring; idempotent. Returns True
    when newly recorded."""
    find_rumor(rumor_id)
    if rumor_id in ctx.known_rumors:
        return False
    ctx.known_rumors.append(rumor_id)
    return True


# --- the favor exchange (phase 2): mutation wrappers -----------------------


def _ledger(ctx, dealer_id: str) -> dict:
    """The dealer's book on the player, created on first contact."""
    return ctx.rumor_favor.setdefault(dealer_id, {"favor": 0, "earned": []})


def offer_rumor(ctx, dealer_id: str, rumor_id: str) -> int:
    """Sell a heard rumor: +its authored value, once per
    (rumor, dealer). Returns the favor earned (0 when the keyring
    doesn't know it or this book already paid)."""
    if rumor_id not in ctx.known_rumors:
        return 0
    value = find_rumor(rumor_id).value
    book = _ledger(ctx, dealer_id)
    if rumor_id in book["earned"]:
        return 0
    book["earned"].append(rumor_id)
    book["favor"] += value
    return value


def buy_exclusive(ctx, dealer_id: str, rumor_id: str, price: int) -> bool:
    """Buy a held exclusive: floor-guarded spend, then :func:`hear`.
    False — with no state touched — when the favor can't cover the
    price or the knowledge is already on the keyring."""
    find_rumor(rumor_id)
    if rumor_id in ctx.known_rumors or favor_for(ctx.rumor_favor, dealer_id) < price:
        return False
    book = _ledger(ctx, dealer_id)
    book["favor"] -= price
    hear(ctx, rumor_id)
    return True


# Re-exports: hosts read the dealer registry through this facade,
# never from the data module directly.
__all__ = ["find_dealer", "is_dealer"]
