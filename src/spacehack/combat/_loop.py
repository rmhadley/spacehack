"""Main combat loop — the turn-by-turn run_combat orchestrator.

:func:`run_combat` — unified loop taking a ``rules`` module
for flavor-specific behavior. Works for both space and ground.

Callers in ``__main__.py`` and ``_encounter.py`` hand off control
here and receive a ``CombatResult`` back.
"""

from __future__ import annotations

from typing import Any

import tcod.console
import tcod.context
import tcod.event

from .. import ui
from .. import world
from ..engine import RNG
from ..data.pilot_skills import PilotSkills
from ..input_helpers import _try_open_guide

from ._ai import _run_enemy_turn
from ._weapons import _fire_weapons
from ._actions import (
    start_player_turn,
    move_entity,
    _sync_back_hull,
)
from ._types import EnemyInstance, CombatResult
from ._stats import (
    init_combat_state,
    calc_hit_chance,
    calc_flee_chance,
    _calc_dodge_bonus,
    _distance,
)
from ._animations import (
    _resolve_target,
    _paint_target_highlight,
    _paint_range_line,
)



# ---------------------------------------------------------------------------
# Shared helpers + unified loop
# ---------------------------------------------------------------------------

# Vim movement deltas — same for space and ground.
_VIM_KEYS: dict[str, tuple[int, int]] = {
    "h": (-1, 0), "j": (0, 1), "k": (0, -1), "l": (1, 0),
    "y": (-1, -1), "u": (1, -1), "b": (-1, 1), "n": (1, 1),
}

# Numeric key mapping for weapon toggle (1-9, numpad 1-9).
_NUM_KEYS: dict[str, int] = {
    "n1": 0, "n2": 1, "n3": 2, "n4": 3, "n5": 4,
    "n6": 5, "n7": 6, "n8": 7, "n9": 8,
    "kp_1": 0, "kp_2": 1, "kp_3": 2, "kp_4": 3, "kp_5": 4,
    "kp_6": 5, "kp_7": 6, "kp_8": 7, "kp_9": 8,
}


# Shared helpers — called by the unified loop, not by rules modules.

def _cycle_target(target_idx: int, n_enemies: int, direction: int = 1) -> int:
    """Cycle target_idx forward (+1) or backward (-1).

    Only cycles if there are multiple enemies; returns unchanged
    index otherwise.
    """
    if n_enemies <= 1:
        return target_idx
    return (target_idx + direction) % n_enemies


def _toggle_weapon(
    idx: int, active_weapons: list[bool], ctx, rules,
) -> list[bool]:
    """Toggle weapon at idx on/off. Returns updated list."""
    if 0 <= idx < len(active_weapons):
        active_weapons[idx] = not active_weapons[idx]
        rules.set_active_weapons(ctx, active_weapons)
        _weapons = rules.player_weapons(ctx)
        _state = "ON" if active_weapons[idx] else "OFF"
        if idx < len(_weapons):
            from ..data.weapons import find_weapon as _fw
            try:
                _name = _fw(_weapons[idx]).name
            except KeyError:
                _name = _weapons[idx]
            ctx.log.add(f"Weapon {idx + 1} ({_name}): {_state}")
    return active_weapons


def _handle_fire(console, ctx, game_map, rules, target_idx: int) -> bool:
    """Fire all active weapons at the current target.

    Iterates active weapons, animates each shot, applies hit/miss
    and damage, checks for kill. Returns ``True`` if the target
    died (caller should check victory).

    Uses only ``rules.*`` functions — works identically for space
    and ground combat.
    """
    from .. import message_log as _ml
    from ..data.weapons import find_weapon as _fw

    _weapons = rules.player_weapons(ctx)
    _active = rules.active_weapons(ctx)
    _fire_ids = [
        _weapons[i] for i in range(len(_weapons))
        if i < len(_active) and _active[i]
    ]
    if not _fire_ids:
        ctx.log.add("No active weapons to fire.")
        return False

    _enemies = rules.get_enemies(ctx)
    if target_idx >= len(_enemies) or not rules.enemy_alive(_enemies[target_idx]):
        ctx.log.add("No valid target.")
        return False
    _target = _enemies[target_idx]

    _player_pos = ctx.player.pos

    for _wid in _fire_ids:
        if not rules.enemy_alive(_target):
            break

        _ok, _reason = rules.can_fire(_wid, ctx)
        if not _ok:
            try:
                _wname = _fw(_wid).name
            except KeyError:
                _wname = _wid
            ctx.log.add(f"{_wname}: {_reason}")
            continue

        _hit = RNG.randint(1, 100) <= rules.hit_chance(_wid, _target, ctx)

        rules.animate_fire(
            console, ctx, game_map,
            _player_pos, rules.enemy_pos(_target),
            is_hit=_hit,
        )

        try:
            _wname = _fw(_wid).name
        except KeyError:
            _wname = _wid

        if _hit:
            _dmg = rules.damage(_wid, _target, ctx)
            ctx.log.add_colored(
                f"{_wname} hits {rules.enemy_name(_target)} for {_dmg}!",
                _ml.COLOR_PLAYER_ACTION,
            )
            if not rules.enemy_alive(_target):
                ctx.log.add_colored(
                    f"{rules.enemy_name(_target)} destroyed!",
                    _ml.COLOR_COMBAT_EVENT,
                )
                rules.on_kill(game_map, _target, ctx)
                return True
        else:
            ctx.log.add_colored(
                f"{_wname} misses {rules.enemy_name(_target)}!",
                _ml.COLOR_PLAYER_ACTION,
            )

        rules.consume_shot(_wid, ctx)

    return False


