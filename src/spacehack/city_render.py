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


def _debug_overlay_lines(
    game_map: world.GameMap, player_pos: world.Position,
    camera_x: int, camera_y: int,
) -> list[str]:
    """Build the text lines for the debug overlay."""
    transit = [
        e for e in game_map.entities
        if getattr(e, 'transit_station_id', None)
    ]
    npcs = [e for e in game_map.entities if getattr(e, 'city_npc_id', '')]
    buildings = getattr(game_map, 'city_buildings', {})
    tile = game_map.tiles[player_pos.y][player_pos.x]
    district = _district_at(game_map, player_pos.x, player_pos.y)
    return [
        f"cam {camera_x},{camera_y}  @ {player_pos.x},{player_pos.y}",
        f"district: {district}",
        f"tile: {tile.kind} '{tile.char}'",
        f"transit stops: {len(transit)}",
        f"buildings: {len(buildings)}",
        f"NPCs: {len(npcs)}",
    ]


def render_city_debug_overlay(
    console: FrameBuffer,
    game_map: world.GameMap,
    player_pos: world.Position,
    camera_x: int, camera_y: int,
    region_x: int, region_y: int,
) -> None:
    """Paint a compact debug HUD over the bottom-left of the city view.

    Shows camera coords, player tile, current district, transit
    stations, building count, and NPC count.  Gated behind
    ``SPACEHACK_DEV`` at the call site.
    """
    map_w, map_h = city_view_region()
    lines = _debug_overlay_lines(game_map, player_pos, camera_x, camera_y)
    _DBG_FG = (180, 240, 180)
    _DBG_BG = (15, 15, 25)
    start_y = region_y + map_h - len(lines) - 1
    for i, line in enumerate(lines):
        y = start_y + i
        if not (region_y <= y < region_y + map_h):
            continue
        for j, ch in enumerate(line):
            x = region_x + j
            if region_x <= x < region_x + map_w:
                console.write_cell(x, y, ch, fg=_DBG_FG, bg=_DBG_BG)


def _district_at(
    game_map: world.GameMap, x: int, y: int,
) -> str:
    """Return the district name at (x, y) or 'outskirts'."""
    districts = getattr(game_map, 'city_districts', {})
    for name, (x1, y1, x2, y2) in districts.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return "outskirts"


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
