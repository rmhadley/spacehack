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
from .data import solar_systems as solar_systems_module
from . import npc as npc_module
from .data.species import find_species
from .data.classes import find_class
from .npc import TalkOutcome, _run_npc_talk
from . import world
from . import combat
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, WINDOW_TITLE, load_tileset, make_console, open_terminal, seed_rng, should_quit
from .input_helpers import Outcome, _run_pick, _run_confirm, _vim_action, _is_q_press, _is_m_press, _is_period_press, _is_g_press, _is_c_press, _is_t_press, _try_open_guide
from .menus import (
    ShipBuyOutcome, ShipMenuAction, PlanetMenuOutcome,
    MissionOutcome, QuestLogOutcome,
    render_ship_buy, update_ship_buy, _run_ship_buy,
    _offerings_to_menu, render_mission_offerings, update_mission_offerings,
    _mission_navigate, _run_mission_offerings,
    render_quest_log, update_quest_log, _run_quest_log,
    render_ship_menu, _ship_menu_navigate, update_ship_menu, _run_ship_menu,
    _run_mech_menu,
    _find_hangar_ship,
    render_planet_menu, update_planet_menu, _run_planet_menu,
)
from .navigation import (
    JumpMenuOutcome, GotoOutcome, NavigationOutcome,
    _render_aoi_panel,
    render_navigation, update_navigation, _run_navigation,
    _nearest_body_name,
    _add_bounty_spawns_to_map,
    _detect_combat_encounter,
    _check_auto_comms_warning,
    _run_goto,
    render_jump_menu, update_jump_menu, _run_jump_menu,
    _run_cargo_scan,
    _responsive_sleep,
    _animate_jump,
    _jump_to_system,
)
from .city import _animate_ship_to_y, _launch_to_space, _return_to_city
from .time import advance_time, format_date

