"""Space combat engine — turn-based ship-to-ship battles.

Refactored from a single ``combat.py`` (1951 lines) into a package
with one sub-module per domain:

* ``_types.py`` — data types (CombatPhase, CombatMode, EnemyInstance)
* ``_stats.py`` — pure stat calculations (hull, hit/flee chance, init)
* ``_actions.py`` — action resolution (damage, turns, movement)
* ``_animations.py`` — visual effects (laser shots, explosions)
* ``_loop.py`` — main combat turn loop (run_combat)
* ``_encounter.py`` — encounter wrapper + death screen

Re-exports all public symbols so ``from . import combat`` and
``combat._handle_combat_encounter(...)`` continue to work after
the migration from a single-file module to a package.
"""

from ._types import CombatPhase, CombatMode, EnemyInstance
from ._stats import (
    _calc_hull, _calc_max_hull, _calc_hull_for_enemy,
    _calc_power_gen, _calc_max_shields,
    _calc_ap, _calc_dodge_bonus, _distance,
    calc_hit_chance, calc_flee_chance,
    init_combat_state,
)
from ._actions import (
    can_afford_action,
    resolve_damage,
    start_player_turn,
    start_enemy_turn,
    move_entity,
    _sync_back_hull,
)
from ._animations import (
    _responsive_sleep,
    _bresenham_line,
    _COMBAT_EXPLOSION_RINGS,
    _resolve_target,
    _paint_target_highlight,
    _paint_range_line,
    _render_anim_frame,
    _animate_laser_shot,
    _animate_explosion,
)
from ._loop import run_combat
from ._encounter import _handle_combat_encounter, _render_death_screen
