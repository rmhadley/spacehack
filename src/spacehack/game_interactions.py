"""Movement-blocker interactions for the city, space, and dungeon loop."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import time
from . import main_quest as main_quest_module, message_log
from . import mission as mission_module
from . import npc as npc_module
from . import ship as ship_module
from . import solar_system as solar_system_module
from . import ui
from . import world
from .data import solar_systems as solar_systems_module
from .game_context import BountySpawn
from .menus import ShipBuyOutcome, ShipMenuAction, PlanetMenuOutcome, MissionOutcome, _run_mission_offerings, _run_planet_menu, _run_ship_buy, _run_ship_menu, _run_mech_menu
from .navigation import JumpMenuOutcome, _pick_bounty_spawn_pos, _run_cargo_scan, _run_jump_menu, _animate_jump, _jump_to_system
from .city import _animate_ship_to_y
from .time import add_days_to_date
from .npc import TalkOutcome, _run_npc_talk
from .game_flow import _adopt_dungeon_transition, _apply_ship_buy_result, _first_walkable, _launch_owned_ship, _prep_cached_dungeon, _run_pygame_dungeon_confirm

@dataclass
class GameLoopState:
    ctx: Any
    console: Any
    map_w: int
    map_h: int
    log: Any
    stats: Any
    game_map: Any
    player: Any
    current_mode: str
    current_city_id: str
    city_game_map: Any = None
    city_player: Any = None
    space_game_map: Any = None
    space_player: Any = None
    player_owned_ship: Any = None
    player_active_missions: Any = None

def resolve_blocker(state, code, blocker, dx, dy):
    """Resolve one movement blocker."""
    if code == 'wall':
        return _resolve_wall(state, dx, dy, blocker)
    if code == 'occupied':
        return _resolve_occupied(state, blocker)
    return None

def _resolve_wall(state, dx, dy, blocker):
    """Resolve a wall collision."""
    log = state.log
    if state.current_mode == 'space':
        return _resolve_space_wall(state, dx, dy, blocker)
    log.add(world.blocked_message_for(blocker))
    return None

def _resolve_space_wall(state, dx, dy, blocker):
    """Resolve space jump-point and planet wall interactions."""
    log = state.log
    target_x = state.player.pos.x + dx
    target_y = state.player.pos.y + dy
    if state.game_map.in_bounds(target_x, target_y):
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
            _jump_result = _resolve_jump_at_wall(state, jp, target_system_id, target_jp_id)
            if _jump_result is not None:
                return _jump_result
        elif pid is not None:
            return _resolve_planet_wall(state, pid)
    log.add(world.blocked_message_for(blocker))
    return None

def _resolve_jump_at_wall(state, jp, target_system_id, target_jp_id):
    """Handle a selected jump-point interaction."""
    ctx = state.ctx
    console = state.console
    log = state.log
    log.add(f'You approach {jp.name}.')
    outcome = _run_jump_menu(ctx, jp, target_system_id)
    if outcome is JumpMenuOutcome.JUMP:
        ship_record_for_fuel = ship_module.find_ship(state.player_owned_ship.ship_id)
        if state.player_owned_ship.fuel < ship_module.JUMP_FUEL_COST:
            log.add(f'Not enough fuel! The jump requires {ship_module.JUMP_FUEL_COST} units; you have {state.player_owned_ship.fuel}.')
            return 'CONTINUE'
        state.player_owned_ship.fuel -= ship_module.JUMP_FUEL_COST
        log.add(f'Jump drive engaged. Fuel: {state.player_owned_ship.fuel} / {ship_record_for_fuel.max_fuel}.')
        _animate_jump(ctx, console, ctx.player)
        new_game_map, state.player = _jump_to_system(ctx=ctx, jp=jp, target_system_id=target_system_id, target_jp_id=target_jp_id)
        state.game_map = new_game_map
        ctx.game_map = state.game_map
        ctx.player = state.player
        return 'CONTINUE'
    return None

def _resolve_planet_wall(state, pid):
    """Resolve a planet approach, exploration, or landing."""
    ctx = state.ctx
    console = state.console
    log = state.log
    planet_obj = solar_system_module.find_planet(pid)
    log.add(f'You approach {planet_obj.name}.')
    outcome = _run_planet_menu(ctx, planet_obj)
    if outcome is PlanetMenuOutcome.EXPLORE:
        from .data.planets import find_planet_spec as _fps
        from .dungeon import init_fog as _init_fog, reveal_around as _reveal_around, generate_dungeon as _generate_dungeon, populate_dungeon as _populate_dungeon
        _surface_key = f'surface:{pid}'
        _dungeon_map = ctx.interiors.get(_surface_key)
        if _dungeon_map is not None:
            _dungeon_map.interior_cache_key = _surface_key
            _spawn = _prep_cached_dungeon(_dungeon_map)
        else:
            try:
                _pspec = _fps(pid)
                _params = getattr(_pspec, 'dungeon_params', None)
                if _params is None:
                    log.add(f'Nothing to explore on {planet_obj.name}.')
                    return 'CONTINUE'
                _dungeon_map, _spawn = _generate_dungeon(_params)
            except (ValueError, KeyError):
                log.add(f'The surface of {planet_obj.name} is too hazardous to explore.')
                return 'CONTINUE'
            _dungeon_map.entry_spawn = _spawn
            _dungeon_map.interior_cache_key = _surface_key
            if pid == 'mars':
                main_quest_module.prepare_mars_surface(ctx, _dungeon_map, _spawn)
            else:
                main_quest_module.prepare_delve_site(ctx, _dungeon_map, _spawn, pid)
            _populate_dungeon(_dungeon_map, _params, _spawn, tier=_pspec.mission_tier)
            ctx.interiors[_surface_key] = _dungeon_map
        main_quest_module.spawn_quest_npcs(ctx, _dungeon_map, pid, spawn_pos=_spawn)
        if _dungeon_map.seen is None:
            _init_fog(_dungeon_map)
        _reveal_around(_dungeon_map, _spawn)
        _dungeon_player = world.Entity(char='@', fg=(255, 255, 255), pos=_spawn, name='Player')
        _dungeon_map.entities.append(_dungeon_player)
        _dungeon_map.location_name = f'{planet_obj.name} Surface'
        state.space_game_map = state.game_map
        state.space_player = state.player
        state.game_map = _dungeon_map
        state.player = _dungeon_player
        ctx.game_map = state.game_map
        ctx.player = state.player
        state.current_mode = 'dungeon'
        ctx.ground_hp = ctx.ground_max_hp
        log.add(f'You descend to the surface of {planet_obj.name}.')
        return 'CONTINUE'
    if outcome is PlanetMenuOutcome.LAND:
        _run_cargo_scan(ctx, pid)
        from .data.planets import load_planet as _plp, hangar_anchor as _phang, has_landable_port as _phlp
        if not _phlp(pid):
            log.add(f'You see no port on {planet_obj.name}.')
            return 'CONTINUE'
        _new_city_map = _plp(pid)
        main_quest_module.spawn_quest_npcs(ctx, _new_city_map, pid)
        _anchor = _phang(pid)
        _new_city_player = world.Entity(char='@', fg=(255, 255, 255), pos=world.Position(_anchor.x, _anchor.y + 1), name='Player')
        if state.player_owned_ship is not None:
            _ship_spec = ship_module.find_ship(state.player_owned_ship.ship_id)
            _hangar_ship = world.Entity(char=_ship_spec.char, fg=_ship_spec.fg, pos=world.Position(_anchor.x, -(solar_system_module.SOL_VIEW_H // 2) - 1), name=f'Your Ship: {ship_module.ship_display_name(state.player_owned_ship)}', ship_id=_ship_spec.id, owned=True)
            _new_city_map.entities.append(_hangar_ship)
            _animate_ship_to_y(ctx, console, _hangar_ship, _new_city_map, target_y=_anchor.y, location=pid.replace('_', ' ').title())
            log.add(f'You touch down on {planet_obj.name}.')
        _new_city_map.entities.append(_new_city_player)
        ctx.militia_scanned.clear()
        state.city_game_map = _new_city_map
        state.city_player = _new_city_player
        state.game_map = _new_city_map
        state.player = _new_city_player
        ctx.game_map = state.game_map
        ctx.player = state.player
        state.current_city_id = pid
        state.current_mode = 'city'
        if ctx.ground_hp < ctx.ground_max_hp:
            ctx.ground_hp = ctx.ground_max_hp
            log.add('You rest at the city and fully recover.')
    return 'CONTINUE'


def _resolve_occupied(state, blocker):
    """Resolve an occupied movement tile."""
    log = state.log
    if blocker.ship_id:
        return _resolve_ship_blocker(state, blocker)
    if blocker.trade_terminal or blocker.mech_terminal or blocker.armory_terminal or blocker.main_quest_console or blocker.main_quest_door or blocker.interaction_flavor or blocker.dungeon_interaction or blocker.computer_terminal:
        return _resolve_terminal_blocker(state, blocker)
    if blocker.npc_ship_id:
        return _resolve_npc_ship_blocker(state, blocker)
    if blocker.npc_id:
        return _resolve_npc_blocker(state, blocker)
    log.add(world.blocked_message_for(blocker))
    return None

def _resolve_ship_blocker(state, blocker):
    """Resolve owned-ship launch and ship purchases."""
    ctx = state.ctx
    console = state.console
    log = state.log
    ship = ship_module.find_ship(blocker.ship_id)
    if blocker.owned:
        result = _run_ship_menu(ctx, ship)
        if result is ShipMenuAction.QUIT:
            return 'QUIT'
        _launch_result = _launch_owned_ship(ctx, console, result, state.player_owned_ship, state.city_game_map, state.city_player, state.current_city_id, ship)
        if _launch_result is not None:
            state.game_map, state.player = _launch_result
            ctx.game_map = state.game_map
            ctx.player = state.player
            state.current_mode = 'space'
        return 'CONTINUE'
    else:
        _trade_in_value = 0
        if state.player_owned_ship is not None:
            _old_ship = ship_module.find_ship(state.player_owned_ship.ship_id)
            _trade_in_value = max(0, _old_ship.price // 2)
        _effective_price = max(0, ship.price - _trade_in_value)
        result = _run_ship_buy(ctx, blocker, ship, effective_price=_effective_price)
        if result is ShipBuyOutcome.QUIT:
            return 'QUIT'
        if result is ShipBuyOutcome.BUY:
            _purchased_ship = _apply_ship_buy_result(ctx, state.city_game_map, blocker, ship, state.player_owned_ship, result, _effective_price, _trade_in_value)
            if _purchased_ship is None:
                if ctx.stats.credits < _effective_price:
                    short = _effective_price - ctx.stats.credits
                    log.add(f'Including trade-in ({_trade_in_value}$) you need {_effective_price}$, but you are {short}$ short.')
                return 'CONTINUE'
            state.player_owned_ship = _purchased_ship
        elif result is ShipBuyOutcome.TOO_EXPENSIVE:
            _apply_ship_buy_result(ctx, state.city_game_map, blocker, ship, state.player_owned_ship, result, _effective_price, _trade_in_value)
    return None

def _resolve_terminal_blocker(state, blocker):
    """Resolve city terminals and dungeon interfaces."""
    ctx = state.ctx
    log = state.log
    if blocker.trade_terminal:
        from .trade import open_trade as _open_trade
        _open_trade(ctx, state.current_city_id)
    elif blocker.mech_terminal:
        _run_mech_menu(ctx, state.current_city_id)
        return 'CONTINUE'
    elif blocker.armory_terminal:
        from .menus._armory import _run_armory_menu
        _run_armory_menu(ctx, state.current_city_id)
        return 'CONTINUE'
    elif blocker.main_quest_console or blocker.main_quest_door:
        main_quest_module.bump_mars_door(ctx)
        return 'CONTINUE'
    elif blocker.interaction_flavor:
        log.add(blocker.interaction_flavor)
    elif blocker.dungeon_interaction:
        from .dungeon_extensions import activate_interaction_state, interaction_is_available, interaction_spec_at, transition_floor
        _interaction = interaction_spec_at(ctx, blocker.dungeon_interaction)
        if _interaction is None:
            log.add('The alien interface is unresponsive.')
        elif _interaction.action == 'activate_state':
            if activate_interaction_state(ctx, blocker.dungeon_interaction):
                from .main_quest import show_gate_popup
                show_gate_popup(ctx, _interaction.faction_label, _interaction.popup_message, title=_interaction.popup_title)
                if _interaction.objective_type:
                    log.add_colored(f'{_interaction.name}: data extracted. Incomprehensible.', message_log.COLOR_IMPORTANT_EVENT)
                else:
                    log.add_colored(f'{_interaction.name} activated. The gated system is online.', message_log.COLOR_IMPORTANT_EVENT)
            else:
                log.add(f'{_interaction.name} is already active.')
        elif _interaction.action == 'transition_floor':
            if not interaction_is_available(ctx, blocker.dungeon_interaction):
                log.add(f'{_interaction.name} is inert. Required systems are offline.')
            else:
                try:
                    _next_map, _next_player = transition_floor(ctx, _interaction.destination_floor - ctx.dungeon_extension.current_floor)
                except ValueError:
                    log.add('The elevator refuses to move.')
                else:
                    state.game_map = _next_map
                    state.player = _next_player
                    _adopt_dungeon_transition(ctx, state.game_map, state.player)
                    state.current_mode = 'dungeon'
                    log.add(f'{_interaction.name} descends into the next secured floor.')
        return 'CONTINUE'
    elif blocker.computer_terminal:
        if state.current_mode == 'dungeon':
            from . import ui as _ui
            _comp_result = None
            _pygame_comp = _run_pygame_dungeon_confirm(ctx, title='Ship Computer Terminal', body='Restore emergency power to the ship?\n\nThis will boost interior lighting and sensor range.', accept_label='Activate', cancel_label='Leave', caption='spacehack - ship computer')
            if _pygame_comp == 'QUIT':
                return 'QUIT'
            if _pygame_comp == 'CONFIRM':
                _comp_result = _ui.MenuAction.CONFIRM
            if _comp_result == ui.MenuAction.CONFIRM:
                if getattr(state.game_map, 'power_restored', False):
                    log.add("The ship's power grid is already online.")
                else:
                    state.game_map.sight_radius = 20
                    state.game_map.power_restored = True
                    from .dungeon import reveal_around as _r2
                    _r2(state.game_map, state.player.pos, radius=20)
                    log.add_colored('Emergency power restored. Interior sensors online.', message_log.COLOR_IMPORTANT_EVENT)
            return 'CONTINUE'
        log.add(world.blocked_message_for(blocker))
    return None

def _resolve_npc_ship_blocker(state, blocker):
    """Resolve boarding a boardable NPC ship."""
    ctx = state.ctx
    console = state.console
    map_w = state.map_w
    map_h = state.map_h
    log = state.log
    from .data.npc_ships import find_npc_ship as _find_ship
    try:
        _npcspec = _find_ship(blocker.npc_ship_id)
        if _npcspec.is_boardable:
            _pygame_board = _run_pygame_dungeon_confirm(ctx, title=f'Board the {_npcspec.name}?', body='The derelict can be searched for salvage and mission cargo.', accept_label='Board', cancel_label='Fly past', caption='spacehack - boarding')
            if _pygame_board == 'QUIT':
                return 'QUIT'
            _board_result = PlanetMenuOutcome.LAND if _pygame_board == 'CONFIRM' else PlanetMenuOutcome.BACK if _pygame_board == 'BACK' else None
            if _board_result is None:
                return 'CONTINUE'
            if _board_result == PlanetMenuOutcome.QUIT:
                return 'QUIT'
            if _board_result == PlanetMenuOutcome.LAND:
                from .dungeon import load_layout as _load_layout, animate_breach as _animate_breach, init_fog as _init_fog, reveal_around as _reveal_around
                _wreck_sid = getattr(blocker, 'salvage_wreck_spawn_id', None)
                _mission = None
                if _wreck_sid is not None:
                    for _am in state.player_active_missions:
                        if getattr(_am, 'salvage_wreck_spawn_id', None) == _wreck_sid:
                            _mission = _am
                            break
                _dungeon_map = None
                _spawn = None
                _is_reboard = False
                if _wreck_sid is not None and _wreck_sid in ctx.interiors:
                    _dungeon_map = ctx.interiors[_wreck_sid]
                    _spawn = _prep_cached_dungeon(_dungeon_map)
                    _is_reboard = True
                elif _mission is not None and _mission.salvage_layout_id:
                    try:
                        _dungeon_map, _spawn = _load_layout(_mission.salvage_layout_id, loot_budget=_npcspec.loot_budget, component_good_id=_mission.heist_target_good_id, component_mission_id=_mission.mission_id)
                    except (FileNotFoundError, ValueError):
                        log.add("The derelict's interior is too damaged to explore.")
                        return 'CONTINUE'
                    _dungeon_map.wreck_spawn_id = _wreck_sid
                    _dungeon_map.entry_spawn = _spawn
                    ctx.interiors[_wreck_sid] = _dungeon_map
                elif _wreck_sid is not None and _wreck_sid.endswith('_wreck'):
                    _mq_spawn_id = _wreck_sid[:-6]
                    _mq_step_id = None
                    _mq_step = main_quest_module.find_salvage_step_for_spawn(ctx, _mq_spawn_id)
                    if _mq_step is not None and ctx.main_quest_progress.get(_mq_step.id) in ('available', 'active') and _mq_step.salvage_layout_id:
                        _mq_step_id = _mq_step.id
                    if _mq_step_id is not None:
                        try:
                            _dungeon_map, _spawn = _load_layout(_mq_step.salvage_layout_id, loot_budget=_npcspec.loot_budget)
                        except (FileNotFoundError, ValueError):
                            log.add("The derelict's interior is too damaged to explore.")
                            return 'CONTINUE'
                        _mq_candidates = []
                        for _e in _dungeon_map.entities:
                            if getattr(_e, 'loot_data', None) is None:
                                continue
                            for _dy in (-2, 0, 2):
                                for _dx in (-2, 0, 2):
                                    _nx = _e.pos.x + _dx
                                    _ny = _e.pos.y + _dy
                                    if 0 <= _nx < _dungeon_map.width and 0 <= _ny < _dungeon_map.height and _dungeon_map.tiles[_ny][_nx].walkable and (not any((_oe.pos.x == _nx and _oe.pos.y == _ny for _oe in _dungeon_map.entities))):
                                        _mq_candidates.append((_nx, _ny))
                        if not _mq_candidates:
                            _mq_candidates = [(_spawn.x, _spawn.y)]
                        from .engine import RNG as _RNG
                        _lr = _mq_candidates[_RNG.randint(0, len(_mq_candidates) - 1)]
                        _mq_goods = list(_mq_step.delve_good_ids)
                        if not _mq_goods:
                            log.add('The derelict holds no quest data.')
                            return 'CONTINUE'
                        from .data.trade_goods import find_trade_good as _ftg
                        try:
                            _gname = _ftg(_mq_goods[0][0]).name
                        except (KeyError, ImportError):
                            _gname = _mq_goods[0][0].replace('_', ' ').title()
                        _mq_loot_name = f'Quest Component: {_gname}'
                        _mq_loot = world.Entity(char='%', fg=(255, 215, 0), pos=world.Position(_lr[0], _lr[1]), name=_mq_loot_name, width=1, height=1, loot_data={'goods': _mq_goods})
                        _mq_loot.main_quest_step_id = _mq_step_id
                        _dungeon_map.entities.append(_mq_loot)
                        _dungeon_map.wreck_spawn_id = _wreck_sid
                        _dungeon_map.entry_spawn = _spawn
                        ctx.interiors[_wreck_sid] = _dungeon_map
                if _dungeon_map is None and _mission is None and (not (_wreck_sid or '').endswith('_wreck')):
                    try:
                        _dungeon_map, _spawn = _load_layout('scout_a', loot_budget=_npcspec.loot_budget)
                    except (FileNotFoundError, ValueError):
                        log.add("The derelict's interior is too damaged to explore.")
                        return 'CONTINUE'
                    try:
                        ctx.game_map.entities.remove(blocker)
                        _sys_id = solar_system_module.current_solar_system_id
                        if _sys_id in ctx.procedural_spawns:
                            ctx.procedural_spawns[_sys_id] = [_ps for _ps in ctx.procedural_spawns[_sys_id] if _ps.npc_id != _npcspec.id or _ps.pos != blocker.pos]
                    except (ValueError, AttributeError):
                        pass
                if _dungeon_map is None:
                    log.add("The derelict's interior is too damaged to explore.")
                    return 'CONTINUE'
                if _spawn is None:
                    _spawn = _first_walkable(_dungeon_map)
                if _dungeon_map.seen is None:
                    _init_fog(_dungeon_map)
                _reveal_around(_dungeon_map, _spawn)
                _dungeon_player = world.Entity(char='@', fg=(255, 255, 255), pos=_spawn, name='Player')
                _dungeon_map.entities.append(_dungeon_player)
                if not _is_reboard:
                    _animate_breach(ctx, console, _dungeon_map, _spawn, region_w=map_w, region_h=map_h)
                _dungeon_map.location_name = _npcspec.name
                state.space_game_map = state.game_map
                state.space_player = state.player
                state.game_map = _dungeon_map
                state.player = _dungeon_player
                ctx.game_map = state.game_map
                ctx.player = state.player
                state.current_mode = 'dungeon'
                ctx.ground_hp = ctx.ground_max_hp
                log.add(f'You cut through the hull and enter the {_npcspec.name}.')
                return 'CONTINUE'
            return 'CONTINUE'
    except KeyError:
        pass
    log.add(world.blocked_message_for(blocker))
    return None

def _resolve_npc_blocker(state, blocker):
    """Resolve NPC dialogue, delivery, and mission acceptance."""
    ctx = state.ctx
    log = state.log
    stats = state.stats
    npc_obj = npc_module.find_npc(blocker.npc_id)
    _planet_tier = 1
    try:
        from .data.planets import find_planet_spec as _fps
        _planet_tier = _fps(state.current_city_id).mission_tier
    except KeyError:
        pass
    _deliverable = mission_module.find_deliverable_missions(state.player_active_missions, npc_obj.id, state.current_city_id, owned_ship=state.player_owned_ship)
    result, _deliver_mission = _run_npc_talk(ctx, npc_obj, deliver_missions=_deliverable or None)
    if result is TalkOutcome.QUIT:
        return 'QUIT'
    if result is TalkOutcome.QUEST:
        return 'CONTINUE'
    if result is TalkOutcome.DELIVER:
        if _deliver_mission is not None:
            _heist_good = getattr(_deliver_mission, 'heist_target_good_id', None)
            if _heist_good is not None and getattr(_deliver_mission, 'heist_good_secured', False):
                log.add(f"You hand over the stolen {_heist_good.replace('_', ' ')}.")
            _today = ctx.time_day + (ctx.time_month - 1) * 30
            mission_module.complete_mission(_deliver_mission, state.player_owned_ship, stats, log, current_day=_today, ctx=ctx)
            if not _deliver_mission.is_procedural:
                ctx.completed_mission_ids.add(_deliver_mission.mission_id)
            try:
                state.player_active_missions.remove(_deliver_mission)
            except ValueError:
                pass
            ctx.player_active_missions = state.player_active_missions
    if result is TalkOutcome.WORK:
        if len(state.player_active_missions) >= mission_module.MAX_ACTIVE_MISSIONS:
            log.add(f'Your mission log is full ({mission_module.MAX_ACTIVE_MISSIONS}/{mission_module.MAX_ACTIVE_MISSIONS}). Abandon one first (Q).')
        else:
            _board = mission_module.ensure_board(ctx, npc_obj.id, max_slots=5, planet_id=state.current_city_id)
            _active_ids = frozenset((m.mission_id for m in state.player_active_missions))
            _completed_ids = frozenset(ctx.completed_mission_ids)
            if _board.last_refresh_month != ctx.time_month:
                mission_module.fill_empty_slots(_board, planet_tier=_planet_tier, completed_ids=_completed_ids, active_ids=_active_ids, planet_id=state.current_city_id, generated=ctx.generated_missions, ctx=ctx)
                _board.last_refresh_month = ctx.time_month
            offerings = mission_module.board_offerings(_board, generated=ctx.generated_missions)
            if not offerings:
                log.add(f'{npc_obj.name} has no work for you right now.')
            else:
                outcome, picked = _run_mission_offerings(ctx, npc_obj, offerings)
                if outcome is MissionOutcome.QUIT:
                    return 'QUIT'
                if outcome is MissionOutcome.ACCEPT and picked is not None:
                    if mission_module.try_accept_mission(picked, state.player_owned_ship, log, active_count=len(state.player_active_missions)):
                        mission_module.board_remove(_board, picked.id)
                        _bounty_spawn_id: str | None = None
                        _wreck_spawn_id: str | None = None
                        _spawn_ok = True
                        if picked.target_enemy_id is not None and picked.target_system_id is not None:
                            _bounty_spawn_id = f'bounty_{picked.id}_{int(time.time())}'
                            _squad_size = getattr(picked, 'bounty_target_squad_size', 1)
                            _wingmate_enemy_id = getattr(picked, 'bounty_wingmate_enemy_id', None) or picked.target_enemy_id
                            try:
                                _target_sys = solar_systems_module.find_solar_system(picked.target_system_id)
                                _used = frozenset(((_bs.pos.x, _bs.pos.y) for _bs in ctx.bounty_spawns.get(picked.target_system_id, [])))
                                _spawn_pos = _pick_bounty_spawn_pos(_target_sys, used_positions=_used)
                                if _spawn_pos is not None:
                                    from .data.npc_ships import find_npc_ship as _bfns
                                    _bounty_warning_range = 0
                                    try:
                                        _bounty_spec = _bfns(picked.target_enemy_id)
                                        _bounty_warning_range = max(12, _bounty_spec.detect_radius * 2)
                                    except (KeyError, ImportError):
                                        pass
                                    _heist_sid = None
                                    if getattr(picked, 'heist_target_good_id', None) is not None and getattr(picked, 'salvage_layout_id', None) is None:
                                        _heist_sid = _bounty_spawn_id
                                    _bs = BountySpawn(spawn_id=_bounty_spawn_id, enemy_id=picked.target_enemy_id, pos=_spawn_pos, bounty_target_name=getattr(picked, 'bounty_target_name', None), squad_size=_squad_size, loadout_pct=getattr(picked, 'bounty_target_loadout_pct', 0), comms_warning_range=_bounty_warning_range, heist_spawn_id=_heist_sid)
                                    if picked.target_system_id not in ctx.bounty_spawns:
                                        ctx.bounty_spawns[picked.target_system_id] = []
                                    ctx.bounty_spawns[picked.target_system_id].append(_bs)
                                    _wing_offsets = [(2, 0), (-2, 0), (0, 2), (0, -2), (2, 2)]
                                    for _wi in range(min(_squad_size - 1, len(_wing_offsets))):
                                        _wox, _woy = _wing_offsets[_wi]
                                        _wpos = world.Position(_spawn_pos.x + _wox, _spawn_pos.y + _woy)
                                        if 0 <= _wpos.x < _target_sys.width and 0 <= _wpos.y < _target_sys.height:
                                            _wbs = BountySpawn(spawn_id=f'{_bounty_spawn_id}_wing{_wi}', enemy_id=_wingmate_enemy_id, pos=_wpos, bounty_target_name=None, squad_size=_squad_size, loadout_pct=0, squad_group_id=_bounty_spawn_id, comms_warning_range=0)
                                            ctx.bounty_spawns[picked.target_system_id].append(_wbs)
                                    _squad_note = f' ({_squad_size}-ship squad)' if _squad_size > 1 else ''
                                    if getattr(picked, 'salvage_wreck_enemy_id', None) is not None:
                                        _wreck_spawn_id = f'wreck_{picked.id}_{int(time.time())}'
                                        _wreck_pos = world.Position(min(_spawn_pos.x + 5, _target_sys.width - 1), _spawn_pos.y)
                                        _wbs = BountySpawn(spawn_id=_wreck_spawn_id, enemy_id=picked.salvage_wreck_enemy_id, pos=_wreck_pos, bounty_target_name=None, squad_size=1, loadout_pct=0, salvage_wreck=True)
                                        ctx.bounty_spawns[picked.target_system_id].append(_wbs)
                                        log.add(f'Salvage site marked in {_target_sys.name}: wreck + {_squad_size}-ship patrol.')
                                    else:
                                        log.add(f'Bounty target marked in {_target_sys.name}.{_squad_note}')
                                else:
                                    _spawn_ok = False
                                    mission_module.board_return_static(_board, picked.id)
                                    log.add(f'Cannot accept: {_target_sys.name} bounty system full. Clear an existing bounty first.')
                            except KeyError:
                                pass
                        if _spawn_ok:
                            _dl_days = getattr(picked, 'deadline_days', 0)
                            _deadline = None
                            if _dl_days > 0:
                                _deadline = add_days_to_date(ctx.time_day, ctx.time_month, ctx.time_year, _dl_days)
                            _is_proc = picked.id in ctx.generated_missions
                            _del_npc = picked.delivery_target_npc_id
                            _del_planet = picked.delivery_target_planet_id
                            _heist_good = getattr(picked, 'heist_target_good_id', None)
                            if _heist_good is not None:
                                _del_npc = npc_obj.id
                                _del_planet = state.current_city_id
                            _new_active = mission_module.ActiveMission(mission_id=picked.id, is_procedural=_is_proc, title=picked.title, required_cargo_size=picked.required_cargo_size, delivery_target_npc_id=_del_npc, delivery_target_planet_id=_del_planet, deadline_days=_dl_days, accept_day=ctx.time_day + (ctx.time_month - 1) * 30, time_deadline=_deadline, reward_credits=picked.reward_credits, reward_xp=picked.reward_xp, early_bonus_pct=picked.early_bonus_pct, bounty_spawn_id=_bounty_spawn_id, target_enemy_id=picked.target_enemy_id, target_system_id=picked.target_system_id, bounty_target_name=getattr(picked, 'bounty_target_name', None), bounty_target_squad_size=getattr(picked, 'bounty_target_squad_size', 1), bounty_target_loadout_pct=getattr(picked, 'bounty_target_loadout_pct', 0), bounty_wingmate_enemy_id=getattr(picked, 'bounty_wingmate_enemy_id', None), tier=picked.tier, heist_target_good_id=_heist_good, salvage_wreck_enemy_id=getattr(picked, 'salvage_wreck_enemy_id', None), salvage_layout_id=getattr(picked, 'salvage_layout_id', None), salvage_wreck_spawn_id=_wreck_spawn_id, is_smuggle=getattr(picked, 'is_smuggle', False), smuggle_good_id=getattr(picked, 'smuggle_good_id', None))
                            mission_module.commit_accept_mission(picked, state.player_owned_ship, log)
                            state.player_active_missions.append(_new_active)
                            ctx.player_active_missions = state.player_active_missions
    return None
