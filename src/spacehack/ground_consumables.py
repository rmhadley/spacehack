"""Ground consumable rules and combat-local effect state.

Catalog entries describe values; this module owns the transactional use
boundary shared by exploration, the character screen, and ground combat.
"""

from __future__ import annotations

from dataclasses import dataclass

from .data.ground_items import GroundConsumableSpec, find_ground_consumable


@dataclass(frozen=True)
class ActiveConsumableEffect:
    """One temporary combat effect with data-defined remaining duration."""

    effect_id: str
    remaining_turns: int
    regen_amount: int = 0
    ap_bonus: int = 0


def effect_from_spec(spec: GroundConsumableSpec) -> ActiveConsumableEffect | None:
    """Build a temporary effect from a catalog entry, if it has one."""
    if spec.duration_turns <= 0:
        return None
    if spec.combat_regen_amount <= 0 and spec.combat_ap_bonus <= 0:
        return None
    return ActiveConsumableEffect(
        effect_id=spec.effect_id,
        remaining_turns=spec.duration_turns,
        regen_amount=spec.combat_regen_amount,
        ap_bonus=spec.combat_ap_bonus,
    )


def _decrement_stack(items, index: int) -> None:
    """Consume one charge from a validated stack."""
    stack = items[index]
    if stack.quantity <= 1:
        del items[index]
        return
    from .ground_equipment import GroundItemStack

    items[index] = GroundItemStack(stack.item_type, stack.item_id, stack.quantity - 1)


def _use_outside_combat(ctx, spec: GroundConsumableSpec) -> bool:
    """Apply an exploration-legal consumable effect."""
    if not spec.outside_full_heal:
        ctx.log.add(f"{spec.name} can only be used in ground combat.")
        return False
    if ctx.ground_hp >= ctx.ground_max_hp:
        ctx.log.add("Ground HP is already full.")
        return False
    ctx.ground_hp = ctx.ground_max_hp
    return True


def _use_in_combat(ctx, spec: GroundConsumableSpec) -> bool:
    """Apply a combat effect and charge its AP cost transactionally."""
    from .combat import _rules_ground

    if _rules_ground.player_ap(ctx) < spec.use_ap_cost:
        ctx.log.add(
            f"Need {spec.use_ap_cost} AP to use {spec.name} "
            f"(have {_rules_ground.player_ap(ctx)}).",
        )
        return False
    if not _rules_ground.apply_consumable_effect(ctx, spec):
        return False
    _rules_ground.set_player_ap(
        ctx, _rules_ground.player_ap(ctx) - spec.use_ap_cost,
    )
    return True


def use_consumable(ctx, index: int, *, in_combat: bool) -> bool:
    """Use one pack charge, consuming it only after effect validation."""
    items = getattr(ctx, "ground_expedition_items", [])
    if not 0 <= index < len(items):
        ctx.log.add("That consumable is no longer available.")
        return False
    stack = items[index]
    if stack.item_type != "consumable":
        ctx.log.add("That pack item is not a consumable.")
        return False
    try:
        spec = find_ground_consumable(stack.item_id)
    except KeyError:
        ctx.log.add("That consumable is invalid.")
        return False
    applied = (
        _use_in_combat(ctx, spec)
        if in_combat else _use_outside_combat(ctx, spec)
    )
    if not applied:
        return False
    _decrement_stack(items, index)
    ctx.log.add(f"Used {spec.name}.")
    return True