def _pick_bounty_spawn_pos(system) -> world.Position | None:
    """Return a free-space position in ``system`` for placing a bounty
    target enemy. Prefers a cell near the first non-sun planet, falling
    back to the first jump gate or a centre-of-map position.

    Returns ``None`` if the system has no bodies (shouldn't happen
    with the current data).
    """
    # Try first non-sun planet: offset by (planet.width + 3, 0) cells
    # so the bounty sits east of the planet in clear space.
    for p in system.planets:
        if getattr(p, 'sun', False):
            continue
        sx = p.pos.x + p.width + 3
        sy = p.pos.y + p.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            return world.Position(sx, sy)
    # Fallback: first jump gate
    for jp in system.jump_points:
        sx = jp.pos.x + jp.width + 6
        sy = jp.pos.y + jp.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            return world.Position(sx, sy)
    # Last resort: centre-ish of the map
    return world.Position(system.width // 2, system.height // 2)


def _remove_bounty_spawn(ctx, spawn_id: str, system_id: str | None) -> None:
    """Remove the bounty spawn with ``spawn_id`` from
    ``ctx.bounty_spawns[system_id]``, and from the current
    ``ctx.game_map.entities`` if the player is in that system.

    No-op if the spawn doesn't exist (e.g. was already removed).
    """
    if system_id is None or system_id not in ctx.bounty_spawns:
        return
    # Snapshot the spawn's position before filtering it out.
    _pos_to_remove = None
    for _bs in ctx.bounty_spawns[system_id]:
        if _bs.spawn_id == spawn_id:
            _pos_to_remove = _bs.pos
            break
    ctx.bounty_spawns[system_id] = [
        _bs for _bs in ctx.bounty_spawns[system_id]
        if _bs.spawn_id != spawn_id
    ]
    if _pos_to_remove is not None:
        # Also remove the matching entity from the game_map if the
        # player is currently in the spawn's system.
        _cur_sys = getattr(solar_system_module.current_system(), 'id', None)
        if _cur_sys == system_id and ctx.game_map is not None:
            _target_entity = None
            for _e in ctx.game_map.entities:
                if not getattr(_e, 'owned', False) and _e.pos == _pos_to_remove:
                    _target_entity = _e
                    break
            if _target_entity is not None:
                try:
                    ctx.game_map.entities.remove(_target_entity)
                except ValueError:
                    pass

def _run_game(context: tcod.context.Context, species_id: str, class_id: str) -> None:
    """Render the small city + HUD + msg log and handle vim movement.

    Walking into a wall logs a short message. Walking into a
    non-interactable entity logs a "bump" message. Walking into
    a ship (at the space port) opens the ship-buy modal; walking
    into a guild NPC opens the flavor-talk modal.
    """
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
    player_active_mission: mission_module.ActiveMission | None = None
    character_info = {'species_id': species_id, 'species_name': species.name, 'class_id': class_id, 'class_name': klass.name}
    ctx = GameContext(context=context, character_info=character_info, log=log, game_map=game_map, player=player, stats=stats, player_owned_ship=player_owned_ship, player_active_mission=player_active_mission)
    map_w = SCREEN_WIDTH - HUD_WIDTH
    map_h = SCREEN_HEIGHT - MSG_LOG_HEIGHT
    console = make_console()
    city_game_map = game_map
    city_player = player
    current_mode: str = 'city'
    current_city_id: str = 'earth'
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
            # Paint NPC flash events (jump gate spawn/despawn rings).
            if ctx.npc_flash_events:
                from .npc_ships import render_npc_flash_events
                render_npc_flash_events(console, ctx, cam_x, cam_y, view_w, view_h)
        else:
            world.render_world(console, game_map, region_x=0, region_y=0, region_w=map_w, region_h=map_h)
        active_mission_text = mission_module.find_mission(player_active_mission.mission_id).title if player_active_mission is not None else None
        _show_ship_hud = current_mode == 'space' and player_owned_ship is not None
        _ship_cat = ship_module.find_ship(ctx.player_owned_ship.ship_id) if _show_ship_hud else None
        if current_mode == 'space':
            _location = solar_system_module.current_system().name
        else:
            _location = current_city_id.replace('_', ' ').title()
        # Detect available terminals on the current city map.
        _has_trade = any(e.trade_terminal for e in game_map.entities) if current_mode == 'city' else False
        _has_mech = any(e.mech_terminal for e in game_map.entities) if current_mode == 'city' else False
        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=map_h, character=character_info, stats=stats, active_mission=active_mission_text, location=_location, owned_ship=player_owned_ship if _show_ship_hud else None, ship_catalog=_ship_cat, has_trade_terminal=_has_trade, has_mech_terminal=_has_mech, date_str=format_date(ctx))
        message_log.render_message_log(console, log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        ctx.context.present(console)
        for event in tcod.event.wait():
            if should_quit(event):
                return
            # ? = open game guide (checked early so it can't be shadowed).
            if _try_open_guide(event, ctx):
                continue
            if _is_q_press(event):
                outcome, new_active = _run_quest_log(ctx)
                if outcome is QuestLogOutcome.QUIT:
                    return
                if outcome is QuestLogOutcome.ABANDONED:
                    if player_active_mission is not None:
                        abandoned = mission_module.find_mission(player_active_mission.mission_id)
                        log.add(f'You abandoned: {abandoned.title}.')
                        mission_module.abort_mission(abandoned, player_owned_ship, log)
                        # Remove any bounty spawn associated with this mission.
                        if player_active_mission.bounty_spawn_id is not None:
                            _remove_bounty_spawn(
                                ctx,
                                player_active_mission.bounty_spawn_id,
                                abandoned.target_system_id,
                            )
                    player_active_mission = new_active
                    ctx.player_active_mission = new_active
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
                    # Sync local mission state — _handle_combat_encounter
                    # may have cleared ctx.player_active_mission (bounty
                    # auto-complete) but the local copy is stale.
                    player_active_mission = ctx.player_active_mission
                    # After combat, loop: re-check for more nearby enemies
                    # (e.g. a second squad that was just out of range
                    # initially). Keeps fighting until no more are detected.
                    while True:
                        _next_encounter = _detect_combat_encounter(ctx, player.pos, solar_system_module.current_system())
                        if _next_encounter is None:
                            break
                        _result = combat._handle_combat_encounter(ctx, console, _next_encounter)
                        player_active_mission = ctx.player_active_mission
                        if _result != "VICTORY":
                            break
                continue
            # C = open cargo menu (space mode).
            if current_mode == 'space' and _is_c_press(event):
                from .trade import open_cargo as _open_cargo
                _open_cargo(ctx)
                continue
            # T = open comms panel (space mode).
            if current_mode == 'space' and _is_t_press(event):
                from .comms import open_comms as _open_comms
                _attack_data = _open_comms(ctx, player.pos)
                if _attack_data is not None:
                    combat._handle_combat_encounter(ctx, console, _attack_data)
                    player_active_mission = ctx.player_active_mission
                continue
            # Period = wait one turn (space mode: pirates move, shields regen).
            if _is_period_press(event):
                if current_mode == 'space' and (player_owned_ship is not None):
                    _auto_result = _check_auto_comms_warning(ctx, player.pos, solar_system_module.current_system())
                    if _auto_result is not None:
                        _, _attack_data = _auto_result
                        if _attack_data is not None:
                            combat._handle_combat_encounter(ctx, console, _attack_data)
                            player_active_mission = ctx.player_active_mission
                    while True:
                        _encounter = _detect_combat_encounter(ctx, player.pos, solar_system_module.current_system())
                        if _encounter is None:
                            break
                        _result = combat._handle_combat_encounter(ctx, console, _encounter)
                        player_active_mission = ctx.player_active_mission
                        if _result != "VICTORY":
                            break
                    from .npc_ships import move_npcs as _mn
                    _mn(ctx, game_map)
                ctx.log.add('You wait.')
                continue

            delta = _vim_action(event)
            if delta is None:
                continue
            dx, dy = delta
            code, blocker = world.try_move(player, game_map, dx, dy)
            if code == 'moved' and current_mode == 'space' and (player_owned_ship is not None):
                _auto_result = _check_auto_comms_warning(ctx, player.pos, solar_system_module.current_system())
                if _auto_result is not None:
                    _, _attack_data = _auto_result
                    if _attack_data is not None:
                        combat._handle_combat_encounter(ctx, console, _attack_data)
                        player_active_mission = ctx.player_active_mission
                while True:
                    _encounter = _detect_combat_encounter(ctx, player.pos, solar_system_module.current_system())
                    if _encounter is None:
                        break
                    _result = combat._handle_combat_encounter(ctx, console, _encounter)
                    # Sync local mission state after combat.
                    player_active_mission = ctx.player_active_mission
                    if _result != "VICTORY":
                        break
                # Move procedural NPCs after the player moves.
                from .npc_ships import move_npcs as _mn
                _mn(ctx, game_map)
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
                                _animate_jump(ctx, console, ctx.player, active_mission_text=active_mission_text or '')
                                new_game_map, player = _jump_to_system(ctx=ctx, jp=jp, target_system_id=target_system_id, target_jp_id=target_jp_id)
                                game_map = new_game_map
                                ctx.game_map = game_map
                                ctx.player = player
                                continue
                        elif pid is not None:
                            planet_obj = solar_system_module.find_planet(pid)
                            log.add(f'You approach {planet_obj.name}.')
                            outcome = _run_planet_menu(ctx, planet_obj, active_mission_text=active_mission_text)
                            if outcome is PlanetMenuOutcome.LAND:
                                # Shared: runs on ANY landing.
                                _run_cargo_scan(ctx, pid)
                                advance_time(ctx, 1)
                                hangar_ship = _find_hangar_ship(city_game_map, player_owned_ship)

                                if pid == current_city_id:
                                    # Returning to current city — map is cached, just animate ship down.
                                    if hangar_ship is not None:
                                        game_map, player = _return_to_city(ctx, console, hangar_ship, city_game_map, city_player)
                                        current_mode = 'city'
                                else:
                                    # Landing on a new planet — load fresh map.
                                    from .data.planets import load_planet as planets_load_planet, hangar_anchor as planet_hangar_anchor, has_landable_port as planets_has_landable_port
                                    if not planets_has_landable_port(pid):
                                        log.add(f'You see no port on {planet_obj.name}.')
                                        continue
                                    if city_player in city_game_map.entities:
                                        city_game_map.entities.remove(city_player)
                                    new_city_map = planets_load_planet(pid)
                                    new_anchor = planet_hangar_anchor(pid)
                                    if hangar_ship is not None:
                                        if hangar_ship in city_game_map.entities:
                                            city_game_map.entities.remove(hangar_ship)
                                        hangar_ship.pos = world.Position(new_anchor.x, -(solar_system_module.SOL_VIEW_H // 2) - 1)
                                        new_city_map.entities.append(hangar_ship)
                                        _animate_ship_to_y(ctx, console, hangar_ship, new_city_map, target_y=new_anchor.y)
                                        log.add(f'You touch down on {planet_obj.name}.')
                                    if city_player not in new_city_map.entities:
                                        new_city_map.entities.append(city_player)
                                    city_player.pos = world.Position(new_anchor.x, new_anchor.y + 1)
                                    city_game_map = new_city_map
                                    game_map = new_city_map
                                    player = city_player
                                    ctx.game_map = game_map
                                    ctx.player = player
                                    current_city_id = pid
                                    current_mode = 'city'
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
                            player_owned_ship = ship_module.OwnedShip(ship_id=ship.id, weapons=ship.start_weapons, modules=ship.start_modules, fuel=ship.max_fuel)
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
                elif blocker.npc_id:
                    npc_obj = npc_module.find_npc(blocker.npc_id)
                    deliver_mission: mission_module.Mission | None = None
                    if player_active_mission is not None:
                        active_mission_obj = mission_module.find_mission(player_active_mission.mission_id)
                        if mission_module.is_deliverable_at(active_mission_obj, npc_obj.id, current_city_id):
                            deliver_mission = active_mission_obj
                    result, deliver_in_progress = _run_npc_talk(ctx, npc_obj, deliver_mission=deliver_mission)
                    if result is TalkOutcome.QUIT:
                        return
                    if result is TalkOutcome.DELIVER:
                        if deliver_in_progress is not None:
                            mission_module.complete_mission(deliver_in_progress, player_owned_ship, stats, log)
                        player_active_mission = None
                        ctx.player_active_mission = None
                    if result is TalkOutcome.WORK:
                        if player_active_mission is not None:
                            current = mission_module.find_mission(player_active_mission.mission_id)
                            giver = npc_module.find_npc(current.giver_npc_id)
                            log.add(f'You already have work from {giver.name}. Press Q to view or abandon it.')
                        else:
                            offerings = mission_module.missions_offered_by(npc_obj.id)
                            if not offerings:
                                log.add(f'{npc_obj.name} has no work for you right now.')
                            else:
                                outcome, picked = _run_mission_offerings(ctx, npc_obj, offerings)
                                if outcome is MissionOutcome.ACCEPT and picked is not None:
                                        if mission_module.try_accept_mission(picked, player_owned_ship, log):
                                            _bounty_spawn_id: str | None = None
                                            if picked.target_enemy_id is not None and picked.target_system_id is not None:
                                                # Generate a unique spawn id for this bounty target.
                                                _bounty_spawn_id = f"bounty_{picked.id}_{int(time.time())}"
                                                try:
                                                    _target_sys = solar_systems_module.find_solar_system(picked.target_system_id)
                                                    _spawn_pos = _pick_bounty_spawn_pos(_target_sys)
                                                    if _spawn_pos is not None:
                                                        from .game_context import BountySpawn
                                                        _bs = BountySpawn(
                                                            spawn_id=_bounty_spawn_id,
                                                            enemy_id=picked.target_enemy_id,
                                                            pos=_spawn_pos,
                                                        )
                                                        if picked.target_system_id not in ctx.bounty_spawns:
                                                            ctx.bounty_spawns[picked.target_system_id] = []
                                                        ctx.bounty_spawns[picked.target_system_id].append(_bs)
                                                        # If player is already in the target system, add the
                                                        # entity to the current game_map immediately.
                                                        if solar_system_module.current_solar_system_id == picked.target_system_id:
                                                            _add_bounty_spawns_to_map(ctx, ctx.game_map, picked.target_system_id)
                                                        log.add(f"Bounty target marked in {_target_sys.name}.")
                                                except KeyError:
                                                    pass
                                            player_active_mission = mission_module.ActiveMission(
                                                mission_id=picked.id,
                                                bounty_spawn_id=_bounty_spawn_id,
                                            )
                                            ctx.player_active_mission = player_active_mission
                else:
                    log.add(f'You bump into {blocker.name}.')

def run(context: tcod.context.Context) -> None:
    """Drive the 3 creation screens, then drop into the city game."""
    import os
    import struct
    _seed = struct.unpack('I', os.urandom(4))[0]
    seed_rng(_seed)
    # Show the title splash screen before the character-creation flow.
    ui.render_title_splash(context)
    while True:
        outcome, species_id = _run_pick(context, ui.species_menu())
        if outcome in (Outcome.QUIT, Outcome.BACK):
            return
        outcome, class_id = _run_pick(context, ui.class_menu())
        if outcome is Outcome.QUIT:
            return
        if outcome is Outcome.BACK:
            continue
        outcome = _run_confirm(context, species_id, class_id)
        if outcome is Outcome.QUIT:
            return
        if outcome is Outcome.BACK:
            continue
        _run_game(context, species_id, class_id)
        # After _run_game returns (death or completion), loop back to
        # the main menu so the player can start a fresh run.
        continue

def main() -> None:
    """Top-level entry: load assets, open window, then run the flow."""
    tileset = load_tileset()
    with open_terminal(tileset) as context:
        run(context)
if __name__ == '__main__':
    main()
