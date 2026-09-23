"""Painters for the exploration overlay (split from pygame_overlay).

Every draw routine that turns overlay frames, segments, shield
bubbles, floaters, and glows into pixels lives here;
``pygame_overlay`` keeps the data model + capture builders and
re-exports this module's public painters so existing callers keep
their import paths (the navigation.py hub-over-siblings precedent).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import pygame_ui
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, TILE_HEIGHT, TILE_WIDTH
from .pygame_target_card import _draw_target_card

if TYPE_CHECKING:  # runtime-free: no import cycle with the hub
    from .pygame_overlay import (
        FloatingText, LightGlow, OverlayFrame, OverlaySegment, ShieldBubble,
    )

Color = tuple[int, int, int]


def _segment_position(
    segment: OverlaySegment,
    prev: tuple[int | None, int | None, int | None],
    *,
    origin_x: int,
    origin_y: int,
    origin_cell_x: int,
    origin_cell_y: int,
    padding_x: int,
    padding_y: int,
    tile_width: int = TILE_WIDTH,
    tile_height: int = TILE_HEIGHT,
) -> tuple[int, int]:
    """Compute one segment's pixel ``(x, y)`` from the previous run.

    Glyph-accurate chaining: when this segment continues the previous
    segment's run (no cell gap), it starts exactly where the previous
    text ended instead of at a cell boundary — so a colored split (e.g.
    the shield-regen highlight) never shifts the trailing percentage.
    """
    prev_end_x, prev_end_cell, prev_y = prev
    if prev_y is not None and segment.y != prev_y:
        prev_end_x = prev_end_cell = None
    if (
        prev_end_x is not None
        and prev_end_cell is not None
        and segment.x == prev_end_cell
    ):
        x = prev_end_x
    else:
        x = origin_x + padding_x + (segment.x - origin_cell_x) * tile_width
    y = origin_y + padding_y + (segment.y - origin_cell_y) * tile_height
    return x, y


def _paint_segment(
    pygame: Any,
    screen: Any,
    font: Any,
    segment: OverlaySegment,
    measure: Any,
    *,
    x: int,
    y: int,
    width: int,
    origin_x: int,
    padding_x: int,
    tile_height: int = TILE_HEIGHT,
) -> tuple[int, int, int]:
    """Paint one segment (fit + optional bg) and return its chain state.

    The background highlight spans the drawn glyphs, not the full logical
    cells — proportional glyphs are narrower than the 16px cells, so a
    cell-wide fill would read wider than its text.
    """
    text = pygame_ui.fit_text(
        segment.text, max(1, origin_x + width - padding_x - x), measure,
    )
    text_width = measure(text)
    if segment.bg is not None and text:
        pygame.draw.rect(screen, segment.bg, pygame.Rect(x, y, text_width, tile_height))
    pygame_ui.draw_text(pygame, screen, font, text, x, y, color=segment.color)
    return x + text_width, segment.x + len(segment.text), segment.y


def _draw_segment_rows(
    pygame: Any,
    screen: Any,
    font: Any,
    segments: tuple[OverlaySegment, ...],
    *,
    origin_x: int,
    origin_y: int,
    width: int,
    origin_cell_x: int,
    origin_cell_y: int,
    padding_x: int,
    padding_y: int,
    tile_width: int,
    tile_height: int,
) -> None:
    """Paint text runs after the caller has installed its clipping region."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    prev: tuple[int | None, int | None, int | None] = (None, None, None)
    for segment in segments:
        x, y = _segment_position(
            segment,
            prev,
            origin_x=origin_x,
            origin_y=origin_y,
            origin_cell_x=origin_cell_x,
            origin_cell_y=origin_cell_y,
            padding_x=padding_x,
            padding_y=padding_y,
            tile_width=tile_width,
            tile_height=tile_height,
        )
        prev = _paint_segment(
            pygame, screen, font, segment, measure,
            x=x, y=y, width=width, origin_x=origin_x, padding_x=padding_x,
            tile_height=tile_height,
        )


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
    tile_width: int = TILE_WIDTH,
    tile_height: int = TILE_HEIGHT,
) -> None:
    """Paint captured text at logical-cell-relative positions with clipping."""
    clip = pygame.Rect(origin_x, origin_y, width, height)
    screen.set_clip(clip)
    try:
        _draw_segment_rows(
            pygame, screen, font, segments,
            origin_x=origin_x, origin_y=origin_y, width=width,
            origin_cell_x=origin_cell_x, origin_cell_y=origin_cell_y,
            padding_x=padding_x, padding_y=padding_y,
            tile_width=tile_width, tile_height=tile_height,
        )
    finally:
        screen.set_clip(None)


def _bubble_ring_width(strength: float) -> int:
    """Map shield strength (0..1) to the shield-ring stroke width in px.

    A nearly-depleted shield collapses to a 1px hairline; a full shield
    draws a 3px ring, so the bubble visibly thins as shields approach
    zero before popping at exactly 0.
    """
    return 1 + round(2 * max(0.0, min(1.0, strength)))


