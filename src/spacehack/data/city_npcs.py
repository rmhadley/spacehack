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
    wander_radius: int = 2
    move_chance: float = 0.5


# Earth's ambient population. NPCs are placed on the road-adjacent
# pavement (sidewalk/plaza/landing pad) exactly like the transit stops,
# so they read as pedestrians moving along the curbs. Anchors were chosen
# by inspecting the rebuilt Earth map and verifying each cell is walkable,
# clear of doors, and within peopled districts.
EARTH_POPULATION: tuple[CityNpc, ...] = (
    # Civic plaza / central hub — a security guard holds his post.
    CityNpc("earth_hub_guard", "militia_trooper", (72, 55), wander_radius=1, move_chance=0.2),
    # Market district — a couple of civilian pedestrians.
    CityNpc("earth_market_walker_a", "civillian_bystander", (20, 76), wander_radius=4, move_chance=0.8),
    CityNpc("earth_market_walker_b", "civillian_bystander", (26, 77), wander_radius=4, move_chance=0.8),
    # Waterfront / bar district.
    CityNpc("earth_bar_patron", "civillian_bystander", (114, 17), wander_radius=3, move_chance=0.7),
    # Spaceport apron — a dock worker loitering near the pad.
    CityNpc("earth_pad_worker", "civillian_bystander", (31, 25), wander_radius=3, move_chance=0.5),
    # Militia district — a patrol trooper.
    CityNpc("earth_militia_patrol", "militia_trooper", (65, 77), wander_radius=3, move_chance=0.4),
)


__all__ = ["CityNpc", "EARTH_POPULATION"]
