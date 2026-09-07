"""Weapon-slot rows for the Character screen's Equipment tab.

Split from ``character_screen`` (ratchet); helpers of the parent
screen are imported lazily at call time.
"""

from __future__ import annotations


def _lazy():
    """The parent screen module, imported lazily (it imports this)."""
    from . import character_screen as _cs
    return _cs

from .game_context import GameContext


def _weapon_rows(
    ctx: GameContext, equipment_management: bool, swap_allowed: bool,
) -> list:
    """Build the two weapon-slot rows for the active ground loadout."""
    rows: list = []
    instances = list(ctx.equipped_ground_weapons)
    while len(instances) < 2:
        instances.append(None)
    weapon_ids = [instance.weapon_id if instance is not None else "" for instance in instances]
    first_weapon_is_two_handed = _first_weapon_is_two_handed(weapon_ids)
    for index, instance in enumerate(instances[:2], 1):
        rows.append(_weapon_row(
            ctx, index, instance,
            occupied_by_two_handed=(
                index == 2 and first_weapon_is_two_handed
            ),
            equipment_management=equipment_management,
            swap_allowed=swap_allowed,
        ))
    return rows


def _first_weapon_is_two_handed(weapons: list[str]) -> bool:
    """Return whether the first equipped weapon is two-handed."""
    from .data.ground_weapons import find_ground_weapon

    if not weapons[0]:
        return False
    try:
        return find_ground_weapon(weapons[0]).hands == 2
    except KeyError:
        return False


def _weapon_row(
    ctx: GameContext,
    index: int,
    instance,
    *,
    occupied_by_two_handed: bool,
    equipment_management: bool,
    swap_allowed: bool,
):
    """Build one weapon-slot row (filled, empty, or occupied-by-2H)."""
    from .data.ground_weapons import find_ground_weapon

    label = f"Weapon slot {index}"
    if occupied_by_two_handed:
        return _lazy()._equipment_row(f"{label}: --- (occupied by 2H)")
    if instance is not None:
        try:
            spec = find_ground_weapon(instance.weapon_id)
            _managed = _weapon_managed(ctx, index - 1, equipment_management, swap_allowed)
            return _lazy()._equipment_row(
                f"{label}: {spec.name}{_weapon_ammo_indicator(spec, instance)}",
                _weapon_detail_text(spec),
                action=f"SWAP:weapon:{index - 1}" if _managed else "",
                selectable=True if not equipment_management else _managed,
            )
        except KeyError:
            pass
    _managed = _weapon_managed(ctx, index - 1, equipment_management, swap_allowed)
    return _lazy()._equipment_row(
        f"{label}: Fists", "",
        action=f"SWAP:weapon:{index - 1}" if _managed else "",
        selectable=False if not equipment_management else _managed,
    )


def _weapon_ammo_indicator(spec, instance) -> str:
    """Return the current/max magazine indicator for reloadable weapons."""
    if spec.ammo_capacity <= 0:
        return ""
    loaded = instance.loaded_ammo if instance.loaded_ammo is not None else 0
    return f" [{loaded}/{spec.ammo_capacity}]"


def _weapon_detail_text(spec) -> str:
    """Format one weapon's stats and armor-bypass detail line."""
    detail = (
        f"{spec.damage_type.title()}   Damage {spec.damage}   "
        f"Accuracy {spec.accuracy}%   Range {spec.min_range}-"
        f"{spec.max_range}   AP {spec.ap_cost}"
    )
    if spec.armor_bypass:
        detail += "   Armor bypass"
    return detail


def _weapon_managed(
    ctx: GameContext, slot_index: int, equipment_management: bool, swap_allowed: bool,
) -> bool:
    """Return whether one weapon slot is actionable in management mode."""
    if not equipment_management:
        return False
    _options = _lazy()._swap_options(ctx, "weapon", str(slot_index))
    return _lazy()._managed_swap_enabled(
        ctx, "weapon", str(slot_index), _options,
        swap_allowed=swap_allowed,
    )
