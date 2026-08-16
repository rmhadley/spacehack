"""Main gameplay loop orchestration.

The title/menu dispatcher lives in :mod:`spacehack.title_flow`; this module
contains the long-lived city, space, and dungeon event loop.
"""
from __future__ import annotations
from . import character, faction, main_quest as main_quest_module, message_log
from . import mission as mission_module
from . import ship as ship_module
from . import solar_system as solar_system_module
from . import tutorial as tutorial_module
from . import world
from . import combat
from . import pygame_engine
from .data.classes import find_class
from .data.species import find_species
from .game_context import GameContext
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from .time import tick_move
from .hud import ground_player_fg as _ground_player_fg
from .npc_ships import render_npc_flash_events
from .xp import add_xp as _add_xp
from .input_helpers import _movement_action, _is_q_press, _is_m_press, _is_period_press, _is_g_press, _is_o_press, _is_p_press, _is_r_press, _is_i_press, _is_backslash_press, _is_t_press, _is_f_press, _is_c_press, _is_shift_x_press, _is_shift_r_press, _is_shift_d_press, _is_shift_o_press, _is_f5_press, _is_f6_press, _is_f9_press, _try_open_guide
from .menus import QuestLogOutcome, _run_quest_log
from .navigation import GotoOutcome, NavigationOutcome, _run_navigation, _run_goto, _remove_bounty_spawn
from .pygame_runtime import PygameContext
from .game_interactions import GameLoopState, resolve_blocker
from .game_flow import _run_combat_loop, _save_and_exit, _open_character_for_mode, _pickup_loot_near, _run_pygame_exit_confirm, _dungeon_post_move_tick, _adopt_dungeon_transition, _handle_dungeon_exit_tile, _maybe_show_post_prison_orbit_in_space, _is_salvage_secured

def _present_overlay(state, ctx, console, map_h, location, space_view=None):
    """Capture and present the Pygame HUD overlay."""
    if getattr(ctx.context, '_runtime', None) is None:
        raise RuntimeError('The shared Pygame runtime is required for gameplay presentation')
    from . import pygame_overlay
    _has_trade = any(e.trade_terminal for e in state.game_map.entities) if state.current_mode == 'city' else False
    _has_mech = any(e.mech_terminal for e in state.game_map.entities) if state.current_mode == 'city' else False
    _has_armory = any(e.armory_terminal for e in state.game_map.entities) if state.current_mode == 'city' else False
    _shield_bubbles = ()
    if space_view is not None:
        _cam_x, _cam_y, _rx, _ry, _view_w, _view_h = space_view
        _shield_bubbles = pygame_overlay.shield_bubbles_for_map(
            state.game_map, camera_x=_cam_x, camera_y=_cam_y,
            region_w=_view_w, region_h=_view_h, region_x=_rx, region_y=_ry,
            player_owned_ship=ctx.player_owned_ship,
        )
    _overlay = pygame_overlay.capture(
        ctx, mode=state.current_mode, location=location,
        screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
        hud_view_height=map_h, has_trade_terminal=_has_trade,
        has_mech_terminal=_has_mech, has_armory_terminal=_has_armory,
        shields=_shield_bubbles,
    )
    if _overlay is None:
        raise RuntimeError('The shared Pygame runtime is required for gameplay presentation')
    ctx.context.present(console, overlay=_overlay)


def _tint_player_glyph(state) -> None:
    """Tint the on-map '@' to mirror ground health each frame.

    A wounded character signals "heal now" at a glance. Space mode
    shows the ship hull instead; its own HUD carries the readout.
    """
    if state.current_mode == 'space':
        return
    state.player.fg = _ground_player_fg(
        state.ctx.ground_hp, state.ctx.ground_max_hp,
    )


