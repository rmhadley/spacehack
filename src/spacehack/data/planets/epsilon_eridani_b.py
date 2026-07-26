"""ε Eri b — a warm rocky super-Earth, the first deep-space settlement.

A rugged, self-reliant colony carved into dry canyons and dust plains.
Tough pioneers, solar-panel fields, and a no-nonsense militia that keeps
the peace this far from Sol.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE corner — "The Dusty Glass" saloon.
  * militia, S row — frontier law enforcement.

NPC overrides: barkeep + militia captain get frontier-pioneer flavour.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import WARM_EARTH


SPEC = PlanetSpec(
    theme=WARM_EARTH,
    id="eri_b",
    name="ε Eri b",
    char="p",
    fg=(190, 130, 90),
    description="A warm, rocky super-Earth — the first deep-space settlement.",
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
            label="militia",   x_lo=40, x_hi=55, y_lo=26, y_hi=35,
            door_x=47, npc_id="militia_captain",
            door_north=True,
        ),
    ),
    showroom_ships=(
        ("scout",  3, 2),
        ("hauler", 7, 2),
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
            "militia_captain",
            npc_module.NPC(
                id="militia_captain",
                name="Range Marshal",
                guild="militia",
                char="K",
                fg=(170, 140, 120),
                flavor_text=(
                    "This far from Sol, we make our own law. "
                    "Keep your nose clean and your drive hot."
                ),
            ),
        ),
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
)
