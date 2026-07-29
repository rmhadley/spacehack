"""City/space transition helpers extracted from ``__main__.py``.

Contains :func:`_animate_ship_to_y`, :func:`_launch_to_space`,
and :func:`_return_to_city`.
"""

from __future__ import annotations
import tcod.console
from . import world
from . import hud
from . import message_log
from . import mission as mission_module
from . import ship as ship_module
from . import solar_system as solar_system_module
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, MSG_LOG_HEIGHT
from .navigation import _add_bounty_spawns_to_map, _responsive_sleep
from .time import format_date


def _animate_ship_to_y(ctx, console: tcod.console.Console, ship_ent: world.Entity, game_map: world.GameMap, *, target_y: int, frame_seconds: float = 0.08, location: str = '') -> None:
    """Walk ``ship_ent.pos.y`` one cell per frame toward ``target_y``.

    Each frame paints ``game_map`` (plus HUD + msg log) around the
    moving ship and calls :meth:`tcod.context.Context.present`. Direction
    is determined by the sign of ``target_y - ship_ent.pos.y``: negative
    walks north (off-screen above), positive walks south. After this
    returns, ``ship_ent.pos.y == target_y``.

    Used by both launch (target offscreen above) and return-to-city
    (target :data:`world.HANGAR_ANCHOR`). ``frame_seconds`` is the
    per-frame sleep; 0.08 reads as a brisk but visible glide.
    """
    direction = -1 if ship_ent.pos.y > target_y else 1
    _has_trade = any(e.trade_terminal for e in game_map.entities)
    _has_mech = any(e.mech_terminal for e in game_map.entities)
    while ship_ent.pos.y != target_y:
        ship_ent.pos = world.Position(ship_ent.pos.x, ship_ent.pos.y + direction)
        console.clear()
        world.render_world(console, game_map, region_x=0, region_y=0, region_w=solar_system_module.SOL_VIEW_W, region_h=solar_system_module.SOL_VIEW_H)
        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=solar_system_module.SOL_VIEW_H, character=ctx.character_info, stats=ctx.stats, location=location or None, date_str=format_date(ctx), has_trade_terminal=_has_trade, has_mech_terminal=_has_mech, player_xp=ctx.player_xp, player_level=ctx.player_level)
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        ctx.context.present(console)
        _responsive_sleep(frame_seconds)


def _launch_to_space(ctx, console: tcod.console.Console, city_game_map: world.GameMap, hangar_ship_ent: world.Entity, ship_obj: ship_module.Ship, current_city_id: str, city_player: world.Entity) -> tuple[world.GameMap, world.Entity]:
    """Animate ``hangar_ship_ent`` off the top of the city viewport and
    return ``(space_game_map, space_player_entity)``.

    The hangar ship is moved offscreen via :func:`_animate_ship_to_y`
    but kept in ``city_game_map.entities`` so the future return
    animation walks the SAME entity back to HANGAR_ANCHOR (no need
    to splice a new entity into/out of the city's entity list).

    The returned ``space_game_map`` is freshly built via
    :func:`solar_system_module.make_solar_system` and has the
    player-ship Entity docked at ``current_city_id`` (whatever
    planet the player just launched from) via
    :func:`solar_system_module.place_docked_ship`.
    """
    if city_player in city_game_map.entities:
        city_game_map.entities.remove(city_player)
    offscreen_y = -(solar_system_module.SOL_VIEW_H // 2) - 1
    if hangar_ship_ent.pos.y > offscreen_y:
        _animate_ship_to_y(ctx, console, hangar_ship_ent, city_game_map, target_y=offscreen_y, location=current_city_id.replace('_', ' ').title())
        ctx.log.add(f'You launch the {ship_obj.name} into space.')
    space_map = solar_system_module.make_solar_system()
    _add_bounty_spawns_to_map(ctx, space_map, solar_system_module.current_solar_system_id)
    from .npc_ships import spawn_npcs as _sn
    _sn(ctx, space_map, solar_system_module.current_solar_system_id)
    origin_planet = solar_system_module.find_planet(current_city_id)
    space_player = solar_system_module.place_docked_ship(ship_obj, origin_planet)
    space_map.entities.append(space_player)
    return (space_map, space_player)


def _return_to_city(ctx, console: tcod.console.Console, hangar_ship_ent: world.Entity, city_game_map: world.GameMap, city_player_ent: world.Entity) -> tuple[world.GameMap, world.Entity]:
    """Animate the same ``hangar_ship_ent`` down to :data:`world.HANGAR_ANCHOR`
    and return ``(city_game_map, city_player_entity)``.

    Mirrors :func:`_launch_to_space`: the ship entity is the SAME
    instance that was animated offscreen during launch, so no
    entity-list swap is needed on the city map.
    """
    _animate_ship_to_y(ctx, console, hangar_ship_ent, city_game_map, target_y=world.HANGAR_ANCHOR.y, location='Earth')
    if city_player_ent not in city_game_map.entities:
        city_game_map.entities.append(city_player_ent)
    ctx.log.add('You return to Earth and dock at your hangar.')
    return (city_game_map, city_player_ent)