def _draw_shield_bubbles(
    pygame: Any,
    screen: Any,
    bubbles: tuple[ShieldBubble, ...],
    *,
    map_width: int,
    map_height: int,
) -> None:
    """Paint subtle cyan ellipses around shielded ships within the map.

    The ring thickness scales with ``strength`` (current/max shields):
    a full shield draws a chunky double ring, while a weak shield thins
    to a single hairline just before the bubble disappears at zero.
    """
    screen.set_clip(pygame.Rect(0, 0, map_width * TILE_WIDTH, map_height * TILE_HEIGHT))
    try:
        for bubble in bubbles:
            center_x = (bubble.x + bubble.width / 2) * TILE_WIDTH
            center_y = (bubble.y + bubble.height / 2) * TILE_HEIGHT
            radius_x = max(12, bubble.width * TILE_WIDTH / 2 + 6)
            radius_y = max(12, bubble.height * TILE_HEIGHT / 2 + 6)
            strength = max(0.0, min(1.0, bubble.strength))
            bright = tuple(int(base * (0.65 + 0.35 * strength)) for base in (80, 210, 255))
            rect = pygame.Rect(
                int(center_x - radius_x), int(center_y - radius_y),
                int(radius_x * 2), int(radius_y * 2),
            )
            ring = _bubble_ring_width(strength)
            pygame.draw.ellipse(screen, bright, rect, width=ring)
            # Inner ring only while the outer stroke is >= 2px, i.e. roughly
            # above 25% shields — weaker bubbles collapse to a single hairline.
            inner = rect.inflate(-2 * ring, -2 * ring)
            if ring >= 2 and inner.width > 2 and inner.height > 2:
                pygame.draw.ellipse(screen, (55, 145, 220), inner, width=1)
    finally:
        screen.set_clip(None)


def _draw_floaters(
    pygame: Any,
    screen: Any,
    floaters: tuple[FloatingText, ...],
    *,
    map_width: int,
    map_height: int,
) -> None:
    """Paint native floating combat numbers over the map region.

    Each floater is drawn with the shared Pygame font at roughly one
    cell wide, centred on its anchor cell, rising ``age``*2px per
    frame and fading toward dim grey as it approaches ``lifetime``.
    A four-way 1px shadow keeps the text readable over bright map
    glyphs and explosions. Clipped to the map area so floaters never
    spill into the HUD or message-log panels.
    """
    if not floaters:
        return
    screen.set_clip(pygame.Rect(0, 0, map_width * TILE_WIDTH, map_height * TILE_HEIGHT))
    try:
        font = pygame_ui.cell_font(pygame, line_height=22)
        measure = lambda text: pygame_ui.measure_font(font, text)
        shadow = (10, 10, 14)
        for floater in floaters:
            frac = max(0.0, 1.0 - floater.age / max(1, floater.lifetime))
            color = tuple(
                int(channel * frac + 90 * (1 - frac))
                for channel in floater.color
            )
            x = floater.x * TILE_WIDTH + TILE_WIDTH // 2 - measure(floater.text) // 2
            y = floater.y * TILE_HEIGHT - min(floater.age, floater.lifetime) * 2
            for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                pygame_ui.draw_text(
                    pygame, screen, font, floater.text,
                    x + dx, y + dy, color=shadow, antialias=False,
                )
            pygame_ui.draw_text(pygame, screen, font, floater.text, x, y, color=color)
    finally:
        screen.set_clip(None)


