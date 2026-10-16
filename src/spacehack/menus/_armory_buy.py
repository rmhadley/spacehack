"""Catalog BUY rows for the armory split terminal.

The three buy-view row builders (weapons/armour, ammunition restock,
consumables), split from menus/_armory to pay the 1000-line ratchet
(2026-09-23); _armory re-exports the surface.
"""
from __future__ import annotations


def _damage_token(spec) -> str:
    """The damage stat with its fire rate when it differs: ``5x2`` for
    burst weapons (doc 50 SETTLED 8), plain damage otherwise."""
    damage = f"{spec.damage}"
    if getattr(spec, "shots_per_action", 1) > 1:
        damage += f"x{spec.shots_per_action}"
    return damage


def _weapon_detail(spec) -> str:
    """Format a ground weapon's useful armory details."""
    hands = "2H" if spec.hands == 2 else "1H"
    bypass = "  Armor bypass" if spec.armor_bypass else ""
    return (
        f"{hands}  {spec.damage_type.title()}  Damage: {_damage_token(spec)}  "
        f"Accuracy: {spec.accuracy}%  Range: {spec.min_range}-{spec.max_range}"
        f"{bypass}"
    )



def _armor_detail(spec) -> str:
    """Format one armor piece's slot, defense, and cybernetic effects."""
    return (
        f"{spec.slot.title()}  Defense: {spec.defense}"
        f"  {spec.description}"
    )


def _buy_rows(ctx, weapons, armor):
    """Build catalog rows for the Buy view from resolved stock lists.
    Prices are the band-adjusted charge (doc 102 SETTLED 4)."""
    from .. import pygame_split, pygame_ui
    from ._armory import _buy_price

    rows = [pygame_split.section_header("WEAPONS")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(_buy_price(ctx, spec.price)),
            _weapon_detail(spec),
            f"BUY_WEAPON:{spec.id}",
        )
        for spec in sorted(weapons, key=lambda item: item.price)
    )
    rows.append(pygame_split.section_header("ARMOUR"))
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(_buy_price(ctx, spec.price)),
            _armor_detail(spec),
            f"BUY_ARMOR:{spec.id}",
        )
        for spec in sorted(armor, key=lambda item: item.price)
    )
    return tuple(rows)

def _restock_rows(ctx):
    """Build restock rows for every caliber, unconditionally (doc 52.2).

    SETTLED 5: the restock list never filters by what is carried —
    every bandolier caliber is always a row; the detail shows the
    current reserve against the effective cap.
    """
    from .. import pygame_split, pygame_ui
    from ..bandolier import effective_cap
    from ..data.ground_items import list_ground_ammo

    rows = [pygame_split.section_header("AMMUNITION")]
    for spec in sorted(list_ground_ammo(), key=lambda item: item.price_per_round):
        current = ctx.bandolier.get(spec.ammo_type, 0)
        from ._armory import _buy_price
        _per = _buy_price(ctx, spec.price_per_round)
        rows.append(pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(_per),
            f"Reserve {current}/{effective_cap(spec.ammo_type)}"
            f"  {_per}$/round",
            f"RESTOCK:{spec.id}",
        ))
    return tuple(rows)

def _buy_consumable_rows(ctx):
    """Build buy rows for the ground consumable catalog."""
    from .. import pygame_split, pygame_ui
    from ..data.ground_items import list_ground_consumables
    from ._armory import _buy_price

    rows = [pygame_split.section_header("CONSUMABLES")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(_buy_price(ctx, spec.price)),
            f"Stack 0/{spec.quantity_per_stack}  {spec.effect_label or spec.name}",
            f"BUY_CONSUMABLE:{spec.id}",
        )
        for spec in sorted(list_ground_consumables(), key=lambda item: item.price)
        if spec.shop_available
    )
    return tuple(rows)

