"""Science Port — Alpha Centauri's research station interior.

A small orbital-station interior the player lands on when they bump
the Science Port station (see
:class:`spacehack.data.solar_systems.alpha_centauri._stations`).
Reuses the city's :func:`spacehack.data.planets.load_planet`
loader (mirrors Earth/Mars) so the rendering / movement / NPC
interaction code doesn't need a separate "station interior" code
path — players dock here exactly the way they dock on a planet city.

Layout (60x40 city grid, smaller than Earth + Mars but with the
same shape so the player isn't disoriented):

  * ``spaceport`` building, NW corner, with two showroom ships +
    the player's owned-shp hangar anchor just south of it.
  * ``lab`` building, NE corner, with a ``research_officer`` NPC
    — the science flavour + future mission giver for research
    quests. New NPC id lives in :data:`spacehack.data.npcs.NPCS`.

The station is intentionally compact (vs. Earth/Mars which carry
four civic buildings each) — sci-port shouldn't feel like a small
city, it should feel like a small station with one lab + one
landing bay.

Why not a separate ``StationInterior`` data class? — Because the
existing :class:`PlanetSpec` shape already captures everything
needed (id, name, char, fg, description, width, height,
hangar_anchor, buildings, showroom_ships). A station is "a PlanetSpec
without an in-space body" — and we can always introduce a dedicated
class later if the station semantics genuinely diverge (e.g. station
modules panel, station-only quest flow).
"""
from __future__ import annotations

from ... import world
from . import PlanetSpec
from .themes import STATION


SPEC = PlanetSpec(
    theme=STATION,
    id="ac_station",
    name="Science Port",
    char="#",
    fg=(150, 200, 220),                            # cool steel-blue to match the station glyph.
    description=(
        "A close-orbit research outpost around Proxima Centauri - "
        "long-baseline stellar studies and a quiet dock for science crews."
    ),
    width=40,                                       # smaller than Earth/Mars (60x40).
    height=24,
    hangar_anchor=world.Position(7, 14),           # just south of the spaceport building.
    buildings=(
        # Hangar / showroom for new arrivals.
        world.CityBuilding(
            label="spaceport",
            x_lo=2,  x_hi=15, y_lo=2,  y_hi=10,
            door_x=8, npc_id="",
        ),
        # Research lab with the science officer.
        world.CityBuilding(
            label="lab",
            x_lo=22, x_hi=37, y_lo=8,  y_hi=18,
            door_x=29, npc_id="research_officer",
        ),
    ),
    showroom_ships=(
        # Two ships for science-vessel flavour (a Scout + the bigger Hauler
        # for cargo runs between the lab and Proxima).
        ("scout",  3, 2),
        ("hauler", 7, 4),
    ),
    npc_overrides=(),        # reuse the global NPCS catalog for research_officer.
)
