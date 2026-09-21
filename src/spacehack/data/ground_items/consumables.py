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
        effect_label="Restore HP",
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
        effect_label="Temporary AP boost",
    ),
    # Doc 47.5 SETTLED 34/36: a very rare loot-only consumable, never
    # sold; the effect_label IS the explanation (no guide entry).
    GroundConsumableSpec(
        id="tinker_kit",
        name="Tinker Kit",
        effect_id="tinker",
        quantity_per_stack=2,
        use_ap_cost=0,
        price=0,
        effect_label=(
            "Modify an item of your choice, increasing its "
            "effectiveness, up to Prototype."
        ),
        shop_available=False,
    ),
)