def _present_frame(state):
    """Present one gameplay frame."""
    ctx = state.ctx
    console = state.console
    map_w = state.map_w
    map_h = state.map_h
    main_quest_module.check_quest_gates(ctx)
    tutorial_module.tick(ctx, mode=state.current_mode)
    _maybe_show_post_prison_orbit_in_space(ctx, state.current_mode)
    if ctx.main_quest_pending_message:
        _summon = ctx.main_quest_pending_message
        _objective = ctx.main_quest_pending_objective
        main_quest_module.show_quest_summon(ctx, _summon, objective=_objective)
        ctx.main_quest_pending_message = ''
        ctx.main_quest_pending_objective = ''
    console.clear()
    _tint_player_glyph(state)
    if state.current_mode == 'space':
        view_w = solar_system_module.SOL_VIEW_W
        view_h = solar_system_module.SOL_VIEW_H
        cam_x, cam_y, rx, ry = world.camera_for_view(state.game_map, state.player.pos, region_w=view_w, region_h=view_h)
        world.render_world_view(console, state.game_map, region_x=rx, region_y=ry, region_w=view_w, region_h=view_h, camera_x=cam_x, camera_y=cam_y)
        render_npc_flash_events(console, ctx, cam_x, cam_y, view_w, view_h)
    elif state.current_mode == 'dungeon':
        cam_x, cam_y, rx, ry = world.camera_for_view(state.game_map, state.player.pos, region_w=map_w, region_h=map_h)
        world.render_world_view(console, state.game_map, region_x=rx, region_y=ry, region_w=map_w, region_h=map_h, camera_x=cam_x, camera_y=cam_y)
    else:
        world.render_world(console, state.game_map, region_x=0, region_y=0, region_w=map_w, region_h=map_h)
    if state.current_mode == 'space':
        _location = solar_system_module.current_system().name
    elif state.current_mode == 'dungeon':
        _location = getattr(state.game_map, 'location_name', 'Derelict Ship')
    else:
        _location = state.current_city_id.replace('_', ' ').title()
    _space_view = (
        cam_x, cam_y, rx, ry, view_w, view_h
    ) if state.current_mode == 'space' else None
    _present_overlay(state, ctx, console, map_h, _location, _space_view)

def _handle_dev_quest_event(state, event):
    """Handle developer main-quest selection."""
    if not _is_shift_o_press(event):
        return None
    import os as _os
    if _os.environ.get('SPACEHACK_DEV'):
        from .dev_mode import Outcome as _DevOutcome, advance_main_quest as _advance_main_quest, choose_main_quest_faction as _choose_main_quest_faction
        ctx = state.ctx
        if ctx.main_quest_chain:
            state.log.add(f'[DEV MODE] Act 0 faction already set to {ctx.main_quest_chain}.')
        else:
            _faction_outcome, _faction_id = _choose_main_quest_faction(ctx.context)
            if _faction_outcome is _DevOutcome.QUIT:
                return 'QUIT'
            if _faction_outcome is _DevOutcome.CONFIRM and _faction_id is not None:
                _advance_main_quest(ctx, _faction_id)
    return 'HANDLED'


def _reload_text_overlay_dev(state) -> None:
    """Dev-only: re-parse the story-text JSON overlay (F5)."""
    import os as _os
    if not _os.environ.get('SPACEHACK_DEV'):
        return
    from .data.main_quest import reload_text_overlay as _mq_text
    from .data.npcs import reload_text_overlay as _npc_text
    from .data.trade_goods import reload_text_overlay as _goods_text
    _mq_text()
    _npc_text()
    _goods_text()
    state.log.add('Dev: story text overlay reloaded (F5).')


def _dev_quicksave(state) -> None:
    """Dev-only: write the quicksave checkpoint file (F6)."""
    import os as _os
    if not _os.environ.get('SPACEHACK_DEV'):
        return
    from .dev_mode import quick_save as _quick_save
    _system_id = solar_system_module.current_solar_system_id
    if state.current_mode == 'dungeon':
        _quick_save(
            state.ctx,
            mode='dungeon',
            city_id=state.current_city_id,
            system_id=_system_id,
            space_player_pos=(
                (state.space_player.pos.x, state.space_player.pos.y)
                if state.space_player else None
            ),
        )
    else:
        _quick_save(
            state.ctx,
            mode=state.current_mode,
            city_id=state.current_city_id,
            system_id=_system_id,
        )
    state.log.add('[DEV MODE] Quicksaved (F6).')


