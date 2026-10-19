"""Ground consumable rules and the combat-local use boundary.

Catalog entries describe values; this module owns the transactional use
boundary shared by exploration, the character screen, and ground combat.
Timed effects are status-catalog rows now (doc 103 Build A): a
consumable's ``effect_id`` resolves against ``data/statuses.py``.
"""

from __future__ import annotations

from .data.ground_items import GroundConsumableSpec, find_ground_consumable

# The tinker kit's catalog identity (doc 47.5): one authored constant,
# never a scattered string compare. The kit raises one eligible owned
# item's quality by one tier, capped at prototype (SETTLED 31/32).
KIT_ITEM_ID = "tinker_kit"
KIT_EFFECT_ID = "tinker"


def is_tinker_kit(spec: GroundConsumableSpec) -> bool:
    """True for the quality-raise consumable (doc 47.5 SETTLED 33)."""
    return spec.effect_id == KIT_EFFECT_ID


def resolve_pack_consumable(ctx, index: int) -> GroundConsumableSpec | None:
    """Resolve one pack stack to its consumable spec, or None.

    The single stack-resolution seam: the kit manage flow and the kit
    charge consume must agree on what sits at ``index`` for the
    bump-then-consume transaction to hold.
    """
    items = getattr(ctx, "ground_expedition_items", [])
    if not 0 <= index < len(items):
        return None
    stack = items[index]
    if stack.item_type != "consumable":
        return None
    try:
        return find_ground_consumable(stack.item_id)
    except KeyError:
        return None


def consume_kit_charge(ctx, index: int) -> bool:
    """Consume one tinker-kit charge from a validated pack stack."""
    spec = resolve_pack_consumable(ctx, index)
    if spec is None or not is_tinker_kit(spec):
        return False
    _decrement_stack(getattr(ctx, "ground_expedition_items", []), index)
    return True


def kit_drop_payload() -> dict:
    """One qty-1 tinker-kit field-item payload (doc 47.5 SETTLED 34)."""
    return {"item_type": "consumable", "item_id": KIT_ITEM_ID, "quantity": 1}


def _decrement_stack(items, index: int) -> None:
    """Consume one charge from a validated stack."""
    stack = items[index]
    if stack.quantity <= 1:
        del items[index]
        return
    from .ground_equipment import GroundItemStack

    items[index] = GroundItemStack(stack.item_type, stack.item_id, stack.quantity - 1)


def _use_outside_combat(ctx, spec: GroundConsumableSpec) -> bool:
    """Apply an exploration-legal consumable (doc 103 Build C, the
    prose-gate 5-everywhere ruling): the med pack restores its
    instant 5 (clamped, logged like the combat use) AND applies the
    regen status — the FULL heal is retired and the full-HP refusal
    stands (waste protection); the stim applies the stim status,
    spending its duration on exploration steps. The exploration gate
    is catalog data — no v1 row besides the two legal ones reaches
    the generic path (the tinker kit runs its own manage flow
    upstream), so an illegal row's refusal line authors with the
    first one."""
    from . import message_log as _ml
    from .combat import _statuses
    from .data.statuses import REGEN_ID

    if not spec.exploration_legal:
        return False
    if spec.effect_id == REGEN_ID and ctx.ground_hp >= ctx.ground_max_hp:
        ctx.log.add("Ground HP is already full.")
        return False
    if spec.combat_heal_amount > 0:
        _before = ctx.ground_hp
        ctx.ground_hp = min(
            ctx.ground_max_hp, ctx.ground_hp + spec.combat_heal_amount,
        )
        _healed = ctx.ground_hp - _before
        if _healed > 0:
            ctx.log.add_colored(
                f"{spec.name}: +{_healed} HP.", _ml.COLOR_PLAYER_ACTION,
            )
    if spec.duration_turns > 0:
        _statuses.apply(
            ctx.active_statuses, spec.effect_id,
            source=spec.name, theater="ground",
        )
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
