"""Weapons catalog: specs for all equippable ship weapons.

Each weapon is a frozen WeaponSpec dataclass. Adding a new weapon
is one entry in a WEAPONS tuple — no if/else chains, no dispatcher
rewrites.

The combat engine reads all fields from the spec generically.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WeaponSpec:
    """One equippable ship weapon.

    Attributes:
        id: registry key, e.g. "light_laser".
        name: display name, e.g. "Light Laser".
        slot_type: "energy" or "missile" (controls ammo/power rules).
        damage: base damage per hit (before skill/range modifiers).
        accuracy: base hit % (0-100).
        ap_cost: action points to fire once.
        power_cost: power drained per shot (energy weapons only).
        ammo_capacity: -1 = no ammo (energy weapon); >0 = max rounds.
        ammo_per_shot: rounds consumed per shot (missile weapons).
        cargo_per_round: cargo space consumed per round of ammo.
        price: credits cost to buy from a mechanic.
        min_range: minimum cell distance to target.
        max_range: maximum cell distance to target.
    """
    id: str
    name: str
    slot_type: str                     # "energy" or "missile"
    damage: int
    accuracy: int                      # 0-100
    ap_cost: int = 1
    power_cost: int = 0
    ammo_capacity: int = -1            # -1 = energy weapon (no ammo)
    ammo_per_shot: int = 1
    cargo_per_round: int = 0
    price: int = 0                    # credits cost to buy
    min_range: int = 1
    max_range: int = 5
    tech_level: int = 1               # minimum planet tech level to stock this


# Lazy-built registry
_BY_ID: dict[str, WeaponSpec] | None = None


def _build_registry() -> dict[str, WeaponSpec]:
    from . import lasers as lasers_module
    from . import missiles as missiles_module
    combined: dict[str, WeaponSpec] = {}
    for w in lasers_module.WEAPONS:
        combined[w.id] = w
    for w in missiles_module.WEAPONS:
        combined[w.id] = w
    return combined


def _registry() -> dict[str, WeaponSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_weapon(weapon_id: str) -> WeaponSpec:
    """Look up a WeaponSpec by id; raises KeyError on miss."""
    try:
        return _registry()[weapon_id]
    except KeyError:
        raise KeyError(f"unknown weapon id: {weapon_id!r}") from None


def list_weapons() -> tuple[WeaponSpec, ...]:
    """All registered weapons, in undefined order."""
    return tuple(_registry().values())
