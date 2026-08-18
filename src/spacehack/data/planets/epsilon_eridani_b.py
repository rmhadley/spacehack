"""ε Eri b — a warm rocky super-Earth, the first deep-space settlement.

A rugged, self-reliant colony carved into dry canyons and dust plains.
Tough pioneers, solar-panel fields, and a no-nonsense militia that keeps
the peace this far from Sol.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE corner — "The Dusty Glass" saloon.
  * merchants, SW corner — the colony's trade hall.
  * militia, S row — frontier law enforcement.

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
from .themes import WARM_EARTH


SPEC = PlanetSpec(
    theme=WARM_EARTH,
    id="eri_b",
    name="Epsilon Eri b",
    char="p",
    fg=(190, 130, 90),
    description="A warm, rocky super-Earth - the first deep-space settlement.",
    width=60,
    height=40,
    hangar_anchor=world.Position(13, 17),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=4,  x_hi=23, y_lo=3,  y_hi=12,
            door_x=13, npc_id="",
        ),
        world.CityBuilding(
            label="bar",       x_lo=34, x_hi=41, y_lo=8,  y_hi=13,
            door_x=37, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants", x_lo=4,  x_hi=24, y_lo=25, y_hi=36,
            door_x=14, npc_id="guild_master",
            door_north=True,
        ),
        world.CityBuilding(
            label="militia",   x_lo=40, x_hi=55, y_lo=26, y_hi=35,
            door_x=47, npc_id="militia_captain",
            door_north=True,
        ),
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
