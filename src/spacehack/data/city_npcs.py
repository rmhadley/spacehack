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

AC_RING_POPULATION: tuple[CityNpc, ...] = (
    # Dock crew and researchers circulate between the four ring sectors.
    CityNpc("ac_dock_crew", "civillian_bystander", (60, 24), wander_radius=55, move_chance=0.9),
    CityNpc("ac_archive_tech", "civillian_bystander", (84, 23), wander_radius=55, move_chance=0.85),
    CityNpc("ac_lab_tech", "civillian_bystander", (88, 55), wander_radius=55, move_chance=0.9),
    CityNpc("ac_commons_visitor", "civillian_bystander", (107, 40), wander_radius=55, move_chance=0.85),
    CityNpc("ac_observation_guard", "militia_trooper", (13, 40), wander_radius=55, move_chance=0.8),
    CityNpc("ac_hub_coordinator", "civillian_bystander", (60, 44), wander_radius=55, move_chance=0.9),
)


ERI_B_POPULATION: tuple[CityNpc, ...] = (
    # Cargo movement on the west plateau and freight crossing.
    CityNpc("eri_pad_loader", "civillian_bystander", (38, 38), wander_radius=110, move_chance=0.9),
    CityNpc("eri_freight_runner", "civillian_bystander", (83, 62), wander_radius=110, move_chance=0.9),
    # Social traffic at the canyon overlook and beacon spine.
    CityNpc("eri_bar_regular", "civillian_bystander", (80, 76), wander_radius=110, move_chance=0.85),
    CityNpc("eri_beacon_courier", "civillian_bystander", (70, 47), wander_radius=110, move_chance=0.9),
    # Frontier security patrols on the eastern approach.
    CityNpc("eri_gate_patrol", "militia_trooper", (143, 96), wander_radius=110, move_chance=0.9),
    CityNpc("eri_bridge_guard", "militia_trooper", (110, 79), wander_radius=110, move_chance=0.85),
    # Surveyors working the southern terraces.
    CityNpc("eri_surveyor_a", "civillian_bystander", (58, 119), wander_radius=110, move_chance=0.8),
    CityNpc("eri_surveyor_b", "civillian_bystander", (128, 125), wander_radius=110, move_chance=0.8),
)


MARS_POPULATION: tuple[CityNpc, ...] = (
    # Market square — colonists crossing the plaza.
    CityNpc("mars_colonist_a", "civillian_bystander", (64, 35), wander_radius=80, move_chance=0.9),
    CityNpc("mars_colonist_b", "civillian_bystander", (71, 42), wander_radius=80, move_chance=0.9),
    CityNpc("mars_colonist_c", "civillian_bystander", (74, 46), wander_radius=80, move_chance=0.85),
    # Entertainment district — patrons move along the north boulevard.
    CityNpc("mars_bar_patron", "civillian_bystander", (116, 22), wander_radius=80, move_chance=0.85),
    CityNpc("mars_bar_patron_b", "civillian_bystander", (115, 21), wander_radius=80, move_chance=0.85),
    # Spaceport apron — dock workers on the logistics boulevard.
    CityNpc("mars_pad_worker", "civillian_bystander", (14, 89), wander_radius=80, move_chance=0.8),
    CityNpc("mars_pad_worker_b", "civillian_bystander", (21, 93), wander_radius=80, move_chance=0.8),
    # Security district — troopers walking the east avenue.
    CityNpc("mars_militia_patrol", "militia_trooper", (127, 73), wander_radius=80, move_chance=0.9),
    CityNpc("mars_militia_patrol_b", "militia_trooper", (130, 73), wander_radius=80, move_chance=0.9),
    # Civic services — a hunter checking the board.
    CityNpc("mars_bounty_hunter", "civillian_bystander", (83, 38), wander_radius=80, move_chance=0.85),
)


