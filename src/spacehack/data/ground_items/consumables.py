"""Ground consumable catalog — stackable field items with explicit effects.

Each entry is a frozen :class:`GroundConsumableSpec`. ``effect_id`` is
the table key for the Phase 5 effect registry; numeric healing, AP, and
duration values remain data-driven so variants do not require runtime
conditionals.
"""

from . import GroundConsumableSpec

CONSUMABLES: tuple[GroundConsumableSpec, ...] = (
    GroundConsumableSpec(
        id="med_pack",
        name="Med Pack",
        effect_id="restore_hp",
        quantity_per_stack=3,
        use_ap_cost=1,
        price=60,
        outside_full_heal=True,
        combat_heal_amount=5,
        combat_regen_amount=2,
        duration_turns=3,
    ),
    GroundConsumableSpec(
        id="stim",
        name="Combat Stim",
        effect_id="stim",
        quantity_per_stack=2,
        use_ap_cost=1,
        price=80,
        duration_turns=3,
        combat_ap_bonus=1,
    ),
)
