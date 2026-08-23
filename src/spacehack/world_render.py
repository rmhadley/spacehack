"""Renderer-neutral draw-command generation for world maps.

The game's framebuffers and Pygame presenter consume a flat
:class:`WorldDrawCommand` stream. This module builds that stream from a
:class:`world.GameMap` (tiles + entities) for a camera viewport, handling
remembered-tile dimming and entity visibility. It is split out of
:mod:`spacehack.world` so the shared game-world module stays within the
project architecture budget; importing :mod:`spacehack.world` re-exports the
public helpers here.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import world
from .framebuffer import FrameBuffer


# Remembered-tile dimming factor: previously-seen cells that are no
# longer in line of sight render at this fraction of their normal
# colour (design doc 04: "explored-out-of-sight = dim").
_DIM_FACTOR: float = 0.35


@dataclass(frozen=True)
class WorldDrawCommand:
    """One renderer-neutral cell draw operation in screen-cell space."""

    x: int
    y: int
    char: str
    fg: tuple[int, int, int]
    bg: tuple[int, int, int] | None = None


def _dim_color(color: tuple[int, int, int]) -> tuple[int, int, int]:
    """Scale an (r, g, b) colour down to remembered-sight brightness."""
    return tuple(max(0, min(255, int(c * _DIM_FACTOR))) for c in color)


def _is_static_entity(e) -> bool:
    """Whether ``e`` never moves — safe to remember on explored tiles."""
    return not (
        e.npc_char_id or e.npc_id or e.npc_ship_id
        or e.procedural_squad_id or e.squad_id
    )


def _tile_render_colors(game_map, x: int, y: int, tile) -> tuple[tuple, tuple]:
    """Return ``(fg, bg)`` for a revealed tile (dimmed if only remembered)."""
    if game_map.is_visible(x, y):
        return tile.fg, tile.bg
    return _dim_color(tile.fg), _dim_color(tile.bg)


def _entity_render_fg(game_map, e):
    """Return the fg to draw ``e`` with, or ``None`` to skip it."""
    if game_map.is_visible(e.pos.x, e.pos.y):
        return e.fg
    if game_map.is_revealed(e.pos.x, e.pos.y) and _is_static_entity(e):
        return _dim_color(e.fg)
    return None


def _append_tile_commands(
    commands: list[WorldDrawCommand],
    game_map: world.GameMap,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
    camera_x: int,
    camera_y: int,
) -> None:
    """Append visible tile commands for a camera viewport."""
    for ty in range(region_h):
        for tx in range(region_w):
            map_x = camera_x + tx
            map_y = camera_y + ty
            if not (0 <= map_x < game_map.width and 0 <= map_y < game_map.height):
                continue
            if not game_map.is_revealed(map_x, map_y):
                continue
            tile = game_map.tiles[map_y][map_x]
            fg, bg = _tile_render_colors(game_map, map_x, map_y, tile)
            commands.append(WorldDrawCommand(
                region_x + tx, region_y + ty, tile.char, fg, bg,
            ))


def _entity_draw_order(entities, sort_entities: bool):
    """Return visible entities in the requested renderer draw order."""
    if not sort_entities:
        return entities
    return sorted(entities, key=lambda item: item.loot_data is None)


def _visible_entities(game_map, *, camera_x, camera_y, region_w, region_h):
    """Return entities whose footprint intersects the camera viewport."""
    return [
        entity for entity in game_map.entities
        if (
            entity.pos.x < camera_x + region_w
            and entity.pos.x + entity.width > camera_x
            and entity.pos.y < camera_y + region_h
            and entity.pos.y + entity.height > camera_y
        )
    ]


def _append_one_entity(
    commands: list[WorldDrawCommand],
    game_map: world.GameMap,
    entity,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
    camera_x: int,
    camera_y: int,
) -> None:
    """Emit one entity's footprint glyphs clipped to the camera viewport."""
    fg = _entity_render_fg(game_map, entity)
    if fg is None:
        return
    for dx in range(entity.width):
        for dy in range(entity.height):
            map_x = entity.pos.x + dx
            map_y = entity.pos.y + dy
            if not (
                camera_x <= map_x < camera_x + region_w
                and camera_y <= map_y < camera_y + region_h
            ):
                continue
            commands.append(WorldDrawCommand(
                region_x + map_x - camera_x,
                region_y + map_y - camera_y,
                entity.char,
                fg,
            ))


