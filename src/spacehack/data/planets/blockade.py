"""Blockade Station — a militia checkpoint on the edge of federation space.

Two blockade stations guard the border past Luyten's Star — the last
outpost of charted space. The station interior is functional and
utilitarian: a landing bay and a militia command post with the
Blockade Officer who questions every ship heading into the void.

Layout (60x40):

  * spaceport, NW corner.
  * militia, S row — blockade command centre.

Reuses the global ``blockade_officer`` NPC from the NPCS catalog
(no overrides needed).
"""
from __future__ import annotations

from ... import world
from . import PlanetSpec
from .themes import STATION


SPEC = PlanetSpec(
    theme=STATION,
    id="blockade",
    name="Blockade Station",
    char="#",
    fg=(130, 230, 220),
    description="A militia blockade station guarding the edge of federation space.",
    width=60,
    height=40,
    hangar_anchor=world.Position(13, 17),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=4,  x_hi=23, y_lo=3,  y_hi=12,
            door_x=13, npc_id="",
        ),
        world.CityBuilding(
            label="militia",   x_lo=40, x_hi=55, y_lo=26, y_hi=35,
            door_x=47, npc_id="blockade_officer",
            door_north=True,
        ),
    ),
    showroom_ships=(
        ("scout",  3, 2),
        ("hauler", 7, 2),
    ),
    npc_overrides=(),
    produces=(
        ("weapons_blackmarket", 5),
    ),
    demands=(
        ("food_rations", 10),
        ("electronics", 8),
        ("fuel_cells", 12),
    ),
    trade_npc_id="blockade_officer",
)
