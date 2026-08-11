"""Native Pygame presentation for the read-only space navigation map.

The map is intentionally not another terminal screenshot. The previous screen
used a fixed mini-map and an ASCII list, which made a large system read like a
dense block of characters. This module presents the live system data natively:
Pygame draws a plotted overview, proportional body markers, map tags, a colour
legend, and a compact destination index.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from . import pygame_ui
from .data import solar_systems as solar_system_module


Color = tuple[int, int, int]

MARKER_LABEL_COLOR: Color = (245, 248, 255)
MARKER_LABEL_BACKGROUND: Color = (3, 4, 8)
MARKER_LABEL_GAP = 6


class PygameNavigationUnavailable(RuntimeError):
    """Raised when the navigation screen cannot use the active Pygame runtime."""


@dataclass(frozen=True)
class NavigationMarker:
    """One plotted celestial body or the player's ship."""

    tag: str
    name: str
    kind: str
    x: int
    y: int
    width: int
    height: int
    color: Color


@dataclass(frozen=True)
class NavigationAoiRow:
    """One readable entry in the destination index."""

    tag: str
    label: str
    detail: str
    color: Color


@dataclass(frozen=True)
class NavigationAoiSection:
    """A labelled group in the destination index."""

    title: str
    rows: tuple[NavigationAoiRow, ...]
    color: Color


@dataclass(frozen=True)
class NavigationFrame:
    """Native map presentation data plus compatibility row fields."""

    title: str = "NAVIGATION"
    position: str = ""
    map_width: int = 1
    map_height: int = 1
    stars: tuple[tuple[int, int], ...] = ()
    markers: tuple[NavigationMarker, ...] = ()
    aoi_sections: tuple[NavigationAoiSection, ...] = ()
    legend: tuple[tuple[str, Color], ...] = ()


def _distance(body: Any, ship_pos: Any) -> float:
    """Return the Euclidean distance from the ship to a body's centre."""
    center_x = body.pos.x + (getattr(body, "width", 1) - 1) / 2
    center_y = body.pos.y + (getattr(body, "height", 1) - 1) / 2
    return round(math.hypot(center_x - ship_pos.x, center_y - ship_pos.y), 1)


def _marker(body: Any, *, tag: str, kind: str) -> NavigationMarker:
    """Convert a solar-system body into a renderer-neutral plot marker."""
    return NavigationMarker(
        tag=tag,
        name=body.name,
        kind=kind,
        x=body.pos.x,
        y=body.pos.y,
        width=getattr(body, "width", 1),
        height=getattr(body, "height", 1),
        color=tuple(body.fg),
    )


def _body_section(
    title: str,
    bodies: Any,
    *,
    tag_prefix: str,
    kind: str,
    color: Color,
    ship_pos: Any,
) -> tuple[NavigationAoiSection, tuple[NavigationMarker, ...]]:
    """Build one sorted body section and its plotted markers."""
    ordered = tuple(sorted(bodies, key=lambda body: (_distance(body, ship_pos), body.name)))
    rows = tuple(
        NavigationAoiRow(
            tag=f"{tag_prefix}{index}",
            label=body.name,
            detail=f"{_distance(body, ship_pos):.1f}u",
            color=color,
        )
        for index, body in enumerate(ordered, 1)
    )
    markers = tuple(
        _marker(body, tag=f"{tag_prefix}{index}", kind=kind)
        for index, body in enumerate(ordered, 1)
    )
    return NavigationAoiSection(title, rows, color), markers


