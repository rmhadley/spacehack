"""Navigation, jump, and space-map helpers.

This module is now a re-export hub. The implementation lives in focused
sibling modules (each under the 1,000-line architecture limit):

* :mod:`spacehack.navigation_render` — NAVIGATION overlay + AOI panel.
* :mod:`spacehack.navigation_spawns` — bounty / intercept spawn placement.
* :mod:`spacehack.navigation_combat` — combat encounter detection + auto-comms.
* :mod:`spacehack.navigation_scan` — militia cargo-scan exposure/confiscation.
* :mod:`spacehack.navigation_travel` — GO TO, jump gate, jump animation,
  system transition, and the responsive-sleep animation primitive.

Existing callers keep ``from .navigation import ...`` — every name below is
re-exported so the public surface is unchanged.
"""

from __future__ import annotations

from .navigation_combat import (
    _calc_flee_chance,
    _check_auto_comms_warning,
    _detect_combat_encounter,
    _militia_scan_chance,
)
from .navigation_render import (
    _render_aoi_panel,
    render_navigation,
    NAV_SHIP_FG,
)
from .navigation_scan import (
    _apply_scan_confiscation,
    _compute_scan_exposure,
    _fail_smuggle_mission,
    _militia_scan_target,
    _run_cargo_scan,
    _run_space_cargo_scan,
)
from .navigation_spawns import (
    _add_bounty_spawns_to_map,
    _bounty_leader_entity,
    _nearest_body_name,
    _pick_bounty_spawn_pos,
    _remove_bounty_spawn,
)
from .navigation_travel import (
    GotoOutcome,
    JumpMenuOutcome,
    NavigationOutcome,
    _JUMP_FRAME_S,
    _JUMP_RING_CHARS,
    _animate_jump,
    _jump_to_system,
    _responsive_sleep,
    _run_goto,
    _run_jump_menu,
    _run_navigation,
    _run_pygame_goto_menu,
    _run_pygame_jump_menu,
)

__all__ = [
    "GotoOutcome",
    "JumpMenuOutcome",
    "NavigationOutcome",
    "NAV_SHIP_FG",
    "_JUMP_FRAME_S",
    "_JUMP_RING_CHARS",
    "_add_bounty_spawns_to_map",
    "_animate_jump",
    "_apply_scan_confiscation",
    "_bounty_leader_entity",
    "_calc_flee_chance",
    "_check_auto_comms_warning",
    "_compute_scan_exposure",
    "_detect_combat_encounter",
    "_fail_smuggle_mission",
    "_jump_to_system",
    "_militia_scan_chance",
    "_militia_scan_target",
    "_nearest_body_name",
    "_pick_bounty_spawn_pos",
    "_remove_bounty_spawn",
    "_render_aoi_panel",
    "_responsive_sleep",
    "_run_cargo_scan",
    "_run_goto",
    "_run_jump_menu",
    "_run_navigation",
    "_run_pygame_goto_menu",
    "_run_pygame_jump_menu",
    "_run_space_cargo_scan",
    "render_navigation",
]
