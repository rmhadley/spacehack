"""Main combat loop — the turn-by-turn run_combat orchestrator.

run_combat drives the player action and enemy AI loop, handling
input events, rendering frames, and coordinating all sub-module
functions (stats, actions, animations).

Callers in __main__.py and _encounter.py hand off control here
and receive a ``(result, defeated_spec_ids)`` tuple back.
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
from ._types import EnemyInstance
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




def _remove_dead_entity(
    game_map: world.GameMap,
    enemy_ents: dict,
    target_idx: int,
) -> None:
    """Remove a destroyed enemy's world entity from the game map.

    Pops the entity from ``enemy_ents`` by index and removes it from
    ``game_map.entities`` so its glyph doesn't linger on screen.
    No-op if the index is not in the mapping.
    """
    _dead_ent = enemy_ents.pop(target_idx, None)
    if _dead_ent is not None and _dead_ent in game_map.entities:
        game_map.entities.remove(_dead_ent)


def _spawn_loot_drops(
    game_map: world.GameMap,
    target_pos: world.Position,
    enemy_spec: Any,
) -> None:
    """Spawn 1-2 loot items near a destroyed enemy ship."""
    _spec_loot = getattr(enemy_spec, 'cargo_goods', None) or ()
    _loot_items = list(_spec_loot)
    if not _loot_items:
        _loot_items = ["scrap_metal"]
    _drop_count = min(len(_loot_items), RNG.randint(1, 2))
    for _li in range(_drop_count):
        _loot_id = RNG.choice(_loot_items)
        _lx = target_pos.x + RNG.randint(-1, 1)
        _ly = target_pos.y + RNG.randint(-1, 1)
        if not game_map.is_walkable(_lx, _ly):
            _lx, _ly = target_pos.x, target_pos.y
        game_map.entities.append(world.Entity(
            char="%", fg=(255, 215, 0),
            pos=world.Position(_lx, _ly),
            name="Loot", width=1, height=1,
            loot_data={"good_id": _loot_id, "quantity": RNG.randint(1, 3)},
        ))


def run_combat(
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
    Returns ``(result, defeated_spec_ids)`` where ``result`` is
    ``\"VICTORY\"``, ``\"DEFEAT\"``, or ``\"FLEE\"`` and
    ``defeated_spec_ids`` lists the ``spec_id`` of each enemy
    destroyed during combat (empty for non-VICTORY outcomes).

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
    # Track which enemy spec IDs were defeated (for bounty completion).
    _defeated_spec_ids: list[str] = []
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
            # ---- Check victory (don't prune list — indices must stay stable for _enemy_ents) ----
            _alive_enemies = [e for e in enemy_insts if e.alive]
            if not _alive_enemies:
                _result = "VICTORY"
                break
            if not enemy_insts[target_idx].alive:
                # Move target to next alive enemy (search forward from
                # current index so we don't snap back to the first alive
                # enemy, which would make enemies past a dead one
                # unreachable via Tab).
                _n = len(enemy_insts)
                for _offset in range(1, _n + 1):
                    _candidate = (target_idx + _offset) % _n
                    if enemy_insts[_candidate].alive:
                        target_idx = _candidate
                        break
                else:
                    target_idx = 0

            # ---- Sync entity positions to game_map so rendering works ----
            if _player_ent is not None:
                _player_ent.pos = player_state["pos"]
            for _i, _inst in enumerate(enemy_insts):
                if _i in _enemy_ents:
                    _enemy_ents[_i].pos = _inst.pos

            # ---- Compute closest alive enemy for flee distance ----
            _closest_enemy = min(
                _alive_enemies,
                key=lambda _e: _distance(player_state["pos"], _e.pos),
            )

            # ---- Compute hit chance for ALL weapons against current target ----
            _weapon_hit_chances: dict[str, int] = {}
            # Player's current evade bonus: +5% per cell moved this turn
            # (capped at 30%) plus half-rate pilot piloting (soft cap 60%).
            # Surfaced in the combat HUD so the player sees the impact
            # of spending AP on movement while in combat.
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
            # Range-accuracy line — drawn AFTER the world view so it
            # sits on top of the space background but BEFORE the target
            # highlight so the gold recolor takes visual priority over
            # the line. Uses the first active weapon for range display.
            _range_wid = None
            if weapons_list:
                _first_active = next((i for i, a in enumerate(active_weapons) if a), None)
                if _first_active is not None and _first_active < len(weapons_list):
                    _range_wid = weapons_list[_first_active]
            if _range_wid is not None:
                _tgt = _resolve_target(enemy_insts, target_idx)
                if _tgt is not None:
                    _paint_range_line(
                        console,
                        player_state["pos"], _tgt.pos,
                        _range_wid,
                        _cam_x, _cam_y, view_w, view_h, 0, 0,
                    )

            # Targeted-enemy reticle — drawn AFTER the range line
            # so the gold recolor sits on top of the line marker.
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
                flee_chance=calc_flee_chance(
                    player_state["piloting"],
                    _closest_enemy.pilot_piloting,
                    player_state["hull"] / max(player_state["max_hull"], 1),
                    _distance(player_state["pos"], _closest_enemy.pos),
                    flee_attempts,
                ),
                hit_chances=_weapon_hit_chances,
                evade_bonus=_evade_bonus,
            )
            _ml.render_message_log(
                console, log,
                screen_width=SCREEN_WIDTH,
                screen_height=SCREEN_HEIGHT,
            )
            context.present(console)

            # ---- Auto-end-turn guard (outside ``for event``) ----
            # If ``ap_remaining`` hit 0 from the previous action
            # (move, fire, target switch), or the player pressed
            # ``w``, or a flee attempt failed, run the enemy turn
            # IMMEDIATELY — don't block on the next keypress. The
            # three paths in the event loop below drive this guard
            # by setting ``combat_mode = \"WAIT\"`` (or zeroing AP)
            # and breaking out of the event loop. Putting this
            # outside ``for event in tcod.event.wait()`` is the
            # fix for the bug where the game blocked on input
            # after AP reached 0 and the player had to press any
            # key to advance.
            if player_state["ap_remaining"] <= 0 or combat_mode == "WAIT":
                combat_mode = "WAIT"
                # Delegate enemy AI to its own module.
                _result = _run_enemy_turn(
                    console, context, game_map,
                    player_state, enemy_insts, enemy_specs,
                    _enemy_ents, target_idx, log,
                    weapons_list, active_weapons,
                    _weapon_hit_chances, _evade_bonus,
                    flee_attempts, view_w, view_h, _calc_cam,
                )
                if _result is not None:
                    break
                # Tick NPCs on the space map between combat rounds
                # so the rest of the universe doesn't freeze.
                if ctx is not None:
                    from ..npc_ships import move_npcs as _tick_npcs
                    _tick_npcs(ctx, game_map)
                    # Re-check for NEW enemies that moved within detection
                    # range during the NPC tick. If found, merge them in.
                    # Use entity-ID matching to avoid duplicating enemies
                    # already in combat (whose positions may have shifted
                    # due to move_npcs).
                    from ..navigation import _detect_combat_encounter as _re_detect
                    from .. import solar_system as _ss_module
                    _new_encounter = _re_detect(ctx, player_state["pos"], _ss_module.current_system())
                    if _new_encounter is not None:
                        _new_specs, _new_positions = _new_encounter
                        _existing_entity_ids = {id(_e) for _e in _enemy_ents.values()}
                        for _ni, (_ns, _np) in enumerate(zip(_new_specs, _new_positions)):
                            # Find the world entity at this position.
                            _found_entity = None
                            for _ge in game_map.entities:
                                if getattr(_ge, 'owned', False):
                                    continue
                                if _ge.pos.x == _np.x and _ge.pos.y == _np.y:
                                    _found_entity = _ge
                                    break
                            # Skip if this entity is already in combat.
                            if _found_entity is not None and id(_found_entity) in _existing_entity_ids:
                                continue
                            # Also skip if already in enemy_insts by position
                            # (belt-and-suspenders).
                            _already = any(
                                _ei.pos.x == _np.x and _ei.pos.y == _np.y
                                for _ei in enemy_insts
                            )
                            if _already:
                                continue
                            # Create EnemyInstance for the new joiner.
                            _ps_dummy, _new_ei = init_combat_state(
                                player_ship_catalog, player_owned_ship,
                                player_state["pos"], player_pilot_skills,
                                _ns, _np,
                            )
                            enemy_insts.append(_new_ei)
                            if _found_entity is not None:
                                _enemy_ents[len(enemy_insts) - 1] = _found_entity
                            _c_log(f"{_ns.name} joins the fight!")
                # New player turn: reset AP, increment counter,
                # drop out of WAIT, then ``continue`` so the
                # top-of-loop render block paints the fresh
                # player turn BEFORE we block on input again.
                combat_mode = "DEFAULT"
                turn += 1
                start_player_turn(player_state)
                continue

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
                        flee_attempts, view_w, view_h, _calc_cam,
                        _defeated_spec_ids, _closest_enemy,
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
                        _p_log(f"Weapon {_idx + 1} ({weapons_list[_idx]}): {_state}")
                    break

    finally:
        # Always persist hull damage, even on FLEE/DEFEAT.
        _sync_back_hull(player_state, player_owned_ship)

    return _result, _defeated_spec_ids


def _check_fire_ready(
    player_state: dict,
    weapon_id: str,
    target_idx: int,
    enemies: list[EnemyInstance],
) -> tuple[bool, str]:
    """Quick pre-flight check before firing.

    Returns (ok, reason_message). Called by the fire (f) handler
    for each weapon in the active list.
    """
    if not (0 <= target_idx < len(enemies) and enemies[target_idx].alive):
        return False, "No valid target."
    return can_afford_action(player_state, weapon_id)
