"""Breach-entry animation must render hulls of any size.

Regression: boarding the 92-column survey ship crashed with
``city 92x34 is larger than viewport region 80x54`` when the animation
still demanded a centered whole-map fit. It now rides the same camera
viewport as gameplay.
"""

from __future__ import annotations

import types

from src.spacehack import dungeon_animation, world
from src.spacehack.framebuffer import FrameBuffer


class _RecordingContext:
    """Fake loop context that snapshots each presented frame."""

    def __init__(self, width: int, height: int):
        self.frames: list[list[list[str]]] = []
        console = FrameBuffer(width, height)
        self.context = types.SimpleNamespace(present=self._capture)
        self.console = console

    def _capture(self, console: FrameBuffer) -> None:
        self.frames.append(
            [
                [console.cell(x, y).char for x in range(console.width)]
                for y in range(console.height)
            ]
        )


def _hull(width: int, height: int, breaches: list[tuple[int, int]]):
    tiles = [
        [world.DUNGEON_FLOOR for _ in range(width)] for _ in range(height)
    ]
    for x, y in breaches:
        tiles[y][x] = world.BREACH
    return world.GameMap(
        width=width, height=height, tiles=tiles, entities=[],
    )


def test_breach_animation_scrolls_hulls_wider_than_the_viewport(monkeypatch):
    monkeypatch.setattr(
        "src.spacehack.navigation._responsive_sleep", lambda _seconds: None,
    )
    game_map = _hull(92, 34, breaches=[(45, 17)])
    ctx = _RecordingContext(80, 54)

    dungeon_animation.animate_breach(
        ctx, ctx.console, game_map, world.Position(45, 20),
        region_w=80, region_h=54,
    )

    # Four spark frames plus the settled frame.
    assert len(ctx.frames) == 5
    # Camera centers horizontally on the boarding point (clamped to the
    # 12-column scroll range), so the breach spark lands in view.
    assert ctx.frames[0][17][40] == "*"
    # Authored breach tiles are restored after the explosion.
    assert game_map.tiles[17][45].kind == "breach"


def test_breach_animation_keeps_small_hulls_centered(monkeypatch):
    monkeypatch.setattr(
        "src.spacehack.navigation._responsive_sleep", lambda _seconds: None,
    )
    game_map = _hull(20, 10, breaches=[(5, 5)])
    ctx = _RecordingContext(80, 54)

    dungeon_animation.animate_breach(
        ctx, ctx.console, game_map, world.Position(7, 7),
        region_w=80, region_h=54,
    )

    # A hull smaller than the region is centered: (80-20)//2, (54-10)//2.
    assert ctx.frames[0][27][35] == "*"
