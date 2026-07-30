"""Main combat loop — the turn-by-turn run_combat orchestrator.

Two versions exist:

  * :func:`run_combat` — unified loop taking a ``rules`` module
    for flavor-specific behavior. Works for both space and ground.
  * :func:`_run_combat_legacy` — original space-only loop. Kept
    until all callers migrate to the unified version.

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




def _run_combat_legacy(
    console,
    context,
    player_ship_catalog,
    player_owned_ship,
    player_pos: world.Position,
    player_pilot_skills: PilotSkills,
    enemy_specs: list,
    enemy_positions: list[world.Position],
    game_map: world.GameMap,
    log,
    ctx = None,
) -> tuple[str, list[str]]:
    """Drive the combat turn loop using tcod events.

    Accepts lists of enemy specs and positions for multi-enemy combat.
    Returns a :class:`CombatResult` with ``outcome``, ``defeated_names``,
    and ``defeated_bounty_ids`` fields.

    The player cycles targets with Tab. On VICTORY all dead enemy
    entities are removed from ``game_map.entities``. The player's
    hull damage is synced back to ``OwnedShip.hull_damage_pct`` on
    any exit path.
    """
    from .. import hud as _hud
    from .. import message_log as _ml
    from ..engine import SCREEN_WIDTH, SCREEN_HEIGHT

    if not enemy_specs or not enemy_positions:
        return ("FLEE", [])

    # Build initial combat state(s)
    try:
        enemy_insts: list[EnemyInstance] = []
        for _i in range(len(enemy_specs)):
            if _i == 0:
                _ps, _ei = init_combat_state(
                    player_ship_catalog, player_owned_ship,
                    player_pos, player_pilot_skills,
                    enemy_specs[_i], enemy_positions[_i],
                )
                player_state = _ps
            else:
                _, _ei = init_combat_state(
                    player_ship_catalog, player_owned_ship,
                    player_pos, player_pilot_skills,
                    enemy_specs[_i], enemy_positions[_i],
                )
            enemy_insts.append(_ei)
    except Exception:
        return ("FLEE", [])  # Graceful fallback on init failure

    # -------- Find player entity on map --------
    _player_ent = None
    for _e in game_map.entities:
        if getattr(_e, 'owned', False):
            _player_ent = _e
            break

    # -------- Build enemy-entity mapping (before dedup, so positions align) --------
    # Maps enemy_insts index -> world.Entity for position syncing and
    # entity exclusion in AI movement checks. Matched by position
    # before dedup shifts any instances. Uses id()-based _matched set
    # so two overlapping enemy_insts at the same pre-dedup cell don't
    # both claim the same world.Entity from game_map.entities.
    _enemy_ents: dict[int, Any] = {}
    _matched: set[int] = set()
    for _i, _inst in enumerate(enemy_insts):
        for _e in game_map.entities:
            if _e is _player_ent or getattr(_e, 'owned', False):
                continue
            if id(_e) in _matched:
                continue
            if _e.pos.x == _inst.pos.x and _e.pos.y == _inst.pos.y:
                _enemy_ents[_i] = _e
                _matched.add(id(_e))
                break
        # Override enemy name with the entity's custom name (e.g. bounty
        # targets like "Crimson Jack" instead of "Pirate Scout").
        _ent = _enemy_ents.get(_i)
        if _ent is not None and getattr(_ent, 'name', ''):
            _inst.name = _ent.name

    # -------- Deduplicate overlapping positions --------
    # If two or more enemies share the same cell (possible after
    # extended pirate movement on the space map), Tab targeting
    # appears to skip one (the reticle doesn't visually move) and
    # entity-index maps alias. Push overlapping instances apart.
    _occupied: set[tuple[int, int]] = set()
    for _inst in enemy_insts:
        _key = (_inst.pos.x, _inst.pos.y)
        if _key in _occupied:
            # Try 8 directions to find a free cell nearby.
            _placed = False
            for _odx, _ody in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]:
                _nk = (_inst.pos.x + _odx, _inst.pos.y + _ody)
                if _nk not in _occupied and game_map.in_bounds(*_nk) and game_map.is_walkable(*_nk):
                    _inst.pos = world.Position(*_nk)
                    _occupied.add(_nk)
                    _placed = True
                    break
            if not _placed:
                # Last resort: slide east cell-by-cell until a free
                # cell is found or the map boundary is reached, so
                # enemies pushed from the same origin end up at
                # distinct positions.
                _inst.pos = world.Position(_inst.pos.x + 2, _inst.pos.y)
                _attempts = 0
                while (_inst.pos.x, _inst.pos.y) in _occupied and _attempts < 20:
                    _nx = _inst.pos.x + 1
                    if not game_map.in_bounds(_nx, _inst.pos.y):
                        break
                    _inst.pos = world.Position(_nx, _inst.pos.y)
                    _attempts += 1
                _occupied.add((_inst.pos.x, _inst.pos.y))
        else:
            _occupied.add(_key)

    from ..message_log import COLOR_PLAYER_ACTION, COLOR_ENEMY_ACTION, COLOR_COMBAT_EVENT
    from ..data.trade_goods import find_trade_good as _ftg

    weapons_list = list(getattr(player_owned_ship, 'weapons', ()) or ())
    active_weapons = [True] * max(1, len(weapons_list))
    target_idx = 0
    combat_mode = "DEFAULT"
    flee_attempts: int = 0
    turn: int = 1
    _result: str | None = None  # None = still fighting; set on combat end

    def _p_log(msg: str) -> None:
        """Log a player-facing combat event (green)."""
        log.add_colored(msg, COLOR_PLAYER_ACTION)

    def _e_log(msg: str) -> None:
        """Log an enemy-facing combat event (red)."""
        log.add_colored(msg, COLOR_ENEMY_ACTION)

    def _c_log(msg: str) -> None:
        """Log a system combat event (gold)."""
        log.add_colored(msg, COLOR_COMBAT_EVENT)

    _c_log(f"Combat starts! {len(enemy_insts)} enemy ship(s): "
           + ", ".join(e.name for e in enemy_insts))
    _cr = CombatResult()
    start_player_turn(player_state)

    view_w = 80
    view_h = 54

    # Helper to compute camera centred on player
    def _calc_cam():
        _cw = max(0, game_map.width - view_w)
        _ch = max(0, game_map.height - view_h)
        _cx = max(0, min(
            player_state["pos"].x - view_w // 2,
            _cw,
        ))
        _cy = max(0, min(
            player_state["pos"].y - view_h // 2,
            _ch,
        ))
        return _cx, _cy

    try:
        while True:
            # ---- Check victory ----
            _alive_enemies = [e for e in enemy_insts if e.alive]
            if not _alive_enemies:
                _result = "VICTORY"
                break

            # ---- Sync entity positions to game_map ----
            if _player_ent is not None:
                _player_ent.pos = player_state["pos"]
            for _i, _inst in enumerate(enemy_insts):
                if _i in _enemy_ents:
                    _enemy_ents[_i].pos = _inst.pos

            # ---- Auto-end-turn guard (BEFORE render — Q4) ----
            # If AP hit 0 or the player pressed w / failed flee,
            # run the enemy turn immediately instead of rendering
            # a frame where the player can't act.
            if player_state["ap_remaining"] <= 0 or combat_mode == "WAIT":
                combat_mode = "WAIT"
                _result = _run_enemy_turn(
                    console, context, game_map,
                    player_state, enemy_insts, enemy_specs,
                    _enemy_ents, target_idx, log,
                    weapons_list, active_weapons,
                    _weapon_hit_chances, _evade_bonus,
                    flee_attempts, view_w, view_h, _calc_cam,
                    ctx=ctx,
                )
                if _result is not None:
                    break
                # Tick NPCs on the space map between combat rounds
                if ctx is not None:
                    from ..npc_ships import move_npcs as _tick_npcs
                    _tick_npcs(ctx, game_map)
                    from ..navigation import _detect_combat_encounter as _re_detect
                    from .. import solar_system as _ss_module
                    _new_encounter = _re_detect(ctx, player_state["pos"], _ss_module.current_system())
                    if _new_encounter is not None:
                        _new_specs, _new_positions = _new_encounter
                        _existing_entity_ids = {id(_e) for _e in _enemy_ents.values()}
                        for _ni, (_ns, _np) in enumerate(zip(_new_specs, _new_positions)):
                            _found_entity = None
                            for _ge in game_map.entities:
                                if getattr(_ge, 'owned', False):
                                    continue
                                # Skip loot entities — their "Loot" name would
                                # override the enemy spec name in the combat HUD.
                                if getattr(_ge, 'loot_data', None) is not None:
                                    continue
                                if _ge.pos.x == _np.x and _ge.pos.y == _np.y:
                                    _found_entity = _ge
                                    break
                            if _found_entity is not None and id(_found_entity) in _existing_entity_ids:
                                continue
                            _already = any(
                                _ei.pos.x == _np.x and _ei.pos.y == _np.y
                                for _ei in enemy_insts
                            )
                            if _already:
                                continue
                            _ps_dummy, _new_ei = init_combat_state(
                                player_ship_catalog, player_owned_ship,
                                player_state["pos"], player_pilot_skills,
                                _ns, _np,
                            )
                            enemy_insts.append(_new_ei)
                            if _found_entity is not None:
                                _enemy_ents[len(enemy_insts) - 1] = _found_entity
                                if getattr(_found_entity, 'name', ''):
                                    _new_ei.name = _found_entity.name
                            _c_log(f"{getattr(_found_entity, 'name', '') or _ns.name} joins the fight!")
                combat_mode = "DEFAULT"
                turn += 1
                start_player_turn(player_state)
                continue

            # ---- Re-target if current target is dead ----
            if not enemy_insts[target_idx].alive:
                _n = len(enemy_insts)
                for _offset in range(1, _n + 1):
                    _candidate = (target_idx + _offset) % _n
                    if enemy_insts[_candidate].alive:
                        target_idx = _candidate
                        break
                else:
                    target_idx = 0

            # ---- Compute closest alive enemy for flee distance ----
            _closest_enemy = min(
                _alive_enemies,
                key=lambda _e: _distance(player_state["pos"], _e.pos),
            )

            # ---- Compute flee chance once per frame (Q2) ----
            _flee_chance = calc_flee_chance(
                player_state["piloting"],
                _closest_enemy.pilot_piloting,
                player_state["hull"] / max(player_state["max_hull"], 1),
                _distance(player_state["pos"], _closest_enemy.pos),
                flee_attempts,
            )

            # ---- Compute hit chance for ALL weapons against current target ----
            _weapon_hit_chances: dict[str, int] = {}
            _evade_bonus = _calc_dodge_bonus(
                player_state.get("cells_moved_this_turn", 0),
                int(player_state.get("piloting", 0) * 0.5),
            )
            if weapons_list and target_idx < len(enemy_insts):
                _target = enemy_insts[target_idx]
                _dist = _distance(player_state["pos"], _target.pos)
                _dodge = _calc_dodge_bonus(
                    _target.cells_moved_this_turn,
                    int(_target.pilot_piloting * 0.5),
                )
                for _wid in weapons_list:
                    try:
                        _weapon_hit_chances[_wid] = calc_hit_chance(
                            _wid, player_state["gunnery"], _dist, _dodge,
                        )
                    except KeyError:
                        pass

            # ---- Render ----
            console.clear()
            _sys = getattr(game_map, 'width', None)
            if _sys is not None:
                _cam_x, _cam_y = _calc_cam()
                world.render_world_view(
                    console, game_map,
                    region_x=0, region_y=0,
                    region_w=view_w, region_h=view_h,
                    camera_x=_cam_x, camera_y=_cam_y,
                )
            _range_wid = None
            if weapons_list and any(active_weapons):
                from ..data.weapons import find_weapon as _fw
                _active_ids = [weapons_list[i] for i, a in enumerate(active_weapons) if a]
                _range_wid = min(_active_ids, key=lambda _wid: _fw(_wid).max_range)
            if _range_wid is not None:
                _tgt = _resolve_target(enemy_insts, target_idx)
                if _tgt is not None:
                    _paint_range_line(
                        console,
                        player_state["pos"], _tgt.pos,
                        _range_wid,
                        _cam_x, _cam_y, view_w, view_h, 0, 0,
                    )
            _tgt = _resolve_target(enemy_insts, target_idx)
            if _tgt is not None:
                _paint_target_highlight(
                    console, _cam_x, _cam_y, view_w, view_h, 0, 0, _tgt,
                )
            _hud.render_combat_hud(
                console,
                screen_width=SCREEN_WIDTH,
                screen_height=SCREEN_HEIGHT,
                player_state=player_state,
                enemies=enemy_insts,
                target_idx=target_idx,
                player_mode=combat_mode,
                active_weapons=active_weapons,
                weapon_list=tuple(weapons_list),
                flee_chance=_flee_chance,
                hit_chances=_weapon_hit_chances,
                evade_bonus=_evade_bonus,
                range_weapon_id=_range_wid,
            )
            _ml.render_message_log(
                console, log,
                screen_width=SCREEN_WIDTH,
                screen_height=SCREEN_HEIGHT,
            )
            context.present(console)

            # ---- Wait for input ----
            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    _result = "FLEE"
                    break
                if not isinstance(event, tcod.event.KeyDown):
                    continue

                if ctx is not None and _try_open_guide(event, ctx):
                    continue

                sym_name: str = getattr(event.sym, "name", "").lower()
                sym = event.sym

                # End-of-turn logic was hoisted OUT of this event
                # loop into a top-of-while guard above (right
                # after ``context.present(console)``). This is the
                # fix for the bug where the game blocked on a
                # keypress after AP hit 0. The three triggers —
                # ``w`` key, ESC flee failure, and AP==0 — all set
                # ``combat_mode = \"WAIT\"`` (or zero out
                # ``ap_remaining``) and ``break`` out of this event
                # loop; the outer guard then runs the enemy turn
                # and re-renders the new player turn.

                # [Tab] / [Left] / [Right] -> Cycle target
                if sym_name in ("tab", "left", "right") and len(enemy_insts) > 1:
                    if sym_name in ("tab", "right"):
                        target_idx = (target_idx + 1) % len(enemy_insts)
                    else:
                        target_idx = (target_idx - 1) % len(enemy_insts)
                    break

                # Movement in space mode
                _vim_keys = {"h": (-1,0), "j": (0,1), "k": (0,-1), "l": (1,0),
                             "y": (-1,-1), "u": (1,-1), "b": (-1,1), "n": (1,1)}
                if sym_name in _vim_keys and player_state["ap_remaining"] > 0:
                    dx, dy = _vim_keys[sym_name]
                    new_pos, ok = move_entity(
                        player_state["pos"], dx, dy, game_map,
                    )
                    if ok:
                        player_state["pos"] = new_pos
                        player_state["ap_remaining"] -= 1
                        player_state["cells_moved_this_turn"] += 1
                    break

                # ESC -> flee attempt
                if sym in ui._ESCAPE_SYMS:
                    _chance = calc_flee_chance(
                        player_state["piloting"],
                        _closest_enemy.pilot_piloting,
                        player_state["hull"] / max(player_state["max_hull"], 1),
                        _distance(player_state["pos"], _closest_enemy.pos),
                        flee_attempts,
                    )
                    if RNG.randint(1, 100) <= _chance:
                        _p_log("You fled!")
                        if ctx is not None:
                            ctx.player_counters.combat_flees += 1
                        _result = "FLEE"
                        break
                    else:
                        flee_attempts += 1
                        _e_log(f"Flee failed! ({_chance}% chance)")
                        player_state["ap_remaining"] = 0
                        combat_mode = "WAIT"
                    break

                # [s] -> Cycle shield regen rate 0-10
                if sym_name == "s":
                    max_sh = player_state.get("max_shields", 0)
                    if max_sh > 0:
                        cur = player_state.get("shield_regen_rate", 0)
                        next_rate = (cur + 1) % 11
                        player_state["shield_regen_rate"] = next_rate
                        if next_rate == 0:
                            _p_log(f"Shield regen: OFF")
                        else:
                            _p_log(f"Shield regen rate: {next_rate}/10")
                    else:
                        _p_log("No shields installed.")
                    break

                # [w] -> End player turn (wait)
                if sym_name == "w":
                    combat_mode = "WAIT"
                    break

                # [f] -> Fire ALL active weapons
                if sym_name == "f":
                    _fire_weapons(
                        console, context, game_map,
                        player_state, enemy_insts, enemy_specs,
                        _enemy_ents, target_idx, log,
                        weapons_list, active_weapons,
                        _weapon_hit_chances, _evade_bonus,
                        view_w, view_h, _calc_cam,
                        _cr, _closest_enemy,
                        _flee_chance,
                        ctx=ctx,
                    )
                    break

                # [1]–[9] -> Toggle weapon on/off
                # tcod.KeySym.N1–N9 have .name returning "N1"–"N9" (lowered to "n1"–"n9").
                # tcod.KeySym.KP_1–KP_9 have .name returning "KP_1"–"KP_9" (lowered to "kp_1"–"kp_9").
                # Note: lowercase letters like "h", "f", "w" work because enum names
                # are single uppercase letters ("H", "F", "W") matching after .lower().
                _num_keys = {
                    "n1": 0, "n2": 1, "n3": 2, "n4": 3, "n5": 4,
                    "n6": 5, "n7": 6, "n8": 7, "n9": 8,
                    "kp_1": 0, "kp_2": 1, "kp_3": 2, "kp_4": 3, "kp_5": 4,
                    "kp_6": 5, "kp_7": 6, "kp_8": 7, "kp_9": 8,
                }
                if sym_name in _num_keys:
                    _idx = _num_keys[sym_name]
                    if _idx < len(active_weapons):
                        active_weapons[_idx] = not active_weapons[_idx]
                        _state = "ON" if active_weapons[_idx] else "OFF"
                        from ..data.weapons import find_weapon as _fw
                        _p_log(f"Weapon {_idx + 1} ({_fw(weapons_list[_idx]).name}): {_state}")
                    break

    finally:
        # Always persist hull damage, even on FLEE/DEFEAT.
        _sync_back_hull(player_state, player_owned_ship)

    _cr.outcome = _result
    return _cr


# ---------------------------------------------------------------------------
# Unified combat loop (rules-module-driven)
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
                # Failed flee — end turn (AP will be zeroed by rules)
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

