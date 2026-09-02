"""ε Eri b — a warm rocky super-Earth, the first deep-space settlement.

A rugged, self-reliant colony carved into dry canyons and dust plains.
Tough pioneers, solar-panel fields, and a no-nonsense militia that keeps
the peace this far from Sol.

Layout (200x140):

  * spaceport on the western landing plateau.
  * bar at the central canyon overlook — "The Dusty Glass" saloon.
  * merchants at the eastern freight interchange.
  * militia at the southern frontier gate.
  * four elevated crossings connect the terraced settlement.

NPC overrides: barkeep + guild master get frontier-pioneer
flavour; the militia building keeps its regular captain. The Act 0
``demolitions_expert`` stands in the militia hall ADDITIVELY
(``quest_npc_spots``) while the militia chain's recruit step is
live, then leaves — the seek-help lead surfaces at any militia
captain, and the expert is present only when the chain needs him.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import CANYON_SETTLEMENT
from ..city_npcs import ERI_B_POPULATION


SPEC = PlanetSpec(
    theme=CANYON_SETTLEMENT,
    id="eri_b",
    name="Epsilon Eri b",
    char="p",
    fg=(190, 130, 90),
    description="A warm, rocky super-Earth - the first deep-space settlement.",
    width=200,
    height=140,
    hangar_anchor=world.Position(34, 43),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=20, x_hi=45, y_lo=18, y_hi=25,
            door_x=30, npc_id="",
        ),
        world.CityBuilding(
            label="bar", x_lo=67, x_hi=84, y_lo=68, y_hi=74,
            door_x=74, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants", x_lo=116, x_hi=142, y_lo=70, y_hi=78,
            door_x=126, npc_id="guild_master",
        ),
        world.CityBuilding(
            label="militia", x_lo=151, x_hi=179, y_lo=105, y_hi=114,
            door_x=164, npc_id="militia_captain",
        ),
    ),
    city_layout_id="eri_canyon_settlement",
    city_npc_population=ERI_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="west plateau",
            pos=world.Position(23, 32), serves="eri_spaceport",
            destinations=("bar", "merchants", "militia"),
        ),
        world.TransitStation(
            id="bar", name="Dusty Glass", district="canyon overlook",
            pos=world.Position(72, 76), serves="eri_bar",
            destinations=("spaceport", "merchants", "militia"),
        ),
        world.TransitStation(
            id="merchants", name="Freight Interchange", district="trade",
            pos=world.Position(124, 80), serves="eri_merchants",
            destinations=("spaceport", "bar", "militia"),
        ),
        world.TransitStation(
            id="militia", name="Eastern Gate", district="frontier gate",
            pos=world.Position(162, 116), serves="eri_militia",
            destinations=("spaceport", "bar", "merchants"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "eri_spaceport_interior"),
        ("bar", "eri_bar_interior"),
        ("merchants", "eri_merchants_interior"),
        ("militia", "eri_militia_interior"),
    ),
    showroom_ships=(
        ("hauler",   7, 2),
        ("freighter", 15, 2),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Settler",
                guild="bar",
                char="b",
                fg=(200, 160, 100),
                flavor_text=(
                    "Dust gets in everything out here. Sit, "
                    "wet your throat, and tell me what brought "
                    "you past the beacon."
                ),
            ),
        ),
        (
            "guild_master",
            npc_module.NPC(
                id="guild_master",
                name="Settlement Trader",
                guild="merchants",
                char="G",
                fg=(210, 170, 100),
                flavor_text=(
                    "First settlement past Sol runs on what gets "
                    "hauled in. Electronics, meds, machine parts - "
                    "bring them and I'll make it worth your fuel."
                ),
            ),
        ),
    ),
    # The Act 0 demolitions_expert stands here (additively) only while
    # mil_q4_demolitions is live — see spawn_quest_npcs.
    quest_npc_spots=(
        ("demolitions_expert", "militia"),
    ),
    produces=(
        ("ore_processed", 30),
        ("food_rations", 15),
    ),
    demands=(
        ("electronics", 10),
        ("medical_supplies", 8),
        ("machine_parts", 10),
    ),
    tech_level=3,
    mission_tier=2,
)
