"""Ground consumable catalog — stackable field items with explicit effects.

Each entry is a frozen :class:`GroundConsumableSpec`. ``effect_id``
resolves against the status catalog (``find_status``, doc 103); the
numeric fields below are the descriptive display values (the status
row owns the applied numbers).
"""

from . import GroundConsumableSpec

CONSUMABLES: tuple[GroundConsumableSpec, ...] = (
    GroundConsumableSpec(
        id="med_pack",
        name="Med Pack",
        # Doc 103 Build A: the timed effect is the regen status row;
        # Build C: the instant 5 applies at BOTH use sites (the
        # prose-gate 5-everywhere ruling), the full heal is retired.
        effect_id="regen",
        quantity_per_stack=3,
        use_ap_cost=1,
        price=60,
        exploration_legal=True,
        combat_heal_amount=5,
        combat_regen_amount=2,
        duration_turns=3,
        effect_label="Restore HP",
    ),
    GroundConsumableSpec(
        id="stim",
        name="Combat Stim",
        # Doc 103 Build C (q12a): exploration-legal — the approach
        # spends it (pre-buffing with a walking cost).
        effect_id="stim",
        quantity_per_stack=2,
        use_ap_cost=1,
        price=80,
        exploration_legal=True,
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
