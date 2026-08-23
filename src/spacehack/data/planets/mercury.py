"""Mercury — a scorched rocky world, closest to Sol.

A small solar research station studies the sun from the best vantage
point in the system. The station is heavily shielded and cooled —
without protection, the surface heat would melt a ship in minutes.

Mercury is the Phase 5 proof city: it exercises the *same* data-driven
city pipeline as Earth (buildings, transit, authored interiors, ambient
NPCs) while reading as a clearly different place — a compact desert
research base instead of a river city. Everything below is data on the
spec; no builder code is Mercury-specific.

Layout (40x30, compact):

  * spaceport, NW corner (port apron + pad south of it).
  * lab, NE — solar observatory, run by the research officer.
  * bar, SW — station cantina (every base has a bar).
  * supply depot, SE — stores rations, electronics, and fuel cells.
"""
from __future__ import annotations

from ... import world
from ...dungeon import DungeonParams
from . import PlanetSpec
from .themes import DESERT
from ..city_npcs import MERCURY_POPULATION


SPEC = PlanetSpec(
    theme=DESERT,
    id="mercury",
    name="Mercury",
    char="m",
    fg=(180, 175, 165),
    description="A scorched rocky world - closest to Sol, home to a solar research station.",
    width=40,
    height=30,
    hangar_anchor=world.Position(7, 14),
    buildings=(
        # Building rectangles mirror the authored exterior footprints in
        # mercury_city.LANDMARK_ORIGINS; doors open onto the deck's
        # service roads or the landing apron.
        world.CityBuilding(
            label="spaceport",
            x_lo=2,  x_hi=15, y_lo=2,  y_hi=10,
            door_x=8, npc_id="",
        ),
        world.CityBuilding(
            label="lab",
            x_lo=22, x_hi=37, y_lo=8,  y_hi=18,
            door_x=29, npc_id="research_officer",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=4,  x_hi=14, y_lo=20, y_hi=26,
            door_x=9, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="supply",
            x_lo=21, x_hi=32, y_lo=20, y_hi=26,
            door_x=26, npc_id="depot_attendant",
        ),
    ),
    city_layout_id="mercury_station",
    city_npc_population=MERCURY_POPULATION,
    transit_stations=(
        # One stop beside each building's door (never on the door, the
        # road, or the apron in front of it) plus a commons hub on the
        # plaza. The network is fully connected so the player can ride
        # directly between districts.
        world.TransitStation(
            id="port", name="Spaceport", district="spaceport",
            pos=world.Position(12, 11),
            destinations=("hub", "lab", "bar", "supply"),
        ),
        world.TransitStation(
            id="hub", name="Commons Hub", district="bar",
            pos=world.Position(18, 21),
            destinations=("port", "lab", "bar", "supply"),
        ),
        world.TransitStation(
            id="lab", name="Solar Lab", district="lab",
            pos=world.Position(34, 20),
            destinations=("port", "hub", "bar", "supply"),
        ),
        world.TransitStation(
            id="bar", name="Cantina", district="bar",
            pos=world.Position(15, 26),
            destinations=("port", "hub", "lab", "supply"),
        ),
        world.TransitStation(
            id="supply", name="Supply Depot", district="supply",
            pos=world.Position(33, 28),
            destinations=("port", "hub", "lab", "bar"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "mercury_spaceport_interior"),
        ("lab", "mercury_lab_interior"),
        ("bar", "mercury_bar_interior"),
        ("supply", "mercury_supply_interior"),
    ),
    showroom_ships=(
        ("scout", 3, 2),
    ),
    npc_overrides=(),
    produces=(
        ("research_data", 10),
    ),
    demands=(
        ("food_rations", 10),
        ("electronics", 8),
        ("fuel_cells", 15),
    ),
    tech_level=1,
    # Militia chain delve site (mil_q2_cache): the classified requisition
    # cache sits deep in the scorched cave system under the research
    # station. Same BSP generator as the Mars surface — planet-themed
    # tiles (charred dark rock + ember floor).
    explorable_site_name="caves",
    dungeon_params=DungeonParams(
        width=80,
        height=60,
        min_room_size=4,
        max_room_size=14,
        room_fill_pct=0.6,
        tile_wall=world.Tile(
            kind="dungeon_wall", char="#", walkable=False,
            fg=(110, 90, 80), bg=(25, 18, 12),
        ),
        tile_floor=world.Tile(
            kind="dungeon_floor", char=".", walkable=True,
            fg=(200, 140, 90), bg=(60, 35, 18),
        ),
        # Scorched-cave fauna: scavenger packs + faster prowlers.
        monster_pool=("rock_scavenger", "dust_prowler"),
        monster_density=1.5,
        cache_guardian_pool=("assault_drone",),
        cache_guardian_count=1,
    ),
)