def _resolve_flee(ctx, rules, flee_attempts: list[int]) -> str | None:
    """Attempt to flee combat. Returns "FLEE" on success, None on failure.

    On failure, zeroes the player's AP so the enemy turn triggers.
    """
    from .. import message_log as _ml
    _chance = rules.flee_chance(ctx)
    if RNG.randint(1, 100) <= _chance:
        ctx.log.add("You fled!")
        if hasattr(ctx, 'player_counters'):
            ctx.player_counters.combat_flees += 1
        return "FLEE"
    else:
        flee_attempts[0] += 1
        ctx.log.add_colored(
            f"Flee failed! ({_chance}% chance)",
            _ml.COLOR_ENEMY_ACTION,
        )
        # Force end of turn by zeroing AP
        return None


def _end_turn(ctx, game_map, rules) -> str | None:
    """Run enemy turns + reinforcements. Returns "DEFEAT" if player
    died, ``None`` otherwise."""
    _dmg = rules.run_enemy_turns(ctx, game_map)
    if _dmg >= 999:  # signal: player death
        rules.on_player_death(ctx)
        return "DEFEAT"

    rules.check_reinforcements(ctx, game_map)
    return None


def run_combat(
    console,
    ctx,
    game_map: world.GameMap,
    rules,
) -> CombatResult:
    """Unified turn-based combat loop — space or ground.

    The caller MUST have called ``rules.init(...)`` before calling
    this function. The loop owns turn structure, AP management, key
    dispatch, weapon fire orchestration, and victory/flee/death
    resolution. Everything flavor-specific is delegated to ``rules``.

    Args:
        console: tcod console for rendering.
        ctx: GameContext with all session state.
        game_map: the current GameMap.
        rules: a module exporting the combat rules contract
            (e.g. ``_rules_space`` or ``_rules_ground``).

    Returns:
        A :class:`CombatResult` with ``outcome`` (``"VICTORY"``,
        ``"DEFEAT"``, or ``"FLEE"``) and tracking of defeated
        enemies.
    """
    from .. import message_log as _ml
    from ..input_helpers import _try_open_guide

    _flee_attempts: list[int] = [0]
    _target_idx: int = 0
    _turn: int = 1
    _result: str | None = None

    # Initial combat log
    _enemies = rules.get_enemies(ctx)
    if _enemies:
        ctx.log.add_colored(
            f"Combat starts! {len(_enemies)} enemy(s): "
            + ", ".join(rules.enemy_name(e) for e in _enemies),
            _ml.COLOR_COMBAT_EVENT,
        )

    while True:
        # ---- Victory check ----
        _enemies = rules.get_enemies(ctx)
        if not _enemies:
            _result = "VICTORY"
            break

        # ---- Re-target if current target is dead ----
        if _target_idx >= len(_enemies) or not rules.enemy_alive(_enemies[_target_idx]):
            _target_idx = 0

        # ---- Render ----
        rules.render_frame(console, ctx, game_map)
        ctx.context.present(console)

        # ---- Wait for input ----
        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                _result = "FLEE"
                break
            if not isinstance(event, tcod.event.KeyDown):
                continue

            if _try_open_guide(event, ctx):
                continue

            sym_name: str = getattr(event.sym, "name", "").lower()
            sym = event.sym

            # [Tab] / [Left] / [Right] -> Cycle target
            if sym_name in ("tab", "left", "right"):
                _dir = -1 if sym_name == "left" else 1
                _target_idx = _cycle_target(_target_idx, len(_enemies), _dir)
                break

            # Vim movement
            if sym_name in _VIM_KEYS and rules.player_ap(ctx) > 0:
                _dx, _dy = _VIM_KEYS[sym_name]
                _moved = rules.try_move(ctx, game_map, _dx, _dy)
                if not _moved:
                    ctx.log.add("Blocked.")
                break

            # [s] -> Defense toggle (shields in space, no-op in ground)
            if sym_name == "s":
                rules.handle_defense(ctx)
                break

            # [w] -> End player turn
            if sym_name == "w":
                # Force AP to 0 so end-turn guard triggers
                break  # break out of event loop; AP check below handles it

            # [f] -> Fire ALL active weapons
            if sym_name == "f":
                _handle_fire(console, ctx, game_map, rules, _target_idx)
                break

            # [1]–[9] -> Toggle weapon on/off
            if sym_name in _NUM_KEYS:
                _idx = _NUM_KEYS[sym_name]
                _active = rules.active_weapons(ctx)
                _active = _toggle_weapon(_idx, _active, ctx, rules)
                break

            # ESC -> Flee
            if sym in ui._ESCAPE_SYMS:
                _flee_result = _resolve_flee(ctx, rules, _flee_attempts)
                if _flee_result == "FLEE":
                    _result = "FLEE"
                    break
                # Failed flee — zero AP so enemy gets their turn
                rules.set_player_ap(ctx, 0)
                break

        if _result is not None:
            break

        # ---- End-turn guard: if AP ≤ 0, run enemy turns ----
        if rules.player_ap(ctx) <= 0:
            _end_result = _end_turn(ctx, game_map, rules)
            if _end_result == "DEFEAT":
                _result = "DEFEAT"
                break
            _turn += 1
            rules.reset_turn(ctx)

    # ---- Sync state back ----
    rules.sync_state(ctx)

    # ---- Build result ----
    if hasattr(rules, 'get_combat_result'):
        _cr = rules.get_combat_result()
    else:
        _cr = CombatResult()
    _cr.outcome = _result or "FLEE"
    return _cr

