"""The transponder / ID layer (doc 40): every ship broadcasts.

An ID is an identifier that maps to relations — the game's detect →
identify → rate → behave loop has lived in LIVE mode since day one;
this module adds the choice of which key readers resolve. Three
states: LIVE (true ratings — the pre-existing default), DARK (the
transponder is off; nothing resolves; countered only by physical
spotting and dense sensor lines), SPOOFED (a collected false ID
broadcasts in your place and its implied relations are what readers
react to).

Rep moves only while live — actions under a fake ID cannot alter
the true ID (the mask cuts both ways on both axes: friends don't
recognize you, and your deeds don't follow you home).

Design doc: docs/design/in_progress/40_DESIGN_TRANSPONDER_ID.md
"""

from __future__ import annotations

import random
from typing import Any

LIVE = "live"
DARK = "dark"
SPOOFED = "spoofed"

# The three spoof sources and what a reader resolves for each.
_KIND_LABELS = {
    "scrubbed": "Scrubbed hull",
    "cloned": "Cloned ID",
    "fabricated": "Fabricated ID",
}


def generate_registration(rng: random.Random | None = None) -> str:
    """A Sol-registry hull number (``SC-4471``) for the player's ship.

    Two letters + four digits; generated once per run and persisted.
    """
    chooser = rng or random
    letters = chooser.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
    letters += chooser.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
    return f"{letters}-{chooser.randint(1000, 9999)}"


def broadcast_mode(ctx) -> str:
    """The ship's broadcast state: LIVE, DARK, or SPOOFED.

    DARK is the master switch — the transponder is off, so nothing
    broadcasts even with a face worn and ready. A worn identity is
    applied only when the transponder is on.
    """
    if getattr(ctx, "broadcast_dark", False):
        return DARK
    if getattr(ctx, "broadcast_identity", None) is not None:
        return SPOOFED
    return LIVE


def resolved_identity(ctx) -> dict[str, Any] | None:
    """What a scanner reads right now, or None (dark / nothing worn).

    LIVE resolves the true registration (readers then pull the true
    faction ratings — the pre-existing behavior). SPOOFED resolves
    the worn false ID. DARK resolves nothing.
    """
    mode = broadcast_mode(ctx)
    if mode == SPOOFED:
        return ctx.broadcast_identity
    if mode == LIVE:
        return {
            "id": getattr(ctx, "ship_registration", ""),
            "kind": "true",
            "label": "Your true registration",
            "faction": None,
        }
    return None


def identity_label(identity: dict[str, Any] | None) -> str:
    """A one-line description for logs and the F-screen."""
    if identity is None:
        return "no broadcast"
    kind = identity.get("kind", "true")
    prefix = "Registration" if kind == "true" else _KIND_LABELS.get(kind, "ID")
    return f"{prefix} {identity.get('id', '??')}"


def toggle_dark(ctx) -> None:
    """Flip the transponder off/on (free — it is your ship's breaker)."""
    ctx.broadcast_dark = not getattr(ctx, "broadcast_dark", False)


def cycle_identity(ctx, step: int = 1) -> None:
    """Move to the next collected illegal ID (or back to none).

    Cycling is the F-screen interaction: none → first → ... → last →
    none. The library rides the player; a fresh lawful ship purchase
    does not lose it (identity rides the player across lawful
    purchases — the registry transfers the owner).
    """
    library = list(getattr(ctx, "collected_ids", ()) or ())
    if not library:
        return
    worn = getattr(ctx, "broadcast_identity", None)
    current = worn.get("id") if worn else None
    ids = [entry.get("id") for entry in library]
    next_index = 0 if current is None or current not in ids else (
        (ids.index(current) + step) % (len(ids) + (1 if step > 0 else 0))
    )
    if current is not None and step > 0 and ids.index(current) == len(ids) - 1:
        next_index = None  # cycling off the end returns to no face
    ctx.broadcast_identity = (
        dict(library[next_index]) if next_index is not None else None
    )


def collect_id(ctx, identity: dict[str, Any]) -> bool:
    """Add an illegal ID to the library. Returns False on duplicates.

    Acquisition is a process elsewhere (services, the capture
    pipeline — doc 40 rules it rare and involved); this only files
    the result.
    """
    library = list(getattr(ctx, "collected_ids", ()) or [])
    if any(entry.get("id") == identity.get("id") for entry in library):
        return False
    library.append(dict(identity))
    ctx.collected_ids = library
    return True


def ensure_registration(ctx) -> str:
    """The ship's registration, generating and persisting one if absent.

    Existing saves migrate here: first load after the layer ships
    assigns a registration (the hull was always registered — the
    paper just wasn't on screen).
    """
    reg = getattr(ctx, "ship_registration", "")
    if reg:
        return reg
    reg = generate_registration()
    ctx.ship_registration = reg
    return reg


def npc_identity(entity) -> dict[str, Any] | None:
    """What an NPC ship broadcasts, from its catalog spec.

    NPCs broadcast by default (the honest asymmetry: a merchant
    stamps its guild proudly; a pirate in lawless space stamps
    openly — "one of us" is the safety). Each hull carries a
    registration generated on first read and kept for its life —
    readers see a hull number, same flavor as the player's. Returns
    None for non-ships.
    """
    _pid = getattr(entity, "npc_ship_id", "")
    if not _pid:
        return None
    from .data.npc_ships import find_npc_ship
    try:
        _spec = find_npc_ship(_pid)
    except (KeyError, ImportError):
        return None
    _reg = getattr(entity, "npc_registration", "")
    if not isinstance(_reg, str) or not _reg:
        _reg = generate_registration()
        entity.npc_registration = _reg
    return {
        "id": _reg,
        "kind": "npc",
        "label": _spec.name,
        "faction": getattr(_spec, "faction", None),
    }


def apparent_faction(ctx) -> str | None:
    """The faction a reader resolves from the current broadcast.

    LIVE resolves the player's true relations — readers then pull
    faction_reputation (the pre-existing behavior). SPOOFED resolves
    the worn face's faction (a pirate face in Ross reads as one of
    theirs). DARK resolves nothing.
    """
    worn = resolved_identity(ctx)
    if worn is None:
        return None
    return worn.get("faction") or None


# Scrub brokers: NPC id -> credits for one scrubbed ID (doc 40 Q6 —
# acquisition is rare, involved, and PRICED; the first sandbox vector.
# Militia/fabricated ids come from act 1 quest content, not purchasable).
SCRUB_BROKERS: dict[str, int] = {
    "deadfall_scrubber": 6000,
}


def scrub_price(npc_id: str) -> int | None:
    """The scrubbed-ID price a broker NPC charges, or None."""
    return SCRUB_BROKERS.get(npc_id)


def buy_scrubbed_id(ctx, npc_id: str) -> bool:
    """Purchase one scrubbed ID from a broker. False: wrong NPC,
    can't afford, or the library already holds this hull number."""
    price = scrub_price(npc_id)
    if price is None or ctx.stats.credits < price:
        return False
    face = {
        "id": generate_registration(),
        "kind": "scrubbed",
        "label": "Scrubbed hull",
        "faction": None,
        "origin": "no history, no debts",
    }
    if not collect_id(ctx, face):
        return False
    ctx.stats.credits -= price
    return True


__all__ = [
    "LIVE", "DARK", "SPOOFED",
    "npc_identity", "apparent_faction",
    "scrub_price", "buy_scrubbed_id",
    "generate_registration", "broadcast_mode", "resolved_identity",
    "identity_label", "toggle_dark", "cycle_identity", "collect_id",
    "ensure_registration",
]
