"""Entry point for spacehack.

Run with ``python -m spacehack``.

Flow on a new game:

    species menu  ->  class menu  ->  confirm  ->  game (city + HUD + msg log)
       ^ ESC = quit       ^ ESC = back     ^ ESC = back        ^ ESC = quit

The game screen is a small city + space-port + 4 guild halls.
Movement uses the standard roguelike vim keys
(``h`` / ``j`` / ``k`` / ``l`` for cardinals, ``y`` / ``u`` / ``b`` / ``n``
for diagonals). Walking into a wall logs a short message. Walking
onto a tile holding another entity opens a context dialog:

    * ship at the space port -> ship-buy modal (Enter / ESC)
    * guild NPC -> flavor dialog (ESC to leave)
    * anything else -> "You bump into X" log line
"""
from __future__ import annotations
import time
import math
from enum import Enum, auto
import tcod.console
import tcod.context
import tcod.event
from . import character
from . import hud
from . import message_log
from . import mission as mission_module
from . import ship as ship_module
from . import solar_system as solar_system_module
from . import ui
from .game_context import GameContext
from . import faction
from .data import solar_systems as solar_systems_module
from . import npc as npc_module
from .data.species import find_species
from .data.classes import find_class
from .npc import TalkOutcome, _run_npc_talk
from . import world
from . import combat
from .combat._rules_ground import init as _ground_init
from .combat._loop import run_combat as _run_combat_unified
from .combat import _rules_ground
from .xp import add_xp as _add_xp
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, WINDOW_TITLE, load_tileset, make_console, open_terminal, seed_rng, should_quit
from .input_helpers import Outcome, _run_pick, _run_confirm, _vim_action, _is_q_press, _is_m_press, _is_period_press, _is_g_press, _is_i_press, _is_t_press, _is_f_press, _is_c_press, _is_shift_x_press, _try_open_guide
from .menus import (
    ShipBuyOutcome, ShipMenuAction, PlanetMenuOutcome,
    MissionOutcome, QuestLogOutcome,
    render_ship_buy, update_ship_buy, _run_ship_buy,
    _offerings_to_menu, render_mission_offerings, update_mission_offerings,
    _mission_navigate, _run_mission_offerings,
    render_quest_log, update_quest_log, _run_quest_log,
    render_ship_menu, _ship_menu_navigate, update_ship_menu, _run_ship_menu,
    _run_mech_menu,
    _run_planet_menu,
)
from .navigation import (
    JumpMenuOutcome, GotoOutcome, NavigationOutcome,
    _render_aoi_panel,
    render_navigation, update_navigation, _run_navigation,
    _nearest_body_name,
    _add_bounty_spawns_to_map,
    _remove_bounty_spawn,
    _detect_combat_encounter,
    _check_auto_comms_warning,
    _run_goto,
    render_jump_menu, update_jump_menu, _run_jump_menu,
    _run_cargo_scan,
    _responsive_sleep,
    _animate_jump,
    _jump_to_system,
)
from .city import _animate_ship_to_y, _launch_to_space
from .time import tick_move, add_days_to_date
from .saveload import save_game as _save_game
from .npc_ships import move_npcs as _move_npcs, render_npc_flash_events


# ---------------------------------------------------------------------------
# Space-mode helpers (combat + NPC movement shared by multiple input paths)
# ---------------------------------------------------------------------------

def _run_combat_loop(ctx, console, player, *, also_move_npcs: bool = False) -> None:
    """Run combat encounters in a loop until no more are detected.

    Checks auto-comms warnings, runs the detection→combat loop, and
    optionally moves NPCs afterward.  Combat handlers mutate
    ``ctx.player_active_missions`` in place — callers sync their
    local copy after this returns.
    """
    _auto_result = _check_auto_comms_warning(
        ctx, player.pos, solar_system_module.current_system(),
    )
    if _auto_result is not None:
        _, _attack_data = _auto_result
        if _attack_data is not None:
            combat._handle_combat_encounter(ctx, console, _attack_data)

    while True:
        _encounter = _detect_combat_encounter(
            ctx, player.pos, solar_system_module.current_system(),
        )
        if _encounter is None:
            break
        _result = combat._handle_combat_encounter(ctx, console, _encounter)
        if _result != "VICTORY":
            break

    if also_move_npcs:
        _move_npcs(ctx, ctx.game_map)


# --- End space-mode helpers ---

def _bounty_landmarks(system) -> list[world.Position]:
    """Return one spawn position per landmark (planet, gate, station)
    in ``system``, ordered by distance from the system centre."""
    _positions: list[world.Position] = []
    # Non-sun planets — offset east of each planet.
    for p in system.planets:
        if getattr(p, 'sun', False):
            continue
        sx = p.pos.x + p.width + 3
        sy = p.pos.y + p.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            _positions.append(world.Position(sx, sy))
    # Jump gates — offset east of each gate.
    for jp in system.jump_points:
        sx = jp.pos.x + jp.width + 6
        sy = jp.pos.y + jp.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            _positions.append(world.Position(sx, sy))
    # Stations — offset east of each station.
    for st in getattr(system, 'stations', ()) or ():
        sx = st.pos.x + st.width + 3
        sy = st.pos.y + st.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            _positions.append(world.Position(sx, sy))
    # Sort by distance from system centre for deterministic order.
    _cx, _cy = system.width // 2, system.height // 2
    _positions.sort(key=lambda p: (p.x - _cx) ** 2 + (p.y - _cy) ** 2)
    return _positions


def _pick_bounty_spawn_pos(
    system, *,
    used_positions: frozenset = frozenset(),
) -> world.Position | None:
    """Return a free-space position in ``system`` for placing a bounty
    target enemy. Picks the first unused landmark position (sorted by
    distance from system centre). Returns ``None`` if all landmarks in
    the system are already occupied by other bounty spawns — the
    player must clear an existing bounty before another can spawn here.
    """
    for _pos in _bounty_landmarks(system):
        if (_pos.x, _pos.y) not in used_positions:
            return _pos
    return None


