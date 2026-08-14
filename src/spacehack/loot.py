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

from enum import Enum, auto

from .game_context import GameContext
from .data.trade_goods import find_trade_good


class _LootOutcome(Enum):
    IGNORE = auto()
    TAKE = auto()
    LEAVE = auto()
    QUIT = auto()


def _run_pygame_loot(ctx: GameContext, title: str, body: str, take_label: str) -> str | None:
    """Run the loot choice through the generic Pygame menu worker."""
    from . import pygame_menu, pygame_ui

    item = pygame_menu.MenuItem(take_label, "", "TAKE")
    frame = pygame_menu.MenuFrame(
        title=title,
        body=body,
        items=(item,),
        hints=(pygame_ui.modal_hint(
            "ENTER secure/take", "ESC leave", pygame_ui.GUIDE_HINT,
        ),),
        selected=0,
    )
    outcome, action, _selected = pygame_menu.run_for_context(
        getattr(ctx, "context", ctx),
        (frame,),
        caption=f"spacehack - {title.lower()}",
    )
    if outcome == "GUIDE":
        from .help import _open_context_guide
        _open_context_guide(ctx, "Trading & Economy")
        return _run_pygame_loot(ctx, title, body, take_label)
    if outcome == "SELECT" and action == "TAKE":
        return "TAKE"
    if outcome == "QUIT":
        return "QUIT"
    return "LEAVE"


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


def _drop_expedition_entry_at_loot(ctx: GameContext, loot_entity, index: int):
    """Drop one carried Expedition Pack item at the current loot position."""
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


def _pack_drop_options(ctx: GameContext) -> tuple[tuple[str, str], ...]:
    """Build valid drop choices without exposing malformed pack entries."""
    options = []
    for index, entry in enumerate(ctx.ground_expedition_inventory):
        try:
            name = _ground_equipment_loot_name(entry)
        except (KeyError, TypeError, ValueError):
            continue
        options.append((f"Drop {name}", f"DROP_PACK:{index}"))
    return tuple(options)


def _choose_pack_drop(ctx: GameContext, loot_entity) -> int | None:
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
    if not chosen.startswith("DROP_PACK:"):
        return None
    try:
        _drop_index = int(chosen.split(":", 1)[1])
    except ValueError:
        return None
    return _drop_index


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
    drop_index = _choose_pack_drop(ctx, loot_entity)
    if drop_index is None:
        ctx.log.add(f"Expedition Pack full - left the {name} behind.")
        return False
    if not 0 <= drop_index < len(ctx.ground_expedition_inventory):
        return False
    dropped, dropped_entity = _drop_expedition_entry_at_loot(
        ctx, loot_entity, drop_index,
    )
    if not _pack_loot(ctx, entry):
        ctx.game_map.entities.remove(dropped_entity)
        ctx.ground_expedition_inventory.insert(drop_index, dropped)
        ctx.log.add(f"Expedition Pack full - left the {name} behind.")
        return False
    _finish_loot_pickup(ctx, loot_entity, f"Packed ground equipment: {name}.")
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


def _run_cargo_loot_modal(
    ctx: GameContext,
    loot_entity,
    good,
    quantity: int,
    goods: list[tuple[str, int]],
    is_quest: bool,
    is_heist: bool,
) -> str:
    """Build and run the cargo/quest/heist pickup modal; return its outcome."""
    if is_quest:
        title = "QUEST CACHE"
        parts = [
            f"{find_trade_good(gid).name} x{qty}"
            for gid, qty in goods
        ]
        body = "Secured quest contents: " + ", ".join(parts)
        take_label = "Secure"
    elif is_heist:
        title = "MISSION CARGO"
        body = f"Secured mission cargo: {good.name} x{quantity}"
        take_label = "Secure"
    else:
        title = "CARGO DEBRIS"
        body = (
            f"You found {good.name} x{quantity}. "
            f"Value: {good.base_price}$ each | Volume: {good.volume} crate(s)"
        )
        take_label = "Take"
    return _run_pygame_loot(ctx, title, body, take_label)


def _open_equipment_loot(ctx: GameContext, loot_entity) -> None:
    """Handle the ground-equipment branch of loot pickup."""
    outcome = _run_pygame_loot(
        ctx,
        "GROUND EQUIPMENT",
        f"Found ground equipment: {loot_entity.loot_data.get('item_id', 'unknown')}. "
        "Pack it into the Expedition Pack?",
        "Pack",
    )
    if outcome == "TAKE":
        _apply_equipment_loot_pickup(ctx, loot_entity)
    elif outcome == "QUIT":
        raise SystemExit
    else:
        ctx.log.add("Left the ground equipment behind.")


def open_loot_pickup(ctx: GameContext, loot_entity) -> None:
    """Open a simple modal to pick up cargo, quest, or ground gear loot.

    Shows what's available and lets the player take it (or leave it).
    Insufficient cargo space logs the shortfall without taking anything.
    """
    if loot_entity.loot_data.get("item_type") in {"weapon", "armor"}:
        _open_equipment_loot(ctx, loot_entity)
        return
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
    outcome = _run_cargo_loot_modal(
        ctx, loot_entity, good, quantity, goods, is_quest,
        getattr(loot_entity, "heist_mission", False),
    )
    if outcome == "TAKE":
        _apply_loot_pickup(ctx, loot_entity, owned, is_quest, goods, good_id, quantity, good)
    elif outcome == "QUIT":
        raise SystemExit
    else:
        ctx.log.add("Left the cargo debris in space.")
