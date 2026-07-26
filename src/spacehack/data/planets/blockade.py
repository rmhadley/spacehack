"""Blockade — Militia Blockade Station interior used at Luyten's
Star, the edge of federation space.

Shares the same layout as the generic depot (40x24, spaceport +
office building) but the office NPC is a hardcoded
``blockade_officer`` with militia flavour text. This is a
separate PlanetSpec (not an NPC override of the depot) because
the blockade has its own building label and the two stations
would need conflicting overrides if they shared the depot spec.
"""
from __future__ import annotations

from ... import world
from . import PlanetSpec


# Military-industrial theme: cool steel blues, dark greys,
# reads as a military checkpoint rather than a civilian depot.
BLOCKADE_THEME = world.PlanetTheme(
    floor=world.Tile(
        kind="floor", char="\u2591", walkable=True,
        fg=(160, 190, 220), bg=(55, 70, 90),
    ),
)


SPEC = PlanetSpec(
    theme=BLOCKADE_THEME,
    id="blockade",
    name="Blockade Station",
    char="#",
    fg=(130, 230, 220),
    description="A militia blockade station on the edge of federation space.",
    width=40,
    height=24,
    hangar_anchor=world.Position(7, 14),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=2, x_hi=15, y_lo=2, y_hi=10,
            door_x=8, npc_id="",
        ),
        world.CityBuilding(
            label="militia", x_lo=22, x_hi=37, y_lo=8, y_hi=18,
            door_x=29, npc_id="blockade_officer",
        ),
    ),
    showroom_ships=(
        ("scout", 3, 2),
        ("hauler", 7, 4),
    ),
    npc_overrides=(),
)
