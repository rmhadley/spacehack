"""Field items in the armory split terminal: consumable stack rows,
consumable purchase, and bandolier restock (doc 52.2).

Ammo stopped being a field item when the bandolier landed (doc 52
phase 2): the class retired here alongside its buy path, leaving
consumables as the only stack the armory moves and RESTOCK as the
ammunition verb. Split from menus/_armory to pay the 1000-line
ratchet; _armory re-exports the surface.
"""

from __future__ import annotations


def _field_item_name(stack) -> str:
    """Resolve one consumable stack's display name and quantity."""
    from ..data.ground_items import find_ground_item
    spec = find_ground_item(stack.item_type, stack.item_id)
    return f"{spec.name} [{stack.quantity}/{spec.quantity_per_stack}]"

def _field_item_detail(stack) -> str:
    """Format quantity and purchase details for one consumable stack."""
    from ..data.ground_items import find_ground_item

    spec = find_ground_item(stack.item_type, stack.item_id)
    effect = f"  {spec.effect_label or spec.name}"
    return (
        f"{stack.item_type.title()}  {stack.quantity}/{spec.quantity_per_stack}"
        f"  {spec.price}$ each{effect}"
    )

def _field_item_rows(entries, action_prefix: str, section_label: str):
    """Build rows for owned consumable stacks."""
    from .. import pygame_split

    rows = [pygame_split.section_header(section_label)]
    for index, stack in enumerate(entries):
        try:
            rows.append(pygame_split.SplitRow(
                _field_item_name(stack),
                "",
                _field_item_detail(stack),
                f"{action_prefix}:{index}",
            ))
        except (KeyError, TypeError, ValueError):
            continue
    if len(rows) == 1:
        rows.append(pygame_split.SplitRow(
            "[empty]", "", "No field-item stacks.", "", False,
        ))
    return tuple(rows)

async def _choose_field_item_destination(ctx, item_id: str) -> str:
    """Choose a destination before paying for a consumable."""
    from .. import pygame_story
    from ..data.ground_items import find_ground_item

    spec = find_ground_item("consumable", item_id)
    return await pygame_story.choose(
        ctx,
        title="BUY CONSUMABLE",
        body=f"{spec.name} - {spec.price}$ each",
        options=(
            ("Armory Storage", f"BUY_ITEM_ARMORY:consumable:{item_id}"),
            ("Expedition Pack", f"BUY_ITEM_EXPEDITION:consumable:{item_id}"),
        ),
        caption="spacehack - field-item purchase", compact=True,
    )

def _destination_storages(ctx, destination: str) -> tuple[list, list]:
    """``(equipment_list, item_list)`` for one purchase destination."""
    from .. import ground_equipment
    from ._armory import _armory_items, _expedition_items, _expedition_storage

    if destination == ground_equipment.EXPEDITION_INVENTORY:
        return _expedition_storage(ctx), _expedition_items(ctx)
    return [], _armory_items(ctx)

def _field_item_purchase_maximum(
    ctx, item_id: str, destination: str,
) -> int:
    """Return affordable and destination-capacity-limited quantity."""
    from .. import ground_equipment
    from ..data.ground_items import find_ground_item
    from ._armory import _strength

    spec = find_ground_item("consumable", item_id)
    affordable = ctx.stats.credits // spec.price
    if destination != ground_equipment.EXPEDITION_INVENTORY:
        return affordable
    equipment, items = _destination_storages(ctx, destination)
    capacity = ground_equipment.field_item_capacity(
        equipment, items, "consumable", item_id,
        strength=_strength(ctx), container=destination,
    )
    return min(affordable, capacity or 0)

async def _choose_field_item_quantity(
    ctx, item_id: str, destination: str,
) -> int | None:
    """Choose a consumable quantity after destination selection."""
    from .. import pygame_quantity
    from ..data.ground_items import find_ground_item

    spec = find_ground_item("consumable", item_id)
    maximum = _field_item_purchase_maximum(ctx, item_id, destination)
    if maximum < 1:
        if ctx.stats.credits < spec.price:
            ctx.log.add(f"You cannot afford {spec.name}.")
        else:
            ctx.log.add("That destination cannot hold any more field items.")
        return None
    try:
        return await pygame_quantity.run_for_context(
            ctx.context, ctx, f"BUY {spec.name}", maximum, spec.price,
            prefill=maximum,
        )
    except pygame_quantity.PygameQuantityQuit:
        raise SystemExit

async def _purchase_field_item(
    ctx, item_id: str, destination: str,
) -> None:
    """Buy an exact consumable quantity after destination validation."""
    from .. import ground_equipment
    from ..data.ground_items import find_ground_item
    from ._armory import _strength

    spec = find_ground_item("consumable", item_id)
    quantity = await _choose_field_item_quantity(ctx, item_id, destination)
    if quantity is None:
        return
    cost = quantity * spec.price
    if cost > ctx.stats.credits:
        ctx.log.add("You can no longer afford that consumable.")
        return
    destination_equipment, destination_items = _destination_storages(
        ctx, destination,
    )
    try:
        ground_equipment.add_item_quantity(
            destination_equipment, destination_items, "consumable",
            item_id, quantity,
            strength=_strength(ctx), container=destination,
        )
    except (KeyError, ValueError) as exc:
        ctx.log.add(str(exc))
        return
    ctx.stats.credits -= cost
    label = "Expedition Pack" if destination == ground_equipment.EXPEDITION_INVENTORY else "Armory Storage"
    ctx.log.add(f"Bought {spec.name} x{quantity} into {label} for {cost}$.")

async def _restock_bandolier(ctx, item_id: str) -> None:
    """Restock one bandolier caliber, priced per round (doc 52.2).

    SETTLED 2: charge rounds-actually-added x ``price_per_round``.
    SETTLED 5: every caliber restocks unconditionally - the rows and
    this handler never check what is equipped or owned.
    """
    from .. import pygame_quantity
    from ..bandolier import effective_cap, refill, space_remaining
    from ..data.ground_items import find_ground_ammo

    spec = find_ground_ammo(item_id)
    space = space_remaining(
        ctx.bandolier, spec.ammo_type, effective_cap(spec.ammo_type),
    )
    maximum = min(space, ctx.stats.credits // spec.price_per_round)
    if maximum < 1:
        if space < 1:
            ctx.log.add(f"Your {spec.name} reserve is already full.")
        else:
            ctx.log.add(f"You cannot afford {spec.name}.")
        return
    quantity = None
    try:
        quantity = await pygame_quantity.run_for_context(
            ctx.context, ctx, f"RESTOCK {spec.name}", maximum,
            spec.price_per_round, prefill=maximum,
        )
    except pygame_quantity.PygameQuantityQuit:
        raise SystemExit
    if not quantity:
        return
    added = refill(ctx, spec.ammo_type, quantity)
    cost = added * spec.price_per_round
    ctx.stats.credits -= cost
    ctx.log.add(f"Restocked {added} {spec.name} for {cost}$.")
