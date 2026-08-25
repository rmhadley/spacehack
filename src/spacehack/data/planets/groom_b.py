"""Groombridge 34 b — a hardpan boomtown at the end of the North
Arm.

The arm runs out here: beyond the gate is nothing but dark. The
ore fields draw hard-bitten prospectors, the bar doubles as a
bounty office, and the militia doesn't come this far. Law and order
are whatever you bring with you.

Layout (120x80, authored linear boomtown):

  * One full-width ore-haul road through the mid-map; a southern
    service road closes the ring with two connectors.
  * Spaceport + landing apron, west end.
  * The Last Gate bar, centre-north, facing the haul road.
  * Bounty office, centre-south, across the road from the bar.
  * Depot, east end -- last fuel before the gate.
  * Tailings mounds, claim stakes, and shanty shacks; no militia.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import GROOM_B_POPULATION


# Footprints match the groom_*.layout assets stamped by groom_city.py.
_SPACEPORT_ORIGIN = (5, 13)
_BAR_ORIGIN = (47, 15)
_BOUNTIES_ORIGIN = (40, 51)
_DEPOT_ORIGIN = (86, 50)

_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 12, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 7)
_BOUNTIES_DOOR = (_BOUNTIES_ORIGIN[0] + 10, _BOUNTIES_ORIGIN[1] + 7)
_DEPOT_DOOR = (_DEPOT_ORIGIN[0] + 12, _DEPOT_ORIGIN[1] + 8)


SPEC = PlanetSpec(
    id="groom_b",
    name="Groombridge 34 b",
    char="p",
    fg=(110, 100, 90),
    description="A rough mining world at the end of the arm - no laws, no militia.",
    width=120,
    height=80,
    hangar_anchor=world.Position(17, 31),
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
            label="bounties",
            x_lo=_BOUNTIES_ORIGIN[0], x_hi=_BOUNTIES_ORIGIN[0] + 19,
            y_lo=_BOUNTIES_ORIGIN[1], y_hi=_BOUNTIES_ORIGIN[1] + 7,
            door_x=_BOUNTIES_DOOR[0], npc_id="bounty_master",
        ),
        world.CityBuilding(
            label="depot",
            x_lo=_DEPOT_ORIGIN[0], x_hi=_DEPOT_ORIGIN[0] + 23,
            y_lo=_DEPOT_ORIGIN[1], y_hi=_DEPOT_ORIGIN[1] + 8,
            door_x=_DEPOT_DOOR[0], npc_id="depot_attendant",
        ),
    ),
    city_layout_id="groom_hardpan_boomtown",
    city_npc_population=GROOM_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="west apron",
            # East of the door approach, beside the landing pad.
            pos=world.Position(21, 24),
            destinations=("bar", "bounties", "depot"),
        ),
        world.TransitStation(
            id="bar", name="The Last Gate", district="mid-town",
            # East of the door approach.
            pos=world.Position(60, 24),
            destinations=("spaceport", "bounties", "depot"),
        ),
        world.TransitStation(
            id="bounties", name="Bounty Office", district="south side",
            # West of the door approach.
            pos=world.Position(46, 60),
            destinations=("spaceport", "bar", "depot"),
        ),
        world.TransitStation(
            id="depot", name="Depot", district="east end",
            # West of the door approach.
            pos=world.Position(94, 60),
            destinations=("spaceport", "bar", "bounties"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "groom_spaceport_interior"),
        ("bar", "groom_bar_interior"),
        ("bounties", "groom_bounties_interior"),
        ("depot", "groom_depot_interior"),
    ),
    showroom_ships=(
        ("hauler", -6, -3),
        ("cruiser", 0, -4),
        ("frigate", 6, -3),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Prospector",
                guild="bar",
                char="b",
                fg=(210, 130, 80),
                flavor_text=(
                    "Out past the gate there's nothing - that's the "
                    "point. In here, a pilot can get rich or get dead. "
                    "Sometimes both."
                ),
            ),
        ),
        (
            "bounty_master",
            npc_module.NPC(
                id="bounty_master",
                name="Claim Clerk",
                guild="bhguild",
                char="B",
                fg=(255, 190, 110),
                flavor_text=(
                    "The guild's posters reach farther than any patrol. "
                    "Bring me proof out here and credits change hands - "
                    "no questions worth asking."
                ),
            ),
        ),
    ),
    produces=(
        ("ore_processed", 35),
        ("weapons_blackmarket", 6),
    ),
    demands=(
        ("food_rations", 15),
        ("fuel_cells", 12),
        ("medical_supplies", 10),
    ),
    tech_level=3,
    mission_tier=3,
)