def _replace_game_state(state, loaded_ctx) -> None:
    """Swap the running loop state onto a loaded context, in place.

    ``_run_gameplay`` holds one ``GameLoopState`` object for the whole
    session, so quickload mutates its fields rather than reassigning it
    (mirrors ``_apply_movement_interaction``'s field-copy pattern).
    """
    _new = _loaded_game_state(
        state.ctx.context, state.console, state.map_w, state.map_h, loaded_ctx,
    )
    state.ctx = _new.ctx
    state.log = _new.log
    state.stats = _new.stats
    state.game_map = _new.game_map
    state.player = _new.player
    state.current_mode = _new.current_mode
    state.current_city_id = _new.current_city_id
    state.city_game_map = _new.city_game_map
    state.city_player = _new.city_player
    state.space_game_map = _new.space_game_map
    state.space_player = _new.space_player
    state.player_owned_ship = _new.player_owned_ship
    state.player_active_missions = _new.player_active_missions


def _dev_quickload(state) -> None:
    """Dev-only: restore the quicksave checkpoint (F9)."""
    import os as _os
    if not _os.environ.get('SPACEHACK_DEV'):
        return
    from .dev_mode import quick_load as _quick_load
    _ctx = _quick_load(state.ctx.context)
    if _ctx is None:
        state.log.add('Dev: no quicksave to load - press F6 to save one.')
        return
    _replace_game_state(state, _ctx)
    state.log.add('[DEV MODE] Quicksave loaded (F9).')


def _handle_dev_event(state, event):
    """Handle developer-only input."""
    ctx = state.ctx
    log = state.log
    if _is_f5_press(event):
        _reload_text_overlay_dev(state)
        return 'HANDLED'
    if _is_f6_press(event):
        _dev_quicksave(state)
        return 'HANDLED'
    if _is_f9_press(event):
        _dev_quickload(state)
        return 'HANDLED'
    if _is_shift_x_press(event):
        import os as _os
        if _os.environ.get('SPACEHACK_DEV'):
            _add_xp(ctx, 200)
        return 'HANDLED'
    if _is_shift_r_press(event):
        import os as _os
        if _os.environ.get('SPACEHACK_DEV') and state.current_mode == 'dungeon':
            if state.game_map.seen is not None:
                for _row in state.game_map.seen:
                    for _i in range(len(_row)):
                        _row[_i] = True
                if state.game_map.visible is not None:
                    for _row in state.game_map.visible:
                        for _i in range(len(_row)):
                            _row[_i] = True
                log.add('Dev: fog of war fully revealed.')
        return 'HANDLED'
    if _is_shift_d_press(event):
        import os as _os
        if _os.environ.get('SPACEHACK_DEV'):
            from .time import advance_time as _adv_time
            _adv_time(ctx, 30)
            log.add('Dev: skipped 30 days.')
        return 'HANDLED'
    return _handle_dev_quest_event(state, event)

