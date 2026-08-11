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

from ._ship_buy import ShipBuyOutcome, _run_ship_buy
from ._missions import (
    MissionOutcome, _run_mission_offerings,
)
from ._quest_log import QuestLogOutcome, render_quest_log, _run_quest_log
from ._ship_menu import (
    ShipMenuAction, _run_ship_menu, _find_hangar_ship,
)
from ._mechanic import _run_mech_menu
from ._armory import _run_armory_menu
from ._planet import PlanetMenuOutcome, _run_planet_menu