def _draw_glow_surface(pygame: Any, glow: LightGlow, frac: float) -> Any:
    """Build one fading radial glow surface for ``glow`` at intensity ``frac``."""
    px_radius = max(1, glow.radius * TILE_WIDTH)
    size = px_radius * 2 + 2
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    for r in range(px_radius, 0, -1):
        alpha = int(120 * frac * (1 - r / px_radius))
        if alpha <= 0:
            continue
        pygame.draw.circle(
            surface, (*glow.color, alpha),
            (size // 2, size // 2), r,
        )
    return surface


def _draw_glows(
    pygame: Any,
    screen: Any,
    glows: tuple[LightGlow, ...],
    *,
    map_width: int,
    map_height: int,
) -> None:
    """Paint native radial light glows over the map region.

    Each glow is a filled circle whose colour fades with ``age`` toward
    zero as it approaches ``lifetime``. Drawn with ``BLEND_RGBA_ADD``
    so overlapping glows brighten, and so the glow adds light to the
    map glyphs beneath it rather than replacing them. Clipped to the
    map area so glows never spill into the HUD or message-log panels.
    """
    if not glows:
        return
    screen.set_clip(pygame.Rect(0, 0, map_width * TILE_WIDTH, map_height * TILE_HEIGHT))
    try:
        for glow in glows:
            frac = max(0.0, 1.0 - glow.age / max(1, glow.lifetime))
            if frac <= 0.0:
                continue
            surface = _draw_glow_surface(pygame, glow, frac)
            cx = glow.x * TILE_WIDTH + TILE_WIDTH // 2
            cy = glow.y * TILE_HEIGHT + TILE_HEIGHT // 2
            screen.blit(
                surface, (cx - surface.get_width() // 2, cy - surface.get_height() // 2),
                special_flags=pygame.BLEND_RGBA_ADD,
            )
    finally:
        screen.set_clip(None)


def _draw_hud_panel(
    pygame: Any,
    screen: Any,
    frame: OverlayFrame,
    palette: Any,
    logical_width: int,
    logical_height: int,
    tile_width: int = TILE_WIDTH,
    tile_height: int = TILE_HEIGHT,
    origin_x: int = 0,
    origin_y: int = 0,
) -> None:
    """Paint the right-hand HUD column's panel and captured text."""
    screen_width = logical_width // tile_width
    hud_height = min(frame.hud_height, logical_height // tile_height - frame.hud_top)
    hud_rect = pygame_ui.Rect(
        origin_x + frame.hud_x * tile_width,
        origin_y + frame.hud_top * tile_height,
        (screen_width - frame.hud_x) * tile_width,
        max(0, hud_height) * tile_height,
    )
    pygame_ui.draw_panel(pygame, screen, hud_rect, palette=palette)
    _draw_segments(
        pygame,
        screen,
        pygame_ui.cell_font(pygame, line_height=tile_height),
        frame.hud,
        origin_x=hud_rect.x,
        origin_y=hud_rect.y,
        width=hud_rect.width,
        height=hud_rect.height,
        origin_cell_x=frame.hud_x,
        origin_cell_y=frame.hud_top,
        padding_x=max(1, round(12 * tile_width / TILE_WIDTH)),
        padding_y=max(0, round(4 * tile_height / TILE_HEIGHT)),
        tile_width=tile_width,
        tile_height=tile_height,
    )


def _draw_message_panel(
    pygame: Any,
    screen: Any,
    frame: OverlayFrame,
    palette: Any,
    logical_width: int,
    logical_height: int,
    tile_width: int = TILE_WIDTH,
    tile_height: int = TILE_HEIGHT,
    origin_x: int = 0,
    origin_y: int = 0,
) -> None:
    """Paint the bottom message-log band's panel and captured text."""
    message_height = min(
        frame.message_height,
        max(0, logical_height // tile_height - frame.message_top),
    )
    message_rect = pygame_ui.Rect(
        origin_x,
        origin_y + frame.message_top * tile_height,
        logical_width,
        message_height * tile_height,
    )
    pygame_ui.draw_panel(pygame, screen, message_rect, palette=palette)
    _draw_segments(
        pygame,
        screen,
        pygame_ui.cell_font(pygame, line_height=tile_height),
        frame.messages,
        origin_x=message_rect.x,
        origin_y=message_rect.y,
        width=message_rect.width,
        height=message_rect.height,
        origin_cell_x=0,
        origin_cell_y=frame.message_top,
        padding_x=max(1, round(12 * tile_width / TILE_WIDTH)),
        padding_y=0,
        tile_width=tile_width,
        tile_height=tile_height,
    )


def draw_map_effects(
    pygame: Any,
    screen: Any,
    frame: OverlayFrame,
    *,
    logical_width: int,
    logical_height: int,
) -> None:
    """Paint map effects that belong on the logical surface before scaling."""
    map_width = (logical_width // TILE_WIDTH) - HUD_WIDTH
    map_height = (logical_height // TILE_HEIGHT) - MSG_LOG_HEIGHT
    _draw_shield_bubbles(
        pygame,
        screen,
        frame.shields,
        map_width=map_width,
        map_height=map_height,
    )
    _draw_floaters(
        pygame,
        screen,
        frame.floaters,
        map_width=map_width,
        map_height=map_height,
    )
    _draw_glows(
        pygame,
        screen,
        frame.glows,
        map_width=map_width,
        map_height=map_height,
    )
    if frame.target is not None:
        _draw_target_card(
            pygame,
            screen,
            frame.target,
            map_width=map_width,
            map_height=map_height,
        )


def draw_panels(
    pygame: Any,
    screen: Any,
    frame: OverlayFrame,
    *,
    logical_width: int,
    logical_height: int,
    tile_width: int = TILE_WIDTH,
    tile_height: int = TILE_HEIGHT,
    origin_x: int = 0,
    origin_y: int = 0,
) -> None:
    """Paint HUD and message panels at the target surface's native scale."""
    palette = pygame_ui.DEFAULT_PALETTE
    _draw_hud_panel(
        pygame, screen, frame, palette, logical_width, logical_height,
        tile_width=tile_width, tile_height=tile_height,
        origin_x=origin_x, origin_y=origin_y,
    )
    _draw_message_panel(
        pygame, screen, frame, palette, logical_width, logical_height,
        tile_width=tile_width, tile_height=tile_height,
        origin_x=origin_x, origin_y=origin_y,
    )


def draw(
    pygame: Any,
    screen: Any,
    frame: OverlayFrame,
    *,
    logical_width: int,
    logical_height: int,
) -> None:
    """Paint native map effects, framed HUD, and message-log regions."""
    draw_map_effects(
        pygame,
        screen,
        frame,
        logical_width=logical_width,
        logical_height=logical_height,
    )
    draw_panels(
        pygame,
        screen,
        frame,
        logical_width=logical_width,
        logical_height=logical_height,
    )
