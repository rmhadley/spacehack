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


# Rugged settlement palette: warm earth tones, dry browns, pioneer amber.
ERI_B_THEME = world.PlanetTheme(
    floor=world.Tile(
        kind="floor", char="\u2591", walkable=True,
        fg=(170, 140, 100), bg=(65, 50, 35),
    ),
    grass=world.Tile(
        kind="grass", char="\u2588", walkable=True,
        fg=(150, 110, 60), bg=(55, 38, 22),
    ),
    grass_accent=world.Tile(
        kind="grass", char=",", walkable=True,
        fg=(130, 90, 50), bg=(55, 38, 22),
    ),
    plaza=world.Tile(
        kind="plaza", char="\u2591", walkable=True,
        fg=(200, 170, 130), bg=(145, 115, 80),
    ),
    sidewalk=world.Tile(
        kind="sidewalk", char="\u2592", walkable=True,
        fg=(120, 90, 60), bg=(50, 38, 25),
    ),
    road_surface=world.Tile(
        kind="road", char=".", walkable=True,
        fg=(105, 80, 55), bg=(40, 30, 20),
    ),
    road_ns=world.Tile(
        kind="road", char=":", walkable=True,
        fg=(85, 65, 45), bg=(32, 24, 16),
    ),
    road_ew=world.Tile(
        kind="road", char="-", walkable=True,
        fg=(85, 65, 45), bg=(32, 24, 16),
    ),
    landing_pad=world.Tile(
        kind="landing_pad", char="O", walkable=True,
        fg=(210, 160, 80), bg=(45, 32, 18),
    ),
    neon=world.Tile(
        kind="neon", char="*", walkable=True,
        fg=(255, 180, 80), bg=(35, 22, 12),
    ),
    tree=world.Tile(
        kind="tree", char="\u2663", walkable=True,
        fg=(160, 110, 50), bg=(55, 38, 22),
    ),
    decor=world.Tile(
        kind="plaza", char="\u2666", walkable=True,
        fg=(255, 150, 60), bg=(145, 115, 80),
    ),
)


SPEC = PlanetSpec(
    theme=ERI_B_THEME,
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
)
