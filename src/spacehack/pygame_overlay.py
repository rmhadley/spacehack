"""Native Pygame text overlays for the exploration HUD and message log.

The map remains on the processed bitmap glyph atlas. This module captures the
existing HUD/message-log renderers into renderer-neutral cell commands, then
paints those two regions with the same readable Pygame font and panel treatment
used by the migrated menus. Gameplay state and message semantics stay in the
existing domain renderers.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from . import pygame_ui
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, TILE_HEIGHT, TILE_WIDTH


Color = tuple[int, int, int]


@dataclass(frozen=True)
class OverlaySegment:
    """One contiguous same-color text segment in a logical cell row."""

    x: int
    y: int
    text: str
    color: Color


@dataclass(frozen=True)
class OverlayFrame:
    """Captured HUD and message-log layers for one exploration frame."""

    hud: tuple[OverlaySegment, ...]
    messages: tuple[OverlaySegment, ...]
    hud_x: int
    hud_top: int
    hud_height: int
    message_top: int
    message_height: int


def _segments(commands: Any, *, x_min: int, x_max: int, y_min: int, y_max: int) -> tuple[OverlaySegment, ...]:
    """Group captured cells into naturally rendered text segments."""
    rows: dict[int, list[Any]] = defaultdict(list)
    for command in commands:
        if x_min <= command.x < x_max and y_min <= command.y < y_max:
            rows[command.y].append(command)
    segments: list[OverlaySegment] = []
    for y in sorted(rows):
        ordered = sorted(rows[y], key=lambda command: command.x)
        if not ordered:
            continue
        start = ordered[0].x
        chars = [ordered[0].char]
        color = tuple(ordered[0].fg)
        previous_x = ordered[0].x
        for command in ordered[1:]:
            same_run = command.x == previous_x + 1 and tuple(command.fg) == color
            if same_run:
                chars.append(command.char)
            else:
                segments.append(OverlaySegment(start, y, "".join(chars), color))
                start = command.x
                chars = [command.char]
                color = tuple(command.fg)
            previous_x = command.x
        segments.append(OverlaySegment(start, y, "".join(chars), color))
    return tuple(segments)


def capture(
    ctx: Any,
    *,
    mode: str,
    location: str,
    screen_width: int,
    screen_height: int,
    hud_view_height: int,
    has_trade_terminal: bool = False,
    has_mech_terminal: bool = False,
    has_armory_terminal: bool = False,
) -> OverlayFrame:
    """Capture the authoritative HUD and message log into overlay segments."""
    from . import hud, message_log
    from .pygame_world import CaptureConsole

    capture_console = CaptureConsole(screen_width, screen_height)
    hud.render_hud(
        capture_console,
        ctx,
        screen_width=screen_width,
        hud_view_height=hud_view_height,
        location=location,
        mode=mode,
        has_trade_terminal=has_trade_terminal,
        has_mech_terminal=has_mech_terminal,
        has_armory_terminal=has_armory_terminal,
    )
    hud_segments = _segments(
        capture_console.commands,
        x_min=screen_width - HUD_WIDTH,
        x_max=screen_width,
        y_min=0,
        y_max=hud_view_height,
    )
    capture_console.clear()
    message_log.render_message_log(
        capture_console,
        ctx.log,
        screen_width=screen_width,
        screen_height=screen_height,
    )
    message_segments = _segments(
        capture_console.commands,
        x_min=0,
        x_max=screen_width,
        y_min=screen_height - MSG_LOG_HEIGHT,
        y_max=screen_height,
    )
    return OverlayFrame(
        hud=hud_segments,
        messages=message_segments,
        hud_x=screen_width - HUD_WIDTH,
        hud_top=0,
        hud_height=hud_view_height,
        message_top=screen_height - MSG_LOG_HEIGHT,
        message_height=MSG_LOG_HEIGHT,
    )


def payload(frame: OverlayFrame) -> dict[str, Any]:
    """Serialize an overlay frame for renderer tests or future workers."""
    return asdict(frame)


def _font(pygame: Any, *, line_height: int) -> Any:
    """Choose the largest native font that fits one logical cell row."""
    from .pygame_menu import _font_path

    path = _font_path(pygame)
    for size in range(20, 9, -1):
        candidate = pygame.font.Font(path, size)
        if candidate.get_linesize() <= line_height:
            return candidate
    return pygame.font.Font(path, 10)


def _draw_segments(
    pygame: Any,
    screen: Any,
    font: Any,
    segments: tuple[OverlaySegment, ...],
    *,
    origin_x: int,
    origin_y: int,
    width: int,
    height: int,
) -> None:
    """Paint captured text at logical-cell-relative positions with clipping."""
    clip = pygame.Rect(origin_x, origin_y, width, height)
    screen.set_clip(clip)
    try:
        measure = lambda text: pygame_ui.measure_font(font, text)
        for segment in segments:
            x = segment.x * TILE_WIDTH
            y = segment.y * TILE_HEIGHT + max(0, (TILE_HEIGHT - font.get_linesize()) // 2)
            text = pygame_ui.fit_text(
                segment.text,
                max(1, origin_x + width - x - 8),
                measure,
            )
            pygame_ui.draw_text(
                pygame,
                screen,
                font,
                text,
                x,
                y,
                color=segment.color,
            )
    finally:
        screen.set_clip(None)


def draw(
    pygame: Any,
    screen: Any,
    frame: OverlayFrame,
    *,
    logical_width: int,
    logical_height: int,
) -> None:
    """Paint framed native-text HUD and message-log regions over the map frame."""
    palette = pygame_ui.DEFAULT_PALETTE
    screen_width = logical_width // TILE_WIDTH
    hud_rect = pygame_ui.Rect(
        frame.hud_x * TILE_WIDTH,
        frame.hud_top * TILE_HEIGHT,
        (screen_width - frame.hud_x) * TILE_WIDTH,
        frame.hud_height * TILE_HEIGHT,
    )
    message_rect = pygame_ui.Rect(
        0,
        frame.message_top * TILE_HEIGHT,
        logical_width,
        frame.message_height * TILE_HEIGHT,
    )
    pygame_ui.draw_panel(pygame, screen, hud_rect, palette=palette)
    pygame_ui.draw_panel(pygame, screen, message_rect, palette=palette)
    hud_font = _font(pygame, line_height=TILE_HEIGHT)
    message_font = _font(pygame, line_height=TILE_HEIGHT)
    _draw_segments(
        pygame,
        screen,
        hud_font,
        frame.hud,
        origin_x=hud_rect.x,
        origin_y=hud_rect.y,
        width=hud_rect.width,
        height=hud_rect.height,
    )
    _draw_segments(
        pygame,
        screen,
        message_font,
        frame.messages,
        origin_x=message_rect.x,
        origin_y=message_rect.y,
        width=message_rect.width,
        height=message_rect.height,
    )
