"""Loot pickup domain: cargo debris, quest caches, heist cargo, ground gear.

Entry point: :func:`open_loot_pickup(ctx, entity)` — reached when the
player bumps a ``%`` loot entity in space or a dungeon. Ground-equipment
drops pack into the Expedition Pack; cargo/quest/heist loot goes into the
ship hold (or is secured via mission machinery).

Intercept-mission loot (``heist_mission`` set) is secured as MISSION
CARGO — reserved in the hold, kept out of the trade inventory, and never
sellable. The mission only completes when that specific cargo is secured;
buying the same good at a terminal does not count.

Quest cache / salvage loot (``main_quest_step_id`` set) is handled by
:func:`spacehack.main_quest.secure_quest_loot`: the goods authored in
``loot_data["goods"]`` are granted to the hold and the main-quest step
completes in the same action.
"""
from __future__ import annotations

from .game_context import GameContext
from .data.trade_goods import find_trade_good
from .loot_selection import nearby_loot_entities



def _loot_choice_label(loot_entity) -> str:
    """Build a friendly compact label for one nearby loot entity."""
    data = loot_entity.loot_data or {}
    item_type = data.get("item_type")
    if item_type in {"weapon", "armor"}:
        entry = _ground_equipment_loot_entry(loot_entity)
        try:
            return _ground_equipment_loot_name(entry)
        except (KeyError, TypeError, ValueError):
            return str(data.get("item_id", "Unknown equipment"))
    if item_type in {"ammo", "consumable"}:
        stack = _field_item_loot_stack(loot_entity)
        if stack is not None:
            try:
                return f"{_field_item_loot_name(stack)} x{stack.quantity}"
            except (KeyError, TypeError, ValueError):
                pass
        return str(data.get("item_id", "Unknown field item"))
    if data.get("goods"):
        return f"Quest Cache ({len(data['goods'])} stacks)"
    good_id = data.get("good_id", "")
    try:
        name = find_trade_good(good_id).name
    except (KeyError, TypeError, ValueError):
        name = str(good_id or "Unknown cargo")
    return f"{name} x{data.get('quantity', 1)}"


def _loot_menu_label(loot_entity) -> str:
    """Add invisible width slack for long labels in compact menu rows."""
    label = _loot_choice_label(loot_entity)
    return label + (" " * 8 if len(label) > 20 else "")


def choose_loot_entity(ctx: GameContext, loot_entities):
    """Let the player choose one nearby loot entity before opening pickup."""
    from . import pygame_story

    options = tuple(
        (_loot_menu_label(entity), f"LOOT:{index}")
        for index, entity in enumerate(loot_entities)
    )
    while True:
        chosen = pygame_story.choose(
            ctx,
            title="CHOOSE LOOT",
            body="Choose an item to pick up.",
            options=options,
            caption="spacehack - choose loot",
            compact=True,
        )
        if chosen == "__GUIDE__":
            continue
        if chosen in {None, "__BACK__", "__DISMISS__"}:
            return None
        if chosen == "__QUIT__":
            raise SystemExit
        try:
            index = int(chosen.split(":", 1)[1])
        except (AttributeError, IndexError, ValueError):
            return None
        if 0 <= index < len(loot_entities):
            return loot_entities[index]
        return None


def _ground_equipment_loot_entry(loot_entity):
    """Build and validate a stored entry from an equipment loot entity."""
    from . import ground_equipment

    loot_data = loot_entity.loot_data or {}
    return ground_equipment.StoredGroundEquipment(
        str(loot_data.get("item_type", "")),
        str(loot_data.get("item_id", "")),
    )


def _ground_equipment_loot_name(entry) -> str:
    """Return the catalog display name for an equipment loot entry."""
    from .data.ground_armor import find_ground_armor
    from .data.ground_weapons import find_ground_weapon

    if entry.item_type == "weapon":
        return find_ground_weapon(entry.item_id).name
    return find_ground_armor(entry.item_id).name


