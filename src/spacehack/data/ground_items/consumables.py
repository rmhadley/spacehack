"""Ground consumable catalog — stackable field items with explicit effects.

Each entry is a frozen :class:`GroundConsumableSpec`. ``effect_id`` is
the table key for the Phase 5 effect registry; effects themselves are
not implemented yet, so these specs are inert catalog data for now.
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
    ),
    GroundConsumableSpec(
        id="stim",
        name="Combat Stim",
        effect_id="stim",
        quantity_per_stack=2,
        use_ap_cost=1,
        price=80,
    ),
)
