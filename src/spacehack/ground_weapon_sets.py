"""Ground weapon sets — classification, slot law, and the whole-set swap.

Doc 51 phase 1's data layer. A loadout is two independent sets (ranged
+ melee); the ACTIVE set is ``ctx.equipped_ground_weapons`` — combat
reads it exactly as before — and the other set lives in
``ctx.holstered_ground_weapons``. Set membership derives from the
catalog's ``damage_type`` alone, never a per-weapon flag; the holstered
set is equipment (own ctx field), so expedition capacity never sees it.
"""

from __future__ import annotations

from typing import Iterable

from .data.ground_weapons import find_ground_weapon
from .ground_equipment import GroundWeaponInstance, can_fit_weapons

# Membership table over the catalog's full damage-type domain (doc 51).
# An unknown type must raise — exhaustiveness is load-bearing: a future
# catalog family fails the classification test, not a silent set join.
_SET_BY_DAMAGE_TYPE: dict[str, str] = {
    "melee": "melee",
    "kinetic": "ranged",
    "energy": "ranged",
    "plasma": "ranged",
    "explosive": "ranged",
}


def weapon_set(weapon_id: str) -> str:
    """Resolve a catalog weapon to its set class: "ranged" or "melee"."""
    damage_type = find_ground_weapon(weapon_id).damage_type
    try:
        return _SET_BY_DAMAGE_TYPE[damage_type]
    except KeyError:
        raise ValueError(
            f"unknown damage type {damage_type!r} for weapon {weapon_id!r}"
        ) from None


def can_fit_weapon_set(
    instances: Iterable[GroundWeaponInstance], new_weapon_id: str,
) -> bool:
    """Return whether a weapon joins a set under the slot law.

    A set holds one 2H or up to two 1H (Σ hands ≤ 2, the legacy
    ``can_fit_weapons`` arithmetic) of ONE class — the set's class is
    its first member's. An empty set is class-agnostic: any class
    fits, occupancy counts from zero.
    """
    current = tuple(instances)
    if not can_fit_weapons(current, new_weapon_id):
        return False
    if not current:
        return True
    return weapon_set(new_weapon_id) == weapon_set(current[0].weapon_id)


def exchange_weapon_sets(
    equipped: list[GroundWeaponInstance],
    holstered: list[GroundWeaponInstance],
) -> None:
    """Swap the two sets in place — any composition, either side empty.

    Magazines and quality ride the instances untouched (no reseed, no
    copy); a double-toggle is the identity. Toggling to an empty set is
    the fists floor (SETTLED 1). AP cost and the active-weapon flag
    reset are combat-layer concerns (doc 51 phase 2), not this verb.
    Lists, not ctx — matching ground_equipment's convention so the
    module stays ctx-free and directly testable. The original list
    OBJECTS are mutated in place (callers holding
    ``ctx.equipped_ground_weapons`` see the swap); staging one copy is
    required — sequential slice assignments would otherwise read the
    already-mutated partner.
    """
    staged = list(equipped)
    equipped[:] = holstered
    holstered[:] = staged


def swap_sets_logged(equipped, holstered, log) -> None:
    """Exchange the sets and log the shared outcome line (doc 51 phase 2).

    The one home of ``"Weapon sets swapped."`` — the combat hook and
    the free explore path both route through here so the outcome line
    can never drift between them. Lists + log, still ctx-free.
    """
    exchange_weapon_sets(equipped, holstered)
    log.add("Weapon sets swapped.")


def partition_weapon_sets(
    instances: list[GroundWeaponInstance],
) -> tuple[list[GroundWeaponInstance], list[GroundWeaponInstance]]:
    """Split a legacy mixed loadout into ``(active, holstered)`` sets.

    Doc 51 save migration: the active set after migration is the set
    of the ORIGINAL slot 0 (slot 0 stays fire-able); other-class
    members move to the holstered set in order. Same-class loadouts
    are unchanged; an empty loadout partitions to two empty sets.
    """
    if not instances:
        return [], []
    active_class = weapon_set(instances[0].weapon_id)
    active = [
        instance for instance in instances
        if weapon_set(instance.weapon_id) == active_class
    ]
    holstered = [
        instance for instance in instances
        if weapon_set(instance.weapon_id) != active_class
    ]
    return active, holstered
