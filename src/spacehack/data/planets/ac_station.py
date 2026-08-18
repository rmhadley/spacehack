"""Science Port - Alpha Centauri's research station interior.

The station uses the normal PlanetSpec city loader. It has a landing bay, an
archive lab for the post-prison Research Officer, and a lab building whose
regular research officer resolves through the global catalog. The Act 0
Xenolinguist stands in the lab ADDITIVELY (``quest_npc_spots``) while the lab
chain needs her (the dataset delivery), then leaves.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import STATION


_RESEARCH_OFFICER = npc_module.NPC(
    id="research_officer",
    name="Research Officer",
    guild="lab",
    char="S",
    fg=(150, 220, 200),
    flavor_text=(
        "Long-baseline stellar studies, mostly. Every so often the data "
        "asks us a question - that is when the pay gets interesting."
    ),
)

SPEC = PlanetSpec(
    theme=STATION,
    id="ac_station",
    name="Science Port",
    char="#",
    fg=(150, 200, 220),
    description=(
        "A close-orbit research outpost around Proxima Centauri - "
        "long-baseline stellar studies and a quiet dock for science crews."
    ),
    width=40,
    height=24,
    hangar_anchor=world.Position(7, 14),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=2, x_hi=15, y_lo=2, y_hi=10,
            door_x=8, npc_id="",
        ),
        world.CityBuilding(
            label="archive",
            x_lo=22, x_hi=37, y_lo=2, y_hi=6,
            door_x=29, npc_id="archive_research_officer",
        ),
        world.CityBuilding(
            label="lab",
            x_lo=22, x_hi=37, y_lo=8, y_hi=18,
            door_x=29, npc_id="research_officer",
        ),
    ),
    showroom_ships=(
        ("scout", 3, 2),
        ("hauler", 7, 4),
    ),
    # The archive gets the officer needed by the post-prison research
    # step; the lab building's research_officer slot resolves through
    # the global catalog.
    npc_overrides=(
        ("archive_research_officer", _RESEARCH_OFFICER),
    ),
    # The Act 0 xenolinguist stands in the lab (additively) only while
    # lab_q4_xenolinguist is live — see spawn_quest_npcs.
    quest_npc_spots=(
        ("xenolinguist", "lab"),
    ),
    produces=(
        ("research_data", 20),
    ),
    demands=(
        ("food_rations", 15),
        ("medical_supplies", 10),
        ("electronics", 10),
    ),
    tech_level=2,
    mission_tier=2,
)
