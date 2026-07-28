"""Menu screens extracted from the old ``menus.py`` into a package.

Each sub-module owns one menu domain:

* ``_ship_buy.py`` — ship-buy dialog
* ``_missions.py`` — mission offerings screen
* ``_quest_log.py`` — quest log overlay
* ``_ship_menu.py`` — hangar ship menu (View Cargo / Launch)
* ``_mechanic.py`` — mechanic terminal (Refuel, Repair, Loadout)
* ``_loadout.py`` — loadout management split-screen modal
* ``_planet.py`` — planet-bump dialog

Re-exports all public symbols so ``from .menus import ...`` continues to
work after the migration from a single-file module to a package.
"""

from ._ship_buy import ShipBuyOutcome, render_ship_buy, update_ship_buy, _run_ship_buy
from ._missions import (
    MissionOutcome, _offerings_to_menu, render_mission_offerings,
    update_mission_offerings, _mission_navigate, _run_mission_offerings,
)
from ._quest_log import QuestLogOutcome, render_quest_log, update_quest_log, _run_quest_log
from ._ship_menu import (
    ShipMenuAction, SHIP_MENU_OPTIONS, render_ship_menu,
    _ship_menu_navigate, update_ship_menu, _run_ship_menu, _find_hangar_ship,
)
from ._mechanic import _run_mech_menu
from ._planet import PlanetMenuOutcome, render_planet_menu, update_planet_menu, _run_planet_menu