def _aoi_sections(system: Any, ship_pos: Any) -> tuple[tuple[NavigationAoiSection, ...], tuple[NavigationMarker, ...]]:
    """Build the readable destination index from the live system data."""
    palette = pygame_ui.DEFAULT_PALETTE
    stars = tuple(body for body in system.planets if getattr(body, "sun", False))
    planets = tuple(body for body in system.planets if not getattr(body, "sun", False))
    sections: list[NavigationAoiSection] = []
    markers: list[NavigationMarker] = []
    for title, bodies, prefix, kind, color in (
        ("STARS", stars, "S", "star", (255, 220, 130)),
        ("PLANETS", planets, "P", "planet", palette.text),
        ("JUMP GATES", tuple(system.jump_points), "G", "gate", palette.instruction),
        ("STATIONS", tuple(getattr(system, "stations", ()) or ()), "T", "station", palette.selected_border),
    ):
        if not bodies:
            continue
        section, section_markers = _body_section(
            title, bodies, tag_prefix=prefix, kind=kind,
            color=color, ship_pos=ship_pos,
        )
        sections.append(section)
        markers.extend(section_markers)

    reachable = solar_system_module.reachable_system_ids(system.id)
    if reachable:
        rows = tuple(
            NavigationAoiRow(
                tag="->",
                label=solar_system_module.find_solar_system(system_id).name,
                detail=f"{hops} hop{'s' if hops != 1 else ''}",
                color=palette.selected_border,
            )
            for system_id, hops in sorted(reachable.items(), key=lambda item: (item[1], item[0]))
        )
        sections.append(NavigationAoiSection("REACHABLE SYSTEMS", rows, palette.selected_border))
    return tuple(sections), tuple(markers)


def _native_data(system: Any, ship_pos: Any) -> tuple[tuple[NavigationAoiSection, ...], tuple[NavigationMarker, ...]]:
    """Assemble semantic map data without changing gameplay state."""
    sections, markers = _aoi_sections(system, ship_pos)
    ship = NavigationMarker(
        tag="YOU",
        name="Your ship",
        kind="ship",
        x=ship_pos.x,
        y=ship_pos.y,
        width=1,
        height=1,
        color=(255, 255, 100),
    )
    return sections, markers + (ship,)


def _capture(ctx: Any, ship_pos: Any) -> NavigationFrame:
    """Build a native frame directly from the authoritative system catalog."""
    from . import solar_system

    system = solar_system.current_system()
    sections, markers = _native_data(system, ship_pos)
    return NavigationFrame(
        title=f"NAVIGATION - {system.name.upper()}",
        position=f"Position: ({ship_pos.x}, {ship_pos.y})",
        map_width=system.width,
        map_height=system.height,
        stars=tuple(system.stars),
        markers=markers,
        aoi_sections=sections,
        legend=(
            ("YOU", (255, 255, 100)),
            ("STAR", (255, 220, 130)),
            ("PLANET", pygame_ui.DEFAULT_PALETTE.text),
            ("GATE", pygame_ui.DEFAULT_PALETTE.instruction),
            ("STATION", pygame_ui.DEFAULT_PALETTE.selected_border),
        ),
    )


def _panels(width: int, height: int, *, has_context: bool) -> tuple[pygame_ui.Rect, pygame_ui.Rect, int]:
    """Return the outer frame, map panel, and destination panel."""
    outer = pygame_ui.Rect(32, 28, max(1, width - 64), max(1, height - 56))
    footer_y = (
        pygame_ui.modal_footer_text_y(height, 30)
        if has_context else height - 68
    )
    panel_height = max(1, max(111, footer_y - 12) - 110)
    gap = 18
    usable_width = max(2, outer.width - 32 - gap)
    map_width = max(1, int(usable_width * 0.64))
    index_width = max(1, usable_width - map_width)
    map_panel = pygame_ui.Rect(48, 110, map_width, panel_height)
    index_panel = pygame_ui.Rect(map_panel.x + map_width + gap, 110, index_width, panel_height)
    return outer, map_panel, index_panel


def _font(pygame: Any, frame: NavigationFrame, width: int, height: int) -> Any:
    """Choose a readable font that fits the destination index."""
    from .pygame_merchant import _font_path

    path = _font_path(pygame)
    _, _, index_panel = _panels(width, height, has_context=True)
    content_height = index_panel.height - 74
    content_width = max(1, index_panel.width - 44)

    def _height(candidate: Any) -> int:
        line = candidate.get_linesize() + 6
        row_widths = (
            candidate.size(f"{row.tag} {row.label} {row.detail}")[0]
            for section in frame.aoi_sections
            for row in section.rows
        )
        if max(row_widths, default=0) > content_width:
            return content_height + 1
        return sum(
            line * (1 + len(section.rows)) + 8
            for section in frame.aoi_sections
        )

    return pygame_ui.fit_font(
        pygame, path,
        measure_height=_height,
        available_height=max(1, content_height),
    )


