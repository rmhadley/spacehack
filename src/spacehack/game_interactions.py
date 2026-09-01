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
from .text import get as t_get
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
    city_debug: bool = False

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
    log = state.log
    planet_obj = solar_system_module.find_planet(pid)
    log.add(f'You approach {planet_obj.name}.')
    outcome = _run_planet_menu(ctx, planet_obj)
    if outcome is PlanetMenuOutcome.EXPLORE:
        return _resolve_planet_explore(state, pid, planet_obj)
    if outcome is PlanetMenuOutcome.LAND:
        return _resolve_planet_land(state, pid, planet_obj)
    return 'CONTINUE'

def _resolve_planet_explore(state, pid, planet_obj):
    """Handle the planet-menu Explore option."""
    _dungeon_map, _spawn = _build_surface_dungeon(state.ctx, state.log, pid, planet_obj)
    if _dungeon_map is None:
        return 'CONTINUE'
    return _enter_planet_surface(state, pid, planet_obj, _dungeon_map, _spawn)

def _build_surface_dungeon(ctx, log, pid, planet_obj):
    """Return (dungeon_map, spawn) for a planet surface, cached or fresh."""
    from .data.planets import find_planet_spec as _fps
    from .dungeon import generate_dungeon as _generate_dungeon, populate_dungeon as _populate_dungeon
    _surface_key = f'surface:{pid}'
    _dungeon_map = ctx.interiors.get(_surface_key)
    if _dungeon_map is not None:
        _dungeon_map.interior_cache_key = _surface_key
        return (_dungeon_map, _prep_cached_dungeon(_dungeon_map))
    try:
        _pspec = _fps(pid)
        _params = getattr(_pspec, 'dungeon_params', None)
        if _params is None:
            log.add(f'Nothing to explore on {planet_obj.name}.')
            return (None, None)
        _dungeon_map, _spawn = _generate_dungeon(_params)
    except (ValueError, KeyError):
        log.add(f'The surface of {planet_obj.name} is too hazardous to explore.')
        return (None, None)
    _dungeon_map.entry_spawn = _spawn
    _dungeon_map.interior_cache_key = _surface_key
    if pid == 'mars':
        main_quest_module.prepare_mars_surface(ctx, _dungeon_map, _spawn)
    else:
        main_quest_module.prepare_delve_site(ctx, _dungeon_map, _spawn, pid)
    _populate_dungeon(_dungeon_map, _params, _spawn, tier=_pspec.mission_tier)
    ctx.interiors[_surface_key] = _dungeon_map
    return (_dungeon_map, _spawn)

def _enter_planet_surface(state, pid, planet_obj, dungeon_map, spawn):
    """Move the player onto a planet surface dungeon."""
    ctx = state.ctx
    log = state.log
    from .dungeon import init_fog as _init_fog, reveal_around as _reveal_around
    # Quest NPCs are city-only: the experts stand in their guild
    # buildings, never inside surface dungeons (no duplicate copies).
    if dungeon_map.seen is None:
        _init_fog(dungeon_map)
    _reveal_around(dungeon_map, spawn)
    _dungeon_player = world.Entity(char='@', fg=(255, 255, 255), pos=spawn, name='Player')
    dungeon_map.entities.append(_dungeon_player)
    dungeon_map.location_name = f'{planet_obj.name} Surface'
    state.space_game_map = state.game_map
    state.space_player = state.player
    state.game_map = dungeon_map
    state.player = _dungeon_player
    ctx.game_map = state.game_map
    ctx.player = state.player
    state.current_mode = 'dungeon'
    ctx.ground_hp = ctx.ground_max_hp
    log.add(f'You descend to the surface of {planet_obj.name}.')
    return 'CONTINUE'

