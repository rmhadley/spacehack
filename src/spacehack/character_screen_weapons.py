"""Weapon-set rows for the Character screen's Equipment tab (doc 51.3).

Two class groups — RANGED and MELEE — each with its role marker
(``[ACTIVE]``/``[HOLSTER]``, flipped by X) and its members; empty
groups still render (the fists floor stays visible). The group
vocabulary (class pairs, role markers, home resolution) is
:mod:`spacehack.ground_weapon_sets`' — this module only renders it.
Split from ``character_screen`` (ratchet); helpers of the parent
screen are imported lazily at call time.
"""

from __future__ import annotations

from .game_context import GameContext


def _lazy():
    """The parent screen module, imported lazily (it imports this)."""
    from . import character_screen as _cs
    return _cs


def _weapon_rows(
    ctx: GameContext, equipment_management: bool, swap_allowed: bool,
) -> list:
    """Build the two class-group weapon rows for the ground loadout."""
    from .ground_weapon_sets import SET_CLASSES

    rows: list = []
    for set_class, label in SET_CLASSES:
        rows.append(_set_group_header(ctx, set_class, label))
        rows += _set_member_rows(ctx, set_class, equipment_management, swap_allowed)
    return rows


def _set_group_header(ctx: GameContext, set_class: str, label: str):
    """One group's section row: ``--- WEAPONS - RANGED [ACTIVE] ---``.

    Unfounded classes carry no role marker (the role materializes
    when the set is founded — equip-to-wield founds ACTIVE).
    """
    from .ground_weapon_sets import founded_set_role

    role = founded_set_role(
        ctx.equipped_ground_weapons, ctx.holstered_ground_weapons, set_class,
    )
    marker = f" [{role}]" if role is not None else ""
    return _lazy()._equipment_row(f"--- WEAPONS - {label}{marker} ---")


def _set_member_rows(
    ctx: GameContext, set_class: str, equipment_management: bool, swap_allowed: bool,
) -> list:
    """Slot rows for one class group, padded to the set's capacity.

    A set holds up to two weapons, so the group always SHOWS both slot
    rows (mid-playtest ruling 2026-09-25: capacity must be visible,
    as the old two-slot screen showed it) — a founding 2H marks the
    second row occupied instead of empty.
    """
    from .ground_equipment import WEAPON_SLOT_COUNT

    home = _class_home(ctx, set_class)
    managed = equipment_management and swap_allowed
    rows = []
    for index in range(WEAPON_SLOT_COUNT):
        member = (
            _member_row(ctx, set_class, index, managed)
            if index < len(home) else None
        )
        rows.append(
            member if member is not None
            else _empty_slot_row(set_class, home, managed)
        )
    return rows


def _empty_slot_row(set_class: str, home: list, managed: bool):
    """One open slot row: joinable, or marked occupied by the 2H."""
    from .ground_weapon_sets import _set_is_two_handed

    if _set_is_two_handed(home):
        return _lazy()._equipment_row("--- (occupied by 2H)")
    return _lazy()._equipment_row(
        "[empty]", "",
        action=f"SWAP:weapon:{set_class}" if managed else "",
        selectable=managed,
    )


def _class_home(ctx: GameContext, set_class: str) -> list:
    """The list currently holding a class (empty when unfounded)."""
    from .ground_weapon_sets import class_home

    home = class_home(
        ctx.equipped_ground_weapons, ctx.holstered_ground_weapons, set_class,
    )
    return home if home is not None else []


def _member_row(
    ctx: GameContext, set_class: str, index: int, managed: bool,
):
    """One member row with the tier name coloured, or None when the
    instance no longer resolves."""
    from .data.quality import effective_weapon_spec

    instance = _class_home(ctx, set_class)[index]
    try:
        spec = effective_weapon_spec(instance.weapon_id, instance.quality)
    except KeyError:
        return None
    _text, _runs = _member_label(instance)
    return _lazy()._equipment_row(
        _text,
        _weapon_detail_text(spec),
        action=f"SWAP:weapon:{set_class}:{index}" if managed else "",
        selectable=True,
        runs=_runs,
    )


def _member_label(instance) -> tuple:
    """``(text, runs)`` for one set member: tier name + ammo state."""
    from . import message_log
    from .data.ground_weapons import find_ground_weapon
    from .data.quality import quality_mark
    from .ground_equipment import display_name
    from .ground_weapon_ammo import magazine_indicator

    name = display_name("weapon", instance.weapon_id, instance.quality)
    spec = find_ground_weapon(instance.weapon_id)
    return message_log.with_runs(
        quality_mark(name, instance.quality),
        magazine_indicator(spec, instance),
    )


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
