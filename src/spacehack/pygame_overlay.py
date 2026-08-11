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
    """One contiguous same-color text segment in a logical cell row.

    ``bg`` is the cell background color (``None`` when unpainted). The
    domain HUD renders its shield-regen indicator as a white background
    fill on the shield bar cells — the overlay pipeline must carry it
    or the indicator silently vanishes in the Pygame renderer.
    """

    x: int
    y: int
    text: str
    color: Color
    bg: Color | None = None


def _normalize_bg(value: Any) -> Color | None:
    """Normalize a background color value (``None`` when unpainted).

    Native tcod consoles report the default black background for every
    cell the renderer never painted; treating that as a real background
    would paint black fills behind ordinary HUD text. Map it to ``None``
    so only intentionally painted backgrounds (e.g. the shield-regen
    highlight) produce fills.
    """
    if value is None:
        return None
    color = tuple(value)
    return None if color == (0, 0, 0) else color


def _bg_of(command: Any) -> Color | None:
    """Normalize a command's background color (``None`` when unpainted)."""
    return _normalize_bg(command.bg)


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
        bg = _bg_of(ordered[0])
        previous_x = ordered[0].x
        for command in ordered[1:]:
            same_run = (
                command.x == previous_x + 1
                and tuple(command.fg) == color
                and _bg_of(command) == bg
            )
            if same_run:
                chars.append(command.char)
            else:
                segments.append(OverlaySegment(start, y, "".join(chars), color, bg))
                start = command.x
                chars = [command.char]
                color = tuple(command.fg)
                bg = _bg_of(command)
            previous_x = command.x
        segments.append(OverlaySegment(start, y, "".join(chars), color, bg))
    return tuple(segments)


def _frame_from_commands(
    commands: Any,
    *,
    screen_width: int,
    screen_height: int,
    hud_view_height: int,
) -> OverlayFrame:
    """Build an overlay frame from an already-rendered console."""
    hud_x = screen_width - HUD_WIDTH
    return OverlayFrame(
        hud=_segments(
            commands,
            x_min=hud_x,
            x_max=screen_width,
            y_min=0,
            y_max=hud_view_height,
        ),
        messages=_segments(
            commands,
            x_min=0,
            x_max=screen_width,
            y_min=screen_height - MSG_LOG_HEIGHT,
            y_max=screen_height,
        ),
        hud_x=hud_x,
        hud_top=0,
        hud_height=hud_view_height,
        message_top=screen_height - MSG_LOG_HEIGHT,
        message_height=MSG_LOG_HEIGHT,
    )


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
    message_log.render_message_log(
        capture_console,
        ctx.log,
        screen_width=screen_width,
        screen_height=screen_height,
    )
    return _frame_from_commands(
        tuple(capture_console.commands),
        screen_width=screen_width,
        screen_height=screen_height,
        hud_view_height=hud_view_height,
    )


def frame_from_payload(data: dict[str, Any]) -> OverlayFrame:
    """Deserialize an overlay frame sent to an isolated Pygame worker."""
    def _segments_from(key: str) -> tuple[OverlaySegment, ...]:
        return tuple(
            OverlaySegment(
                x=int(item["x"]),
                y=int(item["y"]),
                text=str(item["text"]),
                color=tuple(item["color"]),
                bg=_normalize_bg(item.get("bg")),
            )
            for item in data.get(key, ())
        )

    return OverlayFrame(
        hud=_segments_from("hud"),
        messages=_segments_from("messages"),
        hud_x=int(data["hud_x"]),
        hud_top=int(data["hud_top"]),
        hud_height=int(data["hud_height"]),
        message_top=int(data["message_top"]),
        message_height=int(data["message_height"]),
    )


