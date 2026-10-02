"""Ground loadout stamp pins — the one hand-stamp builder (doc 48
phase 9, SETTLED 43).

A pin never starves a weapon by accident: both set keys are present
(an absent ``melee`` key means unresolved-and-will-fill) and every
ammo-fed pinned weapon arrives with a FULL magazine plus one pool
entry. Shared by the tactics, flee, and tombstone suites so the law
lives once.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import ground_scale
from src.spacehack.data.ground_weapons import find_ground_weapon


def pinned_loadout(ranged=None, melee=None, **extra) -> dict:
    """A hand-pinned two-set stamp; ``**extra`` overrides any field."""
    stamp = {
        "ranged": list(ranged) if ranged else None,
        "melee": list(melee) if melee else None,
        "loaded": {}, "pool": [], "active": "ranged",
    }
    for _pair_name in ("ranged", "melee"):
        _pair = stamp[_pair_name]
        if not _pair:
            continue
        _ws = find_ground_weapon(_pair[0])
        if not ground_scale.ammo_fed(_ws):
            continue
        stamp["loaded"][_pair[0]] = _ws.ammo_capacity
        _feed = ground_scale.pool_feed(_ws.ammo_type)
        if _feed is not None and not any(
            _e[0] == "ammo" and _e[1] == _feed[0] for _e in stamp["pool"]
        ):
            _entry = ground_scale.roll_pool_entry(
                _ws.ammo_type, SimpleNamespace(randint=lambda lo, hi: hi),
            )
            if _entry is not None:
                stamp["pool"].append(_entry)
    stamp.update(extra)
    return stamp


def pin_entity_loadout(entity, weapon_id: str, quality: int = 0) -> None:
    """Stamp a deterministic full loadout on an entity pre-init (doc 48
    SETTLED 43 — the instance weapon DERIVES from the entity stamp)."""
    entity.rolled_loadout = pinned_loadout((weapon_id, quality))
