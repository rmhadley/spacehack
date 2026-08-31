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

TC_B_POPULATION: tuple[CityNpc, ...] = (
    # Settlers walking the spine avenue end to end.
    CityNpc("tc_settler_a", "civillian_bystander", (54, 48), wander_radius=60, move_chance=0.9),
    CityNpc("tc_settler_b", "civillian_bystander", (80, 48), wander_radius=60, move_chance=0.85),
    CityNpc("tc_settler_c", "civillian_bystander", (127, 62), wander_radius=8, move_chance=0.85),
    # Dockhands working the west apron.
    CityNpc("tc_dockhand_a", "civillian_bystander", (17, 47), wander_radius=10, move_chance=0.8),
    CityNpc("tc_dockhand_b", "civillian_bystander", (33, 55), wander_radius=10, move_chance=0.8),
    # Botanists tending the losing war against the flowerbeds.
    CityNpc("tc_botanist_a", "civillian_bystander", (54, 50), wander_radius=12, move_chance=0.85),
    CityNpc("tc_botanist_b", "civillian_bystander", (100, 77), wander_radius=8, move_chance=0.85),
    # Colonial rangers patrolling the clearing -- a lawful frontier.
    CityNpc("tc_ranger_a", "militia_trooper", (22, 44), wander_radius=14, move_chance=0.85),
    CityNpc("tc_ranger_b", "militia_trooper", (118, 49), wander_radius=14, move_chance=0.85),
)

LAL_C_POPULATION: tuple[CityNpc, ...] = (
    # Couriers thread the central container lanes between the four services.
    CityNpc("lalc_lane_courier_a", "civillian_bystander", (35, 26), wander_radius=55, move_chance=0.9),
    CityNpc("lalc_lane_courier_b", "civillian_bystander", (68, 26), wander_radius=55, move_chance=0.85),
    CityNpc("lalc_lane_courier_c", "civillian_bystander", (35, 47), wander_radius=55, move_chance=0.9),
    # Dock hands stay near the quiet apron and upper crossing.
    CityNpc("lalc_dock_hand", "civillian_bystander", (27, 20), wander_radius=12, move_chance=0.8),
    # A market runner and warrant hunter work the lower loop.
    CityNpc("lalc_market_runner", "civillian_bystander", (60, 65), wander_radius=20, move_chance=0.85),
    CityNpc("lalc_warrant_hunter", "pirate_raider", (91, 65), wander_radius=18, move_chance=0.75),
    CityNpc("lalc_lane_watch", "militia_trooper", (68, 47), wander_radius=55, move_chance=0.8),
    CityNpc("lalc_ledger_runner", "civillian_bystander", (18, 64), wander_radius=18, move_chance=0.85),
)


INDI_B_POPULATION: tuple[CityNpc, ...] = (
    # Farmers walking the field lanes and the harvest road.
    CityNpc("indi_farmer_a", "civillian_bystander", (60, 49), wander_radius=40, move_chance=0.85),
    CityNpc("indi_farmer_b", "civillian_bystander", (100, 49), wander_radius=40, move_chance=0.85),
    CityNpc("indi_farmer_c", "civillian_bystander", (118, 72), wander_radius=10, move_chance=0.8),
    # Dockhands working the west apron.
    CityNpc("indi_dockhand_a", "civillian_bystander", (17, 50), wander_radius=10, move_chance=0.8),
    CityNpc("indi_dockhand_b", "civillian_bystander", (33, 57), wander_radius=10, move_chance=0.8),
    # Merchants around the guild hall.
    CityNpc("indi_merchant_a", "civillian_bystander", (84, 62), wander_radius=6, move_chance=0.8),
    CityNpc("indi_merchant_b", "civillian_bystander", (70, 76), wander_radius=6, move_chance=0.85),
    # Militia troopers on patrol from the east station.
    CityNpc("indi_trooper_a", "militia_trooper", (126, 58), wander_radius=12, move_chance=0.85),
    CityNpc("indi_trooper_b", "militia_trooper", (141, 66), wander_radius=12, move_chance=0.85),
    # Tavern regular outside The Harvest.
    CityNpc("indi_regular", "civillian_bystander", (84, 25), wander_radius=5, move_chance=0.8),
)

