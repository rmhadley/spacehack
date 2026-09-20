"""Shared loot-floor bookkeeping (doc 47 phase 1).

One pure colour table and one entity cap, used by every loot
constructor: hue answers CONTENT — equipment / field items /
cargo / data — never source (SETTLED 5; brightness-for-quality
arrives with phase 2). The cap is shared by both kill paths and
never evicts quest/pad/heist loot (quest-loot security); the
space path previously evicted blind, so exterior heist cargo
could be destroyed by debris churn.
"""
from __future__ import annotations

# Category hues — initial values, tuned at the phase-1 playtest.
EQUIPMENT_FG = (130, 145, 170)   # muted steel — weapons / armor
FIELD_ITEM_FG = (200, 175, 110)  # amber — ammo / consumable stacks
CARGO_FG = (255, 215, 0)         # gold — trade goods
DATA_FG = (190, 190, 255)        # pale violet — pads + quest caches
MISSION_FG = (0, 255, 255)       # cyan — mission / heist cargo (unchanged)

# Payload keys that mark data-class loot (pads teach/reveal; quest
# caches carry a goods manifest).
_DATA_KEYS = ("teaches", "reveals_site", "goods")

_TYPE_FG = {
    "weapon": EQUIPMENT_FG,
    "armor": EQUIPMENT_FG,
    "module": EQUIPMENT_FG,
    "ammo": FIELD_ITEM_FG,
    "consumable": FIELD_ITEM_FG,
}

# Max loot entities on one map; beyond this the oldest NON-protected
# loot is evicted when new loot spawns (silently — SETTLED 8).
MAX_LOOT_ENTITIES: int = 30

# Brightness answers HOW GOOD (SETTLED 5): each tier above base steps
# the equipment hue brighter. The legendary row (4) is live since the
# doc-47 phase-4 delve-bottom guarantee — randarts are its only source.
# Initial values, tuned at playtest.
_QUALITY_BRIGHTNESS: tuple[float, ...] = (1.0, 1.10, 1.22, 1.36, 1.55)


def _brighten(rgb: tuple[int, int, int], quality: int) -> tuple[int, int, int]:
    """Step one hue brighter by tier, clamped at the display maximum."""
    if quality <= 0:
        return rgb
    index = min(quality, len(_QUALITY_BRIGHTNESS) - 1)
    factor = _QUALITY_BRIGHTNESS[index]
    return tuple(min(255, int(channel * factor + 0.5)) for channel in rgb)

# Entity-level markers (set post-construction, read via getattr).
_PROTECTED_ATTRS = ("main_quest_step_id", "heist_mission")


def equipment_payload(
    item_type: str, item_id: str, quality: int = 0,
    randart_seed: int | None = None,
) -> dict:
    """One equipment loot payload; the quality key rides only when > 0
    and the randart seed only when set (base-tier payloads stay
    byte-identical to the pre-quality shape)."""
    payload = {"item_type": item_type, "item_id": item_id}
    if quality > 0:
        payload["quality"] = quality
    if randart_seed is not None:
        payload["randart_seed"] = randart_seed
    return payload


# Container kinds (doc 47.4 SETTLED 6/22): chips are common
# small-value scatter; the lockbox is the digs' rare-cache variant.
CREDIT_CHIP_KIND = "chip"
LOCKBOX_KIND = "lockbox"


def credits_payload(amount: int, kind: str) -> dict:
    """One credit-container payload — picked up as immediate credits
    (never enters the hold; kill drops stay trade-goods)."""
    return {"credits": int(amount), "credits_kind": kind}


def loot_fg(loot_data: dict | None, *, mission: bool = False):
    """Return the category colour for one loot payload (pure).

    Equipment hues brighten with the payload's rolled quality;
    every other category ignores it.
    """
    if mission:
        return MISSION_FG
    if loot_data is None:
        return CARGO_FG
    if any(key in loot_data for key in _DATA_KEYS):
        return DATA_FG
    if "credits" in loot_data:
        return CARGO_FG  # chips/lockboxes read as immediate value (gold)
    fg = _TYPE_FG.get(loot_data.get("item_type"), CARGO_FG)
    if fg is EQUIPMENT_FG:
        return _brighten(fg, loot_data.get("quality", 0))
    return fg


def is_protected_loot(entity) -> bool:
    """True for loot that must never be evicted by the cap.

    Quest caches (goods manifest or step id), teaching/reveal pads,
    and heist/mission cargo — the quest-loot security classes.
    """
    data = getattr(entity, "loot_data", None)
    if data is None:
        return False
    if any(key in data for key in _DATA_KEYS):
        return True
    return any(getattr(entity, attr, None) for attr in _PROTECTED_ATTRS)


def enforce_loot_cap(game_map) -> None:
    """Evict the oldest non-protected loot beyond the cap (silent).

    Removal is identity-based: Entity equality is value-based
    (plain dataclass), so a protected entity can be ``==`` to plain
    debris — evicting by value could delete the protected twin.
    """
    loot = [e for e in game_map.entities if getattr(e, "loot_data", None) is not None]
    excess = len(loot) - MAX_LOOT_ENTITIES
    doomed: set[int] = set()
    for entity in loot:
        if excess <= 0:
            break
        if is_protected_loot(entity):
            continue
        doomed.add(id(entity))
        excess -= 1
    if doomed:
        game_map.entities[:] = [e for e in game_map.entities if id(e) not in doomed]
