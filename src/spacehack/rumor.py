"""The rumor domain (doc 42): resolvers over the lore catalog and the
player's keyring.

Pure computation lives here; the hosts (``npc`` talk rows and the
quest-log ledger) call these — they never resolve ``rumor.*`` text
keys or read the catalog directly. Floors read the RESOLVED sheet the
host passes in (``identity.effective_reputation`` — dark → {} reads
neutral), so every function stays deterministic and ctx-free except
:func:`hear`.
"""

from __future__ import annotations

from typing import Callable

from .data.lore import RumorEntry, find_rumor, list_rumors
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


def hear(ctx, rumor_id: str) -> bool:
    """Record a heard rumor on the keyring; idempotent. Returns True
    when newly recorded."""
    find_rumor(rumor_id)
    if rumor_id in ctx.known_rumors:
        return False
    ctx.known_rumors.append(rumor_id)
    return True
