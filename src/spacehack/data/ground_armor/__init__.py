"""Ground-combat armor catalog: vests, helmets, gloves, boots.

Each item is a frozen :class:`GroundArmorSpec`. Adding a new armor
is one entry in a WARES tuple — no if/else chains.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundArmorSpec:
    """One equippable ground-combat armor piece.

    Attributes:
        id: registry key, e.g. ``light_vest``.
        name: display name, e.g. ``Light Armor Vest``.
        slot: ``"head"``, ``"body"``, ``"hands"``, ``"legs"``, or
            ``"feet"`` — the vocabulary :func:`slot_tiers` ladders
            and ``worn_armor_slots`` authors.
        defense: flat damage reduction applied per hit.
        description: one-line flavour text.
        price: credits cost to buy from an armory.
        tech_level: minimum planet tech level to stock this item.
        ap_bonus: +action points per ground-combat turn (cybernetics).
        hit_bonus: +% hit chance (cybernetics).
        melee_bonus: +flat melee damage (cybernetics).
        hp_bonus: +flat max ground HP (cybernetics).
    """
    id: str
    name: str
    slot: str                     # "head", "body", "hands", "legs", "feet"
    defense: int                  # flat damage reduction
    description: str
    price: int = 0
    tech_level: int = 1
    ap_bonus: int = 0
    hit_bonus: int = 0
    melee_bonus: int = 0
    hp_bonus: int = 0


# ---------------------------------------------------------------------------
# Lazy-built registry
# ---------------------------------------------------------------------------

_BY_ID: dict[str, GroundArmorSpec] | None = None


def _build_registry() -> dict[str, GroundArmorSpec]:
    """Auto-discover all ground-armor modules under this package."""
    import importlib, pkgutil
    combined: dict[str, GroundArmorSpec] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if hasattr(mod, "WARES"):
            for w in mod.WARES:
                combined[w.id] = w
    return combined


def _registry() -> dict[str, GroundArmorSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_ground_armor(armor_id: str) -> GroundArmorSpec:
    """Look up a :class:`GroundArmorSpec` by id; raises :class:`KeyError` on miss."""
    try:
        return _registry()[armor_id]
    except KeyError:
        raise KeyError(f"unknown ground armor id: {armor_id!r}") from None


def list_ground_armor() -> tuple[GroundArmorSpec, ...]:
    """All registered ground armor, in undefined order."""
    return tuple(_registry().values())

def _is_cybernetic(spec) -> bool:
    """A cyber piece carries at least one of the four bonus fields —
    band rolls never hand them out (cyber stays row-authored, doc 48
    SETTLED 55)."""
    return bool(
        spec.ap_bonus or spec.hit_bonus
        or spec.melee_bonus or spec.hp_bonus
    )


def slot_tiers() -> dict[str, dict[int, tuple[str, ...]]]:
    """Per-slot ladders of band-rollable armor ids by tech level —
    the weapon ``family_tiers`` twin (doc 48 SETTLED 55): specs name
    eligible SLOTS, bands roll the tier, and the ladder derives from
    the catalog at call time so new armor content joins the bands
    with no list edits. Cybernetic pieces are excluded (row-authored
    only); unknown slots simply carry no ladder (the roll skips)."""
    ladders: dict[str, dict[int, list[str]]] = {}
    for spec in list_ground_armor():
        if _is_cybernetic(spec):
            continue
        ladders.setdefault(spec.slot, {}).setdefault(
            spec.tech_level, [],
        ).append(spec.id)
    return {
        slot: {tier: tuple(ids) for tier, ids in sorted(tiers.items())}
        for slot, tiers in ladders.items()
    }