def _handle_menu_event(state, event):
    """Handle character, faction, and quest-log input."""
    ctx = state.ctx
    log = state.log
    if _is_f_press(event):
        from .menus._ship_menu import _run_faction_view
        _run_faction_view(ctx)
        return 'HANDLED'
    if _is_c_press(event):
        _open_character_for_mode(ctx)
        return 'HANDLED'
    if _is_q_press(event):
        outcome, abandoned_idx = _run_quest_log(ctx)
        if outcome is QuestLogOutcome.QUIT:
            return 'QUIT'
        if outcome is QuestLogOutcome.ABANDONED and abandoned_idx is not None:
            if 0 <= abandoned_idx < len(state.player_active_missions):
                abandoned = state.player_active_missions[abandoned_idx]
                log.add(f'You abandoned: {abandoned.title}.')
                mission_module.abort_mission(abandoned, state.player_owned_ship, log)
                if getattr(abandoned, 'main_quest_step_id', ''):
                    main_quest_module.fail_smuggle_step(ctx, abandoned)
                if not abandoned.is_procedural:
                    _board = mission_module.find_board_for_mission(ctx, abandoned.mission_id)
                    if _board is not None:
                        mission_module.board_return_static(_board, abandoned.mission_id)
                if abandoned.bounty_spawn_id is not None:
                    _remove_bounty_spawn(ctx, abandoned.bounty_spawn_id, abandoned.target_system_id)
                _wreck_sid_ab = getattr(abandoned, 'salvage_wreck_spawn_id', None)
                if _wreck_sid_ab is not None:
                    _remove_bounty_spawn(ctx, _wreck_sid_ab, abandoned.target_system_id)
                    ctx.interiors.pop(_wreck_sid_ab, None)
                del state.player_active_missions[abandoned_idx]
                ctx.player_active_missions = state.player_active_missions
        return 'HANDLED'
    return None

def _handle_map_navigation_event(state, event):
    """Handle the space map shortcut."""
    if state.current_mode != 'space' or not _is_m_press(event):
        return None
    if _run_navigation(state.ctx, state.player.pos) is NavigationOutcome.QUIT:
        return 'QUIT'
    return 'HANDLED'


def _handle_common_modal_event(state, event):
    """Handle dungeon/space pickup, reload, cargo, and log modals."""
    ctx = state.ctx
    if state.current_mode == 'dungeon' and _is_r_press(event):
        from .ground_reload_ui import reload_exploration
        reload_exploration(ctx)
        return 'HANDLED'
    if state.current_mode in ('dungeon', 'space') and _is_p_press(event):
        if _pickup_loot_near(ctx) and state.current_mode == 'space':
            tutorial_module.notify_pickup(ctx)
        return 'HANDLED'
    if _is_backslash_press(event):
        from .console_log import open_console_log as _open_console_log
        if _open_console_log(ctx) == 'QUIT':
            _save_and_exit(ctx, state.current_mode, state.current_city_id, state.space_player)
            return 'QUIT'
        return 'HANDLED'
    if _is_i_press(event):
        from .trade import open_cargo as _open_cargo
        _open_cargo(ctx)
        return 'HANDLED'
    return None


def _handle_goto_event(state, event):
    """Handle space Go To."""
    if state.current_mode != 'space' or not _is_g_press(event):
        return None
    _goto_outcome, _goto_combat = _run_goto(state.ctx, state.console, state.player)
    if _goto_outcome is GotoOutcome.COMBAT and _goto_combat is not None:
        combat._handle_combat_encounter(state.ctx, state.console, _goto_combat)
        _run_combat_loop(state.ctx, state.console, state.player)
        state.player_active_missions = state.ctx.player_active_missions
    return 'HANDLED'


def _handle_comms_event(state, event):
    """Handle space comms."""
    if state.current_mode != 'space' or not _is_t_press(event):
        return None
    from .comms import open_comms as _open_comms
    _attack_data = _open_comms(state.ctx, state.player.pos)
    if _attack_data is not None:
        combat._handle_combat_encounter(state.ctx, state.console, _attack_data)
        state.player_active_missions = state.ctx.player_active_missions
    return 'HANDLED'


def _handle_wait_event(state, event):
    """Handle period/wait in space or a dungeon."""
    if not _is_period_press(event):
        return None
    if state.current_mode == 'space' and state.player_owned_ship is not None:
        _run_combat_loop(state.ctx, state.console, state.player, also_move_npcs=True)
        state.player_active_missions = state.ctx.player_active_missions
    elif state.current_mode == 'dungeon':
        _dctrl = _dungeon_post_move_tick(state.ctx, state.console, state.game_map)
        if _dctrl == 'DEFEAT':
            return 'QUIT'
        if _dctrl == 'COMBAT':
            return 'HANDLED'
    state.ctx.log.add('You wait.')
    return 'HANDLED'


