"""Ground field-item catalog: ammunition and consumables.

Two frozen spec types (``GroundAmmoSpec``, ``GroundConsumableSpec``)
auto-discovered from submodules, mirroring the ground-weapon and
ground-armor catalogs. The runtime stack type (``GroundItemStack``)
lives in ``ground_equipment.py`` alongside ``StoredGroundEquipment``
because it is mutable inventory state, not a static catalog record.

Ammo and consumables are catalog-only here: they carry identity, stack
limits, and purchase/display data, never combat effects (design doc 19).

Design doc:
``docs/design/in_progress/19_DESIGN_GROUND_AMMO_AND_FIELD_ITEMS.md``
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundAmmoSpec:
    """One ammunition type carried as reserve field ammo.

    Attributes:
        id: registry key, e.g. ``rifle_rounds``.
        name: display name, e.g. ``Rifle Rounds``.
        ammo_type: the weapon ``ammo_type`` this stack feeds (wired in
            Phase 2/3 when weapons gain the field).
        rounds_per_stack: max rounds carried in one Expedition Pack slot.
        price_per_round: credits per round when purchased (Phase 4).
    """

    id: str
    name: str
    ammo_type: str
    rounds_per_stack: int
    price_per_round: int


@dataclass(frozen=True)
class GroundConsumableSpec:
    """One stackable field consumable.

    Attributes:
        id: registry key, e.g. ``med_pack``.
        name: display name, e.g. ``Med Pack``.
        effect_id: table key for the Phase 5 effect registry.
        quantity_per_stack: max charges carried in one pack slot.
        use_ap_cost: action points to use in combat.
        price: credits cost to buy (Phase 4).
    """

    id: str
    name: str
    effect_id: str
    quantity_per_stack: int
    use_ap_cost: int
    price: int


# ---------------------------------------------------------------------------
# Lazy-built registries
# ---------------------------------------------------------------------------

_AMMO_BY_ID: dict[str, GroundAmmoSpec] | None = None
_CONSUMABLE_BY_ID: dict[str, GroundConsumableSpec] | None = None


def _build_registries() -> tuple[
    dict[str, GroundAmmoSpec], dict[str, GroundConsumableSpec],
]:
    """Auto-discover ammo + consumable submodules under this package.

    Submodules export ``AMMO`` (a tuple of :class:`GroundAmmoSpec`) and/or
    ``CONSUMABLES`` (a tuple of :class:`GroundConsumableSpec`).
    """
    import importlib, pkgutil

    ammo: dict[str, GroundAmmoSpec] = {}
    consumables: dict[str, GroundConsumableSpec] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        for spec in getattr(mod, "AMMO", ()):
            ammo[spec.id] = spec
        for spec in getattr(mod, "CONSUMABLES", ()):
            consumables[spec.id] = spec
    return ammo, consumables


def _registries() -> tuple[
    dict[str, GroundAmmoSpec], dict[str, GroundConsumableSpec],
]:
    global _AMMO_BY_ID, _CONSUMABLE_BY_ID
    if _AMMO_BY_ID is None or _CONSUMABLE_BY_ID is None:
        _AMMO_BY_ID, _CONSUMABLE_BY_ID = _build_registries()
    return _AMMO_BY_ID, _CONSUMABLE_BY_ID


def find_ground_ammo(ammo_id: str) -> GroundAmmoSpec:
    """Look up a :class:`GroundAmmoSpec` by id; raises :class:`KeyError` on miss."""
    ammo, _ = _registries()
    try:
        return ammo[ammo_id]
    except KeyError:
        raise KeyError(f"unknown ground ammo id: {ammo_id!r}") from None


def find_ground_consumable(consumable_id: str) -> GroundConsumableSpec:
    """Look up a :class:`GroundConsumableSpec` by id; raises :class:`KeyError` on miss."""
    _, consumables = _registries()
    try:
        return consumables[consumable_id]
    except KeyError:
        raise KeyError(f"unknown ground consumable id: {consumable_id!r}") from None


def find_ground_item(
    item_type: str, item_id: str,
) -> GroundAmmoSpec | GroundConsumableSpec:
    """Resolve a field-item spec by ``(item_type, item_id)``.

    ``item_type`` is ``"ammo"`` or ``"consumable"``; anything else raises.
    """
    if item_type == "ammo":
        return find_ground_ammo(item_id)
    if item_type == "consumable":
        return find_ground_consumable(item_id)
    raise KeyError(f"unknown ground item type: {item_type!r}")


def list_ground_ammo() -> tuple[GroundAmmoSpec, ...]:
    """All registered ground ammo, in undefined order."""
    return tuple(_registries()[0].values())


def list_ground_consumables() -> tuple[GroundConsumableSpec, ...]:
    """All registered ground consumables, in undefined order."""
    return tuple(_registries()[1].values())