def present_exploration(
    ctx: Any,
    console: Any,
    *,
    mode: str,
    location: str,
    screen_width: int,
    screen_height: int,
    hud_view_height: int,
    has_trade_terminal: bool = False,
    has_mech_terminal: bool = False,
    has_armory_terminal: bool = False,
) -> bool:
    """Present an exploration frame with native HUD/log text when shared."""
    from . import hud, message_log

    if getattr(ctx.context, "_runtime", None) is None:
        hud.render_hud(
            console,
            ctx,
            screen_width=screen_width,
            hud_view_height=hud_view_height,
            location=location,
            mode=mode,
            has_trade_terminal=has_trade_terminal,
            has_mech_terminal=has_mech_terminal,
            has_armory_terminal=has_armory_terminal,
        )
        message_log.render_message_log(
            console, ctx.log,
            screen_width=screen_width,
            screen_height=screen_height,
        )
        ctx.context.present(console)
        return False

    frame = capture(
        ctx,
        mode=mode,
        location=location,
        screen_width=screen_width,
        screen_height=screen_height,
        hud_view_height=hud_view_height,
        has_trade_terminal=has_trade_terminal,
        has_mech_terminal=has_mech_terminal,
        has_armory_terminal=has_armory_terminal,
    )
    ctx.context.present(console, overlay=frame)
    return True


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
    origin_cell_x: int,
    origin_cell_y: int,
    padding_x: int = 12,
    padding_y: int = 4,
) -> None:
    """Paint captured text at logical-cell-relative positions with clipping."""
    clip = pygame.Rect(origin_x, origin_y, width, height)
    screen.set_clip(clip)
    try:
        measure = lambda text: pygame_ui.measure_font(font, text)
        prev_end_x: int | None = None   # pixel x where the previous text ended
        prev_end_cell: int | None = None  # cell index after the previous segment
        prev_y: int | None = None
        for segment in segments:
            # Glyph-accurate layout: when this segment continues the previous
            # segment's run (no cell gap), place it exactly where the previous
            # segment's rendered text ends instead of at a cell boundary.
            # Splitting one text run into colored segments (e.g. the shield
            # bar's regen highlight) must not move the remaining text — a
            # cell-aligned start would push the percentage readout right as
            # the highlight grows.
            if prev_y is not None and segment.y != prev_y:
                prev_end_x = prev_end_cell = None
            if (
                prev_end_x is not None
                and prev_end_cell is not None
                and segment.x == prev_end_cell
            ):
                x = prev_end_x
            else:
                x = origin_x + padding_x + (segment.x - origin_cell_x) * TILE_WIDTH
            y = origin_y + padding_y + (segment.y - origin_cell_y) * TILE_HEIGHT
            text = pygame_ui.fit_text(
                segment.text,
                max(1, origin_x + width - padding_x - x),
                measure,
            )
            text_width = measure(text)
            # Background highlight spans the drawn glyphs, not the full
            # logical cells — proportional glyphs are narrower than the
            # 16px cells, so a cell-wide fill reads wider than its text.
            if segment.bg is not None and text:
                pygame.draw.rect(
                    screen,
                    segment.bg,
                    pygame.Rect(x, y, text_width, TILE_HEIGHT),
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
            prev_end_x = x + text_width
            prev_end_cell = segment.x + len(segment.text)
            prev_y = segment.y
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
    hud_height = min(frame.hud_height, logical_height // TILE_HEIGHT - frame.hud_top)
    message_height = min(
        frame.message_height,
        max(0, logical_height // TILE_HEIGHT - frame.message_top),
    )
    hud_rect = pygame_ui.Rect(
        frame.hud_x * TILE_WIDTH,
        frame.hud_top * TILE_HEIGHT,
        (screen_width - frame.hud_x) * TILE_WIDTH,
        max(0, hud_height) * TILE_HEIGHT,
    )
    message_rect = pygame_ui.Rect(
        0,
        frame.message_top * TILE_HEIGHT,
        logical_width,
        message_height * TILE_HEIGHT,
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
        origin_cell_x=frame.hud_x,
        origin_cell_y=frame.hud_top,
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
        origin_cell_x=0,
        origin_cell_y=frame.message_top,
        padding_y=0,
    )