def _handle_space_modal_event(state, event):
    """Handle space, dungeon, and shared modal input."""
    for _handler in (
        _handle_map_navigation_event,
        _handle_common_modal_event,
        _handle_goto_event,
        _handle_comms_event,
        _handle_wait_event,
    ):
        _result = _handler(state, event)
        if _result is not None:
            return _result
    return None

def _handle_dungeon_automation_event(state, event):
    """Handle dungeon goto and auto-explore input."""
    ctx = state.ctx
    console = state.console
    map_w = state.map_w
    map_h = state.map_h
    if state.current_mode == 'dungeon' and _is_g_press(event):
        from .autoexplore import run_dungeon_goto
        _g_result = run_dungeon_goto(ctx, console, state.game_map, state.player, post_step_tick=_dungeon_post_move_tick, map_w=map_w, map_h=map_h, location=getattr(state.game_map, 'location_name', 'Derelict Ship'))
        if _g_result == 'DEFEAT':
            return 'QUIT'
        if _g_result == 'COMBAT':
            return 'HANDLED'
        return 'HANDLED'
    if _is_o_press(event):
        if state.current_mode != 'dungeon':
            ctx.log.add('Auto-explore only works inside dungeons.')
            return 'HANDLED'
        from .autoexplore import run_auto_explore
        _ae_result = run_auto_explore(ctx, console, state.game_map, state.player, post_step_tick=_dungeon_post_move_tick, map_w=map_w, map_h=map_h, location=getattr(state.game_map, 'location_name', 'Derelict Ship'))
        if _ae_result == 'DEFEAT':
            return 'QUIT'
        if _ae_result == 'COMBAT':
            return 'HANDLED'
        return 'HANDLED'
    return None

def _handle_non_movement_event(state, event):
    """Handle global, modal, and dungeon automation events."""
    ctx = state.ctx
    if pygame_engine.quit_or_escape(event):
        if pygame_engine.is_escape(event):
            if not _run_pygame_exit_confirm(ctx):
                return 'HANDLED'
        _save_and_exit(ctx, state.current_mode, state.current_city_id, state.space_player)
        return 'QUIT'
    if _try_open_guide(event, ctx):
        return 'HANDLED'
    _result = _handle_dev_event(state, event)
    if _result is not None:
        return _result
    _result = _handle_menu_event(state, event)
    if _result is not None:
        return _result
    _result = _handle_space_modal_event(state, event)
    if _result is not None:
        return _result
    _result = _handle_dungeon_automation_event(state, event)
    if _result is not None:
        return _result
    return None

def _handle_stairs_down(state):
    """Handle a descending stair transition."""
    ctx, log = state.ctx, state.log
    from .dungeon_extensions import enter_extension, extension_id_at, transition_floor
    try:
        if ctx.dungeon_extension is not None and ctx.dungeon_extension.active:
            _next_map, _next_player = transition_floor(ctx, 1)
            _message = 'You descend deeper into the facility.'
        else:
            _extension_id = extension_id_at(state.game_map, state.player.pos)
            _parent_key = next((_key for _key, _map in ctx.interiors.items() if _map is state.game_map), '')
            if _extension_id is None:
                raise ValueError('No dungeon extension is attached here')
            _next_map, _next_player = enter_extension(
                ctx, state.game_map, state.player,
                extension_id=_extension_id, parent_map_key=_parent_key,
            )
            _message = 'You descend into the alien facility.'
    except (KeyError, ValueError):
        log.add('The stairs lead nowhere yet.')
    else:
        state.game_map, state.player = _next_map, _next_player
        _adopt_dungeon_transition(ctx, state.game_map, state.player)
        state.current_mode = 'dungeon'
        log.add(_message)
    return 'HANDLED'


