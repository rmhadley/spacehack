"""Lalande 21185 c — Whisper, the vault moon.

Whisper is a smuggler depot assembled from sealed freight containers. New
stacks were added wherever there was room until the settlement became a
tight maze: a quiet landing apron feeds a three-lane public grid, with two
crossings and short spurs to the Hush, the Ledger, and the warrant office.
The containers are the architecture; the lanes are the city.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from ..city_npcs import LAL_C_POPULATION
from . import PlanetSpec
from .themes import derive_theme


VAULT = derive_theme(
    floor=(120, 120, 140),
    grass=(60, 66, 92),
    accent=(200, 180, 255),
)


SPEC = PlanetSpec(
    theme=VAULT,
    id="lal_c",
    name="Whisper",
    char="p",
    fg=(90, 100, 140),
    description="The Vault - a smuggler moon where nothing is asked and everything is priced.",
    width=100,
    height=70,
    hangar_anchor=world.Position(17, 20),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=5, x_hi=28, y_lo=4, y_hi=12,
            door_x=17, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=72, x_hi=92, y_lo=5, y_hi=12,
            door_x=82, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants",
            x_lo=5, x_hi=25, y_lo=53, y_hi=60,
            door_x=15, npc_id="guild_master",
        ),
        world.CityBuilding(
            label="bounties",
            x_lo=73, x_hi=87, y_lo=52, y_hi=62,
            door_x=80, npc_id="bounty_master",
        ),
    ),
    city_layout_id="lalc_container_maze",
    city_npc_population=LAL_C_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing apron",
            pos=world.Position(15, 14), serves="lalc_spaceport",
            destinations=("hush", "ledger", "bounties"),
        ),
        world.TransitStation(
            id="hush", name="The Hush", district="upper container row",
            pos=world.Position(79, 14), serves="lalc_bar",
            destinations=("spaceport", "ledger", "bounties"),
        ),
        world.TransitStation(
            id="ledger", name="The Ledger", district="lower west loop",
            pos=world.Position(13, 62), serves="lalc_merchants",
            destinations=("spaceport", "hush", "bounties"),
        ),
        world.TransitStation(
            id="bounties", name="Warrant Office", district="lower east loop",
            pos=world.Position(80, 61), serves="bounties",
            destinations=("spaceport", "hush", "ledger"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "lalc_spaceport_interior"),
        ("bar", "lalc_bar_interior"),
        ("merchants", "lalc_merchants_interior"),
        ("bounties", "lalc_bounties_interior"),
    ),
    showroom_ships=(
        ("hauler", -5, -4),
        ("cruiser", 0, -5),
        ("frigate", 5, -4),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Veiled Registrar",
                guild="bar",
                char="b",
                fg=(190, 180, 255),
                flavor_text=(
                    "Ask for nothing by name, and nothing leaves a "
                    "paper trail. That's the whole law here."
                ),
            ),
        ),
        (
            "guild_master",
            npc_module.NPC(
                id="guild_master",
                name="The Ledger",
                guild="merchants",
                char="g",
                fg=(170, 160, 230),
                flavor_text=(
                    "The Vault keeps two books: what you bring, and "
                    "what you never mention. Both are profitable."
                ),
            ),
        ),
        (
            "bounty_master",
            npc_module.NPC(
                id="bounty_master",
                name="Warrant Clerk",
                guild="bhguild",
                char="B",
                fg=(220, 200, 255),
                flavor_text=(
                    "Some warrants die out here, ignored. Others just "
                    "get... reposted. Credit's real either way."
                ),
            ),
        ),
    ),
    produces=(
        ("weapons_blackmarket", 14),
        ("research_data", 16),
        ("pharmaceuticals", 10),
    ),
    demands=(
        ("food_rations", 12),
        ("fuel_cells", 14),
    ),
    tech_level=4,
    mission_tier=4,
)