def _run_game(
    context: tcod.context.Context,
    species_id: str = "",
    class_id: str = "",
    *,
    loaded_ctx: GameContext | None = None,
) -> None:
    """Render the small city + HUD + msg log and handle vim movement.

    Walking into a wall logs a short message. Walking into a
    non-interactable entity logs a "bump" message. Walking into
    a ship (at the space port) opens the ship-buy modal; walking
    into a guild NPC opens the flavor-talk modal.

    When ``loaded_ctx`` is provided (Continue path), setup is
    skipped and the game resumes from the saved state.
    """
    map_w = SCREEN_WIDTH - HUD_WIDTH
    map_h = SCREEN_HEIGHT - MSG_LOG_HEIGHT
    console = make_console()

    if loaded_ctx is not None:
        # --- Resume from save ---
        ctx = loaded_ctx
        game_map = ctx.game_map
        player = ctx.player
        stats = ctx.stats
        log = ctx.log
        player_owned_ship = ctx.player_owned_ship
        player_active_missions = ctx.player_active_missions
        character_info = ctx.character_info
        current_city_id: str = ctx.current_city_id
        current_mode = getattr(ctx, '_loaded_mode', 'city')
        if current_mode == 'dungeon':
            # Restore space map/player for exit path back to ship.
            space_game_map = getattr(ctx, '_space_game_map', None)
            space_player = getattr(ctx, '_space_player', None)
        elif current_mode == 'space':
            pass  # city map is built fresh on landing — no cache needed
        else:
            city_game_map = game_map
            city_player = player
    else:
        # --- New game setup ---
        species = find_species(species_id)
        klass = find_class(class_id)
        CITY_WIDTH, CITY_HEIGHT = (60, 40)
        game_map = world.make_city(width=CITY_WIDTH, height=CITY_HEIGHT)
        player = world.Entity(char='@', fg=(255, 255, 255), pos=world.Position(x=CITY_WIDTH // 2, y=CITY_HEIGHT // 2), name='Player')
        game_map.entities.append(player)
        stats = character.starting_stats(species_id, class_id)
        log = message_log.MessageLog(capacity=MSG_LOG_HEIGHT)
        log.add(f'You arrive in a quiet Earth city as a {species.name} {klass.name}.')
        log.add("The cobblestones are damp from last night's rain.")
        log.add('Walk with h / j / k / l; diagonals y / u / b / n.')
        log.add('Your starter ship is docked at the space port.')
        log.add('Buildings: North-West space port, South-West merchant guild,')
        log.add('Bar in the plaza, militia + bounty guild on the South-East.')
        log.add('Visit the guild halls to find work or the port to upgrade your ship.')
        # Give the player a free starter ship.
        starter_ship = ship_module.find_ship("starter")
        starter_entity = world.Entity(
            char=starter_ship.char, fg=starter_ship.fg,
            pos=world.HANGAR_ANCHOR,
            name=f'Your Ship: {starter_ship.name}',
            ship_id=starter_ship.id, owned=True,
        )
        game_map.entities.append(starter_entity)
        player_owned_ship: ship_module.OwnedShip = ship_module.OwnedShip(
            ship_id=starter_ship.id,
            weapons=starter_ship.start_weapons,
            modules=starter_ship.start_modules,
            fuel=starter_ship.max_fuel,
        )
        # --- Dev mode: super-powered frigate for playtesting ---
        from .dev_mode import apply_dev_overrides as _apply_dev_overrides
        starter_ship, starter_entity, player_owned_ship = _apply_dev_overrides(
            starter_ship, starter_entity, player_owned_ship, stats, log,
        )
        player_active_missions: list[mission_module.ActiveMission] = []
        character_info = {'species_id': species_id, 'species_name': species.name, 'class_id': class_id, 'class_name': klass.name}
        ctx = GameContext(context=context, character_info=character_info, log=log, game_map=game_map, player=player, stats=stats, player_owned_ship=player_owned_ship, player_active_missions=player_active_missions)
        ctx.faction_reputation = faction.starting_reputation(species_id, class_id)
        ctx.ground_stats = character.starting_ground_stats(species_id, class_id)
        ctx.ground_max_hp = 20 + ctx.ground_stats.stamina * 2
        ctx.ground_hp = ctx.ground_max_hp
        city_game_map = game_map
        city_player = player
        current_mode: str = 'city'
        current_city_id: str = 'earth'
        # Reset module-level solar system state so a prior continue
        # session's system doesn't leak into a fresh game.
        solar_system_module.set_current_solar_system("sol")

    # --- Space state for dungeon boarding ---
    # NOTE: These are bare annotations, NOT assignments with = None.
    # The = None at the end would overwrite the loaded values from
    # ctx._space_game_map / ctx._space_player in the load path above
    # (lines ~197-198), causing the dungeon exit check to always fail
    # on a loaded save because both variables would be None.
    #
    # Both variables are assigned by the three paths that need them:
    #   - _launch_to_space return value (city → space transition)
    #   - boarding a derelict (space → dungeon transition)
    #   - loading a dungeon save (ctx._space_game_map / ctx._space_player)
    space_game_map: world.GameMap | None
    space_player: world.Entity | None

    # --- Main game loop ---
    while True:
        if ctx.player_dead:
            return
        console.clear()
        if current_mode == 'space':
            sys_now = solar_system_module.current_system()
            sol_w = sys_now.width
            sol_h = sys_now.height
            view_w = solar_system_module.SOL_VIEW_W
            view_h = solar_system_module.SOL_VIEW_H
            cam_x = max(0, min(player.pos.x - view_w // 2, sol_w - view_w))
            cam_y = max(0, min(player.pos.y - view_h // 2, sol_h - view_h))
            world.render_world_view(console, game_map, region_x=0, region_y=0, region_w=view_w, region_h=view_h, camera_x=cam_x, camera_y=cam_y)
            render_npc_flash_events(console, ctx, cam_x, cam_y, view_w, view_h)
        else:
            world.render_world(console, game_map, region_x=0, region_y=0, region_w=map_w, region_h=map_h)
        if current_mode == 'space':
            _location = solar_system_module.current_system().name
        elif current_mode == 'dungeon':
            _location = getattr(game_map, 'location_name', 'Derelict Ship')
        else:
            _location = current_city_id.replace('_', ' ').title()
        # Detect available terminals on the current city map.
        _has_trade = any(e.trade_terminal for e in game_map.entities) if current_mode == 'city' else False
        _has_mech = any(e.mech_terminal for e in game_map.entities) if current_mode == 'city' else False
        _has_armory = any(e.armory_terminal for e in game_map.entities) if current_mode == 'city' else False
        hud.render_hud(console, ctx, screen_width=SCREEN_WIDTH, hud_view_height=map_h, location=_location, has_trade_terminal=_has_trade, has_mech_terminal=_has_mech, has_armory_terminal=_has_armory)
        message_log.render_message_log(console, log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        ctx.context.present(console)
        for event in tcod.event.wait():
            if should_quit(event):
                if current_mode == 'dungeon':
                    _save_game(ctx, mode='dungeon', city_id=current_city_id,
                               system_id=solar_system_module.current_solar_system_id,
                               space_player_pos=(space_player.pos.x, space_player.pos.y)
                               if space_player else None)
                else:
                    _save_game(ctx, mode=current_mode, city_id=current_city_id,
                               system_id=solar_system_module.current_solar_system_id)
                return
            # ? = open game guide (checked early so it can't be shadowed).
            if _try_open_guide(event, ctx):
                continue
            # Shift+X = dev mode XP (only when SPACEHACK_DEV is set).
            if _is_shift_x_press(event):
                import os as _os
                if _os.environ.get("SPACEHACK_DEV"):
                    _add_xp(ctx, 200)
                continue
            # F = faction standings (city or space).
            if _is_f_press(event):
                from .menus._ship_menu import _run_faction_view
                _run_faction_view(ctx)
                continue
            # C = Character screen (city or space).
            if _is_c_press(event):
                from .character_screen import open_character_screen
                open_character_screen(ctx)
                continue
            if _is_q_press(event):
                outcome, abandoned_idx = _run_quest_log(ctx)
                if outcome is QuestLogOutcome.QUIT:
                    return
                if outcome is QuestLogOutcome.ABANDONED and abandoned_idx is not None:
                    if 0 <= abandoned_idx < len(player_active_missions):
                        abandoned = player_active_missions[abandoned_idx]
                        log.add(f'You abandoned: {abandoned.title}.')
                        mission_module.abort_mission(abandoned, player_owned_ship, log)
                        # Return static mission to the giver's board if possible.
                        if not abandoned.is_procedural:
                            try:
                                _spec = mission_module.find_mission(abandoned.mission_id)
                                _board = ctx.mission_boards.get(_spec.giver_npc_id)
                                if _board is not None:
                                    mission_module.board_return_static(
                                        _board, abandoned.mission_id,
                                    )
                            except KeyError:
                                pass
                        if abandoned.bounty_spawn_id is not None:
                            _remove_bounty_spawn(
                                ctx,
                                abandoned.bounty_spawn_id,
                                abandoned.target_system_id,
                            )
                        del player_active_missions[abandoned_idx]
                        ctx.player_active_missions = player_active_missions
                continue
            if current_mode == 'space' and _is_m_press(event):
                outcome = _run_navigation(ctx, player.pos)
                if outcome is NavigationOutcome.QUIT:
                    return
                continue
            if current_mode == 'space' and _is_g_press(event):
                _goto_outcome, _goto_combat = _run_goto(ctx, player)
                if _goto_outcome is GotoOutcome.COMBAT and _goto_combat is not None:
                    combat._handle_combat_encounter(ctx, console, _goto_combat)
                    _run_combat_loop(ctx, console, player)
                    player_active_missions = ctx.player_active_missions
                continue
            # C = open cargo menu (space mode).
            if current_mode == 'space' and _is_i_press(event):
                from .trade import open_cargo as _open_cargo
                _open_cargo(ctx)
                continue
            # T = open comms panel (space mode).
            if current_mode == 'space' and _is_t_press(event):
                from .comms import open_comms as _open_comms
                _attack_data = _open_comms(ctx, player.pos)
                if _attack_data is not None:
                    combat._handle_combat_encounter(ctx, console, _attack_data)
                    player_active_missions = ctx.player_active_missions
                continue
            # Period = wait one turn (space mode: NPCs move, shields regen).
            if _is_period_press(event):
                if current_mode == 'space' and (player_owned_ship is not None):
                    _run_combat_loop(ctx, console, player, also_move_npcs=True)
                    player_active_missions = ctx.player_active_missions
                ctx.log.add('You wait.')
                continue

            delta = _vim_action(event)
            if delta is None:
                continue
            dx, dy = delta
            code, blocker = world.try_move(player, game_map, dx, dy)
            if code == 'moved' and current_mode == 'space' and (player_owned_ship is not None):
                _run_combat_loop(ctx, console, player, also_move_npcs=True)
                player_active_missions = ctx.player_active_missions
                tick_move(ctx)
            if code == 'moved' and current_mode == 'dungeon':
                # Reveal fog around new position (using current sight radius)
                from .dungeon import reveal_around as _reveal_around
                _reveal_around(game_map, player.pos, radius=game_map.sight_radius)
                # Check for ground combat (sight-based detection)
                from .dungeon import _detect_ground_combat as _dgc
                _hostile = _dgc(ctx, game_map, player.pos)
                if _hostile is not None:
                    _ground_init(ctx, _hostile, game_map)
                    _ground_result = _run_combat_unified(console, ctx, game_map, _rules_ground)
                    if _ground_result.outcome == "DEFEAT":
                        return
                    # After combat, refresh the map render
                    continue
                # Check if player walked onto the exit tile
                _tile = game_map.tiles[player.pos.y][player.pos.x]
                if _tile.kind == 'exit':
                    if space_game_map is not None and space_player is not None:
                        game_map = space_game_map
                        player = space_player
                        ctx.game_map = game_map
                        ctx.player = player
                        current_mode = 'space'
                        log.add('You exit through the hull breach and return to your ship.')
                        continue
            if code == 'wall':
                if current_mode == 'space':
                    target_x = player.pos.x + dx
                    target_y = player.pos.y + dy
                    if game_map.in_bounds(target_x, target_y):
                        station_id = solar_system_module.station_id_at(target_x, target_y)
                        if station_id is None:
                            jp = solar_system_module.jump_point_at(target_x, target_y)
                            pid = solar_system_module.planet_id_at(target_x, target_y)
                        else:
                            station_for_bump = solar_system_module.find_station(station_id)
                            jp = None
                            pid = station_for_bump.city_planet_id
                        if jp is not None and jp.connects_to:
                            target_system_id, target_jp_id = jp.connects_to[0]
                            log.add(f'You approach {jp.name}.')
                            outcome = _run_jump_menu(ctx, jp, target_system_id)
                            if outcome is JumpMenuOutcome.JUMP:
                                ship_record_for_fuel = ship_module.find_ship(player_owned_ship.ship_id)
                                if player_owned_ship.fuel < ship_module.JUMP_FUEL_COST:
                                    log.add(f'Not enough fuel! The jump requires {ship_module.JUMP_FUEL_COST} units; you have {player_owned_ship.fuel}.')
                                    continue
                                player_owned_ship.fuel -= ship_module.JUMP_FUEL_COST
                                log.add(f'Jump drive engaged. Fuel: {player_owned_ship.fuel} / {ship_record_for_fuel.max_fuel}.')
                                _animate_jump(ctx, console, ctx.player)
                                new_game_map, player = _jump_to_system(ctx=ctx, jp=jp, target_system_id=target_system_id, target_jp_id=target_jp_id)
                                game_map = new_game_map
                                ctx.game_map = game_map
                                ctx.player = player
                                continue
                        elif pid is not None:
                            planet_obj = solar_system_module.find_planet(pid)
                            log.add(f'You approach {planet_obj.name}.')
                            outcome = _run_planet_menu(ctx, planet_obj)
                            if outcome is PlanetMenuOutcome.EXPLORE:
                                from .data.planets import find_planet_spec as _fps
                                from .dungeon import load_layout as _load_layout, init_fog as _init_fog, reveal_around as _reveal_around
                                try:
                                    _pspec = _fps(pid)
                                    _layout_id = _pspec.dungeon_layout_id
                                    if not _layout_id:
                                        log.add(f"Nothing to explore on {planet_obj.name}.")
                                        continue
                                    _dungeon_map, _spawn = _load_layout(_layout_id)
                                except (FileNotFoundError, ValueError, KeyError):
                                    log.add(f"The surface of {planet_obj.name} is too hazardous to explore.")
                                    continue
                                _init_fog(_dungeon_map)
                                _reveal_around(_dungeon_map, _spawn)
                                _dungeon_player = world.Entity(
                                    char='@', fg=(255, 255, 255),
                                    pos=_spawn, name='Player',
                                )
                                _dungeon_map.entities.append(_dungeon_player)
                                _dungeon_map.location_name = f"{planet_obj.name} Surface"
                                space_game_map = game_map
                                space_player = player
                                game_map = _dungeon_map
                                player = _dungeon_player
                                ctx.game_map = game_map
                                ctx.player = player
                                current_mode = 'dungeon'
                                log.add(f'You descend to the surface of {planet_obj.name}.')
                                continue
                            if outcome is PlanetMenuOutcome.LAND:
                                # Shared: runs on ANY landing.
                                _run_cargo_scan(ctx, pid)
                                from .data.planets import load_planet as _plp, hangar_anchor as _phang, has_landable_port as _phlp
                                if not _phlp(pid):
                                    log.add(f'You see no port on {planet_obj.name}.')
                                    continue
                                # Always build the city map fresh — no cache needed.
                                _new_city_map = _plp(pid)
                                _anchor = _phang(pid)
                                # Create fresh city player.
                                _new_city_player = world.Entity(
                                    char='@', fg=(255, 255, 255),
                                    pos=world.Position(_anchor.x, _anchor.y + 1),
                                    name='Player',
                                )
                                # Create fresh hangar ship from player_owned_ship,
                                # place offscreen, animate down to anchor.
                                # NOTE: Player @ is NOT appended until AFTER the
                                # animation — otherwise @ would appear at the dock
                                # before the ship finishes descending.
                                if player_owned_ship is not None:
                                    _ship_spec = ship_module.find_ship(player_owned_ship.ship_id)
                                    _hangar_ship = world.Entity(
                                        char=_ship_spec.char, fg=_ship_spec.fg,
                                        pos=world.Position(_anchor.x, -(solar_system_module.SOL_VIEW_H // 2) - 1),
                                        name=f'Your Ship: {_ship_spec.name}',
                                        ship_id=_ship_spec.id, owned=True,
                                    )
                                    _new_city_map.entities.append(_hangar_ship)
                                    _animate_ship_to_y(ctx, console, _hangar_ship, _new_city_map, target_y=_anchor.y, location=pid.replace('_', ' ').title())
                                    log.add(f'You touch down on {planet_obj.name}.')
                                # NOW add the player — animation is done, ship is at anchor.
                                _new_city_map.entities.append(_new_city_player)
                                # Leaving space mode — reset the comms warning for
                                # this system so it fires again on the next visit.
                                ctx.militia_warned_systems.discard(
                                    solar_system_module.current_solar_system_id,
                                )
                                city_game_map = _new_city_map
                                city_player = _new_city_player
                                game_map = _new_city_map
                                player = _new_city_player
                                ctx.game_map = game_map
                                ctx.player = player
                                current_city_id = pid
                                current_mode = 'city'
                                # Auto-save after landing.
                                _save_game(ctx, mode=current_mode, city_id=current_city_id,
                                           system_id=solar_system_module.current_solar_system_id)
                            continue
                log.add('A wall blocks your path.')
            elif code == 'occupied':
                if blocker.ship_id:
                    ship = ship_module.find_ship(blocker.ship_id)
                    if blocker.owned:
                        result = _run_ship_menu(ctx, ship)
                        if result is ShipMenuAction.QUIT:
                            return
                        if result is ShipMenuAction.LAUNCH and player_owned_ship is not None:
                            hangar_ship = next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)
                            if hangar_ship is not None:
                                space_game_map, space_player_entity = _launch_to_space(ctx, console, city_game_map, hangar_ship, ship, current_city_id=current_city_id, city_player=city_player)
                                game_map = space_game_map
                                player = space_player_entity
                                ctx.game_map = game_map
                                ctx.player = player
                                current_mode = 'space'
                            continue
                    else:
                        # Trade-in: if the player already owns a ship, compute its value.
                        _trade_in_value = 0
                        if player_owned_ship is not None:
                            _old_ship = ship_module.find_ship(player_owned_ship.ship_id)
                            _trade_in_value = max(0, _old_ship.price // 2)
                        _effective_price = max(0, ship.price - _trade_in_value)
                        result = _run_ship_buy(ctx, blocker, ship, effective_price=_effective_price)
                        if result is ShipBuyOutcome.QUIT:
                            return
                        if result is ShipBuyOutcome.BUY:
                            if ctx.stats.credits < _effective_price:
                                short = _effective_price - ctx.stats.credits
                                log.add(f'Including trade-in ({_trade_in_value}$) you need {_effective_price}$, but you are {short}$ short.')
                                continue
                            stats.credits -= _effective_price
                            # Remove the old owned entity from the city, if any.
                            if player_owned_ship is not None:
                                _old_entity = next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)
                                if _old_entity is not None:
                                    try:
                                        city_game_map.entities.remove(_old_entity)
                                    except ValueError:
                                        pass
                            # Place the new ship in the hangar.
                            blocker.pos = world.HANGAR_ANCHOR
                            blocker.owned = True
                            blocker.name = f'Your Ship: {ship.name}'
                            # Preserve mission cargo from the old ship.
                            _old_reserved = player_owned_ship.mission_reserved if player_owned_ship is not None else 0
                            player_owned_ship = ship_module.OwnedShip(ship_id=ship.id, weapons=ship.start_weapons, modules=ship.start_modules, fuel=ship.max_fuel, mission_reserved=_old_reserved)
                            # Warn if the new ship can't hold mission cargo.
                            _new_cap = ship_module.effective_max_cargo(ship, player_owned_ship)
                            if _old_reserved > _new_cap:
                                log.add(f'WARNING: {ship.name} cannot hold your mission cargo ({_old_reserved}/{_new_cap}). Some missions may be undeliverable.')
                            ctx.player_owned_ship = player_owned_ship
                            if _trade_in_value > 0:
                                log.add(f'Traded in for the {ship.name} — paid {_effective_price}$ (trade-in {_trade_in_value}$).')
                            else:
                                log.add(f'You bought the {ship.name} for {ship.price}$ and parked it in your hangar.')
                        elif result is ShipBuyOutcome.TOO_EXPENSIVE:
                            short = _effective_price - ctx.stats.credits
                            log.add(f'You cannot afford the {ship.name} — need {_effective_price}$ (including {_trade_in_value}$ trade-in), {short}$ short.')
                elif blocker.loot_data:
                    from .trade import open_loot_pickup as _open_loot
                    _open_loot(ctx, blocker)
                elif blocker.trade_terminal:
                    from .trade import open_trade as _open_trade
                    _open_trade(ctx, current_city_id)
                elif blocker.mech_terminal:
                    _run_mech_menu(ctx, current_city_id)
                    continue
                elif blocker.armory_terminal:
                    from .menus._armory import _run_armory_menu
                    _run_armory_menu(ctx, current_city_id)
                    continue
                elif blocker.computer_terminal:
                    if current_mode == 'dungeon':
                        from . import ui as _ui
                        _comp_console = make_console()
                        def _comp_render():
                            _comp_console.clear()
                            _comp_console.print(
                                x=_ui.centered_x("Ship Computer Terminal", SCREEN_WIDTH),
                                y=SCREEN_HEIGHT // 3,
                                string="Ship Computer Terminal",
                                fg=_ui.COLOR_TITLE,
                            )
                            _comp_console.print(
                                x=_ui.centered_x("Restore emergency power to the ship?", SCREEN_WIDTH),
                                y=SCREEN_HEIGHT // 3 + 2,
                                string="Restore emergency power to the ship?",
                                fg=_ui.COLOR_DESCRIPTION,
                            )
                            _comp_console.print(
                                x=_ui.centered_x("This will boost interior lighting and sensor range.", SCREEN_WIDTH),
                                y=SCREEN_HEIGHT // 3 + 3,
                                string="This will boost interior lighting and sensor range.",
                                fg=_ui.COLOR_VALUE_DIM,
                            )
                            _comp_console.print(
                                x=_ui.centered_x("ENTER to activate  |  ESC to leave", SCREEN_WIDTH),
                                y=SCREEN_HEIGHT // 3 + 5,
                                string="ENTER to activate  |  ESC to leave",
                                fg=_ui.COLOR_INSTRUCTION,
                            )
                        def _comp_update(event):
                            if isinstance(event, tcod.event.Quit):
                                return _ui.MenuAction.CONFIRM
                            if not isinstance(event, tcod.event.KeyDown):
                                return _ui.MenuAction.NONE
                            if event.sym in _ui._ENTER_SYMS:
                                return _ui.MenuAction.CONFIRM
                            if event.sym in _ui._ESCAPE_SYMS:
                                return _ui.MenuAction.BACK
                            return _ui.MenuAction.NONE
                        _comp_result = ui.Modal(ctx.context, _comp_console).run(_comp_render, _comp_update, ignore=_ui.MenuAction.NONE)
                        if _comp_result == ui.MenuAction.CONFIRM:
                            if getattr(game_map, 'power_restored', False):
                                log.add("The ship's power grid is already online.")
                            else:
                                game_map.sight_radius = 20
                                game_map.power_restored = True
                                from .dungeon import reveal_around as _r2
                                _r2(game_map, player.pos, radius=20)
                                log.add_colored("Emergency power restored. Interior sensors online.",
                                                 message_log.COLOR_IMPORTANT_EVENT)
                        continue
                    log.add(f'You bump into {blocker.name}.')
                elif blocker.npc_ship_id:
                    from .data.npc_ships import find_npc_ship as _find_ship
                    try:
                        _npcspec = _find_ship(blocker.npc_ship_id)
                        if _npcspec.is_boardable:
                            # Show board dialog
                            _board_console = make_console()
                            def _board_render():
                                _board_console.clear()
                                _board_console.print(
                                    x=ui.centered_x(f"Board the {_npcspec.name}?", SCREEN_WIDTH),
                                    y=SCREEN_HEIGHT // 3,
                                    string=f"Board the {_npcspec.name}?",
                                    fg=ui.COLOR_TITLE,
                                )
                                _board_console.print(
                                    x=ui.centered_x("ENTER to board - ESC to fly past", SCREEN_WIDTH),
                                    y=SCREEN_HEIGHT // 3 + 2,
                                    string="ENTER to board - ESC to fly past",
                                    fg=ui.COLOR_INSTRUCTION,
                                )
                            def _board_update(event):
                                if isinstance(event, tcod.event.Quit):
                                    return PlanetMenuOutcome.QUIT
                                if not isinstance(event, tcod.event.KeyDown):
                                    return PlanetMenuOutcome.IGNORE
                                if event.sym in ui._ENTER_SYMS:
                                    return PlanetMenuOutcome.LAND
                                if event.sym in ui._ESCAPE_SYMS:
                                    return PlanetMenuOutcome.BACK
                                return PlanetMenuOutcome.IGNORE
                            _board_result = ui.Modal(ctx.context, _board_console).run(_board_render, _board_update)
                            if _board_result == PlanetMenuOutcome.QUIT:
                                return
                            if _board_result == PlanetMenuOutcome.LAND:
                                from .dungeon import load_layout as _load_layout, animate_breach as _animate_breach, init_fog as _init_fog, reveal_around as _reveal_around
                                try:
                                    _dungeon_map, _spawn = _load_layout(
                                        "scout_a",
                                        loot_budget=_npcspec.loot_budget,
                                    )
                                except (FileNotFoundError, ValueError):
                                    log.add("The derelict's interior is too damaged to explore.")
                                    continue
                                # Despawn the derelict from the space map —
                                # once boarded, it's consumed.
                                try:
                                    ctx.game_map.entities.remove(blocker)
                                    # Also clean up its procedural spawn entry
                                    _sys_id = solar_system_module.current_solar_system_id
                                    if _sys_id in ctx.procedural_spawns:
                                        ctx.procedural_spawns[_sys_id] = [
                                            _ps for _ps in ctx.procedural_spawns[_sys_id]
                                            if _ps.npc_id != _npcspec.id
                                            or _ps.pos != blocker.pos
                                        ]
                                except (ValueError, AttributeError):
                                    pass
                                # Initialize fog of war
                                _init_fog(_dungeon_map)
                                _reveal_around(_dungeon_map, _spawn)
                                # Play breach animation before giving control
                                _dungeon_player = world.Entity(
                                    char='@', fg=(255, 255, 255),
                                    pos=_spawn, name='Player',
                                )
                                _dungeon_map.entities.append(_dungeon_player)
                                _animate_breach(ctx, console, _dungeon_map, _spawn,
                                                region_w=map_w, region_h=map_h)
                                _dungeon_map.location_name = _npcspec.name
                                space_game_map = game_map
                                space_player = player
                                game_map = _dungeon_map
                                player = _dungeon_player
                                ctx.game_map = game_map
                                ctx.player = player
                                current_mode = 'dungeon'
                                log.add(f'You cut through the hull and enter the {_npcspec.name}.')
                                continue
                            continue
                    except KeyError:
                        pass
                    log.add(f'You bump into {blocker.name}.')
                elif blocker.npc_id:
                    npc_obj = npc_module.find_npc(blocker.npc_id)
                    # Look up planet's mission tier for filtering offerings.
                    _planet_tier = 1
                    try:
                        from .data.planets import find_planet_spec as _fps
                        _planet_tier = _fps(current_city_id).mission_tier
                    except KeyError:
                        pass
                    # Find deliverable missions at this NPC+planet.
                    _deliverable = mission_module.find_deliverable_missions(
                        player_active_missions, npc_obj.id, current_city_id,
                    )
                    result, _deliver_mission = _run_npc_talk(
                        ctx, npc_obj, deliver_missions=_deliverable or None,
                    )
                    if result is TalkOutcome.QUIT:
                        return
                    if result is TalkOutcome.DELIVER:
                        if _deliver_mission is not None:
                            _today = ctx.time_day + (ctx.time_month - 1) * 30
                            mission_module.complete_mission(
                                _deliver_mission, player_owned_ship, stats, log,
                                current_day=_today, ctx=ctx,
                            )
                            if not _deliver_mission.is_procedural:
                                ctx.completed_mission_ids.add(_deliver_mission.mission_id)
                            try:
                                player_active_missions.remove(_deliver_mission)
                            except ValueError:
                                pass
                            ctx.player_active_missions = player_active_missions
                    if result is TalkOutcome.WORK:
                        # --- Faction reputation gating: enemy NPCs refuse work ---
                        _guild_name = getattr(npc_obj, 'guild', '')
                        if _guild_name:
                            from .faction import guild_to_faction, get_attitude
                            _npc_faction = guild_to_faction(_guild_name)
                            _npc_rep = ctx.faction_reputation.get(_npc_faction, 0)
                            if get_attitude(_npc_rep) == 'enemy':
                                log.add(f'{npc_obj.name} refuses to speak with you.')
                                continue

                        if len(player_active_missions) >= mission_module.MAX_ACTIVE_MISSIONS:
                            log.add(
                                f"Your mission log is full "
                                f"({mission_module.MAX_ACTIVE_MISSIONS}/"
                                f"{mission_module.MAX_ACTIVE_MISSIONS}). "
                                "Abandon one first (Q)."
                            )
                        else:
                            # Ensure board exists for this NPC on this planet.
                            _board = mission_module.ensure_board(
                                ctx, npc_obj.id, max_slots=5,
                                planet_id=current_city_id,
                            )
                            # Fill empty slots on first visit or month rollover.
                            _active_ids = frozenset(
                                m.mission_id for m in player_active_missions
                            )
                            _completed_ids = frozenset(ctx.completed_mission_ids)
                            if _board.last_refresh_month != ctx.time_month:
                                mission_module.fill_empty_slots(
                                    _board,
                                    planet_tier=_planet_tier,
                                    completed_ids=_completed_ids,
                                    active_ids=_active_ids,
                                    planet_id=current_city_id,
                                    generated=ctx.generated_missions,
                                    ctx=ctx,
                                )
                                _board.last_refresh_month = ctx.time_month
                            offerings = mission_module.board_offerings(
                                _board, generated=ctx.generated_missions,
                            )
                            if not offerings:
                                log.add(f'{npc_obj.name} has no work for you right now.')
                            else:
                                outcome, picked = _run_mission_offerings(ctx, npc_obj, offerings)
                                if outcome is MissionOutcome.ACCEPT and picked is not None:
                                    if mission_module.try_accept_mission(
                                        picked, player_owned_ship, log,
                                        active_count=len(player_active_missions),
                                    ):
                                        mission_module.board_remove(_board, picked.id)
                                        _bounty_spawn_id: str | None = None
                                        _spawn_ok = True  # non-bounty missions always proceed
                                        if picked.target_enemy_id is not None and picked.target_system_id is not None:
                                            _bounty_spawn_id = f"bounty_{picked.id}_{int(time.time())}"
                                            _squad_size = getattr(picked, 'bounty_target_squad_size', 1)
                                            try:
                                                _target_sys = solar_systems_module.find_solar_system(picked.target_system_id)
                                                _used = frozenset(
                                                    (_bs.pos.x, _bs.pos.y)
                                                    for _bs in ctx.bounty_spawns.get(picked.target_system_id, [])
                                                )
                                                _spawn_pos = _pick_bounty_spawn_pos(_target_sys, used_positions=_used)
                                                if _spawn_pos is not None:
                                                    from .game_context import BountySpawn
                                                    from .data.npc_ships import find_npc_ship as _bfns
                                                    # Compute a warning range wider than combat detection so
                                                    # the player gets warned before combat triggers.
                                                    _bounty_warning_range = 0
                                                    try:
                                                        _bounty_spec = _bfns(picked.target_enemy_id)
                                                        _bounty_warning_range = max(12, _bounty_spec.detect_radius * 2)
                                                    except (KeyError, ImportError):
                                                        pass
                                                    # Leader BountySpawn.
                                                    _bs = BountySpawn(
                                                        spawn_id=_bounty_spawn_id,
                                                        enemy_id=picked.target_enemy_id,
                                                        pos=_spawn_pos,
                                                        bounty_target_name=getattr(picked, 'bounty_target_name', None),
                                                        squad_size=_squad_size,
                                                        loadout_pct=getattr(picked, 'bounty_target_loadout_pct', 0),
                                                        comms_warning_range=_bounty_warning_range,
                                                    )
                                                    if picked.target_system_id not in ctx.bounty_spawns:
                                                        ctx.bounty_spawns[picked.target_system_id] = []
                                                    ctx.bounty_spawns[picked.target_system_id].append(_bs)
                                                    # Wingmate BountySpawns (squad_size > 1).
                                                    _wing_offsets = [(2, 0), (-2, 0), (0, 2), (0, -2)]
                                                    for _wi in range(min(_squad_size - 1, len(_wing_offsets))):
                                                        _wox, _woy = _wing_offsets[_wi]
                                                        _wpos = world.Position(_spawn_pos.x + _wox, _spawn_pos.y + _woy)
                                                        if 0 <= _wpos.x < _target_sys.width and 0 <= _wpos.y < _target_sys.height:
                                                            _wbs = BountySpawn(
                                                                spawn_id=f"{_bounty_spawn_id}_wing{_wi}",
                                                                enemy_id=picked.target_enemy_id,
                                                                pos=_wpos,
                                                                bounty_target_name=None,
                                                                squad_size=_squad_size,
                                                                loadout_pct=0,
                                                                squad_group_id=_bounty_spawn_id,
                                                                comms_warning_range=0,  # wingmates use viewport-based, not distance
                                                            )
                                                            ctx.bounty_spawns[picked.target_system_id].append(_wbs)
                                                    _squad_note = f" ({_squad_size}-ship squad)" if _squad_size > 1 else ""
                                                    log.add(f"Bounty target marked in {_target_sys.name}.{_squad_note}")
                                                else:
                                                    # All landmarks in the target system are occupied.
                                                    _spawn_ok = False
                                                    mission_module.board_return_static(_board, picked.id)
                                                    log.add(f"Cannot accept: {_target_sys.name} bounty system full. Clear an existing bounty first.")
                                            except KeyError:
                                                pass
                                        if _spawn_ok:
                                            # Compute deadline if mission has one.
                                            _dl_days = getattr(picked, 'deadline_days', 0)
                                            _deadline = None
                                            if _dl_days > 0:
                                                _deadline = add_days_to_date(
                                                    ctx.time_day, ctx.time_month,
                                                    ctx.time_year, _dl_days,
                                                )
                                            _is_proc = picked.id in ctx.generated_missions
                                            _new_active = mission_module.ActiveMission(
                                                mission_id=picked.id,
                                                is_procedural=_is_proc,
                                                title=picked.title,
                                                required_cargo_size=picked.required_cargo_size,
                                                delivery_target_npc_id=picked.delivery_target_npc_id,
                                                delivery_target_planet_id=picked.delivery_target_planet_id,
                                                deadline_days=_dl_days,
                                                accept_day=ctx.time_day + (ctx.time_month - 1) * 30,
                                                time_deadline=_deadline,
                                                reward_credits=picked.reward_credits,
                                                reward_xp=picked.reward_xp,
                                                early_bonus_pct=picked.early_bonus_pct,
                                                bounty_spawn_id=_bounty_spawn_id,
                                                target_enemy_id=picked.target_enemy_id,
                                                target_system_id=picked.target_system_id,
                                                bounty_target_name=getattr(picked, 'bounty_target_name', None),
                                                bounty_target_squad_size=getattr(picked, 'bounty_target_squad_size', 1),
                                                bounty_target_loadout_pct=getattr(picked, 'bounty_target_loadout_pct', 0),
                                                tier=picked.tier,
                                            )
                                            mission_module.commit_accept_mission(
                                                picked, player_owned_ship, log,
                                            )
                                            player_active_missions.append(_new_active)
                                            ctx.player_active_missions = player_active_missions
                else:
                    log.add(f'You bump into {blocker.name}.')

def run(context: tcod.context.Context) -> None:
    """Show title menu, then either new game or continue from save."""
    import os
    import struct
    _seed = struct.unpack('I', os.urandom(4))[0]
    seed_rng(_seed)
    # Show the title splash screen.
    ui.render_title_splash(context)
    console = make_console()
    while True:
        # --- Title menu ---
        from .saveload import save_exists as _has_save, load_game as _load, delete_save as _delete_save
        _sel = 0
        _save_avail = _has_save()
        _menu_outcome = ui.TitleMenuOutcome.IGNORE
        while _menu_outcome is ui.TitleMenuOutcome.IGNORE:
            console.clear()
            ui.render_title_menu(
                console, SCREEN_WIDTH, SCREEN_HEIGHT,
                selected=_sel, save_available=_save_avail,
            )
            context.present(console)
            for event in tcod.event.wait():
                if should_quit(event):
                    return
                _menu_outcome, _sel = ui.update_title_menu(
                    event, selected=_sel, save_available=_save_avail,
                )
                if _menu_outcome is not ui.TitleMenuOutcome.IGNORE:
                    break
        if _menu_outcome is ui.TitleMenuOutcome.EXIT:
            return
        if _menu_outcome is ui.TitleMenuOutcome.CONTINUE:
            _ctx = _load(context)
            if _ctx is not None:
                _delete_save()  # roguelike: no save scumming
                _run_game(context, loaded_ctx=_ctx)
            else:
                # Corrupted save — flash error then return to menu.
                console.clear()
                _msg = "Save file corrupted."
                console.print(
                    x=ui.centered_x(_msg, SCREEN_WIDTH),
                    y=SCREEN_HEIGHT // 2,
                    string=_msg, fg=(255, 100, 100),
                )
                context.present(console)
                import time as _time
                _time.sleep(1.0)
            continue
        # --- New Game: character creation ---
        while True:
            outcome, species_id = _run_pick(context, ui.species_menu())
            if outcome in (Outcome.QUIT, Outcome.BACK):
                break
            outcome, class_id = _run_pick(context, ui.class_menu())
            if outcome is Outcome.QUIT:
                break
            if outcome is Outcome.BACK:
                continue
            outcome = _run_confirm(context, species_id, class_id)
            if outcome is Outcome.QUIT:
                break
            if outcome is Outcome.BACK:
                continue
            # Fresh seed per run — standard roguelike behavior.
            _seed = struct.unpack('I', os.urandom(4))[0]
            seed_rng(_seed)
            _run_game(context, species_id, class_id)
            break
        # After game ends, loop back to title menu.
        continue

def main() -> None:
    """Top-level entry: load assets, open window, then run the flow."""
    tileset = load_tileset()
    with open_terminal(tileset) as context:
        run(context)
if __name__ == '__main__':
    main()