BARNARDS_C_POPULATION: tuple[CityNpc, ...] = (
    # Pad hands working the west landing apron.
    CityNpc("bnc_padhand_a", "civillian_bystander", (10, 44), wander_radius=8, move_chance=0.8),
    CityNpc("bnc_padhand_b", "civillian_bystander", (23, 52), wander_radius=8, move_chance=0.8),
    # Deck hands walking the full service spine run.
    CityNpc("bnc_deckhand_a", "civillian_bystander", (9, 30), wander_radius=90, move_chance=0.9),
    CityNpc("bnc_deckhand_b", "civillian_bystander", (101, 44), wander_radius=90, move_chance=0.85),
    # Smelter hand tending the helium-3 tank farm.
    CityNpc("bnc_smelter_hand", "civillian_bystander", (88, 46), wander_radius=10, move_chance=0.85),
    # Skimmer pilot waiting by the west inlet cradle.
    CityNpc("bnc_skimmer_pilot", "civillian_bystander", (53, 63), wander_radius=4, move_chance=0.8),
    # A regular loitering outside The Deep Freeze.
    CityNpc("bnc_bar_regular", "civillian_bystander", (99, 24), wander_radius=5, move_chance=0.8),
    # One company trooper patrolling the pad approach.
    CityNpc("bnc_company_trooper", "militia_trooper", (26, 45), wander_radius=14, move_chance=0.8),
)


PROC_B_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the west apron.
    CityNpc("procb_pad_crew_a", "civillian_bystander", (12, 31), wander_radius=6, move_chance=0.8),
    CityNpc("procb_pad_crew_b", "civillian_bystander", (20, 35), wander_radius=6, move_chance=0.8),
    # Pilots drifting between the strip and the cantina.
    CityNpc("procb_pilot_a", "civillian_bystander", (65, 44), wander_radius=5, move_chance=0.85),
    CityNpc("procb_pilot_b", "civillian_bystander", (75, 44), wander_radius=5, move_chance=0.85),
    # A mechanic working out of a strip-side shack.
    CityNpc("procb_mechanic", "civillian_bystander", (40, 37), wander_radius=8, move_chance=0.85),
    # One shady type near the cantina - the lanes get rough this deep.
    CityNpc("procb_shady", "pirate_raider", (82, 37), wander_radius=6, move_chance=0.75),
    # One security patrol walking the strip.
    CityNpc("procb_security", "militia_trooper", (50, 41), wander_radius=8, move_chance=0.85),
    # Depot hand watching the fuel yard.
    CityNpc("procb_depot_hand", "civillian_bystander", (96, 44), wander_radius=6, move_chance=0.8),
)


VEGA_B_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the landing-deck apron.
    CityNpc("vega_pad_crew", "civillian_bystander", (62, 14), wander_radius=6, move_chance=0.8),
    CityNpc("vega_pad_crew_b", "civillian_bystander", (78, 15), wander_radius=6, move_chance=0.8),
    # Reflector techs walking the maintenance lanes between the fan's rays.
    CityNpc("vega_reflector_tech_a", "civillian_bystander", (95, 39), wander_radius=8, move_chance=0.85),
    CityNpc("vega_reflector_tech_b", "civillian_bystander", (108, 50), wander_radius=8, move_chance=0.85),
    # Freight handlers crossing the exchange plaza.
    CityNpc("vega_freight_handler", "civillian_bystander", (60, 74), wander_radius=6, move_chance=0.85),
    CityNpc("vega_freight_handler_b", "civillian_bystander", (79, 74), wander_radius=6, move_chance=0.85),
    # Regulars drifting between The Veil and the observation deck.
    CityNpc("vega_cloud_host_regular", "civillian_bystander", (38, 48), wander_radius=5, move_chance=0.8),
    CityNpc("vega_cloud_regular_b", "civillian_bystander", (47, 50), wander_radius=5, move_chance=0.8),
    # Station security walking the Focus hub.
    CityNpc("vega_array_security", "militia_trooper", (66, 40), wander_radius=10, move_chance=0.85),
    # A station hand on the freight arm.
    CityNpc("vega_station_hand", "civillian_bystander", (76, 60), wander_radius=8, move_chance=0.8),
)


