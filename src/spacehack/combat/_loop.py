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

from ._types import CombatResult
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
    if sym_name in _MOVE_KEYS:
        return f"MOVE:{sym_name}"
    if sym_name in {".", "period"}:
        return "WAIT"
    return {
        "s": "DEFENSE",
        "w": "WAIT",
        "f": "FIRE",
    }.get(sym_name, f"WEAPON:{_NUM_KEYS[sym_name]}" if sym_name in _NUM_KEYS else "")



# ---------------------------------------------------------------------------
# Shared helpers + unified loop
# ---------------------------------------------------------------------------

# Numeric key mapping for weapon toggle — top-row 1-9 only. Numpad
# keys (kp_1..kp_9) are movement now (see world.MOVE_KEYS), so they
# must NOT double as weapon toggles.
_NUM_KEYS: dict[str, int] = {
    "n1": 0, "n2": 1, "n3": 2, "n4": 3, "n5": 4,
    "n6": 5, "n7": 6, "n8": 7, "n9": 8,
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


def _handle_fire(console, ctx, game_map, rules, target_idx: int) -> bool:
    """Fire all active weapons at the current target.

    Iterates active weapons, animates each shot, applies hit/miss
    and damage, checks for kill. Returns ``True`` if the target
    died (caller should check victory).

    Uses only ``rules.*`` functions — works identically for space
    and ground combat.
    """
    from .. import message_log as _ml

    _weapons = rules.player_weapons(ctx)
    _active = rules.active_weapons(ctx)
    # Fire by SLOT index, not weapon id: ammo is tracked per installed
    # launcher, so two of the same missile type keep separate magazines.
    _fire_slots = [
        i for i in range(len(_weapons))
        if i < len(_active) and _active[i]
    ]
    if not _fire_slots:
        ctx.log.add("No active weapons to fire.")
        return False

    _enemies = rules.get_enemies(ctx)
    if target_idx >= len(_enemies) or not rules.enemy_alive(_enemies[target_idx]):
        ctx.log.add("No valid target.")
        return False
    _target = _enemies[target_idx]

    _player_pos = ctx.player.pos

    # Burst-fire rule: track max AP among weapons that actually fire.
    # Pay max(ap_cost) once after the loop, but consume ammo/energy per weapon.
    _max_ap_cost = 0
    _any_fired = False
    _hit = False

    for _slot in _fire_slots:
        if not rules.enemy_alive(_target):
            break

        _wid = _weapons[_slot]
        _ok, _reason = rules.can_fire(_slot, ctx)
        if not _ok:
            try:
                _wname = rules.weapon_name(_wid, ctx)
            except KeyError:
                _wname = _wid
            ctx.log.add(f"{_wname}: {_reason}")
            continue
        if _reason:
            ctx.log.add(_reason)

        _hit = RNG.randint(1, 100) <= rules.hit_chance(_wid, _target, ctx)

        _any_fired = True
        _max_ap_cost = max(_max_ap_cost, rules.weapon_ap_cost(_wid, ctx))

        # Resolve damage BEFORE animating so the floating damage
        # number can ride the shot's impact frames. ``rules.damage``
        # mutates the target (hull/hp), which the animation only
        # reads for position — safe to apply first.
        _dmg_popup = None
        _is_strip = False
        _dmg = 0
        if _hit:
            # Ground enemies (GroundEnemyInstance) have no shields field;
            # getattr keeps the strip check safe across both combat modes.
            _pre_shields = getattr(_target, 'shields', 0)
            _dmg = rules.damage(_wid, _target, ctx)
            _stripped = max(0, _pre_shields - getattr(_target, 'shields', 0))
            # Only EMP weapons produce a shield strip; ground weapons
            # aren't in the ship-weapon catalog (mirrors the HUD's
            # guarded lookup), so skip the lookup when nothing stripped.
            if _stripped > 0:
                try:
                    _is_strip = _fw(_wid).shield_strip > 0
                except KeyError:
                    pass
            _dmg_popup = _damage_popup_for(_dmg, _stripped, _is_strip)

        rules.animate_fire(
            console, ctx, game_map,
            _player_pos, rules.enemy_pos(_target),
            is_hit=_hit,
            damage=_dmg_popup,
        )

        try:
            _wname = rules.weapon_name(_wid, ctx)
        except KeyError:
            _wname = _wid

        if _hit:
            if _is_strip:
                ctx.log.add_colored(
                    f"{_wname} strips {_stripped} shields from "
                    f"{rules.enemy_name(_target)}!",
                    _ml.COLOR_PLAYER_ACTION,
                )
            else:
                ctx.log.add_colored(
                    f"{_wname} hits {rules.enemy_name(_target)} for {_dmg + _stripped}!",
                    _ml.COLOR_PLAYER_ACTION,
                )
        else:
            ctx.log.add_colored(
                f"{_wname} misses {rules.enemy_name(_target)}!",
                _ml.COLOR_PLAYER_ACTION,
            )

        rules.consume_shot(_slot, ctx)

    # Charge max AP once for the entire burst (only if something fired)
    if _any_fired:
        _ap_now = rules.player_ap(ctx)
        rules.set_player_ap(ctx, _ap_now - _max_ap_cost)

    # Kill handling AFTER AP deduction so killing the target still
    # costs the full AP for the burst.  Must be outside the weapon
    # loop (we don't want to return mid-burst before the AP deduction).
    if _hit and not rules.enemy_alive(_target):
        ctx.log.add_colored(
            f"{rules.enemy_name(_target)} destroyed!",
            _ml.COLOR_COMBAT_EVENT,
        )
        rules.on_kill(game_map, _target, ctx)
        return True

    return False


def _end_turn(ctx, game_map, rules) -> str | None:
    """Run enemy turns + reinforcements. Returns "DEFEAT" if player
    died, ``None`` otherwise."""
    _dmg = rules.run_enemy_turns(ctx, game_map)
    if _dmg >= 999:  # signal: player death
        rules.on_player_death(ctx)
        return "DEFEAT"

    rules.check_reinforcements(ctx, game_map)
    return None


def _run_combat_impl(
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
        console: project framebuffer for rendering.
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

    _target_idx: int = 0
    _turn: int = 1
    _result: str | None = None
    # Combat presentation uses the already-open shared Pygame runtime.
    # Input is read through the project-owned runtime event contract; combat
    # does not need a second persistent worker window.
    _presenter = None
    ctx._pygame_combat_presenter = None

    # Initial combat log
    _enemies = rules.get_enemies(ctx)
    if _enemies:
        ctx.log.add_colored(
            f"Combat starts! {len(_enemies)} enemy(s): "
            + ", ".join(rules.enemy_name(e) for e in _enemies),
            _ml.COLOR_COMBAT_EVENT,
        )

    while True:
        # ---- Refresh the engaged set: ground joins any mob now in the
        # player's view so it is part of combat immediately (targetable
        # and acting this round) — space has no mid-fight joins -------
        rules.refresh_engaged(ctx, game_map)

        # ---- End check ----
        # Ground: the fight ends when the player sees no hostile (LOS
        # aggro) — all engaged dead = VICTORY, survivors out of view =
        # DISENGAGED. Space: VICTORY when no enemies remain.
        _enemies = rules.get_enemies(ctx)
        if rules.combat_should_end(ctx, game_map, _enemies):
            _result = "VICTORY" if not _enemies else "DISENGAGED"
            if _result == "DISENGAGED":
                _on_disengage = getattr(rules, "on_disengage", None)
                if _on_disengage is not None:
                    _on_disengage(ctx, game_map)
            break

        # ---- Re-target if current target is dead ----
        if _target_idx >= len(_enemies) or not rules.enemy_alive(_enemies[_target_idx]):
            _target_idx = 0
            rules.set_target_idx(ctx, _target_idx)

        # ---- Render ----
        rules.render_frame(console, ctx, game_map)
        _present(ctx, console)
        _presenter = getattr(ctx, "_pygame_combat_presenter", None)

        # ---- Wait for input ----
        _action = _combat_action(ctx, console, presenter=_presenter)
        if _action in {"QUIT", "FLEE"}:
            _result = "FLEE"
            break
        if _action == "UNAVAILABLE":
            if _presenter is not None:
                _presenter.close()
                _presenter = None
                ctx._pygame_combat_presenter = None
            continue
        if _action == "GUIDE":
            from ..help import _run_help_guide
            _run_help_guide(ctx)
            continue
        if _action == "TARGET":
            _target_idx = _cycle_target(_target_idx, len(_enemies), 1)
            rules.set_target_idx(ctx, _target_idx)
        elif _action.startswith("MOVE:"):
            sym_name = _action.partition(":")[2]
            if rules.player_ap(ctx) > 0:
                _dx, _dy = _MOVE_KEYS.get(sym_name, (0, 0))
                if (_dx, _dy) != (0, 0) and not rules.try_move(ctx, game_map, _dx, _dy):
                    ctx.log.add("Blocked.")
        elif _action == "DEFENSE":
            rules.handle_defense(ctx)
        elif _action == "FIRE":
            _handle_fire(console, ctx, game_map, rules, _target_idx)
            _presenter = getattr(ctx, "_pygame_combat_presenter", None)

        elif _action.startswith("WEAPON:"):
            _idx = int(_action.partition(":")[2])
            _toggle_weapon(_idx, rules.active_weapons(ctx), ctx, rules)
        elif _action == "WAIT":
            # Waiting ends the player's turn and forfeits remaining AP.
            rules.set_player_ap(ctx, 0)

        # ---- End-turn guard: if AP ≤ 0, run enemy turns ----
        if rules.player_ap(ctx) <= 0:
            _end_result = _end_turn(ctx, game_map, rules)
            _presenter = getattr(ctx, "_pygame_combat_presenter", None)
            if _end_result == "DEFEAT":
                _result = "DEFEAT"
                break
            _turn += 1
            rules.reset_turn(ctx)

    # ---- Sync state back ----
    rules.sync_state(ctx)
    if _presenter is not None:
        _presenter.close()
    ctx._pygame_combat_presenter = None

    # ---- Build result ----
    if hasattr(rules, 'get_combat_result'):
        _cr = rules.get_combat_result()
    else:
        _cr = CombatResult()
    _cr.outcome = _result or "VICTORY"
    return _cr


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

