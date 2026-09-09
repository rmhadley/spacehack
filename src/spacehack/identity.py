"""The transponder / ID layer (doc 40): every ship broadcasts.

An ID is an identifier that maps to relations — the game's detect →
identify → rate → behave loop has lived in LIVE mode since day one;
this module adds the choice of which key readers resolve. Three
states: LIVE (true ratings — the pre-existing default), DARK (the
transponder is off; nothing resolves; countered only by physical
spotting and dense sensor lines), SPOOFED (a collected false ID
broadcasts in your place and its implied relations are what readers
react to).

Rep writes follow the broadcast (doc 40): LIVE moves the true
sheet, SPOOFED moves the worn ID's own sheet — a fake builds its
own record — and DARK records nothing. Reads resolve whichever
sheet broadcasts; only time decay always ages the true sheet.

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


def _worn_entry(ctx) -> dict[str, Any] | None:
    """The collected_ids entry for the ID being worn, or None.

    The library entry is the single source of truth for a face's
    sheet — ``broadcast_identity`` is a display copy that diverges
    from the entry after a save/load.
    """
    worn_id = (getattr(ctx, "broadcast_identity", None) or {}).get("id")
    for entry in getattr(ctx, "collected_ids", ()) or ():
        if entry.get("id") == worn_id:
            return entry
    return None


def effective_reputation(ctx) -> dict[str, int]:
    """What any reader resolves right now: the broadcasting ID's sheet.

    LIVE returns a copy of the true dict (ID 1's sheet). SPOOFED
    returns the worn ID's own sheet (absent keys read neutral at the
    reader's ``.get``). DARK returns empty — nothing resolves, every
    reader lands on neutral. Pure: fresh dict every call.
    """
    mode = broadcast_mode(ctx)
    if mode == DARK:
        return {}
    if mode == SPOOFED:
        entry = _worn_entry(ctx)
        return dict((entry or {}).get("rep") or {})
    return dict(getattr(ctx, "faction_reputation", None) or {})


def identity_label(identity: dict[str, Any] | None) -> str:
    """A one-line description for logs and the F-screen."""
    if identity is None:
        return "no broadcast"
    kind = identity.get("kind", "true")
    prefix = "Registration" if kind == "true" else _KIND_LABELS.get(kind, "ID")
    return f"{prefix} {identity.get('id', '??')}"


def toggle_dark(ctx) -> bool:
    """Flip the transponder off/on. False: no cut-out installed (doc 40
    phase 5) — dark is an installed capability, not a free breaker."""
    if not getattr(ctx, "transponder_cutout", False):
        ctx.log.add("No cut-out installed.")
        return False
    ctx.broadcast_dark = not getattr(ctx, "broadcast_dark", False)
    return True


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


def library_position(ctx) -> tuple[int, int]:
    """(position, total) in the ID cycle, 1-based, for display.

    Slot 1 is the true registration; each collected ID adds one. The
    position follows the worn/queued face even while dark — the count
    is what the cycle will resolve, not what currently broadcasts.
    """
    library = list(getattr(ctx, "collected_ids", ()) or ())
    ids = [entry.get("id") for entry in library]
    current = (getattr(ctx, "broadcast_identity", None) or {}).get("id")
    position = ids.index(current) + 2 if current in ids else 1
    return position, len(library) + 1


def collect_id(ctx, identity: dict[str, Any]) -> bool:
    """Add an illegal ID to the library. False: duplicate or the
    slot cap (doc 40 6b — every acquisition path funnels here).

    Acquisition is a process elsewhere (services, the capture
    pipeline — doc 40 rules it rare and involved); this only files
    the result.
    """
    if library_full(ctx):
        return False
    library = list(getattr(ctx, "collected_ids", ()) or [])
    if any(entry.get("id") == identity.get("id") for entry in library):
        return False
    library.append(dict(identity))
    ctx.collected_ids = library
    return True


def apply_worn_delta(ctx, faction: str, delta: int) -> None:
    """Route one rep delta onto the worn ID's sheet (doc 40: a fake
    builds its own record). The library entry is the single source
    of truth — its sheet is created on first write, and the log
    names the worn ID that actually moved."""
    from .faction import _apply_rep_delta
    entry = _worn_entry(ctx)
    if entry is None:
        return
    _apply_rep_delta(
        ctx, faction, delta,
        sheet=entry.setdefault("rep", {}),
        id_label=identity_label(entry),
    )


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
    can't afford, or the library already holds this hull number.

    A scrub IS a zero sheet: the entry materializes literal 0's for
    every faction (doc 40 ruling), so it starts as blank paper."""
    from .faction import _ALL_FACTIONS
    price = scrub_price(npc_id)
    if price is None or ctx.stats.credits < price:
        return False
    face = {
        "id": generate_registration(),
        "kind": "scrubbed",
        "label": "Scrubbed hull",
        "faction": None,
        "origin": "no history, no debts",
        "rep": {faction: 0 for faction in _ALL_FACTIONS},
    }
    if not collect_id(ctx, face):
        return False
    ctx.stats.credits -= price
    return True


# Cut-out techs: NPC id -> credits for the one-time transponder
# cut-out (doc 40 phase 5 — dark's price of entry). The storefront
# split is deliberate: scrub at Deadfall's broker, cut-out here.
CUTOUT_BROKERS: dict[str, int] = {
    "ember_tech": 2500,
}


# Rig dealers: NPC id -> credits for the clone rig (doc 40 phase 6a).
# Sold behind the dealer's talk gate; buying IDs from him is 6b.
RIG_BROKERS: dict[str, int] = {
    "wolf_rig_dealer": 9000,
}


