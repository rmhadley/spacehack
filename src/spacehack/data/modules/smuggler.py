"""Smuggler's holds — conceal contraband from militia cargo scans.

Each entry is a ModuleSpec with slot_type="system". The smuggler_cargo
bonus adds to the player's concealed-cargo capacity (summed like every
other module bonus). It does NOT change storage capacity — only the
militia scan outcome.
"""

from . import ModuleSpec

MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        id="smuggler_hold_mk1", name="Smuggler's Hold Mk. 1",
        slot_type="system",
        description="Conceals up to 10 cargo units from militia scans.",
        smuggler_cargo=10, price=200,
        tech_level=1,
    ),
    ModuleSpec(
        id="smuggler_hold_mk2", name="Smuggler's Hold Mk. 2",
        slot_type="system",
        description="Conceals up to 25 cargo units from militia scans.",
        smuggler_cargo=25, price=500,
        tech_level=2,
    ),
    ModuleSpec(
        id="smuggler_hold_mk3", name="Smuggler's Hold Mk. 3",
        slot_type="system",
        description="Conceals up to 50 cargo units from militia scans.",
        smuggler_cargo=50, price=1200,
        tech_level=3,
    ),
    ModuleSpec(
        id="smuggler_hold_mk4", name="Smuggler's Hold Mk. 4",
        slot_type="system",
        description="Conceals up to 75 cargo units from militia scans.",
        smuggler_cargo=75, price=2500,
        tech_level=4,
    ),
)