def land_at_city(state, planet_id):
    """Land directly on any port city, switching system first.

    The dev-mode city teleport (Shift+T) uses this to reuse the exact
    production landing path — the resulting state is what save/load
    already round-trips. Unknown or portless ids log and continue.
    """
    log = state.log
    from .data.planets import has_landable_port as _phlp
    from .data.solar_systems import system_for_planet as _system_for
    if not _phlp(planet_id):
        log.add(f'You see no port on {planet_id}.')
        return 'CONTINUE'
    solar_system_module.set_current_solar_system(
        _system_for(planet_id).id
    )
    planet_obj = solar_system_module.find_planet(planet_id)
    return _resolve_planet_land(state, planet_id, planet_obj)


def _resolve_planet_land(state, pid, planet_obj):
    """Handle the planet-menu Land option."""
    ctx = state.ctx
    console = state.console
    log = state.log
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
    ctx.current_city_id = pid
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
    if blocker.transit_station_id:
        return _resolve_transit_station(state, blocker)
    if blocker.trade_terminal or blocker.mech_terminal or blocker.armory_terminal or blocker.main_quest_console or blocker.main_quest_door or blocker.interaction_flavor or blocker.dungeon_interaction or blocker.computer_terminal:
        return _resolve_terminal_blocker(state, blocker)
    if blocker.npc_ship_id:
        return _resolve_npc_ship_blocker(state, blocker)
    if blocker.npc_id:
        return _resolve_npc_blocker(state, blocker)
    if blocker.city_npc_id:
        return _resolve_city_npc_blocker(state, blocker)
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
        return _resolve_dungeon_interaction(state, blocker)
    elif blocker.computer_terminal:
        return _resolve_computer_terminal(state, blocker)
    return None


def _resolve_transit_station(state, blocker):
    """Resolve bumping a city transit stop."""
    from .city_transit import resolve_transit_station as _ride
    return _ride(state, blocker)


def _log_extension_activation(state, interaction) -> None:
    """Present and log an activated dungeon interaction."""
    from .main_quest import show_gate_popup

    show_gate_popup(
        state.ctx,
        interaction.faction_label,
        interaction.popup_message,
        title=interaction.popup_title,
    )
    _key = (
        "runtime.prison.data_extracted"
        if interaction.objective_type
        else "runtime.prison.interaction_activated"
    )
    state.log.add_colored(
        t_get(_key).format(name=interaction.name),
        message_log.COLOR_IMPORTANT_EVENT,
    )


def _resolve_extension_activation(state, blocker, interaction) -> None:
    """Handle activation-state interaction feedback."""
    from .dungeon_extensions import activate_interaction_state

    if activate_interaction_state(state.ctx, blocker.dungeon_interaction):
        _log_extension_activation(state, interaction)
    else:
        state.log.add(
            t_get("runtime.prison.interaction_already_active").format(
                name=interaction.name,
            ),
        )


def _resolve_extension_transition(state, blocker, interaction) -> None:
    """Handle a gated floor transition and its feedback."""
    from .dungeon_extensions import interaction_is_available, transition_floor

    if not interaction_is_available(state.ctx, blocker.dungeon_interaction):
        state.log.add(
            t_get("runtime.prison.interaction_offline").format(
                name=interaction.name,
            ),
        )
        return
    try:
        _next_map, _next_player = transition_floor(
            state.ctx,
            interaction.destination_floor - state.ctx.dungeon_extension.current_floor,
        )
    except ValueError:
        state.log.add(t_get("runtime.prison.elevator_refuses"))
        return
    state.game_map = _next_map
    state.player = _next_player
    _adopt_dungeon_transition(state.ctx, state.game_map, state.player)
    state.current_mode = 'dungeon'
    state.log.add(
        t_get("runtime.prison.elevator_descends").format(name=interaction.name),
    )


