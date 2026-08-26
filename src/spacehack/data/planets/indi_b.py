"""Indi b — a temperate agricultural colony at the middle of the
North Arm.

The breadbasket of the arm: broad farmlands under a warm K-type
sun, feeding the shipyards on Cygni b. Calmer than the other two
arm worlds, with a steady merchant trade and a quiet militia post.
The town is a patchwork of crop plots and hedgerows gathered around
a crossroads market; grain flows down the harvest road to the port.

Layout (160x100, authored farmland grid -- see indi_city.py):

  * spaceport + landing apron, west end.
  * bar "The Harvest", north edge.
  * merchants guild, south edge with the silos beside it.
  * militia station, east end -- door faces the patrol lane.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import INDI_B_POPULATION


# Footprints match the indi_*.layout assets stamped by indi_city.py.
_SPACEPORT_ORIGIN = (10, 30)
_BAR_ORIGIN = (70, 16)
_MERCHANTS_ORIGIN = (66, 66)
_MILITIA_ORIGIN = (116, 62)

_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 12, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 7)
_MERCHANTS_DOOR = (_MERCHANTS_ORIGIN[0] + 12, _MERCHANTS_ORIGIN[1])
_MILITIA_DOOR = (_MILITIA_ORIGIN[0] + 10, _MILITIA_ORIGIN[1])


SPEC = PlanetSpec(
    id="indi_b",
    name="Indi b",
    char="p",
    fg=(120, 180, 130),
    description="A temperate world of broad farmlands feeding the arm's shipyards.",
    width=160,
    height=100,
    hangar_anchor=world.Position(25, 52),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=_SPACEPORT_ORIGIN[0], x_hi=_SPACEPORT_ORIGIN[0] + 23,
            y_lo=_SPACEPORT_ORIGIN[1], y_hi=_SPACEPORT_ORIGIN[1] + 8,
            door_x=_SPACEPORT_DOOR[0], npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=_BAR_ORIGIN[0], x_hi=_BAR_ORIGIN[0] + 20,
            y_lo=_BAR_ORIGIN[1], y_hi=_BAR_ORIGIN[1] + 7,
            door_x=_BAR_DOOR[0], npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants",
            x_lo=_MERCHANTS_ORIGIN[0], x_hi=_MERCHANTS_ORIGIN[0] + 23,
            y_lo=_MERCHANTS_ORIGIN[1], y_hi=_MERCHANTS_ORIGIN[1] + 8,
            door_x=_MERCHANTS_DOOR[0], npc_id="guild_master",
            door_north=True,
        ),
        world.CityBuilding(
            label="militia",
            x_lo=_MILITIA_ORIGIN[0], x_hi=_MILITIA_ORIGIN[0] + 21,
            y_lo=_MILITIA_ORIGIN[1], y_hi=_MILITIA_ORIGIN[1] + 7,
            door_x=_MILITIA_DOOR[0], npc_id="militia_captain",
            door_north=True,
        ),
    ),
    city_layout_id="indi_farmland_grid",
    city_npc_population=INDI_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="west apron",
            # East of the door forecourt, north of the landing apron.
            pos=world.Position(28, 41),
            destinations=("bar", "merchants", "militia"),
        ),
        world.TransitStation(
            id="bar", name="The Harvest", district="north fields",
            # South-east of the door approach, beside the north lane.
            pos=world.Position(86, 26),
            destinations=("spaceport", "merchants", "militia"),
        ),
        world.TransitStation(
            id="merchants", name="Guild Hall", district="south fields",
            # Beside the guild lane, just north-east of the door forecourt.
            pos=world.Position(81, 64),
            destinations=("spaceport", "bar", "militia"),
        ),
        world.TransitStation(
            id="militia", name="Militia Post", district="east end",
            # North-west of the station's door-side lane.
            pos=world.Position(122, 58),
            destinations=("spaceport", "bar", "merchants"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "indi_spaceport_interior"),
        ("bar", "indi_bar_interior"),
        ("merchants", "indi_merchants_interior"),
        ("militia", "indi_militia_interior"),
    ),
    showroom_ships=(
        ("hauler", -6, -4),
        ("cruiser", 0, -5),
        ("freighter", 6, -4),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Farmer",
                guild="bar",
                char="b",
                fg=(200, 170, 90),
                flavor_text=(
                    "The grain goes out to Cygni b; the credits come "
                    "back. The rest is weather and patience."
                ),
            ),
        ),
        (
            "guild_master",
            npc_module.NPC(
                id="guild_master",
                name="Grain Factor",
                guild="merchants",
                char="m",
                fg=(255, 210, 120),
                flavor_text=(
                    "Half the arm eats because our combines run on "
                    "time. Freight contracts, futures, or honest "
                    "bulk trade - the hall handles all three."
                ),
            ),
        ),
    ),
    produces=(
        ("food_rations", 30),
        ("luxury_goods", 8),
    ),
    demands=(
        ("machine_parts", 12),
        ("electronics", 10),
        ("medical_supplies", 8),
    ),
    tech_level=2,
    mission_tier=2,
)