def _field_item_loot_stack(loot_entity):
    """Parse one typed ammo/consumable loot stack."""
    from . import ground_equipment

    return ground_equipment.parse_item_stack(loot_entity.loot_data or {})


def _field_item_loot_name(stack) -> str:
    """Return the catalog display name for a field-item stack."""
    from .data.ground_items import find_ground_item

    return find_ground_item(stack.item_type, stack.item_id).name


def _drop_expedition_entry_at_loot(ctx: GameContext, loot_entity, index: int):
    """Drop one carried Expedition Pack equipment item at the loot position."""
    from . import world

    dropped = ctx.ground_expedition_inventory.pop(index)
    dropped_entity = world.Entity(
        char="%",
        fg=(255, 215, 0),
        pos=loot_entity.pos,
        name="Dropped Ground Equipment",
        loot_data={"item_type": dropped.item_type, "item_id": dropped.item_id},
    )
    ctx.game_map.entities.append(dropped_entity)
    return dropped, dropped_entity


def _drop_expedition_stack_at_loot(ctx: GameContext, loot_entity, index: int):
    """Drop one carried field-item stack at the loot position."""
    from . import world

    dropped = ctx.ground_expedition_items.pop(index)
    dropped_entity = world.Entity(
        char="%",
        fg=(255, 215, 0),
        pos=loot_entity.pos,
        name="Dropped Field Item",
        loot_data={
            "item_type": dropped.item_type,
            "item_id": dropped.item_id,
            "quantity": dropped.quantity,
        },
    )
    ctx.game_map.entities.append(dropped_entity)
    return dropped, dropped_entity


def _pack_drop_options(ctx: GameContext) -> tuple[tuple[str, str], ...]:
    """Build valid drop choices without exposing malformed pack entries."""
    options = []
    for index, entry in enumerate(ctx.ground_expedition_inventory):
        try:
            name = _ground_equipment_loot_name(entry)
        except (KeyError, TypeError, ValueError):
            continue
        options.append((f"Drop {name}", f"DROP_PACK:{index}"))
    for index, stack in enumerate(getattr(ctx, "ground_expedition_items", [])):
        try:
            name = _field_item_loot_name(stack)
        except (KeyError, TypeError, ValueError):
            continue
        options.append((f"Drop {name} x{stack.quantity}", f"DROP_STACK:{index}"))
    return tuple(options)


def _choose_pack_drop(ctx: GameContext, loot_entity) -> str | None:
    """Offer a compact drop-or-leave choice when the Expedition Pack is full."""
    from . import pygame_story

    options = _pack_drop_options(ctx) + (("Leave new loot", "LEAVE_LOOT"),)
    chosen = pygame_story.choose(
        ctx,
        title="EXPEDITION PACK FULL",
        body="Drop one carried item to make room, or leave the new loot behind.",
        options=options,
        caption="spacehack - pack full",
        compact=True,
    )
    if not chosen or chosen in {"__BACK__", "__DISMISS__", "LEAVE_LOOT"}:
        return None
    if chosen == "__QUIT__":
        raise SystemExit
    if not chosen.startswith(("DROP_PACK:", "DROP_STACK:")):
        return None
    try:
        int(chosen.split(":", 1)[1])
    except ValueError:
        return None
    return chosen


def _pack_loot(ctx: GameContext, entry) -> bool:
    """Add the entry to the pack; False when the pack is full."""
    from . import ground_equipment

    strength = int(getattr(getattr(ctx, "ground_stats", None), "strength", 10))
    try:
        ground_equipment.add_stored(
            ctx.ground_expedition_inventory,
            entry,
            container=ground_equipment.EXPEDITION_INVENTORY,
            strength=strength,
        )
    except ValueError:
        return False
    return True