def _handle_stairs_up(state):
    """Handle an ascending stair transition."""
    ctx, log = state.ctx, state.log
    from .dungeon_extensions import leave_extension, transition_floor
    try:
        if ctx.dungeon_extension is not None and ctx.dungeon_extension.active and ctx.dungeon_extension.current_floor > 1:
            _parent_map, _parent_player = transition_floor(ctx, -1)
            _message = 'You climb back toward the upper prison.'
        else:
            _parent_map, _parent_player = leave_extension(ctx, state.game_map)
            _message = 'You return to the Mars surface.'
    except ValueError:
        log.add('The stairs are sealed.')
    else:
        state.game_map, state.player = _parent_map, _parent_player
        ctx.game_map, ctx.player = state.game_map, state.player
        log.add(_message)
    return 'HANDLED'


def _handle_dungeon_stairs(state, tile):
    """Handle one dungeon stair transition, if present."""
    if tile.kind == 'stairs_down':
        return _handle_stairs_down(state)
    if tile.kind == 'stairs_up':
        return _handle_stairs_up(state)
    return None


def _remove_secured_salvage_entities(space_game_map, wreck_spawn_id):
    """Remove a secured wreck and its completed guard squad from space."""
    if space_game_map is None or not wreck_spawn_id:
        return
    _group_id = (
        wreck_spawn_id[:-6]
        if wreck_spawn_id.endswith("_wreck")
        else wreck_spawn_id
    )
    space_game_map.entities[:] = [
        _entity for _entity in space_game_map.entities
        if not (
            getattr(_entity, "salvage_wreck_spawn_id", None) == wreck_spawn_id
            or getattr(_entity, "bounty_spawn_id", None) == _group_id
            or getattr(_entity, "bounty_squad_id", None) == _group_id
        )
    ]


def _handle_dungeon_move(state, console, code):
    """Handle dungeon post-move transitions."""
    if code != 'moved' or state.current_mode != 'dungeon':
        return None
    _dctrl = _dungeon_post_move_tick(state.ctx, console, state.game_map)
    if _dctrl in {'DEFEAT', 'COMBAT'}:
        return 'QUIT' if _dctrl == 'DEFEAT' else 'HANDLED'
    _tile = state.game_map.tiles[state.player.pos.y][state.player.pos.x]
    _stairs_result = _handle_dungeon_stairs(state, _tile)
    if _stairs_result is not None:
        return _stairs_result
    if _tile.kind != 'exit':
        return None
    _wreck_spawn_id = getattr(state.game_map, "wreck_spawn_id", None)
    _wreck_secured = (
        _wreck_spawn_id is not None
        and _is_salvage_secured(
            state.ctx, _wreck_spawn_id, state.player_active_missions,
        )
    )
    _exit_transition = _handle_dungeon_exit_tile(
        state.ctx, _tile.kind, state.game_map, state.space_game_map,
        state.space_player, state.player_owned_ship,
        state.player_active_missions, state.log,
    )
    if _exit_transition is None:
        return 'HANDLED'
    state.game_map, state.player, state.current_mode = _exit_transition
    state.space_game_map, state.space_player = state.game_map, state.player
    if _wreck_secured:
        _remove_secured_salvage_entities(
            state.game_map, _wreck_spawn_id,
        )
    return 'HANDLED'

def _apply_movement_interaction(state, code, blocker, dx, dy):
    """Apply blocker interactions and copy state transitions back."""
    _state = GameLoopState(
        ctx=state.ctx, console=state.console, map_w=state.map_w, map_h=state.map_h,
        log=state.log, stats=state.stats, game_map=state.game_map,
        player=state.player, current_mode=state.current_mode,
        current_city_id=state.current_city_id, city_game_map=state.city_game_map,
        city_player=state.city_player, space_game_map=state.space_game_map,
        space_player=state.space_player, player_owned_ship=state.player_owned_ship,
        player_active_missions=state.player_active_missions,
    )
    _result = resolve_blocker(_state, code, blocker, dx, dy)
    state.game_map, state.player = _state.game_map, _state.player
    state.current_mode, state.current_city_id = _state.current_mode, _state.current_city_id
    state.city_game_map, state.city_player = _state.city_game_map, _state.city_player
    state.space_game_map, state.space_player = _state.space_game_map, _state.space_player
    state.player_owned_ship = _state.player_owned_ship
    state.player_active_missions = _state.player_active_missions
    return _result


