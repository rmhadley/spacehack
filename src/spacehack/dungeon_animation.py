"""Visual animations for dungeon transitions."""

from __future__ import annotations

from . import world
from .framebuffer import FrameBuffer


def _breach_positions(game_map: world.GameMap) -> list[world.Position]:
    """Return every authored breach coordinate."""
    return [
        world.Position(x, y)
        for y in range(game_map.height)
        for x in range(game_map.width)
        if game_map.tiles[y][x].kind == "breach"
    ]


def _replace_breaches(
    game_map: world.GameMap,
    positions: list[world.Position],
) -> dict[tuple[int, int], world.Tile]:
    """Temporarily replace breach cells with walls and return originals."""
    originals: dict[tuple[int, int], world.Tile] = {}
    for position in positions:
        key = (position.x, position.y)
        originals[key] = game_map.tiles[position.y][position.x]
        game_map.tiles[position.y][position.x] = world.DUNGEON_WALL
    return originals


def _spark_frames(
    positions: list[world.Position],
    player_pos: world.Position,
) -> list[set[tuple[int, int]]]:
    """Build expanding spark coordinates traveling inward from breaches."""
    frames: list[set[tuple[int, int]]] = [set() for _ in range(4)]
    for breach in positions:
        dx = breach.x - player_pos.x
        dy = breach.y - player_pos.y
        steps = max(abs(dx), abs(dy)) or 1
        step_x, step_y = dx / steps, dy / steps
        for depth in range(4):
            cell = (
                round(breach.x + step_x * depth),
                round(breach.y + step_y * depth),
            )
            for frame in range(depth, 4):
                frames[frame].add(cell)
    return frames


def _render_frame(
    ctx,
    console: FrameBuffer,
    game_map: world.GameMap,
    sparks: set[tuple[int, int]],
    spark_char: str,
    spark_color: tuple[int, int, int],
    *,
    region_w: int,
    region_h: int,
) -> None:
    """Render one breach animation frame and wait for its timing interval."""
    from .navigation import _responsive_sleep
    from . import animation_timing

    console.clear()
    world.render_world(
        console,
        game_map,
        region_x=0,
        region_y=0,
        region_w=region_w,
        region_h=region_h,
    )
    offset_x = (region_w - game_map.width) // 2
    offset_y = (region_h - game_map.height) // 2
    for x, y in sparks:
        if 0 <= x < game_map.width and 0 <= y < game_map.height:
            console.print(
                x=offset_x + x,
                y=offset_y + y,
                string=spark_char,
                fg=spark_color,
            )
    ctx.context.present(console)
    _responsive_sleep(animation_timing.DUNGEON_BREACH)


def _restore_breaches(
    game_map: world.GameMap,
    positions: list[world.Position],
    originals: dict[tuple[int, int], world.Tile],
) -> None:
    """Restore authored breach tiles after the explosion."""
    for position in positions:
        game_map.tiles[position.y][position.x] = originals[
            (position.x, position.y)
        ]


def animate_breach(
    ctx,
    console: FrameBuffer,
    game_map: world.GameMap,
    player_pos: world.Position,
    *,
    region_w: int,
    region_h: int,
) -> None:
    """Play the breach explosion animation and reveal authored breaches."""
    positions = _breach_positions(game_map)
    if not positions:
        return
    originals = _replace_breaches(game_map, positions)
    frames = _spark_frames(positions, player_pos)
    colors = ((255, 200, 100), (255, 160, 60), (255, 120, 40), (255, 255, 255))
    chars = ("*", "+", "o", "#")
    for sparks, char, color in zip(frames, chars, colors):
        _render_frame(
            ctx, console, game_map, sparks, char, color,
            region_w=region_w, region_h=region_h,
        )
    _restore_breaches(game_map, positions, originals)
    _render_frame(
        ctx, console, game_map, set(), "", colors[-1],
        region_w=region_w, region_h=region_h,
    )