def _resolve_dungeon_interaction(state, blocker):
    """Resolve a dungeon extension interaction."""
    from .dungeon_extensions import interaction_spec_at

    _interaction = interaction_spec_at(state.ctx, blocker.dungeon_interaction)
    if _interaction is None:
        state.log.add(t_get("runtime.prison.interface_unresponsive"))
        return 'CONTINUE'
    if _interaction.action == 'activate_state':
        _resolve_extension_activation(state, blocker, _interaction)
    elif _interaction.action == 'transition_floor':
        _resolve_extension_transition(state, blocker, _interaction)
    return 'CONTINUE'

def _resolve_computer_terminal(state, blocker):
    """Resolve the dungeon ship-computer terminal."""
    ctx = state.ctx
    log = state.log
    if state.current_mode != 'dungeon':
        log.add(world.blocked_message_for(blocker))
        return None
    _comp_result = None
    _pygame_comp = _run_pygame_dungeon_confirm(ctx, title='Ship Computer Terminal', body='Restore emergency power to the ship?\n\nThis will boost interior lighting and sensor range.', accept_label='Activate', cancel_label='Leave', caption='spacehack - ship computer')
    if _pygame_comp == 'QUIT':
        return 'QUIT'
    if _pygame_comp == 'CONFIRM':
        _comp_result = ui.MenuAction.CONFIRM
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

def _resolve_npc_ship_blocker(state, blocker):
    """Resolve boarding a boardable NPC ship."""
    log = state.log
    from .data.npc_ships import find_npc_ship as _find_ship
    _boarded = False
    try:
        _npcspec = _find_ship(blocker.npc_ship_id)
        if _npcspec.is_boardable:
            _board_result = _confirm_boarding(state.ctx, _npcspec)
            if _board_result == 'QUIT':
                return 'QUIT'
            if _board_result is not None:
                _dungeon_map, _spawn, _is_reboard = _boardable_wreck_layout(state, blocker, _npcspec)
                if _dungeon_map is not None:
                    _enter_boarding_dungeon(state, _npcspec, _dungeon_map, _spawn, _is_reboard)
            _boarded = True
    except KeyError:
        pass
    if _boarded:
        return 'CONTINUE'
    log.add(world.blocked_message_for(blocker))
    return None

def _confirm_boarding(ctx, npcspec):
    """Ask to board; return 'QUIT', PlanetMenuOutcome.LAND, or None."""
    _pygame_board = _run_pygame_dungeon_confirm(ctx, title=f'Board the {npcspec.name}?', body='The derelict can be searched for salvage and mission cargo.', accept_label='Board', cancel_label='Fly past', caption='spacehack - boarding')
    if _pygame_board == 'QUIT':
        return 'QUIT'
    if _pygame_board == 'CONFIRM':
        return PlanetMenuOutcome.LAND
    return None

def _boardable_wreck_layout(state, blocker, npcspec):
    """Return (dungeon_map, spawn, is_reboard) for a boardable wreck."""
    ctx = state.ctx
    log = state.log
    from .dungeon import load_layout as _load_layout
    _wreck_sid = getattr(blocker, 'salvage_wreck_spawn_id', None)
    _mission = _find_boarding_mission(state, _wreck_sid)
    _dungeon_map = None
    _spawn = None
    _is_reboard = False
    if _wreck_sid is not None and _wreck_sid in ctx.interiors:
        _dungeon_map = ctx.interiors[_wreck_sid]
        _spawn = _prep_cached_dungeon(_dungeon_map)
        _is_reboard = True
    elif _mission is not None and _mission.salvage_layout_id:
        try:
            _dungeon_map, _spawn = _load_layout(_mission.salvage_layout_id, loot_budget=npcspec.loot_budget, component_good_id=_mission.heist_target_good_id, component_mission_id=_mission.mission_id)
        except (FileNotFoundError, ValueError):
            log.add("The derelict's interior is too damaged to explore.")
            return (None, None, False)
        _dungeon_map.wreck_spawn_id = _wreck_sid
        _dungeon_map.entry_spawn = _spawn
        ctx.interiors[_wreck_sid] = _dungeon_map
    elif _wreck_sid is not None and _wreck_sid.endswith('_wreck'):
        _dungeon_map, _spawn, _handled = _build_main_quest_wreck(ctx, npcspec, _wreck_sid, log)
        if _handled:
            return (None, None, False)
    if _dungeon_map is None and _mission is None and (not (_wreck_sid or '').endswith('_wreck')):
        try:
            _dungeon_map, _spawn = _load_layout('scout_a', loot_budget=npcspec.loot_budget)
        except (FileNotFoundError, ValueError):
            log.add("The derelict's interior is too damaged to explore.")
            return (None, None, False)
        _despawn_blocker(ctx, blocker, npcspec)
    if _dungeon_map is None:
        log.add("The derelict's interior is too damaged to explore.")
        return (None, None, False)
    if _spawn is None:
        _spawn = _first_walkable(_dungeon_map)
    return (_dungeon_map, _spawn, _is_reboard)

