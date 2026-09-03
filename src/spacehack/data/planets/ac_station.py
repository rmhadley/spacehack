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
from .themes import RING_STATION
from ..city_npcs import AC_RING_POPULATION


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
    theme=RING_STATION,
    id="ac_station",
    name="Science Port",
    char="#",
    fg=(150, 200, 220),
    description=(
        "A close-orbit research outpost around Proxima Centauri - "
        "long-baseline stellar studies and a quiet dock for science crews."
    ),
    width=120,
    height=80,
    hangar_anchor=world.Position(60, 22),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=52, x_hi=67, y_lo=10, y_hi=18,
            door_x=58, npc_id="",
        ),
        world.CityBuilding(
            label="archive",
            x_lo=73, x_hi=86, y_lo=15, y_hi=21,
            door_x=79, npc_id="archive_research_officer",
        ),
        world.CityBuilding(
            label="lab",
            x_lo=73, x_hi=86, y_lo=53, y_hi=60,
            door_x=77, npc_id="research_officer",
        ),
        world.CityBuilding(
            label="commons",
            x_lo=92, x_hi=103, y_lo=35, y_hi=41,
            door_x=95, npc_id="",
        ),
        world.CityBuilding(
            label="observation",
            x_lo=16, x_hi=27, y_lo=35, y_hi=41,
            door_x=19, npc_id="",
        ),
    ),
    city_layout_id="ac_ring_station",
    city_npc_population=AC_RING_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="spaceport",
            pos=world.Position(56, 19), serves="ac_ring_spaceport",
            destinations=("archive", "lab", "commons", "observation"),
        ),
        world.TransitStation(
            id="archive", name="Archive Vault", district="archive",
            pos=world.Position(82, 24), serves="ac_ring_archive",
            destinations=("spaceport", "lab", "commons", "observation"),
        ),
        world.TransitStation(
            id="lab", name="Analysis Lab", district="analysis",
            pos=world.Position(75, 65), serves="ac_ring_lab",
            destinations=("spaceport", "archive", "commons", "observation"),
        ),
        world.TransitStation(
            id="commons", name="Crew Commons", district="commons",
            pos=world.Position(94, 43), serves="ac_ring_commons",
            destinations=("spaceport", "archive", "lab", "observation"),
        ),
        world.TransitStation(
            id="observation", name="Observation Deck", district="observation",
            pos=world.Position(18, 43), serves="ac_ring_observation",
            destinations=("spaceport", "archive", "lab", "commons"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "ac_ring_spaceport_interior"),
        ("archive", "ac_ring_archive_interior"),
        ("lab", "ac_ring_lab_interior"),
        ("commons", "ac_ring_commons_interior"),
        ("observation", "ac_ring_observation_interior"),
    ),
    showroom_ships=(
        ("scout", 1, 1),
        ("hauler", 9, 1),
    ),
    # The archive gets the officer needed by the post-prison research
    # step; the lab building's research_officer slot resolves through
    # the global catalog.
    npc_overrides=(
        ("archive_research_officer", _RESEARCH_OFFICER),
    ),
    # The Act 0 xenolinguist stands in the lab (additively) only while
    # lab_q4_xenolinguist is live — seated in the archive interior on entry.
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
