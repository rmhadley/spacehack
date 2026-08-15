"""Main combat loop — the turn-by-turn run_combat orchestrator.

:func:`run_combat` — unified loop taking a ``rules`` module
for flavor-specific behavior. Works for both space and ground.

Callers in ``__main__.py`` and ``_encounter.py`` hand off control
here and receive a ``CombatResult`` back.
"""

from __future__ import annotations

from .. import pygame_engine
from .. import world
from ..engine import RNG
from ..world import MOVE_KEYS as _MOVE_KEYS
from ..data.weapons import find_weapon as _fw
from ..input_helpers import _try_open_guide
from ..saveload import delete_save as _delete_save

from . import _rules_ground
from ._types import CombatResult
from ._messages import player_attack_line as _player_attack_line
from ._animations import (
    _damage_popup_for,
    _present,
)


def _combat_action(ctx, console, *, presenter) -> str:
    """Render one interactive combat frame and return its opaque action."""
    from .. import pygame_combat, pygame_runtime

    if presenter is None:
        if not pygame_runtime.is_shared_context(getattr(ctx, "context", None)):
            raise pygame_combat.PygameCombatUnavailable(
                "Combat requires the shared Pygame runtime"
            )
        while True:
            for event in ctx.context.wait_events():
                if pygame_engine.is_quit(event):
                    return "QUIT"
                if not pygame_engine.is_keydown(event):
                    continue
                if _try_open_guide(event, ctx):
                    break
                return _input_action(event)
    try:
        presenter.show(console, interactive=True, ctx=ctx)
        return presenter.wait_action()
    except pygame_combat.PygameCombatQuit:
        return "QUIT"
    except pygame_combat.PygameCombatUnavailable:
        return "UNAVAILABLE"


def _input_action(event: pygame_engine.PygameInputEvent) -> str:
    """Translate a project input event to opaque combat action IDs."""
    sym_name = event.key_name.lower()
    if sym_name == "tab":
        return "TARGET"
    if sym_name in {"backslash", "nonusbackslash", "\\"}:
        return "HISTORY"
    if sym_name in _MOVE_KEYS:
        return f"MOVE:{sym_name}"
    if sym_name in {".", "period"}:
        return "WAIT"
    return {
        "s": "DEFENSE",
        "w": "WAIT",
        "f": "FIRE",
        "r": "RELOAD",
        "c": "CHARACTER",
        "v": "TOGGLE_CARD",
    }.get(sym_name, f"WEAPON:{_NUM_KEYS[sym_name]}" if sym_name in _NUM_KEYS else "")



# ---------------------------------------------------------------------------
# Shared helpers + unified loop
# ---------------------------------------------------------------------------