# ID buyers: NPCs who pay sheet-derived prices for held IDs
# (doc 40 6b — the Wolf dealer is the whole frontier ID market).
ID_BUYERS: tuple[str, ...] = ("wolf_rig_dealer",)


def cutout_price(npc_id: str) -> int | None:
    """The cut-out install price a tech charges, or None."""
    return CUTOUT_BROKERS.get(npc_id)


def rig_price(npc_id: str) -> int | None:
    """The clone-rig price a dealer charges, or None."""
    return RIG_BROKERS.get(npc_id)


def buy_clone_rig(ctx, npc_id: str) -> bool:
    """Buy the clone rig. False: wrong NPC, can't afford, or owned.
    One-time; it rides the player across lawful purchases."""
    price = rig_price(npc_id)
    if price is None or getattr(ctx, "transponder_rig", False):
        return False
    if ctx.stats.credits < price:
        return False
    ctx.transponder_rig = True
    ctx.stats.credits -= price
    return True


def buy_transponder_cutout(ctx, npc_id: str) -> bool:
    """Install the one-time cut-out. False: wrong NPC, can't afford,
    or already installed. It rides the player across lawful purchases."""
    price = cutout_price(npc_id)
    if price is None or getattr(ctx, "transponder_cutout", False):
        return False
    if ctx.stats.credits < price:
        return False
    ctx.transponder_cutout = True
    ctx.stats.credits -= price
    return True


LIBRARY_CAP = 6

ID_SELL_BASE = 500
ID_SELL_RATE = 100


def library_full(ctx) -> bool:
    """Whether the ID library has hit its slot cap (doc 40 6b)."""
    return len(list(getattr(ctx, "collected_ids", ()) or [])) >= LIBRARY_CAP


def sell_value(entry: dict[str, Any]) -> int:
    """What a dealer pays for an ID: base + rate per positive rep
    point on the ENTRY's sheet (doc 40 6b — identities are
    appreciable assets; the ground-up flip is the intended loop)."""
    _sheet = entry.get("rep") or {}
    return ID_SELL_BASE + ID_SELL_RATE * sum(
        max(0, int(v)) for v in _sheet.values()
    )


def remove_id(ctx, entry_id: str) -> bool:
    """Remove one library entry by hull number. False: not held.

    Removing the WORN entry auto-clears the broadcast to live (user
    ruling 2026-09-07) — a removed ID can never keep broadcasting.
    """
    library = list(getattr(ctx, "collected_ids", ()) or [])
    _kept = [entry for entry in library if entry.get("id") != entry_id]
    if len(_kept) == len(library):
        return False
    ctx.collected_ids = _kept
    _worn = getattr(ctx, "broadcast_identity", None)
    if _worn is not None and _worn.get("id") == entry_id:
        ctx.broadcast_identity = None
    return True


__all__ = [
    "LIVE", "DARK", "SPOOFED",
    "npc_identity", "effective_reputation",
    "apply_worn_delta",
    "scrub_price", "buy_scrubbed_id",
    "cutout_price", "buy_transponder_cutout",
    "clone_tier", "roll_clone_sheet", "clone_transponder",
    "rig_price", "buy_clone_rig",
    "LIBRARY_CAP", "library_full", "sell_value", "remove_id",
    "ID_BUYERS",
    "generate_registration", "broadcast_mode", "resolved_identity",
    "identity_label", "toggle_dark", "cycle_identity", "collect_id",
    "library_position", "ensure_registration",
]


# Clone roll bands (doc 40 phase 6a — user-tunable): the source
# faction's values roll in a band that scales with the source hull's
# tier (base_hull thresholds below); every other faction rolls
# near-neutral. Higher tier = better odds of a strong sheet.
CLONE_TIER_BANDS: tuple[int, int] = (40, 80)
CLONE_SOURCE_BANDS: dict[int, tuple[int, int]] = {
    1: (0, 60), 2: (10, 80), 3: (25, 100),
}
CLONE_OTHER_BAND: tuple[int, int] = (-20, 20)


def clone_tier(base_hull: int) -> int:
    """Source hull tier 1..3 from the hull class's base_hull."""
    if base_hull <= CLONE_TIER_BANDS[0]:
        return 1
    if base_hull <= CLONE_TIER_BANDS[1]:
        return 2
    return 3


def roll_clone_sheet(
    source_faction: str, tier: int, rng: random.Random | None = None,
) -> dict[str, int]:
    """The one roll per captured source: the sheet is generated here
    and persisted on the library entry (doc 40 phase 6a)."""
    chooser = rng or random
    from .faction import _ALL_FACTIONS
    _lo, _hi = CLONE_SOURCE_BANDS.get(
        max(1, min(3, tier)), CLONE_SOURCE_BANDS[2],
    )
    sheet: dict[str, int] = {}
    for faction in _ALL_FACTIONS:
        lo, hi = (_lo, _hi) if faction == source_faction else CLONE_OTHER_BAND
        sheet[faction] = chooser.randint(lo, hi)
    return sheet


def clone_transponder(
    ctx, spec, rng: random.Random | None = None,
) -> dict[str, Any] | None:
    """Clone a captured ship's transponder at its C console (6a).

    The roll generates the sheet once and the entry persists it.
    None: the library already holds this hull number (vanishingly
    unlikely — each clone rolls a fresh registration)."""
    from .data.ships import find_ship
    try:
        tier = clone_tier(find_ship(spec.ship_id).base_hull)
    except KeyError:
        tier = 1
    face = {
        "id": generate_registration(rng),
        "kind": "cloned",
        "label": "Cloned hull",
        "faction": spec.faction,
        "origin": f"cloned from a captured {spec.name}",
        "rep": roll_clone_sheet(spec.faction, tier, rng),
    }
    if not collect_id(ctx, face):
        return None
    return face
