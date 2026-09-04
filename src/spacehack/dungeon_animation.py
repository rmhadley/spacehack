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


def _print_sparks(
    console: FrameBuffer,
    sparks: set[tuple[int, int]],
    spark_char: str,
    spark_color: tuple[int, int, int],
    *,
    offset_x: int,
    offset_y: int,
    camera_x: int,
    camera_y: int,
    region_w: int,
    region_h: int,
) -> None:
    """Stamp spark glyphs into the current frame, clipped to the viewport."""
    for x, y in sparks:
        frame_x = offset_x + x - camera_x
        frame_y = offset_y + y - camera_y
        if 0 <= frame_x < region_w and 0 <= frame_y < region_h:
            console.print(
                x=frame_x,
                y=frame_y,
                string=spark_char,
                fg=spark_color,
            )


def _render_frame(
    ctx,
    console: FrameBuffer,
    game_map: world.GameMap,
    player_pos: world.Position,
    sparks: set[tuple[int, int]],
    spark_char: str,
    spark_color: tuple[int, int, int],
    *,
    region_w: int,
    region_h: int,
) -> None:
    """Render one breach animation frame and wait for its timing interval.

    Hulls may exceed the viewport (the survey ship is 92 columns in an
    80-column region), so the frame rides the same camera viewport as
    gameplay, centered on the boarding point.
    """
    from .navigation import _responsive_sleep
    from . import animation_timing

    console.clear()
    camera_x, camera_y, offset_x, offset_y = world.camera_for_view(
        game_map, player_pos, region_w=region_w, region_h=region_h,
    )
    world.render_world_view(
        console, game_map,
        region_x=offset_x, region_y=offset_y,
        region_w=region_w, region_h=region_h,
        camera_x=camera_x, camera_y=camera_y,
    )
    _print_sparks(
        console, sparks, spark_char, spark_color,
        offset_x=offset_x, offset_y=offset_y,
        camera_x=camera_x, camera_y=camera_y,
        region_w=region_w, region_h=region_h,
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
            ctx, console, game_map, player_pos, sparks, char, color,
            region_w=region_w, region_h=region_h,
        )
    _restore_breaches(game_map, positions, originals)
    _render_frame(
        ctx, console, game_map, player_pos, set(), "", colors[-1],
        region_w=region_w, region_h=region_h,
    )