def _find_boarding_mission(state, wreck_sid):
    """Return the active mission whose salvage wreck matches wreck_sid."""
    if wreck_sid is None:
        return None
    for _am in state.player_active_missions:
        if getattr(_am, 'salvage_wreck_spawn_id', None) == wreck_sid:
            return _am
    return None

def _build_main_quest_wreck(ctx, npcspec, wreck_sid, log):
    """Build a main-quest wreck layout; returns (map, spawn, handled)."""
    from .dungeon import load_layout as _load_layout
    _mq_spawn_id = wreck_sid[:-6]
    _mq_step = main_quest_module.find_salvage_step_for_spawn(ctx, _mq_spawn_id)
    _mq_ok = (
        _mq_step is not None
        and ctx.main_quest_progress.get(_mq_step.id) in ('available', 'active')
        and _mq_step.salvage_layout_id
    )
    if not _mq_ok:
        return (None, None, False)
    try:
        _dungeon_map, _spawn = _load_layout(_mq_step.salvage_layout_id, loot_budget=npcspec.loot_budget)
    except (FileNotFoundError, ValueError):
        log.add("The derelict's interior is too damaged to explore.")
        return (None, None, True)
    _lr = _pick_quest_loot_pos(_dungeon_map, _spawn)
    _mq_goods = list(_mq_step.delve_good_ids)
    if not _mq_goods:
        log.add('The derelict holds no quest data.')
        return (None, None, True)
    _place_quest_loot(_dungeon_map, _lr, _mq_step.id, _mq_goods)
    _dungeon_map.wreck_spawn_id = wreck_sid
    _dungeon_map.entry_spawn = _spawn
    ctx.interiors[wreck_sid] = _dungeon_map
    return (_dungeon_map, _spawn, False)

def _pick_quest_loot_pos(dungeon_map, spawn):
    """Pick a walkable tile adjacent to existing loot for quest placement."""
    _mq_candidates = []
    for _e in dungeon_map.entities:
        if getattr(_e, 'loot_data', None) is None:
            continue
        for _dy in (-2, 0, 2):
            for _dx in (-2, 0, 2):
                _nx = _e.pos.x + _dx
                _ny = _e.pos.y + _dy
                if 0 <= _nx < dungeon_map.width and 0 <= _ny < dungeon_map.height and dungeon_map.tiles[_ny][_nx].walkable and (not any((_oe.pos.x == _nx and _oe.pos.y == _ny for _oe in dungeon_map.entities))):
                    _mq_candidates.append((_nx, _ny))
    if not _mq_candidates:
        _mq_candidates = [(spawn.x, spawn.y)]
    from .engine import RNG as _RNG
    return _mq_candidates[_RNG.randint(0, len(_mq_candidates) - 1)]

