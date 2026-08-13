"""Ground-combat weapons catalog: specs for all equippable personal weapons.

Each weapon is a frozen :class:`GroundWeaponSpec` dataclass, distinct
from ship :class:`spacehack.data.weapons.WeaponSpec` — ground weapons
use :attr:`damage_type` (melee/kinetic/energy/plasma/explosive) instead
of ``slot_type``, and ``hands`` instead of ship-system concepts.

Adding a new weapon is one entry in a WARES tuple — no if/else chains.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundWeaponSpec:
    """One equippable ground-combat weapon.

    Attributes:
        id: registry key, e.g. ``combat_knife``.
        name: display name, e.g. ``Combat Knife``.
        damage_type: ``"melee"``, ``"kinetic"``, ``"energy"``,
            ``"plasma"``, or ``"explosive"`` — determines armor
            interactions.
        armor_bypass: True ignores the target's armor DR entirely
            (a molecular edge cuts through plating).
        damage: base damage per hit (before skill/range modifiers).
        accuracy: base hit % (0-100).
        ap_cost: action points to attack once.
        hands: 1 (one-handed, can dual-wield or hold shield) or
            2 (two-handed).
        min_range: minimum cells to target.
        max_range: maximum cells to target. 1 = melee-only.
        ammo_capacity: -1 = infinite (melee/energy), >0 = max
            rounds before needing resupply.
        ammo_per_shot: rounds consumed per attack.
        price: credits cost to buy from an armory.
        tech_level: minimum planet tech level to stock this item.
        shop_available: False hides the weapon from armories entirely
            (monster/enemy-only weapons — the armory lists every
            registered weapon, so this flag is the shop-leak guard).
    """
    id: str
    name: str
    damage_type: str              # "melee", "kinetic", "energy", "plasma", "explosive"
    damage: int
    accuracy: int                  # 0-100
    ap_cost: int = 1
    hands: int = 1                 # 1 or 2
    min_range: int = 1
    max_range: int = 1
    ammo_capacity: int = -1        # -1 = infinite
    ammo_per_shot: int = 1
    price: int = 0
    tech_level: int = 1
    shop_available: bool = True
    armor_bypass: bool = False    # True ignores target armor DR entirely


# ---------------------------------------------------------------------------
# Lazy-built registry
# ---------------------------------------------------------------------------

_BY_ID: dict[str, GroundWeaponSpec] | None = None


def _build_registry() -> dict[str, GroundWeaponSpec]:
    """Auto-discover all ground-weapon modules under this package.

    Every module exporting a ``WARES`` tuple is automatically
    registered — just drop a new ``.py`` in ``data/ground_weapons/``
    and it's picked up without touching any registry code.
    """
    import importlib, pkgutil
    combined: dict[str, GroundWeaponSpec] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if hasattr(mod, "WARES"):
            for w in mod.WARES:
                combined[w.id] = w
    return combined


def _registry() -> dict[str, GroundWeaponSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_ground_weapon(weapon_id: str) -> GroundWeaponSpec:
    """Look up a :class:`GroundWeaponSpec` by id; raises :class:`KeyError` on miss."""
    try:
        return _registry()[weapon_id]
    except KeyError:
        raise KeyError(f"unknown ground weapon id: {weapon_id!r}") from None


def list_ground_weapons() -> tuple[GroundWeaponSpec, ...]:
    """All registered ground weapons, in undefined order."""
    return tuple(_registry().values())
