"""Ground weapon sets — classification, slot law, and the whole-set swap.

Doc 51's data layer. A loadout is two independent sets (ranged +
melee); the ACTIVE set is ``ctx.equipped_ground_weapons`` — combat
reads it exactly as before — and the other set lives in
``ctx.holstered_ground_weapons``. Set membership derives from the
catalog's ``damage_type`` alone, never a per-weapon flag; the holstered
set is equipment (own ctx field), so expedition capacity never sees it.

Phase 3 adds the class-keyed set law (SETTLED 3): homes are resolved
by class through a total founding rule, and installs go through
:func:`install_set_weapon` with magazines preserved end to end. This
module owns the set law; ground_equipment owns the containers — the
import stays one-way.
"""

from __future__ import annotations

from typing import Iterable

from .data.ground_weapons import find_ground_weapon
from .ground_equipment import (
    ARMORY_STORAGE,
    GroundWeaponInstance,
    StoredGroundEquipment,
    can_fit_weapons,
    validate_entry,
    validate_storage,
    validate_transfer_capacity,
    weapon_entry,
    weapon_hands,
    weapon_instance_from_entry,
)

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


# ---------------------------------------------------------------------------
# Phase 3 — class-keyed set targeting (SETTLED 3) and the set-aware install
# ---------------------------------------------------------------------------

# The degenerate no-home refusal (hand-edited same-class-both saves):
# raised as ValueError so screens log it through their existing seam.
NO_WEAPON_HOME_LINE = "No weapon set can take that weapon."


# The two class-keyed groups and their row labels (shared by the
# character screen and the armory — SETTLED 3).
SET_CLASSES: tuple[tuple[str, str], ...] = (
    ("ranged", "RANGED"), ("melee", "MELEE"),
)


def _set_holds_class(instances: list[GroundWeaponInstance], set_class: str) -> bool:
    """Return whether a set currently holds at least one class member."""
    return any(weapon_set(i.weapon_id) == set_class for i in instances)


def class_home(
    equipped: list[GroundWeaponInstance],
    holstered: list[GroundWeaponInstance],
    set_class: str,
) -> list[GroundWeaponInstance] | None:
    """The list currently holding a class (``None`` when unfounded).

    The SAME list object the caller holds — mutation through it is
    visible via ctx. Both hold it (degenerate) → the ACTIVE set wins,
    matching :func:`resolve_weapon_home`.
    """
    if _set_holds_class(equipped, set_class):
        return equipped
    if _set_holds_class(holstered, set_class):
        return holstered
    return None


def resolve_weapon_home(
    equipped: list[GroundWeaponInstance],
    holstered: list[GroundWeaponInstance],
    weapon_id: str,
) -> tuple[list[GroundWeaponInstance], str] | None:
    """Resolve a weapon's class home — total over reachable states.

    ``(home_list, role)`` where the home is the SAME list object the
    caller holds (mutation through it is visible via ctx). Founding
    rule (doc 51 phase 3): the set holding the class wins (both hold
    it → the ACTIVE set); unfounded → the empty set; both empty → the
    ACTIVE set (equip-to-wield). Neither set holds the class and
    neither is empty (both founded on other classes — degenerate
    hand-edited saves) → ``None``: deterministic refusal.
    """
    set_class = weapon_set(weapon_id)
    for candidates, role in ((equipped, "ACTIVE"), (holstered, "HOLSTER")):
        if _set_holds_class(candidates, set_class):
            return candidates, role
    for candidates, role in ((equipped, "ACTIVE"), (holstered, "HOLSTER")):
        if not candidates:
            return candidates, role
    return None


def founded_set_role(
    equipped: list[GroundWeaponInstance],
    holstered: list[GroundWeaponInstance],
    set_class: str,
) -> str | None:
    """``"ACTIVE"``/``"HOLSTER"`` for a class's current home.

    ``None`` when the class is unfounded (both sets empty, or the
    degenerate both-founded-elsewhere state): an unfounded group
    carries no role marker — the role materializes when it is founded.
    """
    if _set_holds_class(equipped, set_class):
        return "ACTIVE"
    if _set_holds_class(holstered, set_class):
        return "HOLSTER"
    return None


def _displaced_indexes(
    home: list[GroundWeaponInstance],
    weapon_id: str,
    displace_index: int | None,
    fits: bool,
) -> tuple[int, ...]:
    """Indexes to displace for an install: none, one picked, or all.

    ``None`` (auto) and every 2H pick displace the whole set; a 1H
    pick displaces exactly the chosen member. The displacement must
    leave a home that passes the set law — a pick that would strand a
    mixed home is refused (purity guards mutations).
    """
    if fits:
        return ()
    if weapon_hands(weapon_id) == 2 or displace_index is None:
        return tuple(range(len(home)))
    if not 0 <= displace_index < len(home):
        raise IndexError("Invalid weapon set member")
    remaining = [
        instance for index, instance in enumerate(home)
        if index != displace_index
    ]
    if not can_fit_weapon_set(remaining, weapon_id):
        raise ValueError("That member cannot be displaced for this weapon.")
    return (displace_index,)


def _plan_set_install(
    home: list[GroundWeaponInstance],
    source: list[StoredGroundEquipment],
    weapon_id: str,
    displace_index: int | None,
    fits: bool,
    displaced_storage: list[StoredGroundEquipment] | None,
    displaced_container: str | None,
    strength: int,
) -> tuple[tuple[int, ...], list[StoredGroundEquipment]]:
    """Validate a set install: displacement plan + destination capacity."""
    indexes = _displaced_indexes(home, weapon_id, displace_index, fits)
    displaced = [weapon_entry(home[index]) for index in indexes]
    if not displaced:
        return indexes, displaced
    if displaced_storage is None:
        raise ValueError("A destination is required for displaced weapons")
    validate_transfer_capacity(
        source, displaced_storage, len(displaced),
        destination_container=displaced_container or ARMORY_STORAGE,
        strength=strength,
    )
    validate_storage([*displaced_storage, *displaced])
    return indexes, displaced


def install_set_weapon(
    equipped: list[GroundWeaponInstance],
    holstered: list[GroundWeaponInstance],
    source: list[StoredGroundEquipment],
    source_index: int,
    *,
    displace_index: int | None = None,
    displaced_storage: list[StoredGroundEquipment] | None = None,
    displaced_container: str | None = None,
    strength: int = 10,
) -> tuple[StoredGroundEquipment, str]:
    """Install a stored weapon into its class home, atomically.

    All validation happens before any mutation (via
    :func:`_plan_set_install`). Returns ``(entry, role)`` — the role
    names where it landed, so screens log the holster honestly;
    ``displaced_container`` defaults to unlimited armory storage.
    """
    if not 0 <= source_index < len(source):
        raise IndexError("Invalid stored ground equipment index")
    entry = source[source_index]
    validate_entry(entry)
    if entry.item_type != "weapon":
        raise ValueError("Stored item is not a weapon")
    resolved = resolve_weapon_home(equipped, holstered, entry.item_id)
    if resolved is None:
        raise ValueError(NO_WEAPON_HOME_LINE)
    home, role = resolved
    fits = can_fit_weapon_set(home, entry.item_id)
    indexes, displaced = _plan_set_install(
        home, source, entry.item_id, displace_index, fits,
        displaced_storage, displaced_container, strength,
    )
    source.pop(source_index)
    for index in sorted(indexes, reverse=True):
        del home[index]
    if displaced_storage is not None:
        displaced_storage.extend(displaced)
    home.append(weapon_instance_from_entry(entry))
    return entry, role