def _handle_movement_event(state, event):
    """Handle movement and post-move transitions."""
    ctx = state.ctx
    console = state.console
    delta = _movement_action(event)
    if delta is None:
        return 'HANDLED'
    dx, dy = delta
    if state.current_mode == 'dungeon':
        _tx, _ty = (state.player.pos.x + dx, state.player.pos.y + dy)
        if state.game_map.in_bounds(_tx, _ty):
            _wall_blocker = next((_e for _e in state.game_map.entities if _e.pos.x == _tx and _e.pos.y == _ty and _e.npc_id), None)
            if _wall_blocker is not None:
                code, blocker = ('occupied', _wall_blocker)
            else:
                code, blocker = world.try_move(state.player, state.game_map, dx, dy)
        else:
            code, blocker = world.try_move(state.player, state.game_map, dx, dy)
    else:
        code, blocker = world.try_move(state.player, state.game_map, dx, dy)
    if code == 'moved' and state.current_mode == 'city':
        tutorial_module.notify_move(ctx)
    if code == 'moved' and state.current_mode == 'space' and (state.player_owned_ship is not None):
        _run_combat_loop(ctx, console, state.player, also_move_npcs=True)
        state.player_active_missions = ctx.player_active_missions
        tick_move(ctx)
    _dungeon_result = _handle_dungeon_move(state, console, code)
    if _dungeon_result is not None:
        return _dungeon_result
    _interaction_result = _apply_movement_interaction(
        state, code, blocker, dx, dy,
    )
    if _interaction_result == 'QUIT':
        return 'QUIT'
    if _interaction_result == 'CONTINUE':
        return 'HANDLED'

def _process_events(state):
    """Process input events."""
    ctx = state.ctx
    for event in ctx.context.wait_events():
        _result = _handle_non_movement_event(state, event)
        if _result is not None:
            if _result == 'QUIT':
                return 'QUIT'
            continue
        _result = _handle_movement_event(state, event)
        if _result == 'QUIT':
            return 'QUIT'

def _run_gameplay(state):
    """Run the city, space, and dungeon loop until death or exit."""
    while not state.ctx.player_dead:
        _present_frame(state)
        _result = _process_events(state)
        if _result == 'QUIT':
            return None

def _loaded_game_state(context, console, map_w, map_h, loaded_ctx):
    """Build gameplay state from a saved context."""
    space_game_map = None
    space_player = None
    ctx = loaded_ctx
    game_map = ctx.game_map
    player = ctx.player
    stats = ctx.stats
    log = ctx.log
    player_owned_ship = ctx.player_owned_ship
    player_active_missions = ctx.player_active_missions
    current_city_id: str = ctx.current_city_id
    current_mode = getattr(ctx, '_loaded_mode', 'city')
    if current_mode == 'dungeon':
        space_game_map = getattr(ctx, '_space_game_map', None)
        space_player = getattr(ctx, '_space_player', None)
        from .dungeon import reveal_around as _load_reveal
        if game_map.seen is not None:
            _load_reveal(game_map, player.pos, radius=game_map.sight_radius)
    elif current_mode != 'space':
        city_game_map = game_map
        city_player = player
    runtime = getattr(context, '_runtime', None)
    if runtime is not None:
        runtime.game_context = ctx
    return GameLoopState(ctx=ctx, console=console, map_w=map_w, map_h=map_h, log=log, stats=stats, game_map=game_map, player=player, current_mode=current_mode, current_city_id=current_city_id, city_game_map=locals().get('city_game_map'), city_player=locals().get('city_player'), space_game_map=space_game_map, space_player=space_player, player_owned_ship=player_owned_ship, player_active_missions=player_active_missions)