def _place_quest_loot(dungeon_map, pos, step_id, goods):
    """Drop the quest component at pos and tag it with the step id."""
    from .data.trade_goods import find_trade_good as _ftg
    try:
        _gname = _ftg(goods[0][0]).name
    except (KeyError, ImportError):
        _gname = goods[0][0].replace('_', ' ').title()
    _mq_loot_name = f'Quest Component: {_gname}'
    _mq_loot = world.Entity(char='%', fg=(255, 215, 0), pos=world.Position(pos[0], pos[1]), name=_mq_loot_name, width=1, height=1, loot_data={'goods': goods})
    _mq_loot.main_quest_step_id = step_id
    dungeon_map.entities.append(_mq_loot)

def _despawn_blocker(ctx, blocker, npcspec):
    """Remove a boarded scout wreck from the system and procedural spawns."""
    try:
        ctx.game_map.entities.remove(blocker)
        _sys_id = solar_system_module.current_solar_system_id
        if _sys_id in ctx.procedural_spawns:
            ctx.procedural_spawns[_sys_id] = [_ps for _ps in ctx.procedural_spawns[_sys_id] if _ps.npc_id != npcspec.id or _ps.pos != blocker.pos]
    except (ValueError, AttributeError):
        pass

def _enter_boarding_dungeon(state, npcspec, dungeon_map, spawn, is_reboard):
    """Move the player into a boardable wreck's interior."""
    ctx = state.ctx
    console = state.console
    log = state.log
    from .dungeon import animate_breach as _animate_breach, init_fog as _init_fog, reveal_around as _reveal_around
    if dungeon_map.seen is None:
        _init_fog(dungeon_map)
    _reveal_around(dungeon_map, spawn)
    _dungeon_player = world.Entity(char='@', fg=(255, 255, 255), pos=spawn, name='Player')
    dungeon_map.entities.append(_dungeon_player)
    if not is_reboard:
        _animate_breach(ctx, console, dungeon_map, spawn, region_w=state.map_w, region_h=state.map_h)
    dungeon_map.location_name = npcspec.name
    state.space_game_map = state.game_map
    state.space_player = state.player
    state.game_map = dungeon_map
    state.player = _dungeon_player
    ctx.game_map = state.game_map
    ctx.player = state.player
    state.current_mode = 'dungeon'
    ctx.ground_hp = ctx.ground_max_hp
    log.add(f'You cut through the hull and enter the {npcspec.name}.')
    return 'CONTINUE'

def _resolve_npc_blocker(state, blocker):
    """Resolve NPC dialogue, delivery, and mission acceptance."""
    ctx = state.ctx
    npc_obj = npc_module.find_npc(blocker.npc_id)
    _planet_tier = _planet_mission_tier(state)
    _deliverable = mission_module.find_deliverable_missions(state.player_active_missions, npc_obj.id, state.current_city_id, owned_ship=state.player_owned_ship)
    result, _deliver_mission = _run_npc_talk(ctx, npc_obj, deliver_missions=_deliverable or None)
    if result is TalkOutcome.QUIT:
        return 'QUIT'
    if result is TalkOutcome.QUEST:
        return 'CONTINUE'
    if result is TalkOutcome.DELIVER:
        _resolve_npc_delivery(state, _deliver_mission)
    elif result is TalkOutcome.WORK:
        _work_result = _resolve_npc_work(state, npc_obj, _planet_tier)
        if _work_result is not None:
            return _work_result
    return None

def _resolve_city_npc_blocker(state, blocker):
    """Resolve bumping into an ambient city citizen.

    Hostile citizens (faction enemy/disliked, or always-hostile mobs)
    trigger a direct-contact ground fight through the shared combat
    runtime; friendly citizens just block foot traffic with a bump line.
    """
    from . import city_npcs as _cn
    if _cn.is_hostile(state.ctx, blocker):
        _cn.run_city_fight(state.ctx, state.console, state.game_map, [blocker])
        return 'CONTINUE'
    state.log.add(world.blocked_message_for(blocker))
    return None


