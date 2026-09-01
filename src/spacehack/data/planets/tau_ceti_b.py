"""Tau Cet b -- a temperate habitable-zone world, Sol's nearest cousin.

A fledgling colony hacked out of an iridescent alien rainforest. The
survey gardens hybridized with the native flora and never stopped:
vivid purple canopy now walls the clearing on every side, glowing
spore patches light the fern meadow, and saplings push through the
plaza tiles each week. The first "New Earth" outside Sol -- still
optimistic, but losing ground gracefully.

Layout (160x100, authored canopy clearing -- see tc_city.py):

  * spaceport + landing apron, west side of the clearing.
  * bar "The Waypoint", north edge, via a short south spur.
  * merchants hall, south-east, door on the perimeter path.

NPC overrides: barkeep + guild master get frontier-colony flavour.
The Act 0 ``salvage_specialist`` stands in the merchants hall
ADDITIVELY (``quest_npc_spots``) while the merchant chain needs her
(the ore delivery + the alloy handover), then leaves.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import TC_B_POPULATION


# Footprints match the tc_*.layout assets stamped by tc_city.py.
_SPACEPORT_ORIGIN = (10, 28)
_BAR_ORIGIN = (98, 20)
_MERCHANTS_ORIGIN = (94, 64)

_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 12, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 7)
_MERCHANTS_DOOR = (_MERCHANTS_ORIGIN[0] + 12, _MERCHANTS_ORIGIN[1] + 8)


SPEC = PlanetSpec(
    id="tc_b",
    name="Tau Cet b",
    char="p",
    fg=(140, 200, 180),
    description="A temperate rocky world in the habitable zone - a new frontier.",
    width=160,
    height=100,
    hangar_anchor=world.Position(25, 50),
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
        ),
    ),
    city_layout_id="tc_canopy_clearing",
    city_npc_population=TC_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="west apron",
            # East of the door forecourt, north of the landing apron.
            pos=world.Position(24, 38), serves="tc_spaceport",
            destinations=("bar", "merchants"),
        ),
        world.TransitStation(
            id="bar", name="The Waypoint", district="north edge",
            # South-east of the door approach, beside the north spur.
            pos=world.Position(105, 29), serves="tc_bar",
            destinations=("spaceport", "merchants"),
        ),
        world.TransitStation(
            id="merchants", name="Merchants Hall", district="south path",
            # East of the door approach, off the southern perimeter leg.
            pos=world.Position(104, 77), serves="tc_merchants",
            destinations=("spaceport", "bar"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "tc_spaceport_interior"),
        ("bar", "tc_bar_interior"),
        ("merchants", "tc_merchants_interior"),
    ),
    showroom_ships=(
        ("hauler", -6, -4),
        ("cruiser", 0, -5),
        ("frigate", 6, -4),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Colony Host",
                guild="bar",
                char="b",
                fg=(200, 140, 255),
                flavor_text=(
                    "Welcome to Tau Cet b - mind the flowerbeds, they "
                    "mind you back. Half our exports are seeds and the "
                    "other half are stories about what grew from them."
                ),
            ),
        ),
        (
            "guild_master",
            npc_module.NPC(
                id="guild_master",
                name="Guild Factor",
                guild="merchants",
                char="m",
                fg=(255, 210, 120),
                flavor_text=(
                    "The jungle gives three harvests a season whether we "
                    "ask or not - so we sell what it sends. You want ore, "
                    "produce, or something the survey teams can't name?"
                ),
            ),
        ),
    ),
    # The Act 0 salvage_specialist stands here (additively) only while
    # mer_q3_transport / mer_q4_calibrate are live -- see spawn_quest_npcs.
    quest_npc_spots=(
        ("salvage_specialist", "merchants"),
    ),
    produces=(
        ("food_rations", 25),
        ("ore_processed", 20),
    ),
    demands=(
        ("electronics", 12),
        ("machine_parts", 10),
        ("luxury_goods", 8),
    ),
    tech_level=2,
    mission_tier=2,
)
