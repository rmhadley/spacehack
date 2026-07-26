"""Vega b — a massive gas giant with a floating observation station.

Not a planetary surface — the player "lands" on an orbital platform
suspended in the upper atmosphere. Cool blues, silver trims, and
wide observation windows looking down into the swirling cloud bands.

Layout (60x40):

  * spaceport (arrival deck), NW corner.
  * bar (observation lounge), NE corner — "The Veil" — floor-to-ceiling
    windows overlooking the gas giant's cloudscape.

NPC overrides: the barkeep becomes the "Cloud Host" — a sleek,
welcoming figure who knows the gossip of the deep-space routes.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec


# Cloud city palette: cool blues, silver, pale whites.
VEGA_B_THEME = world.PlanetTheme(
    floor=world.Tile(
        kind="floor", char="\u2591", walkable=True,
        fg=(180, 200, 230), bg=(60, 75, 95),
    ),
    grass=world.Tile(
        kind="grass", char="\u2588", walkable=True,
        fg=(140, 190, 220), bg=(50, 65, 85),
    ),
    grass_accent=world.Tile(
        kind="grass", char=",", walkable=True,
        fg=(120, 170, 200), bg=(50, 65, 85),
    ),
    plaza=world.Tile(
        kind="plaza", char="\u2591", walkable=True,
        fg=(210, 225, 245), bg=(155, 175, 200),
    ),
    sidewalk=world.Tile(
        kind="sidewalk", char="\u2592", walkable=True,
        fg=(130, 155, 180), bg=(55, 70, 85),
    ),
    road_surface=world.Tile(
        kind="road", char=".", walkable=True,
        fg=(110, 130, 155), bg=(42, 55, 70),
    ),
    road_ns=world.Tile(
        kind="road", char=":", walkable=True,
        fg=(90, 110, 135), bg=(35, 45, 60),
    ),
    road_ew=world.Tile(
        kind="road", char="-", walkable=True,
        fg=(90, 110, 135), bg=(35, 45, 60),
    ),
    landing_pad=world.Tile(
        kind="landing_pad", char="O", walkable=True,
        fg=(200, 230, 255), bg=(45, 60, 75),
    ),
    neon=world.Tile(
        kind="neon", char="*", walkable=True,
        fg=(160, 220, 255), bg=(30, 45, 60),
    ),
    tree=world.Tile(
        kind="tree", char="\u2663", walkable=True,
        fg=(120, 200, 230), bg=(50, 65, 85),
    ),
    decor=world.Tile(
        kind="plaza", char="\u2666", walkable=True,
        fg=(200, 240, 255), bg=(155, 175, 200),
    ),
)


SPEC = PlanetSpec(
    theme=VEGA_B_THEME,
    id="vega_b",
    name="Vega b",
    char="P",
    fg=(200, 200, 220),
    description="A massive gas giant — its upper atmosphere hosts a floating observation deck.",
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
                name="Cloud Host",
                guild="bar",
                char="b",
                fg=(180, 220, 240),
                flavor_text=(
                    "Welcome to the Veil. Drink in the view — "
                    "the clouds below shift faster than the politics above."
                ),
            ),
        ),
    ),
)