def _planet_mission_tier(state):
    """Return the mission tier for the player's current city, defaulting to 1."""
    try:
        from .data.planets import find_planet_spec as _fps
        return _fps(state.current_city_id).mission_tier
    except KeyError:
        return 1

def _resolve_npc_delivery(state, deliver_mission):
    """Complete a handed-over delivery mission."""
    if deliver_mission is None:
        return None
    ctx = state.ctx
    log = state.log
    _heist_good = getattr(deliver_mission, 'heist_target_good_id', None)
    if _heist_good is not None and getattr(deliver_mission, 'heist_good_secured', False):
        log.add(f"You hand over the stolen {_heist_good.replace('_', ' ')}.")
    _today = ctx.time_day + (ctx.time_month - 1) * 30
    mission_module.complete_mission(deliver_mission, state.player_owned_ship, state.stats, log, current_day=_today, ctx=ctx)
    if not deliver_mission.is_procedural:
        ctx.completed_mission_ids.add(deliver_mission.mission_id)
    try:
        state.player_active_missions.remove(deliver_mission)
    except ValueError:
        pass
    ctx.player_active_missions = state.player_active_missions
    return None

def _resolve_npc_work(state, npc_obj, planet_tier):
    """Offer and accept missions at an NPC's board."""
    ctx = state.ctx
    log = state.log
    if len(state.player_active_missions) >= mission_module.MAX_ACTIVE_MISSIONS:
        log.add(f'Your mission log is full ({mission_module.MAX_ACTIVE_MISSIONS}/{mission_module.MAX_ACTIVE_MISSIONS}). Abandon one first (Q).')
        return None
    _board = mission_module.ensure_board(ctx, npc_obj.id, max_slots=5, planet_id=state.current_city_id)
    _active_ids = frozenset((m.mission_id for m in state.player_active_missions))
    _completed_ids = frozenset(ctx.completed_mission_ids)
    if _board.last_refresh_month != ctx.time_month:
        mission_module.fill_empty_slots(_board, planet_tier=planet_tier, completed_ids=_completed_ids, active_ids=_active_ids, planet_id=state.current_city_id, generated=ctx.generated_missions, ctx=ctx)
        _board.last_refresh_month = ctx.time_month
    offerings = mission_module.board_offerings(_board, generated=ctx.generated_missions)
    if not offerings:
        log.add(f'{npc_obj.name} has no work for you right now.')
        return None
    outcome, picked = _run_mission_offerings(ctx, npc_obj, offerings)
    if outcome is MissionOutcome.QUIT:
        return 'QUIT'
    if outcome is MissionOutcome.ACCEPT and picked is not None and mission_module.try_accept_mission(picked, state.player_owned_ship, log, active_count=len(state.player_active_missions)):
        _accept_mission(state, npc_obj, picked, _board, log)
    return None

def _accept_mission(state, npc_obj, picked, board, log):
    """Commit an accepted mission and set up its bounty/wreck spawns."""
    ctx = state.ctx
    mission_module.board_remove(board, picked.id)
    _bounty_spawn_id, _wreck_spawn_id, _spawn_ok = _prepare_mission_spawns(ctx, picked, board, log)
    if not _spawn_ok:
        return None
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

def _prepare_mission_spawns(ctx, picked, board, log):
    """Set up bounty/wreck spawns; returns (bounty_id, wreck_id, ok)."""
    _bounty_spawn_id = None
    _wreck_spawn_id = None
    if picked.target_enemy_id is None or picked.target_system_id is None:
        return (_bounty_spawn_id, _wreck_spawn_id, True)
    _bounty_spawn_id = f'bounty_{picked.id}_{int(time.time())}'
    _squad_size = getattr(picked, 'bounty_target_squad_size', 1)
    try:
        _target_sys = solar_systems_module.find_solar_system(picked.target_system_id)
        _used = frozenset(((_bs.pos.x, _bs.pos.y) for _bs in ctx.bounty_spawns.get(picked.target_system_id, [])))
        _spawn_pos = _pick_bounty_spawn_pos(_target_sys, used_positions=_used)
    except KeyError:
        return (_bounty_spawn_id, _wreck_spawn_id, True)
    if _spawn_pos is None:
        mission_module.board_return_static(board, picked.id)
        log.add(f'Cannot accept: {_target_sys.name} bounty system full. Clear an existing bounty first.')
        return (_bounty_spawn_id, _wreck_spawn_id, False)
    _wreck_spawn_id = _place_bounty_squad(ctx, picked, _target_sys, _spawn_pos, _bounty_spawn_id, _squad_size, log)
    return (_bounty_spawn_id, _wreck_spawn_id, True)

