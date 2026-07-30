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
        slot: ``"helmet"``, ``"vest"``, ``"gloves"``, or ``"boots"``.
        defense: flat damage reduction applied per hit.
        description: one-line flavour text.
        price: credits cost to buy from an armory.
        tech_level: minimum planet tech level to stock this item.
    """
    id: str
    name: str
    slot: str                     # "helmet", "vest", "gloves", "boots"
    defense: int                  # flat damage reduction
    description: str
    price: int = 0
    tech_level: int = 1


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
