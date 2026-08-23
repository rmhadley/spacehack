"""Ambient city NPC catalog — pedestrian/guard/pedlar templates that make
Earth's streets feel inhabited.

Each :class:`CityNpc` is a frozen convenience binding over an existing
ground NPC character (:class:`~spacehack.data.npc_chars.NpcCharSpec`, the
source of faction + combat data) and an existing guild NPC
(:class:`~spacehack.data.npcs.NPC`, the source of the named talk persona
where one exists). Adding a new ambient NPC is one entry in the
:data:`EARTH_POPULATION` tuple — no dispatcher rewrites.

The runtime (``spacehack.city_npcs``) reads these to place, move, and
interact with the NPCs on the rebuilt city map. Hostility flows through
``faction.spec_is_hostile`` via ``npc_char_id``, talk through the guild
NPC's flavor text, and direct-contact combat through the existing ground
combat entry point.

``wander_radius`` caps how far a citizen roams from its anchor — the
Earth population uses a city-spanning radius so everyone walks the whole
city like ships cross a system. ``move_chance`` is the probability of
stepping on a given city tick — space traffic uses ~0.8, so busy
pedestrians sit high.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CityNpc:
    """One ambient NPC template for a city population.

    Attributes:
        id: stable catalog key (also the save/load identity).
        npc_char_id: ``NpcCharSpec.id`` — drives char/fg/name fallback,
            faction hostility, and direct-contact combat stats.
        npc_id: optional ``data.npcs.NPC.id`` — when set, ``name`` and
            talk flavor come from the named guild persona; otherwise the
            char-spec name is used.
        spawn: ``(x, y)`` anchor on the city map (walkable pavement).
        wander_radius: how far the NPC wanders from its anchor (0 = hold).
        move_chance: probability per city tick of taking a step (0-1).
    """
    id: str
    npc_char_id: str
    spawn: tuple[int, int]
    npc_id: str = ""
    wander_radius: int = 80
    move_chance: float = 0.8


# Earth's ambient population. NPCs are placed on the road-adjacent
# pavement (sidewalk/plaza/landing pad) exactly like the transit stops,
# so they read as pedestrians moving along the curbs. Anchors were chosen
# by inspecting the rebuilt Earth map and verifying each cell is walkable,
# clear of doors, and within peopled districts.
#
# Every citizen roams the whole city (radius 80 = city-spanning): they
# pick landmarks across the entire map and walk between districts like
# ships traverse a system. Anchors double as save/load identity and the
# spawn point, but do NOT confine movement to a district.
EARTH_POPULATION: tuple[CityNpc, ...] = (
    # Civic plaza / central hub — a security guard on the beat.
    CityNpc("earth_hub_guard", "militia_trooper", (72, 55), wander_radius=80, move_chance=0.9),
    # Market district — pedestrians crossing the market street.
    CityNpc("earth_market_walker_a", "civillian_bystander", (20, 76), wander_radius=80, move_chance=0.9),
    CityNpc("earth_market_walker_b", "civillian_bystander", (26, 77), wander_radius=80, move_chance=0.9),
    CityNpc("earth_market_walker_c", "civillian_bystander", (24, 74), wander_radius=80, move_chance=0.9),
    # Waterfront / bar district.
    CityNpc("earth_bar_patron", "civillian_bystander", (114, 17), wander_radius=80, move_chance=0.85),
    CityNpc("earth_bar_patron_b", "civillian_bystander", (118, 17), wander_radius=80, move_chance=0.85),
    # Spaceport apron — dock workers crossing the apron.
    CityNpc("earth_pad_worker", "civillian_bystander", (31, 25), wander_radius=80, move_chance=0.8),
    CityNpc("earth_pad_worker_b", "civillian_bystander", (27, 23), wander_radius=80, move_chance=0.8),
    # Militia district — troopers walking the beat.
    CityNpc("earth_militia_patrol", "militia_trooper", (65, 77), wander_radius=80, move_chance=0.9),
    CityNpc("earth_militia_patrol_b", "militia_trooper", (60, 77), wander_radius=80, move_chance=0.9),
)

MERCURY_POPULATION: tuple[CityNpc, ...] = (
    # Station crew — techs crossing the deck between the port and lab.
    # The 100x70 map lets roamers traverse the full base.
    CityNpc("mercury_tech_a", "civillian_bystander", (40, 19), wander_radius=50, move_chance=0.9),
    CityNpc("mercury_tech_b", "civillian_bystander", (50, 21), wander_radius=50, move_chance=0.9),
    CityNpc("mercury_lab_hand", "civillian_bystander", (80, 20), wander_radius=50, move_chance=0.85),
    # Station security — one trooper on the pad apron.
    CityNpc("mercury_pad_guard", "militia_trooper", (3, 12), wander_radius=50, move_chance=0.9),
)

MARS_POPULATION: tuple[CityNpc, ...] = (
    # Market square — colonists crossing the plaza.
    CityNpc("mars_colonist_a", "civillian_bystander", (80, 35), wander_radius=80, move_chance=0.9),
    CityNpc("mars_colonist_b", "civillian_bystander", (88, 39), wander_radius=80, move_chance=0.9),
    CityNpc("mars_colonist_c", "civillian_bystander", (82, 41), wander_radius=80, move_chance=0.85),
    # Bar district — patrons near the cantina.
    CityNpc("mars_bar_patron", "civillian_bystander", (116, 17), wander_radius=80, move_chance=0.85),
    CityNpc("mars_bar_patron_b", "civillian_bystander", (122, 19), wander_radius=80, move_chance=0.85),
    # Spaceport apron — dock workers.
    CityNpc("mars_pad_worker", "civillian_bystander", (28, 24), wander_radius=80, move_chance=0.8),
    CityNpc("mars_pad_worker_b", "civillian_bystander", (32, 26), wander_radius=80, move_chance=0.8),
    # Militia patrol — troopers walking the beat.
    CityNpc("mars_militia_patrol", "militia_trooper", (65, 82), wander_radius=80, move_chance=0.9),
    CityNpc("mars_militia_patrol_b", "militia_trooper", (130, 82), wander_radius=80, move_chance=0.9),
    # Bounty board — a hunter checking the board.
    CityNpc("mars_bounty_hunter", "civillian_bystander", (70, 58), wander_radius=80, move_chance=0.85),
)


__all__ = ["CityNpc", "EARTH_POPULATION"]