def _finish_loot_pickup(ctx: GameContext, loot_entity, message: str) -> None:
    """Log the pickup and remove the loot entity from the map."""
    ctx.log.add(message)
    if loot_entity in ctx.game_map.entities:
        ctx.game_map.entities.remove(loot_entity)


def _drop_selected_pack_item(ctx: GameContext, loot_entity, chosen):
    """Drop one selected equipment or field-item stack and return rollback data."""
    if isinstance(chosen, int):
        chosen = f"DROP_PACK:{chosen}"
    try:
        kind, index_text = chosen.split(":", 1)
        index = int(index_text)
    except (AttributeError, ValueError):
        return None
    if kind == "DROP_PACK":
        if not 0 <= index < len(ctx.ground_expedition_inventory):
            return None
        dropped, entity = _drop_expedition_entry_at_loot(ctx, loot_entity, index)
        rollback = lambda: ctx.ground_expedition_inventory.insert(index, dropped)
    elif kind == "DROP_STACK":
        if not 0 <= index < len(ctx.ground_expedition_items):
            return None
        dropped, entity = _drop_expedition_stack_at_loot(ctx, loot_entity, index)
        rollback = lambda: ctx.ground_expedition_items.insert(index, dropped)
    else:
        return None
    return entity, rollback


def _apply_equipment_loot_pickup(ctx: GameContext, loot_entity) -> bool:
    """Move one ground-equipment drop into the carried Expedition Pack."""
    entry = _ground_equipment_loot_entry(loot_entity)
    try:
        name = _ground_equipment_loot_name(entry)
    except (KeyError, TypeError, ValueError):
        ctx.log.add("Unknown ground equipment - left it behind.")
        return False
    if _pack_loot(ctx, entry):
        _finish_loot_pickup(ctx, loot_entity, f"Packed ground equipment: {name}.")
        return True
    chosen = _choose_pack_drop(ctx, loot_entity)
    if chosen is None:
        ctx.log.add(f"Expedition Pack full - left the {name} behind.")
        return False
    dropped = _drop_selected_pack_item(ctx, loot_entity, chosen)
    if dropped is None:
        return False
    dropped_entity, rollback = dropped
    if not _pack_loot(ctx, entry):
        ctx.game_map.entities.remove(dropped_entity)
        rollback()
        ctx.log.add(f"Expedition Pack full - left the {name} behind.")
        return False
    _finish_loot_pickup(ctx, loot_entity, f"Packed ground equipment: {name}.")
    return True


def _pack_field_item(ctx: GameContext, stack) -> object | None:
    """Add a field-item stack and return an explicit floor remainder."""
    from . import ground_equipment

    strength = int(getattr(getattr(ctx, "ground_stats", None), "strength", 10))
    return ground_equipment.add_item_stack(
        ctx.ground_expedition_inventory,
        ctx.ground_expedition_items,
        stack,
        strength=strength,
    )


def _leave_field_item_remainder(loot_entity, remainder) -> None:
    """Keep an uncollected field-item remainder on the same floor entity."""
    loot_entity.loot_data = {
        "item_type": remainder.item_type,
        "item_id": remainder.item_id,
        "quantity": remainder.quantity,
    }


