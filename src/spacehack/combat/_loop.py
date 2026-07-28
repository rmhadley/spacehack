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
from ..data.weapons import find_weapon
from ..data.pilot_skills import PilotSkills
from ..input_helpers import _try_open_guide

from ._actions import (
    start_player_turn,
    start_enemy_turn,
    move_entity,
    resolve_damage,
    can_afford_action,
)
from ._types import EnemyInstance
from ._stats import (
    init_combat_state,
    calc_hit_chance,
    calc_flee_chance,
    _calc_dodge_bonus,
    _distance,
    _sync_back_hull,
)
from ._actions import (
    start_player_turn,
    start_enemy_turn,
    move_entity,
    resolve_damage,
)
from ._animations import (
    _animate_laser_shot,
    _animate_explosion,
    _resolve_target,
    _paint_target_highlight,
    _paint_range_line,
    _responsive_sleep,
)


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
    from ..engine import SCREEN_WIDTH, SCREEN_HEIGHT, MSG_LOG_HEIGHT, HUD_WIDTH

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
                # Execute enemy turn for ALL alive enemies
                for _ei in enemy_insts:
                    if not _ei.alive:
                        continue
                    start_enemy_turn(_ei)
                    # Enemy AI: burn the full AP per turn. Each iter =
                    # ONE action that costs 1 AP. Move if outside
                    # preferred_range, else fire (when armed). Loop
                    # terminates on ap_remaining==0 or on the idle
                    # branch (already in range, no weapons). Fire
                    # charges 1 AP too (mirrors player fire cost) so
                    # the loop can't spin forever if the AI is unable
                    # to close distance. Tactical choices (hold vs.
                    # fire, range gating) are out of scope for the
                    # simple v1 of this fix.
                    # Find matching spec for this enemy via spec_id
                    _esp = next(
                        (_sp for _sp in enemy_specs if getattr(_sp, 'id', None) == _ei.spec_id),
                        enemy_specs[0] if enemy_specs else None,
                    )
                    if _esp is None:
                        continue
                    # Cache entity-index lookup once per enemy so the
                    # while loop doesn't re-scan enemy_insts per
                    # move step.
                    _e_idx = next(
                        (_j for _j, _je in enumerate(enemy_insts) if _je is _ei),
                        -1,
                    )
                    while _ei.ap_remaining > 0:
                        _edist = _distance(
                            player_state["pos"], _ei.pos,
                        )
                        _moved = False
                        if _edist > _esp.ai_preferred_range:
                            # Attempt to move one cell toward the
                            # player. The target cell must be both
                            # walkable AND unoccupied — the burn-full
                            # AP refactor exposed overlap because
                            # pirates now move up to 4 cells per
                            # turn instead of 1, so two enemies
                            # converging on the player would happily
                            # step onto each other (or onto the
                            # player). Reject collisions with the
                            # player, another enemy that already
                            # moved earlier in this same for-loop
                            # iteration, or any solar-body entity.
                            _dx = 1 if _ei.pos.x < player_state["pos"].x else -1
                            _dy = 1 if _ei.pos.y < player_state["pos"].y else -1
                            _nx = _ei.pos.x + _dx
                            _ny = _ei.pos.y + _dy
                            # Check direct instance-position collision first:
                            # no other alive enemy may occupy the target cell.
                            # Entity-at checks can miss unmapped enemies whose
                            # game_map entity positions are stale, so skip the
                            # entity mapping entirely and check EnemyInstance
                            # positions directly.
                            _blocked_by_other = any(
                                _oe is not _ei and _oe.alive
                                and _oe.pos.x == _nx and _oe.pos.y == _ny
                                for _oe in enemy_insts
                            )
                            if not _blocked_by_other and (
                                game_map.is_walkable(_nx, _ny)
                                and game_map.entity_at(
                                    _nx, _ny, exclude=None,
                                ) is None
                            ):
                                _ei.pos = world.Position(_nx, _ny)
                                _ei.cells_moved_this_turn += 1
                                _ei.ap_remaining -= 1
                                # Sync enemy entity position AFTER AI movement
                                if _e_idx >= 0 and _e_idx in _enemy_ents:
                                    _enemy_ents[_e_idx].pos = _ei.pos
                                _moved = True
                                # Render a frame so the player sees the enemy move
                                # (prevents the \"teleport\" feel of multi-AP movement).
                                _cam_x, _cam_y = _calc_cam()
                                console.clear()
                                world.render_world_view(
                                    console, game_map,
                                    region_x=0, region_y=0,
                                    region_w=view_w, region_h=view_h,
                                    camera_x=_cam_x, camera_y=_cam_y,
                                )
                                _tgt = _resolve_target(enemy_insts, target_idx)
                                if _tgt is not None:
                                    _paint_target_highlight(
                                        console, _cam_x, _cam_y,
                                        view_w, view_h, 0, 0, _tgt,
                                    )
                                _flee_now = calc_flee_chance(
                                    player_state["piloting"],
                                    _closest_enemy.pilot_piloting,
                                    player_state["hull"] / max(player_state["max_hull"], 1),
                                    _distance(player_state["pos"], _closest_enemy.pos),
                                    flee_attempts,
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
                                    evade_bonus=_evade_bonus,
                                    hit_chances=_weapon_hit_chances,
                                    flee_chance=_flee_now,
                                )
                                _ml.render_message_log(
                                    console, log,
                                    screen_width=SCREEN_WIDTH,
                                    screen_height=SCREEN_HEIGHT,
                                )
                                context.present(console)
                                _responsive_sleep(0.05)
                        if not _moved:
                            # Either in preferred range (no move
                            # attempted) OR move was blocked. Pivot
                            # to fire if armed — mirrors the player-
                            # side rule of \"if you can't move, shoot\"
                            # so the AP isn't wasted. If move was
                            # blocked AND the enemy is unarmed, idle
                            # for the rest of the turn rather than
                            # spinning.
                            if _ei.weapons:
                                # Enemy fires
                                _wid = _ei.weapons[0]
                                _dist = _distance(
                                    player_state["pos"], _ei.pos,
                                )
                                _dodge = _calc_dodge_bonus(
                                    player_state.get("cells_moved_this_turn", 0),
                                    int(player_state.get("piloting", 0) * 0.5),
                                )
                                _chance = calc_hit_chance(
                                    _wid, _ei.pilot_gunnery, _dist, _dodge,
                                )
                                # Single roll decides both animation AND damage
                                _e_hit = RNG.randint(1, 100) <= _chance
                                _ecx, _ecy = _calc_cam()
                                _animate_laser_shot(
                                    console, context, game_map,
                                    _ei.pos, player_state["pos"],
                                    is_hit=_e_hit,
                                    cam_x=_ecx, cam_y=_ecy,
                                    view_w=view_w, view_h=view_h,
                                    player_state=player_state,
                                    enemies=enemy_insts,
                                    target_idx=target_idx,
                                    log=log,
                                    weapon_list=tuple(weapons_list),
                                    active_weapons=active_weapons,
                                    evade_bonus=_evade_bonus,
                                    hit_chances=_weapon_hit_chances,
                                    flee_chance=calc_flee_chance(
                                        player_state["piloting"],
                                        _closest_enemy.pilot_piloting,
                                        player_state["hull"] / max(player_state["max_hull"], 1),
                                        _distance(player_state["pos"], _closest_enemy.pos),
                                        flee_attempts,
                                    ),
                                )
                                if _e_hit:
                                    _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
                                        _wid, player_state["hull"],
                                        player_state["shields"],
                                        target_pilot_piloting=player_state.get("piloting", 0),
                                    )
                                    player_state["shields"] = max(0, player_state["shields"] - _sdmg)
                                    player_state["hull"] = _fh
                                    _verb = "glancing hit" if _is_glancing else "hits"
                                    _e_log(f"{_ei.name} {_verb} for {_dmg} hull damage!")
                                    if _fh <= 0:
                                        _e_log("Your ship has been destroyed!")
                                        # Explosion at player position
                                        _ecx, _ecy = _calc_cam()
                                        _animate_explosion(
                                            console, context, game_map,
                                            player_state["pos"],
                                            cam_x=_ecx, cam_y=_ecy,
                                            view_w=view_w, view_h=view_h,
                                            player_state=player_state,
                                            enemies=enemy_insts,
                                            target_idx=target_idx,
                                            log=log,
                                            weapon_list=tuple(weapons_list),
                                            active_weapons=active_weapons,
                                            evade_bonus=_evade_bonus,
                                            hit_chances=_weapon_hit_chances,
                                            flee_chance=calc_flee_chance(
                                                player_state["piloting"],
                                                _closest_enemy.pilot_piloting,
                                                player_state["hull"] / max(player_state["max_hull"], 1),
                                                _distance(player_state["pos"], _closest_enemy.pos),
                                                flee_attempts,
                                            ),
                                        )
                                        _result = "DEFEAT"
                                        break  # exits while
                                else:
                                    _e_log(f"{_ei.name} misses!")
                                # Fire costs 1 AP — mirrors the
                                # player rule (a shot committed is
                                # a shot paid for) and guarantees
                                # the while loop terminates when
                                # ap_remaining hits 0.
                                _ei.ap_remaining -= 1
                            else:
                                # In preferred range and unarmed, OR
                                # blocked move and unarmed — idle
                                # for the rest of the turn.
                                break
                    # Cascade DEFEAT out of the for-loop so the
                    # remaining enemies don't get their turns after
                    # the player is already destroyed. Without this
                    # the inner ``break`` only exits the new while.
                    if _result is not None:
                        break
                # If DEFEAT happened during the enemy turn, exit
                # combat now (don't re-render a fresh player turn).
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

                # [space] / [enter] -> Fire at current target
                if sym_name in ("space", "return"):
                    # Choose first active weapon
                    _weapon_to_fire = None
                    for _wi, _wa in enumerate(active_weapons):
                        if _wa and _wi < len(weapons_list):
                            _weapon_to_fire = weapons_list[_wi]
                            break
                    if _weapon_to_fire is None:
                        _p_log("No active weapon to fire.")
                        break

                    _ok, _reason = _check_fire_ready(
                        player_state, _weapon_to_fire, target_idx, enemy_insts,
                    )
                    if not _ok:
                        _p_log(_reason)
                        break

                    _target_enemy = enemy_insts[target_idx]
                    _target_pos = _target_enemy.pos

                    # Single roll decides both animation AND damage
                    _player_dist = _distance(player_state["pos"], _target_pos)
                    _target_dodge = _calc_dodge_bonus(
                        _target_enemy.cells_moved_this_turn,
                        int(_target_enemy.pilot_piloting * 0.5),
                    )
                    _hit_chance = calc_hit_chance(
                        _weapon_to_fire, player_state["gunnery"],
                        _player_dist, _target_dodge,
                    )
                    _is_hit = RNG.randint(1, 100) <= _hit_chance

                    _cam_x, _cam_y = _calc_cam()
                    _animate_laser_shot(
                        console, context, game_map,
                        player_state["pos"], _target_pos,
                        is_hit=_is_hit,
                        cam_x=_cam_x, cam_y=_cam_y,
                        view_w=view_w, view_h=view_h,
                        player_state=player_state,
                        enemies=enemy_insts,
                        target_idx=target_idx,
                        log=log,
                        weapon_list=tuple(weapons_list),
                        active_weapons=active_weapons,
                        evade_bonus=_evade_bonus,
                        hit_chances=_weapon_hit_chances,
                        flee_chance=calc_flee_chance(
                            player_state["piloting"],
                            _closest_enemy.pilot_piloting,
                            player_state["hull"] / max(player_state["max_hull"], 1),
                            _distance(player_state["pos"], _closest_enemy.pos),
                            flee_attempts,
                        ),
                    )

                    if _is_hit:
                        _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
                            _weapon_to_fire,
                            _target_enemy.hull,
                            _target_enemy.shields,
                            target_pilot_piloting=_target_enemy.pilot_piloting,
                        )
                        _target_enemy.shields = max(0, _target_enemy.shields - _sdmg)
                        _target_enemy.hull = _fh
                        _verb = "glancing hit" if _is_glancing else "hits"
                        _p_log(f"You {_verb} {_target_enemy.name} for {_dmg} hull damage!")
                        if _fh <= 0:
                            _target_enemy.alive = False
                            _defeated_spec_ids.append(_target_enemy.spec_id)
                            _c_log(f"{_target_enemy.name} destroyed!")
                            # Explosion at target position
                            _cam_x, _cam_y = _calc_cam()
                            _animate_explosion(
                                console, context, game_map,
                                _target_pos,
                                cam_x=_cam_x, cam_y=_cam_y,
                                view_w=view_w, view_h=view_h,
                                player_state=player_state,
                                enemies=enemy_insts,
                                target_idx=target_idx,
                                log=log,
                                weapon_list=tuple(weapons_list),
                                active_weapons=active_weapons,
                                evade_bonus=_evade_bonus,
                                hit_chances=_weapon_hit_chances,
                                flee_chance=calc_flee_chance(
                                    player_state["piloting"],
                                    _closest_enemy.pilot_piloting,
                                    player_state["hull"] / max(player_state["max_hull"], 1),
                                    _distance(player_state["pos"], _closest_enemy.pos),
                                    flee_attempts,
                                ),
                            )
                            # Loot drop: spawn 1-2 items near the wreck
                            _spec_loot = getattr(enemy_specs[0], 'cargo_goods', None) or ()
                            _loot_items = list(_spec_loot)
                            if not _loot_items:
                                _loot_items = ["scrap_metal"]
                            _drop_count = min(len(_loot_items), RNG.randint(1, 2))
                            for _li in range(_drop_count):
                                _loot_id = RNG.choice(_loot_items)
                                _lx = _target_pos.x + RNG.randint(-1, 1)
                                _ly = _target_pos.y + RNG.randint(-1, 1)
                                if not game_map.is_walkable(_lx, _ly):
                                    _lx, _ly = _target_pos.x, _target_pos.y
                                game_map.entities.append(world.Entity(
                                    x=_lx, y=_ly, char="%",
                                    fg=(255, 215, 0),
                                    name="Loot",
                                    blocks_movement=False,
                                    loot_data={_loot_id: RNG.randint(1, 3)},
                                ))
                    else:
                        _p_log(f"You miss {_target_enemy.name}!")
                    # Deduct AP, power, ammo
                    _ws = find_weapon(_weapon_to_fire)
                    player_state["ap_remaining"] -= _ws.ap_cost
                    if _ws.slot_type == "energy":
                        player_state["power_pool"] -= _ws.power_cost
                    elif _ws.slot_type == "missile":
                        old = player_state["weapon_ammo"][_weapon_to_fire]
                        player_state["weapon_ammo"][_weapon_to_fire] = old - _ws.ammo_per_shot
                    break

                # [f] -> Burst fire (fire ALL active weapons)
                if sym_name == "f":
                    # Collect all active weapon IDs
                    _fire_list = [
                        weapons_list[wi] for wi, wa in enumerate(active_weapons)
                        if wa and wi < len(weapons_list)
                    ]
                    if not _fire_list:
                        _p_log("No active weapons to fire.")
                        break
                    if not (0 <= target_idx < len(enemy_insts) and enemy_insts[target_idx].alive):
                        _p_log("No valid target.")
                        break

                    # Check combined requirements: max AP cost among selected weapons,
                    # total power cost, and ammo availability.
                    _max_ap = 0
                    _total_power = 0
                    _all_ok = True
                    for _fwid in _fire_list:
                        _ok, _reason = _check_fire_ready(
                            player_state, _fwid, target_idx, enemy_insts,
                        )
                        if not _ok:
                            _p_log(f"{_fwid}: {_reason}")
                            _all_ok = False
                            break
                        _fws = find_weapon(_fwid)
                        _max_ap = max(_max_ap, _fws.ap_cost)
                        _total_power += _fws.power_cost
                    if not _all_ok:
                        break

                    # Burst fire: iterate through each active weapon.
                    _target_enemy = enemy_insts[target_idx]
                    _target_pos = _target_enemy.pos
                    for _fwid in _fire_list:
                        if not _target_enemy.alive:
                            break
                        _fws = find_weapon(_fwid)
                        # Calculate hit chance (respect target state).
                        _player_dist = _distance(player_state["pos"], _target_pos)
                        _target_dodge = _calc_dodge_bonus(
                            _target_enemy.cells_moved_this_turn,
                            int(_target_enemy.pilot_piloting * 0.5),
                        )
                        _hit_chance = calc_hit_chance(
                            _fwid, player_state["gunnery"],
                            _player_dist, _target_dodge,
                        )
                        _is_hit = RNG.randint(1, 100) <= _hit_chance

                        _cam_x, _cam_y = _calc_cam()
                        _animate_laser_shot(
                            console, context, game_map,
                            player_state["pos"], _target_pos,
                            is_hit=_is_hit,
                            cam_x=_cam_x, cam_y=_cam_y,
                            view_w=view_w, view_h=view_h,
                            player_state=player_state,
                            enemies=enemy_insts,
                            target_idx=target_idx,
                            log=log,
                            weapon_list=tuple(weapons_list),
                            active_weapons=active_weapons,
                            evade_bonus=_evade_bonus,
                            hit_chances=_weapon_hit_chances,
                            flee_chance=calc_flee_chance(
                                player_state["piloting"],
                                _closest_enemy.pilot_piloting,
                                player_state["hull"] / max(player_state["max_hull"], 1),
                                _distance(player_state["pos"], _closest_enemy.pos),
                                flee_attempts,
                            ),
                        )

                        if _is_hit:
                            _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
                                _fwid,
                                _target_enemy.hull,
                                _target_enemy.shields,
                                target_pilot_piloting=_target_enemy.pilot_piloting,
                            )
                            _target_enemy.shields = max(0, _target_enemy.shields - _sdmg)
                            _target_enemy.hull = _fh
                            _verb = "glancing hit" if _is_glancing else "hits"
                            _p_log(f"{_fwid} {_verb} {_target_enemy.name} for {_dmg}!")
                            if _fh <= 0:
                                _target_enemy.alive = False
                                _defeated_spec_ids.append(_target_enemy.spec_id)
                                _c_log(f"{_target_enemy.name} destroyed!")
                                _cam_x, _cam_y = _calc_cam()
                                _animate_explosion(
                                    console, context, game_map,
                                    _target_pos,
                                    cam_x=_cam_x, cam_y=_cam_y,
                                    view_w=view_w, view_h=view_h,
                                    player_state=player_state,
                                    enemies=enemy_insts,
                                    target_idx=target_idx,
                                    log=log,
                                    weapon_list=tuple(weapons_list),
                                    active_weapons=active_weapons,
                                    evade_bonus=_evade_bonus,
                                    hit_chances=_weapon_hit_chances,
                                    flee_chance=calc_flee_chance(
                                        player_state["piloting"],
                                        _closest_enemy.pilot_piloting,
                                        player_state["hull"] / max(player_state["max_hull"], 1),
                                        _distance(player_state["pos"], _closest_enemy.pos),
                                        flee_attempts,
                                    ),
                                )
                                # Loot drop
                                _spec_loot = getattr(enemy_specs[0], 'cargo_goods', None) or ()
                                _loot_items = list(_spec_loot)
                                if not _loot_items:
                                    _loot_items = ["scrap_metal"]
                                _drop_count = min(len(_loot_items), RNG.randint(1, 2))
                                for _li in range(_drop_count):
                                    _loot_id = RNG.choice(_loot_items)
                                    _lx = _target_pos.x + RNG.randint(-1, 1)
                                    _ly = _target_pos.y + RNG.randint(-1, 1)
                                    if not game_map.is_walkable(_lx, _ly):
                                        _lx, _ly = _target_pos.x, _target_pos.y
                                    game_map.entities.append(world.Entity(
                                        x=_lx, y=_ly, char="%",
                                        fg=(255, 215, 0),
                                        name="Loot",
                                        blocks_movement=False,
                                        loot_data={_loot_id: RNG.randint(1, 3)},
                                    ))
                        else:
                            _p_log(f"{_fwid} misses {_target_enemy.name}!")
                        # Deduct per-weapon costs
                        if _fws.slot_type == "energy":
                            player_state["power_pool"] -= _fws.power_cost
                        elif _fws.slot_type == "missile":
                            old = player_state["weapon_ammo"][_fwid]
                            player_state["weapon_ammo"][_fwid] = old - _fws.ammo_per_shot
                    # Deduct combined AP (max cost among fired weapons)
                    player_state["ap_remaining"] -= _max_ap
                    break

                # [1]–[9] -> Toggle weapon on/off
                _num_keys = {
                    "1": 0, "2": 1, "3": 2, "4": 3, "5": 4,
                    "6": 5, "7": 6, "8": 7, "9": 8,
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

    Returns (ok, reason_message). Used by both single-fire (space)
    and burst-fire (f) paths so the conditions can't drift apart.
    """
    if not (0 <= target_idx < len(enemies) and enemies[target_idx].alive):
        return False, "No valid target."
    return can_afford_action(player_state, weapon_id)