ROSS_C_POPULATION: tuple[CityNpc, ...] = (
    # Pad hands working the breach apron.
    CityNpc("rsc_padhand_a", "civillian_bystander", (22, 38), wander_radius=6, move_chance=0.8),
    CityNpc("rsc_padhand_b", "civillian_bystander", (29, 41), wander_radius=6, move_chance=0.8),
    # A dome tender working the settlement's southern edge.
    CityNpc("rsc_dome_tender", "civillian_bystander", (33, 40), wander_radius=12, move_chance=0.8),
    # Bazaar browsers circling the slag mound ring.
    CityNpc("rsc_browser_a", "civillian_bystander", (62, 48), wander_radius=6, move_chance=0.9),
    CityNpc("rsc_browser_b", "civillian_bystander", (52, 33), wander_radius=6, move_chance=0.85),
    CityNpc("rsc_browser_c", "civillian_bystander", (66, 32), wander_radius=6, move_chance=0.85),
    # Yard cutters working the breaker bay between the hulks.
    CityNpc("rsc_cutter_a", "civillian_bystander", (79, 33), wander_radius=6, move_chance=0.85),
    CityNpc("rsc_cutter_b", "civillian_bystander", (87, 33), wander_radius=6, move_chance=0.85),
    # A regular loitering outside The Long Burn.
    CityNpc("rsc_bar_regular", "civillian_bystander", (67, 28), wander_radius=4, move_chance=0.8),
    # One ring marshal walking the dock street.
    CityNpc("rsc_ring_marshal", "militia_trooper", (48, 36), wander_radius=10, move_chance=0.8),
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

PROC_C_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the west apron.
    CityNpc("procc_pad_crew_a", "civillian_bystander", (14, 22), wander_radius=6, move_chance=0.8),
    CityNpc("procc_pad_crew_b", "civillian_bystander", (26, 22), wander_radius=6, move_chance=0.8),
    # Researchers crossing the quad between buildings.
    CityNpc("procc_researcher_a", "civillian_bystander", (66, 48), wander_radius=8, move_chance=0.85),
    CityNpc("procc_researcher_b", "civillian_bystander", (84, 48), wander_radius=8, move_chance=0.85),
    # Drill crew tending the rig near the lab terrace.
    CityNpc("procc_drill_crew", "civillian_bystander", (94, 26), wander_radius=8, move_chance=0.85),
    # A caretaker walking the frozen channel bank.
    CityNpc("procc_channel_caretaker", "civillian_bystander", (70, 84), wander_radius=8, move_chance=0.85),
    # A regular loitering near the mess hall.
    CityNpc("procc_mess_regular", "civillian_bystander", (48, 66), wander_radius=5, move_chance=0.8),
    # One campus marshal patrolling the quad.
    CityNpc("procc_campus_marshal", "militia_trooper", (70, 40), wander_radius=12, move_chance=0.85),
)

