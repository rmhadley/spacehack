"""Shared reload actions for ground weapons."""

from __future__ import annotations


def reloadable_pack_slots(ctx, ammo_type: str | None = None) -> tuple[int, ...]:
    """Return equipped reloadable slots with reserve ammo available."""
    from . import ground_equipment
    from .data.ground_weapons import find_ground_weapon

    slots = []
    for slot, instance in enumerate(getattr(ctx, "equipped_ground_weapons", [])):
        try:
            spec = find_ground_weapon(instance.weapon_id)
        except KeyError:
            continue
        if spec.ammo_capacity <= 0 or instance.loaded_ammo is None:
            continue
        if instance.loaded_ammo >= spec.ammo_capacity:
            continue
        if ammo_type is not None and spec.ammo_type != ammo_type:
            continue
        if ground_equipment.reserve_ammo_count(
            getattr(ctx, "ground_expedition_items", []), spec.ammo_type,
        ) > 0:
            slots.append(slot)
    return tuple(slots)


def weapon_reload_option(ctx, slot: str) -> tuple[str, str] | None:
    """Return the explicit Reload button for one equipped weapon, if valid."""
    try:
        _slot = int(slot)
        ctx.equipped_ground_weapons[_slot]
    except (IndexError, TypeError, ValueError):
        return None
    if _slot not in reloadable_pack_slots(ctx):
        return None
    return "Reload", f"RELOAD_SLOT:{_slot}"


def _resolve_reload_target(ctx, slot):
    """``(instance, spec, token-prefixed name)`` for one slot, or None."""
    from .data.ground_weapons import find_ground_weapon
    from .ground_equipment import display_name

    try:
        instance = ctx.equipped_ground_weapons[slot]
        spec = find_ground_weapon(instance.weapon_id)
    except (IndexError, KeyError, TypeError, ValueError):
        ctx.log.add("That weapon cannot be reloaded.")
        return None
    return (
        instance, spec,
        display_name("weapon", instance.weapon_id, instance.quality),
    )


def reload_weapon_slot(
    ctx,
    slot: int,
    *,
    in_ground_combat: bool,
    charge_ap: bool,
) -> bool:
    """Reload one selected weapon, optionally charging combat AP."""
    from . import ground_equipment
    from .combat import _rules_ground

    _target = _resolve_reload_target(ctx, slot)
    if _target is None:
        return False
    _instance, _spec, _name = _target
    if slot not in reloadable_pack_slots(ctx):
        ctx.log.add(f"{_name}: no matching ammo or magazine is full.")
        return False
    if in_ground_combat and _rules_ground.player_ap(ctx) < _spec.reload_ap_cost:
        ctx.log.add(
            f"Need {_spec.reload_ap_cost} AP to reload "
            f"(have {_rules_ground.player_ap(ctx)}).",
        )
        return False
    try:
        _new = ground_equipment.apply_reload(
            ctx.equipped_ground_weapons, slot, ctx.ground_expedition_items,
        )
    except (IndexError, KeyError, ValueError) as exc:
        ctx.log.add(f"{_name}: {exc}")
        return False
    if in_ground_combat and charge_ap:
        _rules_ground.set_player_ap(
            ctx, _rules_ground.player_ap(ctx) - _spec.reload_ap_cost,
        )
    ctx.log.add(f"Reloaded {_name} ({_new.loaded_ammo}/{_spec.ammo_capacity}).")
    return True


async def _choose_reload_slot(ctx, slots: tuple[int, ...]) -> int | None:
    """Show the chooser for ammo that feeds multiple active weapons."""
    from . import pygame_story
    from .data.ground_weapons import find_ground_weapon
    from .ground_equipment import display_name

    choices = tuple(
        (
            f"{display_name('weapon', instance.weapon_id, instance.quality)} "
            f"{instance.loaded_ammo}/"
            f"{find_ground_weapon(instance.weapon_id).ammo_capacity}",
            f"RELOAD_SLOT:{slot}",
        )
        for slot, instance in enumerate(ctx.equipped_ground_weapons)
        if slot in slots
    )
    chosen = await pygame_story.choose(
        ctx,
        title="RELOAD WEAPON",
        body="Choose a weapon to reload.",
        options=choices,
        caption="spacehack - reload",
        compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return None
    if chosen == "__QUIT__":
        raise SystemExit
    try:
        slot = int(chosen.split(":", 1)[1])
    except (IndexError, ValueError):
        ctx.log.add("That reload choice is invalid.")
        return None
    return slot if slot in slots else None


async def reload_pack_ammo(ctx, index: int, in_ground_combat: bool) -> bool:
    """Reload from one ammo stack, choosing among matching weapons."""
    from .data.ground_items import find_ground_ammo

    items = getattr(ctx, "ground_expedition_items", [])
    if not 0 <= index < len(items):
        ctx.log.add("That ammo is no longer available.")
        return False
    if items[index].item_type != "ammo":
        ctx.log.add("That item is not ammunition.")
        return False
    ammo_type = find_ground_ammo(items[index].item_id).ammo_type
    slots = reloadable_pack_slots(ctx, ammo_type)
    if not slots:
        ctx.log.add("No equipped weapon needs that ammo.")
        return False
    slot = await _choose_reload_slot(ctx, slots) if len(slots) > 1 else slots[0]
    return slot is not None and reload_weapon_slot(
        ctx, slot,
        in_ground_combat=in_ground_combat,
        charge_ap=in_ground_combat,
    )


async def reload_exploration(ctx) -> bool:
    """Reload from the dungeon screen without spending a turn."""
    slots = reloadable_pack_slots(ctx)
    if not slots:
        ctx.log.add("No equipped weapon can be reloaded.")
        return False
    slot = await _choose_reload_slot(ctx, slots) if len(slots) > 1 else slots[0]
    return slot is not None and reload_weapon_slot(
        ctx, slot, in_ground_combat=False, charge_ap=False,
    )


async def manage_pack_ammo(
    ctx, index: int, in_ground_combat: bool, *,
    floor_available: bool = True,
) -> str | None:
    """Offer Reload (and Discard, with a floor) for one ammo stack."""
    from . import pygame_story
    from .character_screen import _discard_pack_stack, _item_stack_name

    name = _item_stack_name(ctx.ground_expedition_items[index])
    options = (("Reload", f"STACK_RELOAD:{index}"),)
    if floor_available:
        options += (("Discard", f"STACK_DISCARD:{index}"),)
    chosen = await pygame_story.choose(
        ctx, title="AMMO", body=name,
        options=options,
        caption="spacehack - ammo", compact=True,
    )
    if chosen in {None, "__BACK__", "__DISMISS__", "__GUIDE__"}:
        return None
    if chosen == "__QUIT__":
        raise SystemExit
    if chosen.startswith("STACK_RELOAD:"):
        return "RELOAD" if await reload_pack_ammo(
            ctx, index, in_ground_combat,
        ) else None
    if chosen.startswith("STACK_DISCARD:"):
        return "DISCARD" if _discard_pack_stack(ctx, index) else None
    return None