def _new_character_context(context, species_id, class_id):
    """Create the city, player, starter ship, and fresh game context."""
    species = find_species(species_id)
    klass = find_class(class_id)
    city_width, city_height = (60, 40)
    game_map = world.make_city(width=city_width, height=city_height)
    player = world.Entity(char='@', fg=(255, 255, 255), pos=world.Position(x=city_width // 2, y=city_height // 2), name='Player')
    game_map.entities.append(player)
    stats = character.starting_stats(species_id, class_id)
    log = message_log.MessageLog(capacity=MSG_LOG_HEIGHT)
    for message in (f'You arrive in a quiet Earth city as a {species.name} {klass.name}.', "The cobblestones are damp from last night's rain.", 'Move with arrow keys, h/j/k/l, or numpad; diagonals y/u/b/n.', 'Buildings: North-West space port, South-West merchant guild,', 'Bar in the plaza, militia + bounty guild on the South-East.', 'Visit the guild halls to find work or the port to upgrade your ship.'):
        log.add(message)
    starter_ship = ship_module.find_ship('starter')
    from .data.ships.core import STARTER_NAMES as _starter_names
    from .engine import RNG as _rng
    ship_name = _rng.choice(_starter_names)
    starter_entity = world.Entity(char=starter_ship.char, fg=starter_ship.fg, pos=world.HANGAR_ANCHOR, name=f'Your Ship: {ship_name}', ship_id=starter_ship.id, owned=True)
    game_map.entities.append(starter_entity)
    owned_ship = ship_module.OwnedShip(ship_id=starter_ship.id, display_name=ship_name, weapons=starter_ship.start_weapons, modules=starter_ship.start_modules, fuel=starter_ship.max_fuel)
    log.add(f'Your {ship_name} is docked at the space port.')
    from .dev_mode import apply_dev_overrides as _apply_dev_overrides
    starter_ship, starter_entity, owned_ship = _apply_dev_overrides(starter_ship, starter_entity, owned_ship, stats, log)
    active_missions = []
    character_info = {'species_id': species_id, 'species_name': species.name, 'class_id': class_id, 'class_name': klass.name}
    ctx = GameContext(context=context, character_info=character_info, log=log, game_map=game_map, player=player, stats=stats, player_owned_ship=owned_ship, player_active_missions=active_missions)
    return (ctx, game_map, player, stats, log, owned_ship, active_missions)

def _configure_new_context(ctx, species_id, class_id, tutorial):
    """Apply new-game faction, ground, tutorial, and runtime state."""
    runtime = getattr(ctx.context, '_runtime', None)
    if runtime is not None:
        runtime.game_context = ctx
    ctx.faction_reputation = faction.starting_reputation(species_id, class_id)
    ctx.ground_stats = character.starting_ground_stats(species_id, class_id)
    from .xp import ground_max_hp_bonus as _ground_max_hp_bonus
    ctx.ground_max_hp = 20 + ctx.ground_stats.stamina // 3 + _ground_max_hp_bonus(ctx)
    ctx.ground_hp = ctx.ground_max_hp
    from .dev_mode import apply_dev_ground_loadout as _apply_dev_ground_loadout
    _apply_dev_ground_loadout(ctx)
    if tutorial:
        from .tutorial import setup_tutorial as _setup_tutorial
        _setup_tutorial(ctx)
    solar_system_module.set_current_solar_system('sol')

def _new_game_state(context, console, map_w, map_h, species_id, class_id, tutorial):
    """Build gameplay state for a new character."""
    ctx, game_map, player, stats, log, owned_ship, active_missions = _new_character_context(context, species_id, class_id)
    _configure_new_context(ctx, species_id, class_id, tutorial)
    return GameLoopState(ctx=ctx, console=console, map_w=map_w, map_h=map_h, log=log, stats=stats, game_map=game_map, player=player, current_mode='city', current_city_id='earth', city_game_map=game_map, city_player=player, player_owned_ship=owned_ship, player_active_missions=active_missions)

def _run_game_loop(context: PygameContext, species_id: str='', class_id: str='', *, loaded_ctx: GameContext | None=None, tutorial: bool=False) -> None:
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
        state = _loaded_game_state(context, console, map_w, map_h, loaded_ctx)
    else:
        state = _new_game_state(context, console, map_w, map_h, species_id, class_id, tutorial)
    _run_gameplay(state)
