"""Entry point for spacehack.

Run with ``python -m spacehack``.

Flow on a new game:

    species menu  ->  class menu  ->  confirm  ->  game (city + HUD + msg log)
       ^ ESC = quit       ^ ESC = back     ^ ESC = back        ^ ESC = quit

The game screen is a small city + space-port + 4 guild halls.
Movement accepts three key families (see ``world.MOVE_KEYS``):
vim keys (``h`` / ``j`` / ``k`` / ``l`` for cardinals, ``y`` / ``u`` /
``b`` / ``n`` for diagonals), arrow keys, and the numpad. Walking
into a wall logs a short message. Walking onto a tile holding
another solid entity opens a context dialog:

    * ship at the space port -> ship-buy modal (Enter / ESC)
    * guild NPC -> flavor dialog (ESC to leave)
    * loot -> soft floor object; press P to pick it up
    * anything else -> "You bump into X" log line
"""
from __future__ import annotations


from . import main_quest as main_quest_module  # noqa: F401 - compatibility surface
from . import ship as ship_module  # noqa: F401 - compatibility surface
from . import solar_system as solar_system_module  # noqa: F401 - compatibility surface
from . import tutorial as tutorial_module  # noqa: F401 - compatibility surface
from .game_context import GameContext
from .engine import load_tileset, seed_rng
from .input_helpers import Outcome, _run_pick, _run_confirm  # noqa: F401 - compatibility surface
from .combat._rules_ground import init as _ground_init
from .combat._loop import run_combat as _run_combat_unified
from .city import _build_space_return, _launch_to_space
from .menus import ShipBuyOutcome, ShipMenuAction  # noqa: F401 - compatibility surface
from .saveload import save_game as _save_game
from .pygame_runtime import PygameContext, open_runtime


from .game_flow import (
    _run_combat_loop as _flow_run_combat_loop,
    _save_and_exit as _flow_save_and_exit,
    _run_ground_combat_tick as _flow_run_ground_combat_tick,
    _maybe_show_post_prison_orbit as _flow_maybe_show_post_prison_orbit,
    _maybe_show_post_prison_orbit_in_space as _flow_maybe_show_post_prison_orbit_in_space,
    _is_mars_surface_map as _flow_is_mars_surface_map,
    _is_wreck_interior as _flow_is_wreck_interior,
    _is_mars_facility_map as _flow_is_mars_facility_map,
    _notify_surface_exit as _flow_notify_surface_exit,
    _launch_from_city as _flow_launch_from_city,
    _launch_owned_ship as _flow_launch_owned_ship,
    _apply_ship_buy_result as _flow_apply_ship_buy_result,
    _complete_ship_purchase as _flow_complete_ship_purchase,
    _leave_dungeon_to_space as _flow_leave_dungeon_to_space,
    _handle_dungeon_exit as _flow_handle_dungeon_exit,
    _handle_dungeon_exit_tile as _flow_handle_dungeon_exit_tile,
    _is_salvage_secured as _flow_is_salvage_secured,
    _remove_salvage_wreck as _flow_remove_salvage_wreck,
    _apply_ground_combat_rep as _flow_apply_ground_combat_rep,
)


# Compatibility adapters preserve the historical __main__ injection seams while
# the implementations live in game_flow. Existing tests and callers can still
# replace these module attributes without importing the new module directly.
def _run_combat_loop(ctx, console, player, *, also_move_npcs: bool = False):
    return _flow_run_combat_loop(
        ctx, console, player, also_move_npcs=also_move_npcs,
    )


def _save_and_exit(ctx, current_mode, current_city_id, space_player):
    return _flow_save_and_exit(
        ctx,
        current_mode,
        current_city_id,
        space_player,
        save_game=_save_game,
    )


def _apply_ground_combat_rep(ctx, ground_result):
    return _flow_apply_ground_combat_rep(ctx, ground_result)


def _run_ground_combat_tick(ctx, console, game_map):
    return _flow_run_ground_combat_tick(
        ctx,
        console,
        game_map,
        ground_init=_ground_init,
        apply_rep=_apply_ground_combat_rep,
        run_combat=_run_combat_unified,
    )


def _open_character_for_mode(ctx):
    from .character_screen import open_character_screen

    return open_character_screen(ctx, equipment_management=True)


def _pickup_loot_near(ctx):
    from .game_flow import _pickup_loot_near as _flow_pickup_loot_near

    return _flow_pickup_loot_near(ctx)


def _run_pygame_dungeon_confirm(ctx, **kwargs):
    from .game_flow import _run_pygame_dungeon_confirm as _flow_confirm

    return _flow_confirm(ctx, **kwargs)


def _run_pygame_exit_confirm(ctx):
    from .game_flow import _run_pygame_exit_confirm as _flow_confirm

    return _flow_confirm(ctx)


def _maybe_show_post_prison_orbit(ctx, current_city_id, *, from_mars_prison=False):
    return _flow_maybe_show_post_prison_orbit(
        ctx,
        current_city_id,
        from_mars_prison=from_mars_prison,
    )


