"""Lalande 21185 c — Whisper, the vault moon.

The Requiem's manifest listed a sister ship carrying archives and
military surplus — "Cargo of Record." Nothing was ever found. The
smugglers who run this moon claim the manifest was the lie: the
Record vault always belonged to them, and the Requiem just gave
everyone an excuse to stop looking.

Whatever the truth, Whisper is where the deep arm's secrets surface
for a price. Weapons that never got registered, research data
nobody was supposed to see, pharmaceuticals that skipped every
inspection. People here talk in low voices, keep their hoods up,
and remember that the Tollkeeper watches the only way out.

Layout (60x40), built dark and tight:

  * spaceport, NW corner.
  * bar, NE corner — "The Hush" speakeasy.
  * merchant hall, SW — the Ledger, straight into the dark.
  * bounties, SE — turned-around marks never go home well.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import derive_theme


# The Vault palette — near-black deck, pale ash surface, cold violet
# neon so the whole settlement reads 'lit by screens, not by sun'.
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
            label="bounties",  x_lo=34, x_hi=55, y_lo=26, y_hi=35,
            door_x=44, npc_id="bounty_master",
            door_north=True,
        ),
    ),
    showroom_ships=(
        ("hauler",   7, 2),
        ("cruiser",  11, 4),
        ("frigate",  15, 2),
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