"""Procyon c — a cold icy body on the outer edge of the Procyon system.

A small research outpost drills through kilometres of ice to study
the ancient core samples. The station is cramped, quiet, and always
cold. Tunnels connect a small landing bay to a research lab staffed
by a lone science officer.

Layout (40x24, compact like the Science Port):

  * spaceport, NW corner.
  * lab, NE corner — research officer studies ice-core samples.

No NPC overrides — reuses the global ``research_officer`` catalog
entry (the same officer type as the Alpha Centauri Science Port,
but with the frozen-outpost context).
"""
from __future__ import annotations

from ... import world
from . import PlanetSpec
from .themes import ICE


SPEC = PlanetSpec(
    theme=ICE,
    id="proc_planet_2",
    name="Procyon c",
    char="P",
    fg=(190, 200, 215),
    description="An icy body on Procyon's outer reach — a quiet research outpost.",
    width=40,
    height=24,
    hangar_anchor=world.Position(7, 14),
    buildings=(
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
    ),
    showroom_ships=(
        ("scout",   3, 2),
        ("cruiser", 11, 4),
    ),
    npc_overrides=(),
    produces=(
        ("research_data", 10),
    ),
    demands=(
        ("food_rations", 8),
        ("fuel_cells", 10),
    ),
    tech_level=2,
)