WOLF_B_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew — loitering near the landing pad.
    CityNpc("wolf_pad_crew", "civillian_bystander", (36, 26), wander_radius=90, move_chance=0.8),
    CityNpc("wolf_rigger", "civillian_bystander", (46, 26), wander_radius=90, move_chance=0.85),
    # Scavenger traffic between the pad and depot.
    CityNpc("wolf_scavenger", "civillian_bystander", (50, 26), wander_radius=90, move_chance=0.9),
    # Pirates outside the Salty Grave.
    CityNpc("wolf_bar_guard", "pirate_raider", (20, 62), wander_radius=90, move_chance=0.75),
    CityNpc("wolf_bar_regular", "civillian_bystander", (30, 62), wander_radius=90, move_chance=0.8),
    # Smuggler's Row — static vendors on stalls (wander_radius=0 holds position).
    CityNpc("wolf_vendor_scrap", "civillian_bystander", (8, 68), wander_radius=0, move_chance=0),
    CityNpc("wolf_vendor_arms", "pirate_raider", (17, 68), wander_radius=0, move_chance=0),
    CityNpc("wolf_vendor_gear", "civillian_bystander", (29, 68), wander_radius=0, move_chance=0),
    CityNpc("wolf_vendor_bits", "civillian_bystander", (35, 62), wander_radius=0, move_chance=0),
    # Customers flowing through the market aisles.
    CityNpc("wolf_market_cust_a", "civillian_bystander", (12, 65), wander_radius=4, move_chance=0.9),
    CityNpc("wolf_market_cust_b", "pirate_raider", (28, 65), wander_radius=4, move_chance=0.85),
    CityNpc("wolf_market_cust_c", "civillian_bystander", (18, 65), wander_radius=4, move_chance=0.9),
)


CYGNI_B_POPULATION: tuple[CityNpc, ...] = (
    # Port pad crew.
    CityNpc("cygni_pad_crew", "civillian_bystander", (42, 22), wander_radius=90, move_chance=0.8),
    # Yard workers on the forge-yard floor.
    CityNpc("cygni_yard_a", "civillian_bystander", (58, 12), wander_radius=6, move_chance=0.85),
    CityNpc("cygni_yard_b", "civillian_bystander", (58, 22), wander_radius=6, move_chance=0.9),
    CityNpc("cygni_yard_c", "civillian_bystander", (58, 34), wander_radius=6, move_chance=0.85),
    CityNpc("cygni_yard_d", "civillian_bystander", (58, 54), wander_radius=6, move_chance=0.9),
    CityNpc("cygni_yard_e", "civillian_bystander", (58, 62), wander_radius=6, move_chance=0.85),
    CityNpc("cygni_yard_f", "civillian_bystander", (158, 26), wander_radius=6, move_chance=0.9),
    # Dock market shoppers (browsing between stalls).
    CityNpc("cygni_market_a", "civillian_bystander", (36, 54), wander_radius=4, move_chance=0.9),
    CityNpc("cygni_market_b", "civillian_bystander", (48, 54), wander_radius=4, move_chance=0.85),
    # Militia trooper outside the station house.
    CityNpc("cygni_trooper", "militia_trooper", (134, 86), wander_radius=90, move_chance=0.75),
)




LAL_B_POPULATION: tuple[CityNpc, ...] = (
    # Salvage crew working the yard.
    CityNpc("lal_salvager_a", "civillian_bystander", (20, 24), wander_radius=8, move_chance=0.85),
    CityNpc("lal_salvager_b", "civillian_bystander", (100, 44), wander_radius=8, move_chance=0.9),
    CityNpc("lal_salvager_c", "civillian_bystander", (78, 48), wander_radius=8, move_chance=0.85),
    # Bounty hunters near the board.
    CityNpc("lal_hunter_a", "militia_trooper", (15, 83), wander_radius=6, move_chance=0.8),
    CityNpc("lal_hunter_b", "civillian_bystander", (20, 70), wander_radius=6, move_chance=0.85),
    # Pad crew.
    CityNpc("lal_pad_crew", "civillian_bystander", (39, 12), wander_radius=90, move_chance=0.8),
    CityNpc("lal_yard_hand", "civillian_bystander", (112, 76), wander_radius=90, move_chance=0.85),
)