def _apply_field_item_loot_pickup(ctx: GameContext, loot_entity) -> bool:
    """Pack typed ammo/consumable loot without silently losing overflow."""
    stack = _field_item_loot_stack(loot_entity)
    if stack is None:
        ctx.log.add("Unknown field item - left it behind.")
        return False
    try:
        name = _field_item_loot_name(stack)
        remainder = _pack_field_item(ctx, stack)
    except (KeyError, TypeError, ValueError) as exc:
        ctx.log.add(f"Invalid field item - left it behind ({exc}).")
        return False
    if remainder is None:
        _finish_loot_pickup(ctx, loot_entity, f"Packed {name} x{stack.quantity}.")
        return True
    if remainder.quantity < stack.quantity:
        _leave_field_item_remainder(loot_entity, remainder)
        accepted = stack.quantity - remainder.quantity
        ctx.log.add(f"Packed {name} x{accepted}; left {remainder.quantity} on the floor.")
        return True
    chosen = _choose_pack_drop(ctx, loot_entity)
    if chosen is None:
        ctx.log.add(f"Expedition Pack full - left the {name} behind.")
        return False
    dropped = _drop_selected_pack_item(ctx, loot_entity, chosen)
    if dropped is None:
        return False
    dropped_entity, rollback = dropped
    if _pack_field_item(ctx, stack) is not None:
        ctx.game_map.entities.remove(dropped_entity)
        rollback()
        ctx.log.add(f"Expedition Pack full - left the {name} behind.")
        return False
    _finish_loot_pickup(ctx, loot_entity, f"Packed {name} x{stack.quantity}.")
    return True


def _apply_loot_pickup(
    ctx: GameContext,
    loot_entity,
    owned,
    is_quest: bool,
    goods: list[tuple[str, int]],
    good_id: str,
    quantity: int,
    good,
) -> None:
    """Apply a confirmed trade-good or quest loot pickup."""
    if is_quest:
        from . import main_quest as _mq
        secured = _mq.secure_quest_loot(ctx, loot_entity, goods)
        if not secured:
            for gid, qty in goods:
                owned.inventory[gid] = owned.inventory.get(gid, 0) + qty
            ctx.log.add("Picked up leftover quest cache goods.")
    else:
        secured = False
        if getattr(loot_entity, "heist_mission", False):
            secured = _secure_heist_cargo(ctx, loot_entity, good_id, quantity)
        if secured:
            ctx.log.add(
                f"Secured mission cargo: {good.name} x{quantity} "
                "(reserved in hold). Do not sell!"
            )
        else:
            owned.inventory[good_id] = owned.inventory.get(good_id, 0) + quantity
            ctx.log.add(f"Picked up {good.name} x{quantity} from space debris.")
    if loot_entity in ctx.game_map.entities:
        ctx.game_map.entities.remove(loot_entity)


def _secure_heist_cargo(ctx: GameContext, loot_entity, good_id: str, quantity: int) -> bool:
    """Mark the intercept mission's loot as secured and reserve hold space.

    Returns True if the loot belonged to an active (not-yet-secured)
    intercept mission, in which case the mission's ``heist_good_secured``
    flag is set and the cargo volume is reserved in
    ``owned.mission_reserved`` (the MISSION CARGO hold concept).
    The good does NOT enter the trade inventory — it cannot be sold
    and buying the same good at a terminal does not count.

    Returns False if no matching active mission exists (e.g. the
    mission was abandoned) — the caller falls back to normal debris
    pickup into the trade inventory.
    """
    _good_id = good_id
    _qty = quantity
    for _am in ctx.player_active_missions:
        if getattr(_am, 'heist_target_good_id', None) != _good_id:
            continue
        # Prefer an exact mission link when the loot entity carries one.
        _mid = getattr(loot_entity, 'heist_mission_id', None)
        if _mid and _am.mission_id != _mid:
            continue
        if getattr(_am, 'heist_good_secured', False):
            continue
        # Reserve the same volume that mission._reserved_heist_volume
        # releases on complete/abort (which assumes quantity 1). The
        # flag is set AFTER this lookup so the two stay in sync.
        try:
            _vol = find_trade_good(_good_id).volume * _qty
        except KeyError:
            _vol = 0
        _am.heist_good_secured = True
        _owned = ctx.player_owned_ship
        if _owned is not None:
            _owned.mission_reserved += _vol
        return True
    return False


