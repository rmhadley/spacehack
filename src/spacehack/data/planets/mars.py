"""Mars: humanity's first off-world colony - red, dusty, frontier.

Three buildings the player can visit on the first iteration:

  * ``spaceport`` - no NPC; ships for sale inside.
  * ``bar``       - the Mars Barkeep (override of the global ``barkeep``
                    id). Char + flavor are Mars-flavoured so the
                    same ``barkeep`` npc_id reads differently here
                    than on Earth without touching the global
                    :class:`spacehack.npc.NPCS` catalog.
  * ``militia``   - the Mars Patrol (override of the global
                    ``militia_captain`` id). Same pattern as the
                    bar override.

Missions are still tagged via ``giver_npc_id`` - a future-iteration
mission tagged ``barkeep`` would be offered by the Mars Barkeep on
Mars (NPC lookup resolves to the planet-local override) and by the
Earth Bartender when the player accepts the same mission on Earth.
That cross-planet mission life-cycle is future work; this iteration
just adds the data layer so adding new planets is one module away.
"""
from __future__ import annotations

from ... import world
from ... import npc as npc_module
from . import PlanetSpec


# Mars colour palette: red dust, rusty dirt, warm orange accents —
# the frontier feel of a young colony.
MARS_THEME = world.PlanetTheme(
    grass=world.Tile(kind="grass", char="\u2588", walkable=True, fg=(180, 80, 50), bg=(60, 30, 20)),
    grass_accent=world.Tile(kind="grass", char=",", walkable=True, fg=(140, 60, 35), bg=(60, 30, 20)),
    plaza=world.Tile(kind="plaza", char="\u2591", walkable=True, fg=(200, 150, 100), bg=(140, 100, 65)),
    sidewalk=world.Tile(kind="sidewalk", char="\u2592", walkable=True, fg=(120, 70, 50), bg=(55, 35, 22)),
    road_surface=world.Tile(kind="road", char=".", walkable=True, fg=(110, 70, 50), bg=(42, 28, 20)),
    road_ns=world.Tile(kind="road", char=":", walkable=True, fg=(90, 55, 40), bg=(35, 22, 18)),
    road_ew=world.Tile(kind="road", char="-", walkable=True, fg=(90, 55, 40), bg=(35, 22, 18)),
    landing_pad=world.Tile(kind="landing_pad", char="O", walkable=True, fg=(200, 130, 50), bg=(50, 30, 15)),
    neon=world.Tile(kind="neon", char="*", walkable=True, fg=(255, 180, 60), bg=(50, 25, 10)),
    tree=world.Tile(kind="tree", char="\u2663", walkable=True, fg=(160, 100, 50), bg=(50, 30, 15)),
    decor=world.Tile(kind="plaza", char="\u2666", walkable=True, fg=(255, 120, 60), bg=(140, 100, 65)),
)


SPEC = PlanetSpec(
    theme=MARS_THEME,
    id="mars",
    name="Mars",
    char="M",
    fg=(200, 50, 50),
    description="A red, dusty world - humanity's first off-world colony.",
    width=60,
    height=40,
    hangar_anchor=world.Position(15, 17),
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
        ("scout",   3,  2),
        ("hauler",  7,  2),
        ("cruiser", 11, 4),
    ),
    # Planet-local NPC overrides: re-skin the barkeep + militia
    # captain for the red-dust frontier flavour without touching the
    # global NPCS catalog (so Earth keeps its own Bartender + Captain).
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Mars Barkeep",
                guild="bar",
                char="b",
                fg=(220, 80, 70),
                flavor_text=(
                    "The dust here dries a throat to dust. Sit, drink, "
                    "tell me what you flew in for."
                ),
            ),
        ),
        (
            "militia_captain",
            npc_module.NPC(
                id="militia_captain",
                name="Mars Patrol",
                guild="militia",
                char="P",
                fg=(180, 100, 110),
                flavor_text=(
                    "Keep your head down out there. The colony is "
                    "small, and the perimeter is wide."
                ),
            ),
        ),
    ),
)
