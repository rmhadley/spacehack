"""Engine modules — affect power generation.

Each entry is a ModuleSpec with slot_type="engine".
"""

from . import ModuleSpec

MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        id="compact_reactor", name="Compact Reactor",
        slot_type="engine",
        description="A small fusion plant. +3 power gen.",
        power_gen_bonus=3, price=50,
        tech_level=1,
    ),
    ModuleSpec(
        id="heavy_reactor", name="Heavy Reactor",
        slot_type="engine",
        description="A massive plant. +6 power gen, -1 cargo.",
        power_gen_bonus=6, cargo_bonus=-1, price=120,
        tech_level=3,
    ),
)