def _append_entity_commands(
    commands: list[WorldDrawCommand],
    game_map: world.GameMap,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
    camera_x: int,
    camera_y: int,
    sort_entities: bool = False,
) -> None:
    """Append visible entity footprint commands in draw order."""
    visible = _visible_entities(
        game_map, camera_x=camera_x, camera_y=camera_y,
        region_w=region_w, region_h=region_h,
    )
    for entity in _entity_draw_order(visible, sort_entities):
        _append_one_entity(
            commands, game_map, entity,
            region_x=region_x, region_y=region_y,
            region_w=region_w, region_h=region_h,
            camera_x=camera_x, camera_y=camera_y,
        )


def _resolve_viewport(
    game_map: world.GameMap,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
    camera_x: int,
    camera_y: int,
    centered: bool,
):
    """Return the effective ``(camera, region)`` tuple for a draw request."""
    if centered and (game_map.width > region_w or game_map.height > region_h):
        raise ValueError(
            f"city {game_map.width}x{game_map.height} is larger than "
            f"viewport region {region_w}x{region_h}"
        )
    if centered:
        region_x += (region_w - game_map.width) // 2
        region_y += (region_h - game_map.height) // 2
        return 0, 0, region_x, region_y, game_map.width, game_map.height
    camera_x = max(0, min(camera_x, max(0, game_map.width - region_w)))
    camera_y = max(0, min(camera_y, max(0, game_map.height - region_h)))
    return camera_x, camera_y, region_x, region_y, region_w, region_h


def world_draw_commands(
    game_map: world.GameMap,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
    camera_x: int = 0,
    camera_y: int = 0,
    centered: bool = False,
    sort_entities: bool = False,
) -> tuple[WorldDrawCommand, ...]:
    """Return the shared tile/entity draw stream used by every renderer."""
    camera_x, camera_y, region_x, region_y, region_w, region_h = _resolve_viewport(
        game_map, region_x=region_x, region_y=region_y,
        region_w=region_w, region_h=region_h,
        camera_x=camera_x, camera_y=camera_y, centered=centered,
    )
    commands: list[WorldDrawCommand] = []
    _append_tile_commands(
        commands, game_map,
        region_x=region_x, region_y=region_y,
        region_w=region_w, region_h=region_h,
        camera_x=camera_x, camera_y=camera_y,
    )
    _append_entity_commands(
        commands, game_map,
        region_x=region_x, region_y=region_y,
        region_w=region_w, region_h=region_h,
        camera_x=camera_x, camera_y=camera_y, sort_entities=sort_entities,
    )
    return tuple(commands)


def _render_commands(
    console: FrameBuffer,
    commands: tuple[WorldDrawCommand, ...],
) -> None:
    """Paint a renderer-neutral command stream onto a project framebuffer."""
    for command in commands:
        kwargs = {"x": command.x, "y": command.y, "string": command.char, "fg": command.fg}
        if command.bg is not None:
            kwargs["bg"] = command.bg
        console.print(**kwargs)


def render_world(
    console: FrameBuffer,
    game_map: world.GameMap,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
) -> None:
    """Paint a centered world through the shared draw-command stream."""
    _render_commands(
        console,
        world_draw_commands(
            game_map,
            region_x=region_x, region_y=region_y,
            region_w=region_w, region_h=region_h,
            centered=True,
        ),
    )


def camera_for_view(
    game_map: world.GameMap,
    player_pos: world.Position,
    *,
    region_w: int,
    region_h: int,
) -> tuple[int, int, int, int]:
    """Return ``(camera_x, camera_y, region_x, region_y)`` for a viewport."""
    if game_map.width <= region_w and game_map.height <= region_h:
        return (
            0, 0,
            (region_w - game_map.width) // 2,
            (region_h - game_map.height) // 2,
        )
    _cw = max(0, game_map.width - region_w)
    _ch = max(0, game_map.height - region_h)
    _cx = max(0, min(player_pos.x - region_w // 2, _cw))
    _cy = max(0, min(player_pos.y - region_h // 2, _ch))
    return (_cx, _cy, 0, 0)


def render_world_view(
    console: FrameBuffer,
    game_map: world.GameMap,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
    camera_x: int = 0,
    camera_y: int = 0,
) -> None:
    """Paint a scrollable world through the shared draw-command stream."""
    cam_x = max(0, min(camera_x, max(0, game_map.width - region_w)))
    cam_y = max(0, min(camera_y, max(0, game_map.height - region_h)))
    _render_commands(
        console,
        world_draw_commands(
            game_map,
            region_x=region_x, region_y=region_y,
            region_w=region_w, region_h=region_h,
            camera_x=cam_x, camera_y=cam_y,
            sort_entities=True,
        ),
    )


__all__ = [
    "WorldDrawCommand", "world_draw_commands",
    "render_world", "render_world_view", "camera_for_view",
    "_dim_color", "_is_static_entity", "_tile_render_colors",
    "_entity_render_fg", "_append_tile_commands", "_append_entity_commands",
]