PROC_C_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the apron west of the spaceport.
    CityNpc("procc_pad_crew_a", "civillian_bystander", (14, 22), wander_radius=6, move_chance=0.8),
    CityNpc("procc_pad_crew_b", "civillian_bystander", (28, 20), wander_radius=6, move_chance=0.8),
    # Researchers crossing the quad between the lab and the mess.
    CityNpc("procc_researcher_a", "civillian_bystander", (70, 48), wander_radius=8, move_chance=0.85),
    CityNpc("procc_researcher_b", "civillian_bystander", (82, 50), wander_radius=8, move_chance=0.85),
    # Drill crew staging gear near the lab terrace.
    CityNpc("procc_drill_crew", "civillian_bystander", (94, 26), wander_radius=8, move_chance=0.85),
    # A caretaker walking the frozen channel bank.
    CityNpc("procc_channel_caretaker", "civillian_bystander", (70, 84), wander_radius=8, move_chance=0.85),
    # A regular loitering outside the mess hall.
    CityNpc("procc_mess_regular", "civillian_bystander", (48, 66), wander_radius=5, move_chance=0.8),
    # One campus marshal patrolling the quad.
    CityNpc("procc_campus_marshal", "militia_trooper", (70, 40), wander_radius=12, move_chance=0.85),
    # A science scout camped at the cave mouth — the delve's doorman.
    CityNpc("procc_cave_scout", "civillian_bystander", (124, 28), wander_radius=3, move_chance=0.6),
)

BLOCKADE_SOUTH_POPULATION: tuple[CityNpc, ...] = (
    CityNpc("blockade_south_dockhand_a", "civillian_bystander", (28, 23), wander_radius=10, move_chance=0.8),
    CityNpc("blockade_south_dockhand_b", "civillian_bystander", (40, 32), wander_radius=20, move_chance=0.85),
    CityNpc("blockade_south_inspector", "militia_trooper", (64, 32), wander_radius=12, move_chance=0.8),
    CityNpc("blockade_south_quarantine_guard", "militia_trooper", (94, 47), wander_radius=18, move_chance=0.85),
    CityNpc("blockade_south_cargo_runner", "civillian_bystander", (105, 48), wander_radius=15, move_chance=0.8),
    CityNpc("blockade_south_claims_hunter", "civillian_bystander", (35, 64), wander_radius=8, move_chance=0.8),
    CityNpc("blockade_south_watch_trooper", "militia_trooper", (100, 60), wander_radius=20, move_chance=0.8),
    CityNpc("blockade_south_maintenance_hand", "civillian_bystander", (120, 38), wander_radius=10, move_chance=0.75),
)


AC1_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the west apron.
    CityNpc("ac1_pad_crew_a", "civillian_bystander", (12, 24), wander_radius=6, move_chance=0.8),
    CityNpc("ac1_pad_crew_b", "civillian_bystander", (20, 23), wander_radius=6, move_chance=0.8),
    # Prospectors walking the avenue end to end.
    CityNpc("ac1_prospector_a", "civillian_bystander", (30, 34), wander_radius=40, move_chance=0.9),
    CityNpc("ac1_prospector_b", "civillian_bystander", (65, 34), wander_radius=40, move_chance=0.85),
    # Claim-stakers browsing the south field.
    CityNpc("ac1_staker_a", "civillian_bystander", (35, 50), wander_radius=8, move_chance=0.85),
    CityNpc("ac1_staker_b", "civillian_bystander", (60, 55), wander_radius=8, move_chance=0.8),
    # A regular loitering outside The Claim.
    CityNpc("ac1_bar_regular", "civillian_bystander", (72, 50), wander_radius=4, move_chance=0.8),
    # One dusty claim-jumper near the shacks - the frontier gets rough.
    CityNpc("ac1_claim_jumper", "pirate_raider", (50, 20), wander_radius=6, move_chance=0.75),
)