def _place_bounty_squad(ctx, picked, target_sys, spawn_pos, bounty_spawn_id, squad_size, log):
    """Place a bounty squad and any salvage wreck; returns the wreck id."""
    from .data.npc_ships import find_npc_ship as _bfns
    _wingmate_enemy_id = getattr(picked, 'bounty_wingmate_enemy_id', None) or picked.target_enemy_id
    _bounty_warning_range = 0
    try:
        _bounty_spec = _bfns(picked.target_enemy_id)
        _bounty_warning_range = max(12, _bounty_spec.detect_radius * 2)
    except (KeyError, ImportError):
        pass
    _heist_sid = None
    if getattr(picked, 'heist_target_good_id', None) is not None and getattr(picked, 'salvage_layout_id', None) is None:
        _heist_sid = bounty_spawn_id
    _bs = BountySpawn(spawn_id=bounty_spawn_id, enemy_id=picked.target_enemy_id, pos=spawn_pos, bounty_target_name=getattr(picked, 'bounty_target_name', None), squad_size=squad_size, loadout_pct=getattr(picked, 'bounty_target_loadout_pct', 0), comms_warning_range=_bounty_warning_range, heist_spawn_id=_heist_sid)
    if picked.target_system_id not in ctx.bounty_spawns:
        ctx.bounty_spawns[picked.target_system_id] = []
    ctx.bounty_spawns[picked.target_system_id].append(_bs)
    _wing_offsets = [(2, 0), (-2, 0), (0, 2), (0, -2), (2, 2)]
    for _wi in range(min(squad_size - 1, len(_wing_offsets))):
        _wox, _woy = _wing_offsets[_wi]
        _wpos = world.Position(spawn_pos.x + _wox, spawn_pos.y + _woy)
        if 0 <= _wpos.x < target_sys.width and 0 <= _wpos.y < target_sys.height:
            _wbs = BountySpawn(spawn_id=f'{bounty_spawn_id}_wing{_wi}', enemy_id=_wingmate_enemy_id, pos=_wpos, bounty_target_name=None, squad_size=squad_size, loadout_pct=0, squad_group_id=bounty_spawn_id, comms_warning_range=0)
            ctx.bounty_spawns[picked.target_system_id].append(_wbs)
    _squad_note = f' ({squad_size}-ship squad)' if squad_size > 1 else ''
    _wreck_spawn_id = None
    if getattr(picked, 'salvage_wreck_enemy_id', None) is not None:
        _wreck_spawn_id = f'wreck_{picked.id}_{int(time.time())}'
        _wreck_pos = world.Position(min(spawn_pos.x + 5, target_sys.width - 1), spawn_pos.y)
        _wbs = BountySpawn(spawn_id=_wreck_spawn_id, enemy_id=picked.salvage_wreck_enemy_id, pos=_wreck_pos, bounty_target_name=None, squad_size=1, loadout_pct=0, salvage_wreck=True)
        ctx.bounty_spawns[picked.target_system_id].append(_wbs)
        log.add(f'Salvage site marked in {target_sys.name}: wreck + {squad_size}-ship patrol.')
    else:
        log.add(f'Bounty target marked in {target_sys.name}.{_squad_note}')
    return _wreck_spawn_id