# Numeric key mapping for weapon toggle — top-row 1-9 only. The
# shared Pygame runtime reports these as plain "1".."9"; the old
# tcod-era "n1".."n9" names no longer arrive. Numpad keys are
# movement now (see world.MOVE_KEYS), so they must NOT double as
# weapon toggles.
_NUM_KEYS: dict[str, int] = {
    "1": 0, "2": 1, "3": 2, "4": 3, "5": 4,
    "6": 5, "7": 6, "8": 7, "9": 8,
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
            try:
                _name = rules.weapon_name(_weapons[idx], ctx)
            except KeyError:
                _name = _weapons[idx]
            ctx.log.add(f"Weapon {idx + 1} ({_name}): {_state}")
    return active_weapons


def _handle_character_action(ctx, rules) -> int:
    """Open ground equipment management and charge successful swaps."""
    if rules is not _rules_ground:
        ctx.log.add("The character screen is unavailable here.")
        return 0
    from ..character_screen import open_character_screen

    swaps = open_character_screen(
        ctx,
        equipment_management=True,
        in_ground_combat=True,
    )
    for _ in range(swaps):
        rules.set_player_ap(ctx, rules.player_ap(ctx) - 1)
    refresh = getattr(rules, "refresh_equipment_state", None)
    if refresh is not None:
        refresh(ctx)
    return swaps


def _fire_slot_indexes(weapons: list, active: list) -> list[int]:
    """Return slot indexes the player has left active, by slot not weapon id."""
    return [i for i in range(len(weapons)) if i < len(active) and active[i]]


def _resolve_shot_damage(rules, ctx, wid, target, hit: bool):
    """Resolve a hit into ``(dmg, stripped, is_strip, is_glancing, popup)``.

    A miss returns zeroed values. Ground enemies have no shields field;
    ``getattr`` keeps the strip check safe across both combat modes.
    """
    if not hit:
        return 0, 0, False, False, None
    _pre_shields = getattr(target, 'shields', 0)
    _dmg, _is_glancing = rules.damage(wid, target, ctx)
    _stripped = max(0, _pre_shields - getattr(target, 'shields', 0))
    _is_strip = False
    if _stripped > 0:
        try:
            _is_strip = _fw(wid).shield_strip > 0
        except KeyError:
            pass
    _popup = _damage_popup_for(_dmg, _stripped, _is_strip, glancing=_is_glancing)
    return _dmg, _stripped, _is_strip, _is_glancing, _popup


def _fire_weapon(console, ctx, game_map, rules, slot: int, target, player_pos) -> tuple[bool, int]:
    """Fire one weapon slot; return ``(hit, ap_cost)`` — 0 if it could not fire."""
    from .. import message_log as _ml

    _wid = rules.player_weapons(ctx)[slot]
    _ok, _reason = rules.can_fire(slot, ctx)
    try:
        _wname = rules.weapon_name(_wid, ctx)
    except KeyError:
        _wname = _wid
    if not _ok:
        ctx.log.add(f"{_wname}: {_reason}")
        return False, 0
    if _reason:
        ctx.log.add(_reason)
    _hit = RNG.randint(1, 100) <= rules.hit_chance(_wid, target, ctx)
    _dmg, _stripped, _is_strip, _is_glancing, _popup = _resolve_shot_damage(
        rules, ctx, _wid, target, _hit,
    )
    rules.animate_fire(
        console, ctx, game_map, player_pos, rules.enemy_pos(target),
        is_hit=_hit, damage=_popup, weapon_id=_wid,
    )
    if _hit:
        ctx.log.add_colored(
            _player_attack_line(
                _wid, _wname, rules.enemy_name(target),
                hit=True, hull_dmg=_dmg, shield_dmg=_stripped,
                is_strip=_is_strip, is_glancing=_is_glancing,
            ),
            _ml.COLOR_PLAYER_ACTION,
        )
    else:
        ctx.log.add_colored(
            _player_attack_line(_wid, _wname, rules.enemy_name(target), hit=False),
            _ml.COLOR_PLAYER_ACTION,
        )
    rules.consume_shot(slot, ctx)
    return _hit, rules.weapon_ap_cost(_wid, ctx)


def _log_explosive_result(
    ctx, rules, weapon_id: str, weapon_name: str, target,
    enemy_hits: tuple, player_damage: int, *, primary_hit: bool = True,
) -> None:
    """Log primary, splash, and friendly-fire results for one blast."""
    from .. import message_log as _ml

    _primary_damage = next(
        (_dmg for _enemy, _dmg, _primary in enemy_hits if _primary),
        0,
    )
    ctx.log.add_colored(
        _player_attack_line(
            weapon_id, weapon_name, rules.enemy_name(target),
            hit=primary_hit, hull_dmg=_primary_damage if primary_hit else 0,
        ),
        _ml.COLOR_PLAYER_ACTION,
    )
    for _enemy, _dmg, _primary in enemy_hits:
        if not _primary:
            ctx.log.add_colored(
                f"{weapon_name} blast hits {_enemy.name} for {_dmg} damage.",
                _ml.COLOR_PLAYER_ACTION,
            )
    if player_damage > 0:
        ctx.log.add_colored(
            f"The {weapon_name.lower()} blast catches you for {player_damage} damage!",
            _ml.COLOR_COMBAT_EVENT,
        )


def _process_explosive_kills(ctx, game_map, rules, enemy_hits: tuple) -> None:
    """Run normal loot/XP handling for every enemy killed by a blast."""
    from .. import message_log as _ml

    for _enemy, _dmg, _primary in enemy_hits:
        if rules.enemy_alive(_enemy):
            continue
        ctx.log.add_colored(
            f"{rules.enemy_name(_enemy)} destroyed!",
            _ml.COLOR_COMBAT_EVENT,
        )
        rules.on_kill(game_map, _enemy, ctx)


def _fire_explosive_weapon(
    console, ctx, game_map, rules, slot: int, target, player_pos,
) -> tuple[bool, int]:
    """Fire one explosive weapon and resolve its full friendly-fire blast."""
    _wid = rules.player_weapons(ctx)[slot]
    _ok, _reason = rules.can_fire(slot, ctx)
    _wname = rules.weapon_name(_wid, ctx)
    if not _ok:
        ctx.log.add(f"{_wname}: {_reason}")
        return False, 0
    if _reason:
        ctx.log.add(_reason)
    _hit = RNG.randint(1, 100) <= rules.hit_chance(_wid, target, ctx)
    _enemy_hits, _player_damage = rules.explosive_blast(
        _wid, target, ctx, primary_hit=_hit,
    )
    _primary_damage = next(
        (_dmg for _enemy, _dmg, _primary in _enemy_hits if _primary),
        0,
    )
    _popup = _damage_popup_for(_primary_damage, 0, False)
    rules.animate_fire(
        console, ctx, game_map, player_pos, rules.enemy_pos(target),
        is_hit=_hit, damage=_popup, weapon_id=_wid,
    )
    if _hit or _enemy_hits or _player_damage:
        _log_explosive_result(
            ctx, rules, _wid, _wname, target, _enemy_hits, _player_damage,
            primary_hit=_hit,
        )
        _process_explosive_kills(ctx, game_map, rules, _enemy_hits)
    else:
        from .. import message_log as _ml
        ctx.log.add_colored(
            _player_attack_line(_wid, _wname, rules.enemy_name(target), hit=False),
            _ml.COLOR_PLAYER_ACTION,
        )
    rules.consume_shot(slot, ctx)
    return _hit, rules.weapon_ap_cost(_wid, ctx)


def _fire_active_slot(
    console, ctx, game_map, rules, slot: int, target, player_pos,
) -> tuple[bool, int, bool]:
    """Fire one active slot and report whether it handled its own kills."""
    _wid = rules.player_weapons(ctx)[slot]
    _is_explosive = getattr(
        rules, "is_explosive", lambda _weapon_id: False,
    )(_wid)
    if _is_explosive:
        _hit, _ap_cost = _fire_explosive_weapon(
            console, ctx, game_map, rules, slot, target, player_pos,
        )
    else:
        _hit, _ap_cost = _fire_weapon(
            console, ctx, game_map, rules, slot, target, player_pos,
        )
    return _hit, _ap_cost, _is_explosive and not rules.enemy_alive(target)


def _handle_fire(console, ctx, game_map, rules, target_idx: int) -> bool:
    """Fire all active weapons; return True if the primary target died."""
    _fire_slots = _fire_slot_indexes(rules.player_weapons(ctx), rules.active_weapons(ctx))
    if not _fire_slots:
        ctx.log.add("No active weapons to fire.")
        return False
    _enemies = rules.get_enemies(ctx)
    if target_idx >= len(_enemies) or not rules.enemy_alive(_enemies[target_idx]):
        ctx.log.add("No valid target.")
        return False
    _target = _enemies[target_idx]
    _player_pos = ctx.player.pos
    # Burst-fire: pay max(ap_cost) once, consume ammo per weapon; a killing
    # burst still costs its full AP (kill handling sits after the deduction).
    _max_ap_cost = 0
    _any_hit = False
    _explosive_target_handled = False
    for _slot in _fire_slots:
        if not rules.enemy_alive(_target):
            break
        _hit, _ap_cost, _handled_kills = _fire_active_slot(
            console, ctx, game_map, rules, _slot, _target, _player_pos,
        )
        _explosive_target_handled = _explosive_target_handled or _handled_kills
        _max_ap_cost = max(_max_ap_cost, _ap_cost)
        _any_hit = _any_hit or _hit
    if _max_ap_cost > 0:
        rules.set_player_ap(ctx, rules.player_ap(ctx) - _max_ap_cost)
    if _any_hit and not rules.enemy_alive(_target) and not _explosive_target_handled:
        from .. import message_log as _ml
        ctx.log.add_colored(
            f"{rules.enemy_name(_target)} destroyed!",
            _ml.COLOR_COMBAT_EVENT,
        )
        rules.on_kill(game_map, _target, ctx)
        return True
    return _any_hit and not rules.enemy_alive(_target)


def _end_turn(ctx, game_map, rules) -> str | None:
    """Run enemy turns + reinforcements. Returns "DEFEAT" if player
    died, ``None`` otherwise."""
    _dmg = rules.run_enemy_turns(ctx, game_map)
    if _dmg >= 999:  # signal: player death
        rules.on_player_death(ctx)
        return "DEFEAT"

    rules.check_reinforcements(ctx, game_map)
    return None


def _log_combat_start(ctx, rules) -> None:
    """Log the initial combat banner."""
    from .. import message_log as _ml

    _enemies = rules.get_enemies(ctx)
    if _enemies:
        ctx.log.add_colored(
            f"Combat starts! {len(_enemies)} enemy(s): "
            + ", ".join(rules.enemy_name(e) for e in _enemies),
            _ml.COLOR_COMBAT_EVENT,
        )


def _combat_end_check(ctx, game_map, rules) -> str | None:
    """Return VICTORY/DISENGAGED when the fight is over, else ``None``.

    Ground: the fight ends when the player sees no hostile (LOS aggro) —
    all engaged dead = VICTORY, survivors out of view = DISENGAGED. Space:
    VICTORY when no enemies remain.
    """
    _enemies = rules.get_enemies(ctx)
    if not rules.combat_should_end(ctx, game_map, _enemies):
        return None
    if _enemies:
        _on_disengage = getattr(rules, "on_disengage", None)
        if _on_disengage is not None:
            _on_disengage(ctx, game_map)
        return "DISENGAGED"
    return "VICTORY"


def _retarget_if_dead(ctx, rules, target_idx: int, enemies: list) -> int:
    """Reset the target to the first enemy when the current one died."""
    if target_idx >= len(enemies) or not rules.enemy_alive(enemies[target_idx]):
        rules.set_target_idx(ctx, 0)
        return 0
    return target_idx


def _handle_meta_action(action: str, ctx, presenter):
    """Handle non-combat actions. Returns ``(action, presenter, result, redo)``.

    ``result`` is ``"FLEE"`` when the fight must end, else ``None``.
    ``redo`` is ``True`` when the loop should re-iterate without dispatching.
    """
    if action in {"QUIT", "FLEE"}:
        return action, presenter, "FLEE", False
    if action == "UNAVAILABLE":
        if presenter is not None:
            presenter.close()
            ctx._pygame_combat_presenter = None
            presenter = None
        return action, presenter, None, True
    if action == "GUIDE":
        from ..help import _run_help_guide
        _run_help_guide(ctx)
        return action, presenter, None, True
    if action == "HISTORY":
        # Window-close inside the console log counts as FLEE, matching ESC.
        from ..console_log import open_console_log as _open_console_log
        _quit = _open_console_log(ctx) == "QUIT"
        return action, presenter, "FLEE" if _quit else None, not _quit
    return action, presenter, None, False


def _dispatch_combat_action(console, ctx, game_map, rules, action: str, target_idx: int, presenter):
    """Handle one in-combat action. Returns ``(target_idx, presenter)``."""
    if action == "TARGET":
        _enemies = rules.get_enemies(ctx)
        target_idx = _cycle_target(target_idx, len(_enemies), 1)
        rules.set_target_idx(ctx, target_idx)
    elif action == "TOGGLE_CARD":
        _toggle_card = getattr(rules, "toggle_target_card", None)
        if _toggle_card is not None:
            _toggle_card(ctx)
    elif action.startswith("MOVE:"):
        sym_name = action.partition(":")[2]
        if rules.player_ap(ctx) > 0:
            _dx, _dy = _MOVE_KEYS.get(sym_name, (0, 0))
            if (_dx, _dy) != (0, 0) and not rules.try_move(ctx, game_map, _dx, _dy):
                ctx.log.add("Blocked.")
    elif action == "DEFENSE":
        rules.handle_defense(ctx)
    elif action == "CHARACTER":
        _handle_character_action(ctx, rules)
    elif action == "FIRE":
        _handle_fire(console, ctx, game_map, rules, target_idx)
        presenter = getattr(ctx, "_pygame_combat_presenter", None)
    elif action == "RELOAD":
        _reload = getattr(rules, "reload_weapon", None)
        if _reload is not None:
            _reload(ctx)
        else:
            ctx.log.add("Reload is unavailable here.")
    elif action.startswith("WEAPON:"):
        _idx = int(action.partition(":")[2])
        _toggle_weapon(_idx, rules.active_weapons(ctx), ctx, rules)
    elif action == "WAIT":
        # Waiting ends the player's turn and forfeits remaining AP.
        rules.set_player_ap(ctx, 0)
    return target_idx, presenter


def _end_player_turn(ctx, game_map, rules, turn: int, presenter):
    """Run enemies when AP is spent. Returns ``(turn, presenter, defeat_or_None)``."""
    if rules is _rules_ground and rules.player_hp(ctx) <= 0:
        rules.on_player_death(ctx)
        return turn, presenter, "DEFEAT"
    if rules.player_ap(ctx) > 0:
        return turn, presenter, None
    _end_result = _end_turn(ctx, game_map, rules)
    presenter = getattr(ctx, "_pygame_combat_presenter", None)
    if _end_result == "DEFEAT":
        return turn, presenter, "DEFEAT"
    rules.reset_turn(ctx)
    return turn + 1, presenter, None


def _finish_combat(ctx, rules, result: str | None, presenter) -> CombatResult:
    """Sync state, invalidate death saves, close presenter, and build result."""
    rules.sync_state(ctx)
    if result == "DEFEAT":
        # Continue deletes after a successful load; this handles death
        # after a prior save during the same run. The shared loop owns
        # both ground and space defeat transitions.
        _delete_save()
    if presenter is not None:
        presenter.close()
    ctx._pygame_combat_presenter = None
    if hasattr(rules, 'get_combat_result'):
        _cr = rules.get_combat_result()
    else:
        _cr = CombatResult()
    _cr.outcome = result or "VICTORY"
    return _cr


def _run_combat_impl(console, ctx, game_map: world.GameMap, rules) -> CombatResult:
    """Run the unified turn-based combat loop (space or ground).

    The caller must call ``rules.init`` first. Owns turn structure, AP, key
    dispatch, fire, and victory/flee/death; delegates flavor to ``rules``.
    """
    _target_idx: int = 0
    _turn: int = 1
    _result: str | None = None
    _presenter = None
    ctx._pygame_combat_presenter = None
    _log_combat_start(ctx, rules)
    while True:
        rules.refresh_engaged(ctx, game_map)
        _result = _combat_end_check(ctx, game_map, rules)
        if _result is not None:
            break
        _enemies = rules.get_enemies(ctx)
        _target_idx = _retarget_if_dead(ctx, rules, _target_idx, _enemies)
        rules.render_frame(console, ctx, game_map)
        _present(ctx, console)
        _presenter = getattr(ctx, "_pygame_combat_presenter", None)
        _action = _combat_action(ctx, console, presenter=_presenter)
        _action, _presenter, _result_now, _redo = _handle_meta_action(_action, ctx, _presenter)
        if _result_now is not None:
            _result = _result_now
            break
        if _redo:
            continue
        _target_idx, _presenter = _dispatch_combat_action(
            console, ctx, game_map, rules, _action, _target_idx, _presenter,
        )
        _turn, _presenter, _defeat = _end_player_turn(ctx, game_map, rules, _turn, _presenter)
        if _defeat == "DEFEAT":
            _result = "DEFEAT"
            break
    return _finish_combat(ctx, rules, _result, _presenter)


def run_combat(
    console,
    ctx,
    game_map: world.GameMap,
    rules,
) -> CombatResult:
    """Run combat and always release a transient Pygame presenter."""
    try:
        return _run_combat_impl(console, ctx, game_map, rules)
    finally:
        _presenter = getattr(ctx, "_pygame_combat_presenter", None)
        if _presenter is not None:
            _presenter.close()
            ctx._pygame_combat_presenter = None