def _quest_loot_goods(loot_entity, log) -> list[tuple[str, int]] | None:
    """Validate the quest cache's [(good_id, qty)] list; None when unusable."""
    goods: list[tuple[str, int]] = []
    for _g in (loot_entity.loot_data.get("goods") or []):
        try:
            find_trade_good(str(_g[0]))
        except KeyError:
            log.add("The quest cache contains unknown goods - ignored.")
            continue
        goods.append((str(_g[0]), int(_g[1])))
    if not goods:
        log.add("An empty quest cache.")
        return None
    return goods


def _pickup_volume(good, quantity: int, goods, is_quest: bool) -> int:
    """Total cargo volume of the pickup (all quest goods, or a single good)."""
    if not is_quest:
        return good.volume * quantity
    volume = 0
    for _gid, _qty in goods:
        try:
            volume += find_trade_good(_gid).volume * _qty
        except KeyError:
            continue
    return volume


def _resolve_loot_good(ctx: GameContext, loot_entity, good_id) -> object | None:
    """Look up the trade good, clearing unresolvable debris; None when unknown."""
    try:
        return find_trade_good(good_id)
    except KeyError:
        ctx.log.add("Unknown cargo debris.")
        # Remove the unresolvable loot entity so it doesn't block movement.
        try:
            ctx.game_map.entities.remove(loot_entity)
        except ValueError:
            pass
        return None


def _cargo_room(ctx: GameContext, good, quantity: int, goods, is_quest: bool, owned) -> bool:
    """True when the hold has room; otherwise log the shortfall and return False."""
    from .trade import _free_cargo
    volume = _pickup_volume(good, quantity, goods, is_quest)
    free = _free_cargo(owned)
    if free >= volume:
        return True
    ctx.log.add(
        f"Not enough cargo space to take {good.name} x{quantity} "
        f"(need {volume}, have {free} free)."
    )
    return False


def _apply_field_item_loot(ctx: GameContext, loot_entity) -> None:
    """Immediately pack typed ammo/consumable loot."""
    _apply_field_item_loot_pickup(ctx, loot_entity)


def _apply_equipment_loot(ctx: GameContext, loot_entity) -> None:
    """Immediately pack one ground-equipment loot entity."""
    _apply_equipment_loot_pickup(ctx, loot_entity)


def _apply_trade_good_loot(ctx: GameContext, loot_entity) -> None:
    """Immediately secure trade-good debris, quest caches, or mission cargo."""
    is_quest = bool(getattr(loot_entity, "main_quest_step_id", ""))
    if is_quest:
        goods = _quest_loot_goods(loot_entity, ctx.log)
        if goods is None:
            return
        good_id, quantity = goods[0]
    else:
        goods = []
        good_id = loot_entity.loot_data.get("good_id", "")
        quantity = loot_entity.loot_data.get("quantity", 1)
        if not good_id:
            return
    good = _resolve_loot_good(ctx, loot_entity, good_id)
    if good is None:
        return
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship with cargo space to pick up cargo.")
        return
    if not _cargo_room(ctx, good, quantity, goods, is_quest, owned):
        return
    _apply_loot_pickup(
        ctx, loot_entity, owned, is_quest, goods, good_id, quantity, good,
    )


def _open_single_loot_pickup(ctx: GameContext, loot_entity) -> None:
    """Open the existing pickup flow for one selected loot entity."""
    item_type = loot_entity.loot_data.get("item_type")
    if item_type in {"weapon", "armor"}:
        _apply_equipment_loot(ctx, loot_entity)
    elif item_type in {"ammo", "consumable"}:
        _apply_field_item_loot(ctx, loot_entity)
    else:
        _apply_trade_good_loot(ctx, loot_entity)


def open_loot_pickup(ctx: GameContext, loot_entity) -> None:
    """Choose among nearby loot entities, then open one pickup flow."""
    nearby = nearby_loot_entities(ctx)
    if nearby and loot_entity in nearby:
        selected = choose_loot_entity(ctx, nearby)
        if selected is None:
            return
        loot_entity = selected
    _open_single_loot_pickup(ctx, loot_entity)
