"""Ship modules catalog: engine and system upgrades.

Each module is a frozen ModuleSpec. Effects are additive bonuses
(keyed by field name). The combat engine iterates installed modules
and sums bonuses generically — no if/else chains.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleSpec:
    """One equippable ship module.

    Attributes:
        id: registry key, e.g. "compact_reactor".
        name: display name, e.g. "Compact Reactor".
        slot_type: "engine" or "system".
        description: one-line flavour text.
        power_gen_bonus: additional power generated per turn.
        max_shield_bonus: additional max shield HP.
        shield_recharge_bonus: additional shield regen per turn.
        cargo_bonus: additional cargo capacity (can be negative).
        gunnery_bonus: +accuracy for all weapons.
        piloting_bonus: +dodge, +AP per turn.
        engineering_bonus: +power efficiency, +shield recharge rate.
        max_hull_bonus: additional hull HP.
        speed_bonus: additional moves-per-day in overworld travel.
        price: credits cost to buy.
    """
    id: str
    name: str
    slot_type: str
    description: str
    power_gen_bonus: int = 0
    max_shield_bonus: int = 0
    shield_recharge_bonus: int = 0
    cargo_bonus: int = 0
    gunnery_bonus: int = 0
    piloting_bonus: int = 0
    engineering_bonus: int = 0
    max_hull_bonus: int = 0
    speed_bonus: int = 0
    price: int = 0
    tech_level: int = 1               # minimum planet tech level to stock this


_BY_ID: dict[str, ModuleSpec] | None = None


def _build_registry() -> dict[str, ModuleSpec]:
    """Auto-discover all module catalogs under this package.

    Every module exporting a ``MODULES`` tuple is automatically
    registered — just drop a new ``.py`` in ``data/modules/`` and
    it's picked up without touching any registry code.
    """
    import importlib, pkgutil
    combined: dict[str, ModuleSpec] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if hasattr(mod, "MODULES"):
            for m in mod.MODULES:
                combined[m.id] = m
    return combined


def _registry() -> dict[str, ModuleSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_module(module_id: str) -> ModuleSpec:
    """Look up a ModuleSpec by id; raises KeyError on miss."""
    try:
        return _registry()[module_id]
    except KeyError:
        raise KeyError(f"unknown module id: {module_id!r}") from None


def list_modules() -> tuple[ModuleSpec, ...]:
    """All registered modules, in undefined order."""
    return tuple(_registry().values())