def _plot_point(marker: NavigationMarker, plot: pygame_ui.Rect, map_width: int, map_height: int) -> tuple[int, int]:
    """Project a map-space marker into the pixel plot."""
    center_x = marker.x + marker.width / 2
    center_y = marker.y + marker.height / 2
    return (
        plot.x + round(center_x / max(1, map_width) * plot.width),
        plot.y + round(center_y / max(1, map_height) * plot.height),
    )


def _marker_radius(marker: NavigationMarker, plot: pygame_ui.Rect, map_width: int, map_height: int) -> int:
    """Scale a body's footprint into a legible plotted marker."""
    scale = min(plot.width / max(1, map_width), plot.height / max(1, map_height))
    return max(3, min(28, round(max(marker.width, marker.height) * scale / 2)))


def _marker_label_position(
    marker: NavigationMarker,
    plot: pygame_ui.Rect,
    map_width: int,
    map_height: int,
    font: Any,
) -> tuple[int, int]:
    """Place a marker label above its object, with an edge-safe fallback."""
    center_x, center_y = _plot_point(marker, plot, map_width, map_height)
    radius = _marker_radius(marker, plot, map_width, map_height)
    label_width = pygame_ui.measure_font(font, marker.tag)
    line_height = font.get_linesize()
    x = max(
        plot.x + 4,
        min(center_x - label_width // 2, plot.x + plot.width - label_width - 4),
    )
    above_y = center_y - radius - line_height - MARKER_LABEL_GAP
    below_y = center_y + radius + MARKER_LABEL_GAP
    if above_y >= plot.y + 4:
        return x, above_y
    if below_y + line_height <= plot.y + plot.height - 4:
        return x, below_y
    return x, max(plot.y + 4, above_y)


def _draw_marker_label(
    pygame: Any,
    screen: Any,
    font: Any,
    marker: NavigationMarker,
    plot: pygame_ui.Rect,
    map_width: int,
    map_height: int,
) -> None:
    """Paint a high-contrast label in a small dark backing plate."""
    x, y = _marker_label_position(marker, plot, map_width, map_height, font)
    label_width = pygame_ui.measure_font(font, marker.tag)
    label_rect = pygame.Rect(x - 4, y - 2, label_width + 8, font.get_linesize() + 4)
    pygame.draw.rect(screen, MARKER_LABEL_BACKGROUND, label_rect, border_radius=3)
    pygame.draw.rect(screen, marker.color, label_rect, width=1, border_radius=3)
    pygame_ui.draw_text(
        pygame, screen, font, marker.tag, x, y, color=MARKER_LABEL_COLOR,
    )


def _draw_marker(
    pygame: Any,
    screen: Any,
    font: Any,
    marker: NavigationMarker,
    plot: pygame_ui.Rect,
    map_width: int,
    map_height: int,
) -> None:
    """Paint one distinct marker shape and its readable map label."""
    center = _plot_point(marker, plot, map_width, map_height)
    radius = _marker_radius(marker, plot, map_width, map_height)
    if marker.kind == "ship":
        x, y = center
        pygame.draw.polygon(screen, marker.color, ((x, y - 8), (x - 7, y + 7), (x + 7, y + 7)))
    elif marker.kind == "gate":
        x, y = center
        pygame.draw.polygon(screen, marker.color, ((x, y - radius), (x + radius, y), (x, y + radius), (x - radius, y)))
        pygame.draw.line(screen, pygame_ui.DEFAULT_PALETTE.background, (x, y - radius // 2), (x, y + radius // 2), width=2)
    elif marker.kind == "station":
        pygame.draw.rect(screen, marker.color, pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2), border_radius=3)
    else:
        pygame.draw.circle(screen, marker.color, center, radius)
        if marker.kind == "star":
            pygame.draw.circle(screen, (255, 250, 210), center, max(1, radius // 2))
    _draw_marker_label(pygame, screen, font, marker, plot, map_width, map_height)


def _draw_plot(pygame: Any, screen: Any, font: Any, frame: NavigationFrame, panel: pygame_ui.Rect) -> None:
    """Draw a low-noise plotted overview instead of a character grid."""
    palette = pygame_ui.DEFAULT_PALETTE
    plot = pygame_ui.Rect(panel.x + 22, panel.y + 62, panel.width - 44, max(1, panel.height - 152))
    pygame.draw.rect(screen, (5, 8, 18), pygame.Rect(plot.x, plot.y, plot.width, plot.height), border_radius=4)
    pygame.draw.rect(screen, palette.border, pygame.Rect(plot.x, plot.y, plot.width, plot.height), width=1, border_radius=4)
    for fraction in (0.25, 0.5, 0.75):
        pygame.draw.line(screen, (22, 30, 52), (plot.x + round(plot.width * fraction), plot.y), (plot.x + round(plot.width * fraction), plot.y + plot.height))
        pygame.draw.line(screen, (22, 30, 52), (plot.x, plot.y + round(plot.height * fraction)), (plot.x + plot.width, plot.y + round(plot.height * fraction)))
    for star_x, star_y in frame.stars:
        x = plot.x + round(star_x / max(1, frame.map_width) * plot.width)
        y = plot.y + round(star_y / max(1, frame.map_height) * plot.height)
        pygame.draw.circle(screen, (80, 92, 132), (x, y), 1)
    screen.set_clip(pygame.Rect(plot.x, plot.y, plot.width, plot.height))
    try:
        for marker in frame.markers:
            _draw_marker(pygame, screen, font, marker, plot, frame.map_width, frame.map_height)
    finally:
        screen.set_clip(None)

    pygame_ui.draw_text(pygame, screen, font, "N", plot.x + 8, plot.y + 8, color=palette.border)
    pygame_ui.draw_text(pygame, screen, font, "S", plot.x + 8, plot.y + plot.height - font.get_linesize() - 8, color=palette.border)
    pygame_ui.draw_text(pygame, screen, font, "W", plot.x + 8, plot.y + plot.height // 2 - font.get_linesize() // 2, color=palette.border)
    pygame_ui.draw_text(pygame, screen, font, "E", plot.x + plot.width - pygame_ui.measure_font(font, "E") - 8, plot.y + plot.height // 2 - font.get_linesize() // 2, color=palette.border)


def _draw_legend(pygame: Any, screen: Any, font: Any, frame: NavigationFrame, panel: pygame_ui.Rect) -> None:
    """Draw the marker key below the plotted map."""
    palette = pygame_ui.DEFAULT_PALETTE
    y = panel.y + panel.height - 72
    x = panel.x + 22
    for label, color in frame.legend:
        pygame.draw.circle(screen, color, (x + 5, y + font.get_linesize() // 2), 5)
        pygame_ui.draw_text(pygame, screen, font, label, x + 16, y, color=palette.description)
        x += pygame_ui.measure_font(font, label) + 48
        if x > panel.x + panel.width - 110:
            x = panel.x + 22
            y += font.get_linesize() + 4


def _draw_index(pygame: Any, screen: Any, font: Any, frame: NavigationFrame, panel: pygame_ui.Rect) -> None:
    """Draw the tagged destination index with grouped, scannable rows."""
    palette = pygame_ui.DEFAULT_PALETTE
    content = pygame_ui.Rect(panel.x + 20, panel.y + 62, panel.width - 40, panel.height - 76)
    screen.set_clip(pygame.Rect(content.x, content.y, content.width, content.height))
    try:
        y = content.y
        line = font.get_linesize() + 6
        for section in frame.aoi_sections:
            pygame_ui.draw_text(pygame, screen, font, section.title, content.x, y, color=section.color)
            y += line
            for row in section.rows:
                if y + line > content.y + content.height:
                    return
                tag = row.tag
                tag_width = pygame_ui.measure_font(font, tag)
                pygame_ui.draw_text(pygame, screen, font, tag, content.x, y, color=row.color)
                available = content.width - tag_width - 18
                detail_width = pygame_ui.measure_font(font, row.detail)
                label_width = max(1, available - detail_width - 12)
                label = pygame_ui.fit_text(row.label, label_width, lambda value: pygame_ui.measure_font(font, value))
                pygame_ui.draw_text(pygame, screen, font, label, content.x + tag_width + 10, y, color=palette.text)
                pygame_ui.draw_text(pygame, screen, font, row.detail, content.x + content.width - detail_width, y, color=palette.description)
                y += line
            y += 5
    finally:
        screen.set_clip(None)


def _draw(
    pygame: Any, screen: Any, font: Any, frame: NavigationFrame,
    *, context: Any | None = None,
) -> None:
    """Draw the native overview using the shared modal chrome."""
    width, height = screen.get_size()
    palette = pygame_ui.DEFAULT_PALETTE
    screen.fill(palette.background)
    outer, map_panel, index_panel = _panels(width, height, has_context=context is not None)
    pygame_ui.draw_panel(pygame, screen, outer, palette=palette)
    pygame_ui.draw_centered_text(pygame, screen, font, frame.title, outer, outer.y + 22, color=palette.title)
    pygame_ui.draw_rule(pygame, screen, outer.x + 24, outer.y + 54, outer.width - 48, color=palette.border)
    pygame_ui.draw_panel(pygame, screen, map_panel, palette=palette)
    pygame_ui.draw_panel(pygame, screen, index_panel, palette=palette)
    pygame_ui.draw_text(pygame, screen, font, "SYSTEM MAP", map_panel.x + 20, map_panel.y + 18, color=palette.title)
    pygame_ui.draw_text(
        pygame, screen, font,
        f"{frame.map_width} x {frame.map_height} cells  |  {len(frame.markers) - 1} plotted bodies",
        map_panel.x + 20, map_panel.y + 42, color=palette.description,
    )
    pygame_ui.draw_text(pygame, screen, font, "DESTINATIONS", index_panel.x + 20, index_panel.y + 18, color=palette.title)
    pygame_ui.draw_rule(pygame, screen, map_panel.x + 18, map_panel.y + 54, map_panel.width - 36, color=palette.border)
    pygame_ui.draw_rule(pygame, screen, index_panel.x + 18, index_panel.y + 46, index_panel.width - 36, color=palette.border)
    _draw_plot(pygame, screen, font, frame, map_panel)
    _draw_legend(pygame, screen, font, frame, map_panel)
    _draw_index(pygame, screen, font, frame, index_panel)
    footer_y = (
        pygame_ui.modal_footer_text_y(height, font.get_linesize() + 6)
        if context is not None else height - 68
    )
    pygame_ui.draw_text(pygame, screen, font, frame.position, outer.x + 20, footer_y, color=palette.text)
    hint = pygame_ui.modal_hint("ESC close", pygame_ui.GUIDE_HINT)
    hint_width = pygame_ui.measure_font(font, hint)
    pygame_ui.draw_text(pygame, screen, font, hint, width - hint_width - 44, footer_y, color=palette.instruction)
    if context is not None:
        pygame_ui.draw_context_log(pygame, screen, context)


def _handle_key(pygame: Any, event: Any) -> str:
    """Translate read-only navigation input."""
    if event.type == pygame.QUIT:
        return "QUIT"
    if event.type != pygame.KEYDOWN:
        return "IGNORE"
    if event.key == pygame.K_ESCAPE:
        return "BACK"
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE"
    return "IGNORE"


def run_shared(context: Any, ctx: Any, ship_pos: Any) -> str:
    """Render navigation inside the already-open game window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameNavigationUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    frame = _capture(ctx, ship_pos)
    font = _font(pygame, frame, *screen.get_size())
    while True:
        _draw(pygame, screen, font, frame, context=context)
        engine.present()
        outcome = _handle_key(pygame, pygame.event.wait())
        if outcome != "IGNORE":
            return outcome


def run_for_context(context: Any, ctx: Any, ship_pos: Any) -> str:
    """Use the shared runtime; otherwise request the normal fallback."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(context):
        raise PygameNavigationUnavailable("Navigation requires the shared Pygame runtime")
    return run_shared(context, ctx, ship_pos)
