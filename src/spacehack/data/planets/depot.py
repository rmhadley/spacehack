"""Depot — generic deep-space refueling station interior.

Used by Epsilon Eridani and Tau Ceti refueling depots, and by
Luyten's Star Blockade Station (via NPC overrides). Small
(40x24) station interior with a spaceport and a depot-attendant
room — mirrors the Science Port layout so the player's navigation
muscle memory works across all station interiors.

Planet-specific NPC overrides (``PlanetSpec.npc_overrides``)
customize the attendant's flavour text per-station.
"""
from __future__ import annotations

from ... import world
from . import PlanetSpec


# Warm industrial palette: steel deck plates, amber lights,
# worn-metal walls — reads as a utilitarian refueling stop
# rather than a sleek research outpost.
DEPOT_THEME = world.PlanetTheme(
    floor=world.Tile(
        kind="floor", char="\u2591", walkable=True,
        fg=(200, 200, 180), bg=(70, 65, 50),
    ),
)


SPEC = PlanetSpec(
    theme=DEPOT_THEME,
    id="depot",
    name="Refueling Depot",
    char="#",
    fg=(200, 200, 180),
    description="A deep-space refueling station.",
    width=40,
    height=24,
    hangar_anchor=world.Position(7, 14),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=2, x_hi=15, y_lo=2, y_hi=10,
            door_x=8, npc_id="",
        ),
        world.CityBuilding(
            label="depot", x_lo=22, x_hi=37, y_lo=8, y_hi=18,
            door_x=29, npc_id="depot_attendant",
        ),
    ),
    showroom_ships=(
        ("scout", 3, 2),
        ("hauler", 7, 4),
    ),
    npc_overrides=(),
    produces=(
        ("fuel_cells", 25),
        ("machine_parts", 15),
    ),
    demands=(
        ("food_rations", 10),
        ("electronics", 8),
    ),
    trade_npc_id="depot_attendant",
)