BARNARDS_POPULATION: tuple[CityNpc, ...] = (
    # Miners trudging along the outer and mid rings.
    CityNpc("barnards_miner_a", "civillian_bystander", (40, 23), wander_radius=10, move_chance=0.85),
    CityNpc("barnards_miner_b", "civillian_bystander", (73, 62), wander_radius=10, move_chance=0.85),
    CityNpc("barnards_miner_c", "civillian_bystander", (23, 58), wander_radius=10, move_chance=0.85),
    # Cantina loiterers near The Ember (mid ring, bar door at 21,49).
    CityNpc("barnards_loiter_a", "civillian_bystander", (20, 22), wander_radius=6, move_chance=0.8),
    CityNpc("barnards_loiter_b", "civillian_bystander", (22, 24), wander_radius=6, move_chance=0.8),
    # Pad crew on the landing deck.
    CityNpc("barnards_pad_crew", "civillian_bystander", (56, 46), wander_radius=8, move_chance=0.8),
)

GROOM_B_POPULATION: tuple[CityNpc, ...] = (
    # Prospectors trudging the ore-haul road end to end.
    CityNpc("groom_prospector_a", "civillian_bystander", (30, 40), wander_radius=90, move_chance=0.9),
    CityNpc("groom_prospector_b", "civillian_bystander", (76, 40), wander_radius=90, move_chance=0.85),
    CityNpc("groom_prospector_c", "civillian_bystander", (103, 40), wander_radius=90, move_chance=0.85),
    # Pad crew on the landing apron.
    CityNpc("groom_pad_crew_a", "civillian_bystander", (13, 33), wander_radius=8, move_chance=0.8),
    CityNpc("groom_pad_crew_b", "civillian_bystander", (22, 32), wander_radius=8, move_chance=0.8),
    # Loiterers outside The Last Gate -- one of them is bad news.
    CityNpc("groom_bar_regular", "civillian_bystander", (54, 25), wander_radius=5, move_chance=0.8),
    CityNpc("groom_gate_shade", "pirate_raider", (64, 26), wander_radius=6, move_chance=0.75),
    # Bounty hunters waiting on the office steps.
    CityNpc("groom_hunter_a", "militia_trooper", (43, 60), wander_radius=6, move_chance=0.8),
    CityNpc("groom_hunter_b", "civillian_bystander", (53, 60), wander_radius=6, move_chance=0.8),
    # Depot hand watching the last fuel stop before the gate.
    CityNpc("groom_depot_hand", "civillian_bystander", (102, 60), wander_radius=6, move_chance=0.8),
)

ROSS_B_POPULATION: tuple[CityNpc, ...] = (
    # Pirates near the bar (NE zone, y=1..9).
    CityNpc("ross_pirate_a", "civillian_bystander", (94, 12), wander_radius=6, move_chance=0.8),
    CityNpc("ross_pirate_b", "civillian_bystander", (106, 14), wander_radius=6, move_chance=0.85),
    CityNpc("ross_pirate_c", "civillian_bystander", (92, 16), wander_radius=6, move_chance=0.8),
    # Workers in the central zone (between channels).
    CityNpc("ross_worker_a", "civillian_bystander", (40, 32), wander_radius=10, move_chance=0.9),
    CityNpc("ross_worker_b", "civillian_bystander", (50, 44), wander_radius=10, move_chance=0.85),
    CityNpc("ross_worker_c", "civillian_bystander", (60, 36), wander_radius=10, move_chance=0.85),
    # Bounty hunters near the SW office.
    CityNpc("ross_hunter_a", "militia_trooper", (14, 52), wander_radius=6, move_chance=0.8),
    CityNpc("ross_hunter_b", "civillian_bystander", (22, 54), wander_radius=6, move_chance=0.85),
    # Pad crew on the landing platform.
    CityNpc("ross_pad_crew", "civillian_bystander", (15, 18), wander_radius=90, move_chance=0.8),
    # Depot operator (SE zone).
    CityNpc("ross_depot_hand", "civillian_bystander", (100, 54), wander_radius=6, move_chance=0.8),
)

__all__ = ["CityNpc", "EARTH_POPULATION", "WOLF_B_POPULATION", "CYGNI_B_POPULATION", "LAL_B_POPULATION", "BARNARDS_POPULATION", "ROSS_B_POPULATION", "GROOM_B_POPULATION"]
