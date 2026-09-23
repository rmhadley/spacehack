"""Catalog BUY rows for the armory split terminal.

The three buy-view row builders (weapons/armour, ammunition,
consumables), split from menus/_armory to pay the 1000-line ratchet
(2026-09-23); _armory re-exports the surface.
"""
from __future__ import annotations


def _weapon_detail(spec) -> str:
    """Format a ground weapon's useful armory details."""
    hands = "2H" if spec.hands == 2 else "1H"
    bypass = "  Armor bypass" if spec.armor_bypass else ""
    return (
        f"{hands}  {spec.damage_type.title()}  Damage: {spec.damage}  "
        f"Accuracy: {spec.accuracy}%  Range: {spec.min_range}-{spec.max_range}"
        f"{bypass}"
    )


def _armor_effects(spec) -> str:
    """Format one armor piece's cybernetic bonuses, or an empty string."""
    bonuses = []
    if spec.ap_bonus:
        bonuses.append(f"+{spec.ap_bonus} AP")
    if spec.hit_bonus:
        bonuses.append(f"+{spec.hit_bonus}% Hit")
    if spec.melee_bonus:
        bonuses.append(f"+{spec.melee_bonus} Melee")
    if spec.hp_bonus:
        bonuses.append(f"+{spec.hp_bonus} HP")
    return f"   {' '.join(bonuses)}" if bonuses else ""


def _armor_detail(spec) -> str:
    """Format one armor piece's slot, defense, and cybernetic effects."""
    return (
        f"{spec.slot.title()}  Defense: {spec.defense}"
        f"{_armor_effects(spec)}  {spec.description}"
    )


def _buy_rows(weapons, armor):
    """Build catalog rows for the Buy view from resolved stock lists."""
    from .. import pygame_split, pygame_ui

    rows = [pygame_split.section_header("WEAPONS")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            _weapon_detail(spec),
            f"BUY_WEAPON:{spec.id}",
        )
        for spec in sorted(weapons, key=lambda item: item.price)
    )
    rows.append(pygame_split.section_header("ARMOUR"))
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            _armor_detail(spec),
            f"BUY_ARMOR:{spec.id}",
        )
        for spec in sorted(armor, key=lambda item: item.price)
    )
    return tuple(rows)

def _buy_ammo_rows():
    """Build buy rows for the ground ammo catalog."""
    from .. import pygame_split, pygame_ui
    from ..data.ground_items import list_ground_ammo

    rows = [pygame_split.section_header("AMMUNITION")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price_per_round),
            f"Ammo stack 0/{spec.rounds_per_stack}  {spec.price_per_round}$/round",
            f"BUY_AMMO:{spec.id}",
        )
        for spec in sorted(list_ground_ammo(), key=lambda item: item.price_per_round)
    )
    return tuple(rows)

def _buy_consumable_rows():
    """Build buy rows for the ground consumable catalog."""
    from .. import pygame_split, pygame_ui
    from ..data.ground_items import list_ground_consumables

    rows = [pygame_split.section_header("CONSUMABLES")]
    rows.extend(
        pygame_split.SplitRow(
            spec.name,
            pygame_ui.price_cell(spec.price),
            f"Stack 0/{spec.quantity_per_stack}  {spec.effect_label or spec.name}",
            f"BUY_CONSUMABLE:{spec.id}",
        )
        for spec in sorted(list_ground_consumables(), key=lambda item: item.price)
        if spec.shop_available
    )
    return tuple(rows)

