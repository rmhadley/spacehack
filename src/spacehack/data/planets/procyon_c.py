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


# Ice station palette: cold blues, icy whites, frost.
PROCYON_C_THEME = world.PlanetTheme(
    floor=world.Tile(
        kind="floor", char="\u2591", walkable=True,
        fg=(180, 210, 240), bg=(60, 80, 110),
    ),
    grass=world.Tile(
        kind="grass", char="\u2588", walkable=True,
        fg=(200, 220, 245), bg=(70, 90, 120),
    ),
    grass_accent=world.Tile(
        kind="grass", char=",", walkable=True,
        fg=(180, 200, 230), bg=(70, 90, 120),
    ),
    plaza=world.Tile(
        kind="plaza", char="\u2591", walkable=True,
        fg=(210, 230, 250), bg=(150, 175, 205),
    ),
    sidewalk=world.Tile(
        kind="sidewalk", char="\u2592", walkable=True,
        fg=(130, 160, 195), bg=(55, 75, 100),
    ),
    road_surface=world.Tile(
        kind="road", char=".", walkable=True,
        fg=(110, 140, 175), bg=(40, 60, 85),
    ),
    road_ns=world.Tile(
        kind="road", char=":", walkable=True,
        fg=(90, 120, 155), bg=(35, 50, 70),
    ),
    road_ew=world.Tile(
        kind="road", char="-", walkable=True,
        fg=(90, 120, 155), bg=(35, 50, 70),
    ),
    landing_pad=world.Tile(
        kind="landing_pad", char="O", walkable=True,
        fg=(220, 240, 255), bg=(50, 70, 95),
    ),
    neon=world.Tile(
        kind="neon", char="*", walkable=True,
        fg=(150, 230, 255), bg=(35, 55, 80),
    ),
    tree=world.Tile(
        kind="tree", char="\u2663", walkable=True,
        fg=(140, 210, 240), bg=(70, 90, 120),
    ),
    decor=world.Tile(
        kind="plaza", char="\u2666", walkable=True,
        fg=(200, 240, 255), bg=(150, 175, 205),
    ),
)


SPEC = PlanetSpec(
    theme=PROCYON_C_THEME,
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
        ("scout",  3, 2),
        ("hauler", 7, 4),
    ),
    npc_overrides=(),
)
