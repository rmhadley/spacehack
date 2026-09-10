"""Ground save/load family, split from :mod:`spacehack.saveload`.

Cohesive sibling (the navigation-split precedent): parse/serialize/
restore helpers for ground combat stats, equipped gear, armory and
expedition storage, and field-item stacks. Internal to the saveload
package surface — saveload re-exports the two entry points.
"""

from __future__ import annotations

from .game_context import GameContext


def _ground_equipment_from_dict(raw: object):
    """Parse one stored ground-equipment entry, ignoring malformed records."""
    if not isinstance(raw, dict):
        return None
    item_type = raw.get("item_type")
    item_id = raw.get("item_id")
    if item_type not in {"weapon", "armor"} or not isinstance(item_id, str) or not item_id:
        return None
    try:
        if item_type == "weapon":
            from .data.ground_weapons import find_ground_weapon
            find_ground_weapon(item_id)
        else:
            from .data.ground_armor import find_ground_armor
            find_ground_armor(item_id)
    except (ImportError, KeyError):
        return None
    from .ground_equipment import StoredGroundEquipment
    return StoredGroundEquipment(item_type, item_id)


def _ground_fields(ctx: GameContext) -> dict:
    """Serialize ground combat and equipment fields."""
    # Lazy import: saveload owns _d and imports this module's entry points.
    from .saveload import _d

    return {
        "ground_stats": _d(ctx.ground_stats),
        "equipped_ground_weapons": _d(ctx.equipped_ground_weapons),
        "equipped_ground_armor": _d(ctx.equipped_ground_armor),
        "ground_armory_storage": _d(ctx.ground_armory_storage),
        "ground_expedition_inventory": _d(ctx.ground_expedition_inventory),
        "ground_armory_items": _d(ctx.ground_armory_items),
        "ground_expedition_items": _d(ctx.ground_expedition_items),
        "ground_hp": ctx.ground_hp,
        "ground_max_hp": ctx.ground_max_hp,
    }


def _safe_ground_int(
    raw, default: int, *, minimum: int = 0, maximum: int | None = 100,
) -> int:
    """Parse a bounded ground stat without letting malformed saves escape."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    return min(value, maximum) if maximum is not None else value


def _parse_equipped_ground_armor(raw) -> dict[str, str]:
    """Rebuild valid armor slots, ignoring malformed or mismatched records."""
    from .data.ground_armor import find_ground_armor

    if not isinstance(raw, dict):
        return {}
    slots = {"head", "body", "hands", "legs", "feet"}
    parsed: dict[str, str] = {}
    for slot, item_id in raw.items():
        if slot not in slots or not isinstance(item_id, str):
            continue
        try:
            if find_ground_armor(item_id).slot != slot:
                continue
        except KeyError:
            continue
        parsed[slot] = item_id
    return parsed


def _restore_ground_stats(raw):
    """Rebuild bounded ground stats from a save payload."""
    from .character import GroundStats

    values = raw if isinstance(raw, dict) else {}
    return GroundStats(
        reflexes=_safe_ground_int(values.get("reflexes", 10), 10),
        strength=_safe_ground_int(values.get("strength", 10), 10),
        stamina=_safe_ground_int(values.get("stamina", 10), 10),
    )


def _restore_ground_hp(data: dict) -> tuple[int, int]:
    """Return normalized ``(current_hp, max_hp)`` from a save payload."""
    maximum = max(
        1, _safe_ground_int(data.get("ground_max_hp", 23), 23, maximum=None),
    )
    current = min(
        maximum,
        _safe_ground_int(data.get("ground_hp", 23), 23, maximum=None),
    )
    return current, maximum


def _restore_ground_fields(ctx: GameContext, data: dict) -> None:
    """Restore ground combat and equipment fields."""
    ctx.ground_stats = _restore_ground_stats(data.get("ground_stats"))
    ctx.equipped_ground_weapons = _parse_equipped_ground_weapons(
        data.get("equipped_ground_weapons"),
    )
    ctx.equipped_ground_armor = _parse_equipped_ground_armor(
        data.get("equipped_ground_armor"),
    )
    legacy_storage = data.get("ground_equipment_storage", []) or []
    armory_raw = data.get("ground_armory_storage", legacy_storage) or []
    ctx.ground_armory_storage = [
        stored
        for entry in armory_raw
        if (stored := _ground_equipment_from_dict(entry)) is not None
    ]
    ctx.ground_expedition_inventory = [
        stored
        for entry in (data.get("ground_expedition_inventory", []) or [])
        if (stored := _ground_equipment_from_dict(entry)) is not None
    ]
    ctx.ground_armory_items = _parse_ground_item_stacks(
        data.get("ground_armory_items"),
    )
    ctx.ground_expedition_items = _parse_ground_item_stacks(
        data.get("ground_expedition_items"),
    )
    ctx.ground_hp, ctx.ground_max_hp = _restore_ground_hp(data)


def _parse_ground_item_stacks(raw) -> list:
    """Rebuild field-item stacks, ignoring malformed records."""
    from .ground_equipment import parse_item_stack

    return [
        stack
        for entry in (raw or [])
        if (stack := parse_item_stack(entry)) is not None
    ]


def _parse_equipped_ground_weapons(raw) -> list:
    """Rebuild active weapon instances, migrating legacy string ids."""
    from .ground_equipment import parse_weapon_instance

    return [
        instance
        for entry in (raw or [])
        if (instance := parse_weapon_instance(entry)) is not None
    ]
