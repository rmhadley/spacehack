"""Engine modules — affect power generation.

Each entry is a ModuleSpec with slot_type="engine".
"""

from . import ModuleSpec

MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        id="compact_reactor", name="Compact Reactor Mk. 1",
        slot_type="engine",
        description="A small fusion plant. +3 power, +1 speed.",
        power_gen_bonus=3, speed_bonus=1, price=50,
        tech_level=1,
    ),
    ModuleSpec(
        id="reactor_mk2", name="Reactor Mk. 2",
        slot_type="engine",
        description="Improved fusion core. +5 power, +2 speed.",
        power_gen_bonus=5, speed_bonus=2, price=130,
        tech_level=2,
    ),
    ModuleSpec(
        id="reactor_mk3", name="Reactor Mk. 3",
        slot_type="engine",
        description="High-output tokamak. +8 power, +3 speed.",
        power_gen_bonus=8, speed_bonus=3, price=250,
        tech_level=3,
    ),
    ModuleSpec(
        id="reactor_mk4", name="Reactor Mk. 4",
        slot_type="engine",
        description="Antimatter-enhanced core. +12 power, +4 speed.",
        power_gen_bonus=12, speed_bonus=4, price=420,
        tech_level=4,
    ),
    ModuleSpec(
        id="heavy_reactor", name="Heavy Reactor",
        slot_type="engine",
        description="A massive plant. +6 power, -1 cargo, +1 speed.",
        power_gen_bonus=6, cargo_bonus=-1, speed_bonus=1, price=120,
        tech_level=3,
    ),
)