AC2_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the icy landing bay.
    CityNpc("ac2_pad_crew_a", "civillian_bystander", (12, 24), wander_radius=6, move_chance=0.8),
    CityNpc("ac2_pad_crew_b", "civillian_bystander", (20, 23), wander_radius=6, move_chance=0.8),
    # Researchers crossing the campus quad between the port and lab.
    CityNpc("ac2_researcher_a", "civillian_bystander", (50, 25), wander_radius=10, move_chance=0.85),
    CityNpc("ac2_researcher_b", "civillian_bystander", (55, 22), wander_radius=10, move_chance=0.9),
    # A lab tech walking the spine from the port to the quad.
    CityNpc("ac2_lab_tech", "civillian_bystander", (45, 20), wander_radius=20, move_chance=0.85),
    # A caretaker walking the frozen channel bank.
    CityNpc("ac2_channel_caretaker", "civillian_bystander", (70, 55), wander_radius=8, move_chance=0.85),
    # One campus marshal patrolling the quad.
    CityNpc("ac2_campus_marshal", "militia_trooper", (52, 27), wander_radius=12, move_chance=0.85),
)

AC3_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the landing deck.
    CityNpc("ac3_pad_crew_a", "civillian_bystander", (12, 24), wander_radius=6, move_chance=0.8),
    CityNpc("ac3_pad_crew_b", "civillian_bystander", (20, 23), wander_radius=6, move_chance=0.8),
    # Refinery workers walking the concourse end to end.
    CityNpc("ac3_worker_a", "civillian_bystander", (30, 34), wander_radius=40, move_chance=0.9),
    CityNpc("ac3_worker_b", "civillian_bystander", (60, 34), wander_radius=40, move_chance=0.85),
    # Tank farm hands tending the fuel tanks.
    CityNpc("ac3_tank_hand_a", "civillian_bystander", (40, 50), wander_radius=8, move_chance=0.8),
    CityNpc("ac3_tank_hand_b", "civillian_bystander", (55, 50), wander_radius=8, move_chance=0.8),
    # A regular loitering outside The Ring Band.
    CityNpc("ac3_bar_regular", "civillian_bystander", (65, 50), wander_radius=4, move_chance=0.8),
    # One refinery marshal patrolling the concourse.
    CityNpc("ac3_refinery_marshal", "militia_trooper", (50, 30), wander_radius=12, move_chance=0.85),
)

SIRIUS_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the landing bay.
    CityNpc("sirius_pad_crew_a", "civillian_bystander", (12, 24), wander_radius=6, move_chance=0.8),
    CityNpc("sirius_pad_crew_b", "civillian_bystander", (20, 23), wander_radius=6, move_chance=0.8),
    # Researchers crossing the observation terrace.
    CityNpc("sirius_researcher_a", "civillian_bystander", (50, 25), wander_radius=10, move_chance=0.85),
    CityNpc("sirius_researcher_b", "civillian_bystander", (55, 22), wander_radius=10, move_chance=0.9),
    # A tech walking the promenade end to end.
    CityNpc("sirius_tech", "civillian_bystander", (30, 34), wander_radius=30, move_chance=0.85),
    # A collector tender working the south hull arrays.
    CityNpc("sirius_collector_hand", "civillian_bystander", (70, 50), wander_radius=15, move_chance=0.8),
    # One station marshal patrolling the promenade.
    CityNpc("sirius_station_marshal", "militia_trooper", (40, 34), wander_radius=12, move_chance=0.85),
)

DEPOT_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the landing bay.
    CityNpc("depot_pad_crew_a", "civillian_bystander", (12, 24), wander_radius=6, move_chance=0.8),
    CityNpc("depot_pad_crew_b", "civillian_bystander", (20, 23), wander_radius=6, move_chance=0.8),
    # Freight handlers walking the Freightway end to end.
    CityNpc("depot_handler_a", "civillian_bystander", (30, 34), wander_radius=40, move_chance=0.9),
    CityNpc("depot_handler_b", "civillian_bystander", (60, 34), wander_radius=40, move_chance=0.85),
    # Container stackers tending the cargo yard.
    CityNpc("depot_stacker_a", "civillian_bystander", (20, 52), wander_radius=8, move_chance=0.8),
    CityNpc("depot_stacker_b", "civillian_bystander", (40, 52), wander_radius=8, move_chance=0.8),
    # A hauler pilot loitering outside the fuel depot.
    CityNpc("depot_pilot", "civillian_bystander", (70, 50), wander_radius=4, move_chance=0.8),
    # One yard marshal patrolling the Freightway.
    CityNpc("depot_yard_marshal", "militia_trooper", (45, 34), wander_radius=12, move_chance=0.85),
)

