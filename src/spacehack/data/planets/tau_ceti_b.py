"""τ Cet b — a temperate habitable-zone world, Sol's nearest cousin.

A fledgling colony with optimistic frontier-town energy. Lush green
parks, wide plazas, and a bustling merchant hall. The first "New Earth"
the player encounters outside Sol — a reminder that humanity is
spreading.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE — "The Waypoint" pub.
  * merchants guild, S — active trade hub for this sector.

NPC overrides: barkeep + guild master get frontier-colony flavour.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec


# New Earth palette: lush greens, warm golds, optimistic brights.
TAU_CETI_B_THEME = world.PlanetTheme(
    floor=world.Tile(
        kind="floor", char="\u2591", walkable=True,
        fg=(200, 180, 140), bg=(80, 70, 50),
    ),
    grass=world.Tile(
        kind="grass", char="\u2588", walkable=True,
        fg=(90, 180, 70), bg=(35, 75, 30),
    ),
    grass_accent=world.Tile(
        kind="grass", char=",", walkable=True,
        fg=(70, 150, 55), bg=(35, 75, 30),
    ),
    plaza=world.Tile(
        kind="plaza", char="\u2591", walkable=True,
        fg=(220, 200, 170), bg=(160, 140, 110),
    ),
    sidewalk=world.Tile(
        kind="sidewalk", char="\u2592", walkable=True,
        fg=(140, 120, 90), bg=(65, 55, 40),
    ),
    road_surface=world.Tile(
        kind="road", char=".", walkable=True,
        fg=(120, 110, 90), bg=(50, 45, 35),
    ),
    road_ns=world.Tile(
        kind="road", char=":", walkable=True,
        fg=(100, 90, 70), bg=(40, 35, 25),
    ),
    road_ew=world.Tile(
        kind="road", char="-", walkable=True,
        fg=(100, 90, 70), bg=(40, 35, 25),
    ),
    landing_pad=world.Tile(
        kind="landing_pad", char="O", walkable=True,
        fg=(220, 200, 120), bg=(55, 50, 30),
    ),
    neon=world.Tile(
        kind="neon", char="*", walkable=True,
        fg=(180, 240, 120), bg=(30, 60, 25),
    ),
    tree=world.Tile(
        kind="tree", char="\u2663", walkable=True,
        fg=(60, 200, 50), bg=(35, 75, 30),
    ),
    decor=world.Tile(
        kind="plaza", char="\u2666", walkable=True,
        fg=(255, 200, 80), bg=(160, 140, 110),
    ),
)


SPEC = PlanetSpec(
    theme=TAU_CETI_B_THEME,
    id="tc_b",
    name="τ Cet b",
    char="p",
    fg=(140, 200, 180),
    description="A temperate rocky world in the habitable zone — a new frontier.",
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
    ),
    showroom_ships=(
        ("scout",   3, 2),
        ("hauler",  7, 2),
        ("cruiser", 11, 4),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Colony Host",
                guild="bar",
                char="b",
                fg=(180, 220, 130),
                flavor_text=(
                    "Welcome to τ Cet b — the beer is local, the "
                    "stories are tall, and the landing pads are always open."
                ),
            ),
        ),
        (
            "guild_master",
            npc_module.NPC(
                id="guild_master",
                name="Trade Commissioner",
                guild="merchants",
                char="G",
                fg=(220, 210, 130),
                flavor_text=(
                    "This colony runs on trade. If you've got cargo "
                    "and a working drive, I've got credits."
                ),
            ),
        ),
    ),
)