def _maybe_show_post_prison_orbit_in_space(ctx, current_mode):
    return _flow_maybe_show_post_prison_orbit_in_space(ctx, current_mode)


def _notify_surface_exit(ctx, exited_map):
    return _flow_notify_surface_exit(
        ctx,
        exited_map,
        show_orbit=_maybe_show_post_prison_orbit,
    )


def _launch_owned_ship(
    ctx,
    console,
    result,
    player_owned_ship,
    city_game_map,
    city_player,
    current_city_id,
    ship,
):
    return _flow_launch_owned_ship(
        ctx,
        console,
        result,
        player_owned_ship,
        city_game_map,
        city_player,
        current_city_id,
        ship,
        launch_to_space=_launch_to_space,
        show_orbit=_maybe_show_post_prison_orbit,
    )


def _is_mars_surface_map(ctx, game_map):
    return _flow_is_mars_surface_map(ctx, game_map)


def _is_wreck_interior(game_map):
    return _flow_is_wreck_interior(game_map)


def _is_mars_facility_map(ctx, game_map):
    return _flow_is_mars_facility_map(ctx, game_map)


def _launch_from_city(
    ctx,
    console,
    city_game_map,
    hangar_ship,
    ship,
    current_city_id,
    city_player,
):
    return _flow_launch_from_city(
        ctx,
        console,
        city_game_map,
        hangar_ship,
        ship,
        current_city_id,
        city_player,
        launch_to_space=_launch_to_space,
        show_orbit=_maybe_show_post_prison_orbit,
    )


def _apply_ship_buy_result(
    ctx,
    city_game_map,
    blocker,
    ship,
    player_owned_ship,
    result,
    effective_price,
    trade_in_value,
):
    return _flow_apply_ship_buy_result(
        ctx,
        city_game_map,
        blocker,
        ship,
        player_owned_ship,
        result,
        effective_price,
        trade_in_value,
    )


def _complete_ship_purchase(
    ctx,
    city_game_map,
    blocker,
    ship,
    player_owned_ship,
    effective_price,
    trade_in_value,
):
    return _flow_complete_ship_purchase(
        ctx,
        city_game_map,
        blocker,
        ship,
        player_owned_ship,
        effective_price,
        trade_in_value,
    )


def _leave_dungeon_to_space(
    ctx,
    game_map,
    space_game_map,
    space_player,
    player_owned_ship,
    player_active_missions,
    log,
):
    return _flow_leave_dungeon_to_space(
        ctx,
        game_map,
        space_game_map,
        space_player,
        player_owned_ship,
        player_active_missions,
        log,
        build_space_return=_build_space_return,
        show_orbit=_notify_surface_exit,
    )


def _handle_dungeon_exit(
    ctx,
    game_map,
    space_game_map,
    space_player,
    player_owned_ship,
    player_active_missions,
    log,
):
    return _flow_handle_dungeon_exit(
        ctx,
        game_map,
        space_game_map,
        space_player,
        player_owned_ship,
        player_active_missions,
        log,
        build_space_return=_build_space_return,
        show_orbit=_notify_surface_exit,
    )


def _is_salvage_secured(ctx, wreck_spawn_id, active_missions):
    return _flow_is_salvage_secured(ctx, wreck_spawn_id, active_missions)


def _remove_salvage_wreck(ctx, wreck_spawn_id, space_game_map):
    return _flow_remove_salvage_wreck(ctx, wreck_spawn_id, space_game_map)


def _handle_dungeon_exit_tile(
    ctx,
    tile_kind,
    game_map,
    space_game_map,
    space_player,
    player_owned_ship,
    player_active_missions,
    log,
):
    return _flow_handle_dungeon_exit_tile(
        ctx,
        tile_kind,
        game_map,
        space_game_map,
        space_player,
        player_owned_ship,
        player_active_missions,
        log,
        build_space_return=_build_space_return,
        show_orbit=_notify_surface_exit,
    )

def _run_game(
    context: PygameContext,
    species_id: str = "",
    class_id: str = "",
    *,
    loaded_ctx: GameContext | None = None,
    tutorial: bool = False,
) -> None:
    """Run gameplay inside the already-open shared Pygame runtime."""
    _run_game_loop(
        context,
        species_id,
        class_id,
        loaded_ctx=loaded_ctx,
        tutorial=tutorial,
    )


from .game_loop import _run_game_loop


def run(context: PygameContext) -> None:
    """Show the splash screen and run title/game flow."""
    import os
    from . import title_flow
    from .engine import new_game_seed

    _seed = new_game_seed()
    seed_rng(_seed)
    if os.environ.get("SPACEHACK_DEV"):
        print(f"[DEV MODE] Run seed: {_seed}"
              f"{' (pinned via SPACEHACK_SEED)' if os.environ.get('SPACEHACK_SEED') else ''}")
    title_flow.run_title_flow(
        context,
        _run_game,
        seed_rng=seed_rng,
    )


def main() -> None:
    """Top-level entry: load assets, open window, then run the flow."""
    tileset = load_tileset()
    with open_runtime(tileset) as context:
        run(context)
if __name__ == '__main__':
    main()
