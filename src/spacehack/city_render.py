"""Camera-backed rendering helpers for oversized city maps."""

from __future__ import annotations

from . import world
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH
from .framebuffer import FrameBuffer


def city_view_region() -> tuple[int, int]:
    """Return the map region dimensions beside the HUD and message log."""
    return SCREEN_WIDTH - HUD_WIDTH, SCREEN_HEIGHT - MSG_LOG_HEIGHT


def render_city_view(
    console: FrameBuffer,
    game_map: world.GameMap,
    player_pos: world.Position,
) -> tuple[int, int, int, int]:
    """Render a city around ``player_pos`` and return camera/view metadata."""
    map_w, map_h = city_view_region()
    camera_x, camera_y, region_x, region_y = world.camera_for_view(
        game_map,
        player_pos,
        region_w=map_w,
        region_h=map_h,
    )
    world.render_world_view(
        console,
        game_map,
        region_x=region_x,
        region_y=region_y,
        region_w=map_w,
        region_h=map_h,
        camera_x=camera_x,
        camera_y=camera_y,
    )
    return camera_x, camera_y, region_x, region_y


def present_city_transition_frame(
    ctx,
    console: FrameBuffer,
    game_map: world.GameMap,
    ship_ent: world.Entity,
    location: str,
) -> None:
    """Render and present one city launch or landing animation frame."""
    console.clear()
    render_city_view(console, game_map, ship_ent.pos)
    from . import pygame_overlay

    present_args = {
        "mode": "city",
        "location": location,
        "screen_width": SCREEN_WIDTH,
        "screen_height": SCREEN_HEIGHT,
        "hud_view_height": SCREEN_HEIGHT - MSG_LOG_HEIGHT,
    }
    present_args.update({
        "has_trade_terminal": any(e.trade_terminal for e in game_map.entities),
        "has_mech_terminal": any(e.mech_terminal for e in game_map.entities),
        "has_armory_terminal": any(e.armory_terminal for e in game_map.entities),
    })
    pygame_overlay.present_exploration(ctx, console, **present_args)