BLOCKADE_NORTH_POPULATION: tuple[CityNpc, ...] = (
    CityNpc("blockade_north_dockhand", "civillian_bystander", (28, 23), wander_radius=10, move_chance=0.8),
    CityNpc("blockade_north_courier", "civillian_bystander", (42, 34), wander_radius=20, move_chance=0.85),
    CityNpc("blockade_north_inspector", "militia_trooper", (57, 34), wander_radius=12, move_chance=0.8),
    CityNpc("blockade_north_quarantine_guard", "militia_trooper", (64, 47), wander_radius=18, move_chance=0.85),
    CityNpc("blockade_north_claims_hunter", "civillian_bystander", (35, 50), wander_radius=8, move_chance=0.8),
    CityNpc("blockade_north_watch_trooper", "militia_trooper", (45, 34), wander_radius=20, move_chance=0.8),
    CityNpc("blockade_north_maintenance_hand", "civillian_bystander", (80, 32), wander_radius=10, move_chance=0.75),
)

VENUS_POPULATION: tuple[CityNpc, ...] = (
    # Pad crew working the landing deck apron.
    CityNpc("venus_pad_crew_a", "civillian_bystander", (14, 22), wander_radius=6, move_chance=0.8),
    CityNpc("venus_pad_crew_b", "civillian_bystander", (26, 21), wander_radius=6, move_chance=0.8),
    # Commuters crossing the Promenade between the districts.
    CityNpc("venus_commuter_a", "civillian_bystander", (40, 33), wander_radius=8, move_chance=0.9),
    CityNpc("venus_commuter_b", "civillian_bystander", (90, 33), wander_radius=8, move_chance=0.85),
    # A regular at The Cross, watching the beacon.
    CityNpc("venus_cross_regular", "civillian_bystander", (84, 42), wander_radius=4, move_chance=0.8),
    # A Cloudbreak regular loitering on the west spur.
    CityNpc("venus_cloudbreak_regular", "civillian_bystander", (28, 68), wander_radius=4, move_chance=0.8),
    # A browser outside the exchange hall.
    CityNpc("venus_merchants_browser", "civillian_bystander", (107, 68), wander_radius=5, move_chance=0.85),
    # A stores hand walking the depot lane behind the exchange.
    CityNpc("venus_depot_hand", "civillian_bystander", (94, 83), wander_radius=5, move_chance=0.85),
    # One city marshal patrolling the spine from the plaza south.
    CityNpc("venus_city_marshal", "militia_trooper", (81, 56), wander_radius=12, move_chance=0.85),
)

__all__ = ["CityNpc", "EARTH_POPULATION", "WOLF_B_POPULATION", "CYGNI_B_POPULATION", "LAL_B_POPULATION", "LAL_C_POPULATION", "BARNARDS_POPULATION", "BARNARDS_C_POPULATION", "ROSS_C_POPULATION", "VEGA_B_POPULATION", "ROSS_B_POPULATION", "GROOM_B_POPULATION", "TC_B_POPULATION", "INDI_B_POPULATION", "PROC_B_POPULATION", "PROC_C_POPULATION", "BLOCKADE_SOUTH_POPULATION", "VENUS_POPULATION", "AC1_POPULATION", "AC2_POPULATION", "AC3_POPULATION", "SIRIUS_POPULATION", "DEPOT_POPULATION", "BLOCKADE_NORTH_POPULATION"]
