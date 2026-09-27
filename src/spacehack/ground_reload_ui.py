"""Shared reload actions for ground weapons.

Doc 51 phase 3 removed the menu-facing reload offerings (R is the
only reload verb — in combat at the weapon's reload AP through the
ground rules' own hook, free in dungeon exploration). What remains
is R's free-exploration engine: slot resolution and the transactional
apply that :func:`reload_exploration` drives.
"""

from __future__ import annotations


def reloadable_slots(ctx, ammo_type: str | None = None) -> tuple[int, ...]:
    """Return equipped reloadable slots with bandolier reserve available."""
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
            getattr(ctx, "bandolier", None) or {}, spec.ammo_type,
        ) > 0:
            slots.append(slot)
    return tuple(slots)


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


def reload_weapon_slot(ctx, slot: int) -> bool:
    """Reload one selected weapon — R's free exploration engine.

    Combat R charges the weapon's reload AP through the ground rules'
    own hook; this path never touches AP (doc 51.3 removed the menu
    reloads that once charged here).
    """
    from . import ground_equipment

    _target = _resolve_reload_target(ctx, slot)
    if _target is None:
        return False
    _instance, _spec, _name = _target
    if slot not in reloadable_slots(ctx):
        _log_name_line(ctx, "", _name, _instance.quality,
                       ": no matching ammo or magazine is full.")
        return False
    try:
        _new = ground_equipment.apply_reload(
            ctx.equipped_ground_weapons, slot, ctx.bandolier,
        )
    except (IndexError, KeyError, ValueError) as exc:
        _log_name_line(ctx, "", _name, _instance.quality, f": {exc}")
        return False
    _log_name_line(
        ctx, "Reloaded ", _name, _instance.quality,
        f" ({_new.loaded_ammo}/{_spec.ammo_capacity}).",
    )
    return True


def _log_name_line(
    ctx, prefix: str, name: str, quality: int, suffix: str,
) -> None:
    """Log ``prefix + name + suffix`` with a tiered name coloured.

    Prefix and suffix paint at the line colour; the name run takes
    the quality colour (plain when base).
    """
    from . import message_log
    from .data.quality import quality_mark

    _msg, _runs = message_log.with_runs(
        prefix, quality_mark(name, quality), suffix,
    )
    ctx.log.add(_msg, runs=_runs)


def _reload_choice(slot: int, instance) -> tuple:
    """One reload-chooser option with the weapon name coloured."""
    from . import message_log
    from .data.ground_weapons import find_ground_weapon
    from .data.quality import quality_mark
    from .ground_equipment import display_name

    _name = display_name("weapon", instance.weapon_id, instance.quality)
    _label, _runs = message_log.with_runs(
        quality_mark(_name, instance.quality),
        f" {instance.loaded_ammo}/"
        f"{find_ground_weapon(instance.weapon_id).ammo_capacity}",
    )
    return (_label, f"RELOAD_SLOT:{slot}", _runs)


async def _choose_reload_slot(ctx, slots: tuple[int, ...]) -> int | None:
    """Show the chooser for ammo that feeds multiple active weapons."""
    from . import pygame_story

    choices = tuple(
        _reload_choice(slot, instance)
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


async def reload_exploration(ctx) -> bool:
    """Reload from the ground screen (city or dungeon) without spending a turn."""
    slots = reloadable_slots(ctx)
    if not slots:
        ctx.log.add("No equipped weapon can be reloaded.")
        return False
    slot = await _choose_reload_slot(ctx, slots) if len(slots) > 1 else slots[0]
    return slot is not None and reload_weapon_slot(ctx, slot)
