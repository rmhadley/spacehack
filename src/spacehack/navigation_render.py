"""Navigation overlay + Areas-of-Interest panel rendering.

Extracted from ``navigation.py`` to keep that module under the 1,000-line
architecture limit. Every function here stays under 40 lines.
"""

from __future__ import annotations

import math

from . import solar_system as solar_system_module
from . import ui
from . import world
from .data import solar_systems as solar_systems_module
from .engine import HUD_WIDTH
from .framebuffer import FrameBuffer
from .game_context import GameContext

NAV_SHIP_FG: tuple[int, int, int] = (255, 255, 100)


def _body_dist(body, ship_pos) -> float:
    """Euclidean distance (1 dp) from ``ship_pos`` to ``body``'s centre."""
    cx = body.pos.x + (getattr(body, "width", 1) - 1) / 2.0
    cy = body.pos.y + (getattr(body, "height", 1) - 1) / 2.0
    return round(math.hypot(cx - ship_pos.x, cy - ship_pos.y), 1)


def _clamp_label(label: str, name_w: int) -> str:
    """Truncate ``label`` with an ellipsis to fit ``name_w`` chars."""
    if len(label) <= name_w:
        return label
    return label[:name_w - 1] + "..."


def _aoi_row(label: str, inner_w: int, name_w: int, dist=None) -> str:
    """One AOI row: ``label`` plus an optional ``- {dist}u`` suffix."""
    if dist is None:
        return ui.fit_text(label, inner_w)
    return ui.fit_text(f"{_clamp_label(label, name_w)} - {dist}u", inner_w)


def _aoi_rows(system, ship_pos, inner_w: int, name_w: int):
    """Build the AOI panel's ``(label, fg)`` rows, sorted by distance."""
    rows = [("AREAS OF INTEREST", ui.COLOR_TITLE), ("", ui.COLOR_VALUE_DIM)]
    stars = [p for p in system.planets if getattr(p, "sun", False)]
    if stars:
        rows.append(("Stars", ui.COLOR_TITLE))
        rows.extend(
            (_aoi_row(p.name, inner_w, name_w, _body_dist(p, ship_pos)), ui.COLOR_TITLE)
            for p in stars
        )
        rows.append(("", ui.COLOR_TITLE))
    planets = [p for p in system.planets if not getattr(p, "sun", False)]
    if planets:
        rows.append(("Planets", ui.COLOR_VALUE_WHITE))
        rows.extend(
            (_aoi_row(p.name, inner_w, name_w, _body_dist(p, ship_pos)), ui.COLOR_VALUE_WHITE)
            for p in sorted(planets, key=lambda b: _body_dist(b, ship_pos))
        )
        rows.append(("", ui.COLOR_VALUE_WHITE))
    if system.jump_points:
        rows.append(("Jump Points", ui.COLOR_OPTION_HIGHLIGHT))
        rows.extend(
            (_aoi_row(jp.name, inner_w, name_w, _body_dist(jp, ship_pos)), ui.COLOR_OPTION_HIGHLIGHT)
            for jp in sorted(system.jump_points, key=lambda b: _body_dist(b, ship_pos))
        )
        rows.append(("", ui.COLOR_OPTION_HIGHLIGHT))
    stations = list(getattr(system, "stations", ()) or ())
    if stations:
        rows.append(("Stations", ui.COLOR_OPTION_HIGHLIGHT2))
        rows.extend(
            (_aoi_row(st.name, inner_w, name_w, _body_dist(st, ship_pos)), ui.COLOR_OPTION_HIGHLIGHT2)
            for st in sorted(stations, key=lambda b: _body_dist(b, ship_pos))
        )
        rows.append(("", ui.COLOR_OPTION_HIGHLIGHT2))
    rows.extend(_reachable_rows(system.id, inner_w, name_w))
    return rows


def _reachable_rows(system_id: str, inner_w: int, name_w: int):
    """AOI rows for systems reachable from ``system_id``, sorted by hops."""
    reachable_counts = solar_systems_module.reachable_system_ids(system_id)
    if not reachable_counts:
        return ()
    rows = [("Reachable Systems", ui.COLOR_OPTION_HIGHLIGHT)]
    for dest_id, hops in sorted(reachable_counts.items(), key=lambda kv: (kv[1], kv[0])):
        dest_sys = solar_systems_module.find_solar_system(dest_id)
        row_text = f"{dest_sys.name:<{name_w}} - {hops} hop{('s' if hops > 1 else '')}"
        rows.append((ui.fit_text(row_text, inner_w), ui.COLOR_OPTION_HIGHLIGHT))
    rows.append(("", ui.COLOR_OPTION_HIGHLIGHT))
    return rows


def _render_aoi_panel(
    console, system, ship_pos, *, x: int, y: int, width: int, height: int,
) -> None:
    """Right-side Areas-of-Interest panel for the Map/NAVIGATION overlay."""
    inner_w = max(0, width - 4)
    name_w = max(4, inner_w - 10)
    rows = _aoi_rows(system, ship_pos, inner_w, name_w)
    cy = y + 1
    for label, fg in rows:
        if cy >= y + height - 2:
            break
        if not label:
            cy += 1
            continue
        console.print(x=x + 2, y=cy, string=label, fg=fg)
        cy += 1
    rect = (x + 1, y + 1, max(0, width - 2), max(0, height - 2))
    ui.paint_rect_border(console, rect, fg=ui.COLOR_VALUE_DIM)


def _minimap_cell_body(system, mini_y: int, mini_x: int, *, sample_y, cell_step_x, bodies, nav_map_h: int) -> object | None:
    """Return the body sampled at minimap cell (mini_x, mini_y), or ``None``."""
    by_lo = int(mini_y * sample_y)
    by_hi = int((mini_y + 1) * sample_y) if mini_y + 1 < nav_map_h else system.height
    bx_lo = mini_x * cell_step_x
    bx_hi = bx_lo + cell_step_x
    for y in range(by_lo, by_hi):
        for x in range(bx_lo, bx_hi):
            if not (0 <= x < system.width and 0 <= y < system.height):
                continue
            for body in bodies:
                if (body.pos.x <= x < body.pos.x + body.width
                        and body.pos.y <= y < body.pos.y + body.height):
                    return body
    return None


def _render_nav_minimap(
    console,
    system,
    *,
    map_off_x: int,
    map_off_y: int,
    nav_map_w: int,
    nav_map_h: int,
    ship_pos: world.Position,
) -> None:
    """Paint the mini-map (bodies + ship marker) for the NAVIGATION overlay."""
    sample_x = system.width / nav_map_w
    sample_y = system.height / nav_map_h
    bodies_for_overlay = list(system.planets) + list(system.jump_points)
    cell_step_x = max(1, int(sample_x))
    for mini_y in range(nav_map_h):
        for mini_x in range(nav_map_w):
            planet_here = _minimap_cell_body(
                system, mini_y, mini_x,
                sample_y=sample_y, cell_step_x=cell_step_x,
                bodies=bodies_for_overlay, nav_map_h=nav_map_h,
            )
            if planet_here is not None:
                console.print(
                    x=map_off_x + mini_x, y=map_off_y + mini_y,
                    string=planet_here.char, fg=planet_here.fg,
                )
            else:
                console.print(
                    x=map_off_x + mini_x, y=map_off_y + mini_y,
                    string=".", fg=(80, 80, 110),
                )
    ship_mini_x = int(ship_pos.x / sample_x)
    ship_mini_y = int(ship_pos.y / sample_y)
    if 0 <= ship_mini_x < nav_map_w and 0 <= ship_mini_y < nav_map_h:
        console.print(
            x=map_off_x + ship_mini_x, y=map_off_y + ship_mini_y,
            string="@", fg=NAV_SHIP_FG,
        )


def render_navigation(
    console: FrameBuffer,
    ctx: GameContext,
    *,
    screen_width: int,
    screen_height: int,
    ship_pos: world.Position,
    system=None,
) -> None:
    """Paint the current-solar-system navigation overlay."""
    console.clear()
    if system is None:
        system = solar_system_module.current_system()
    title = f"NAVIGATION - {system.name.upper()} SYSTEM"
    content_y = ui.screen_header(console, screen_width, title)
    inner_view_w = screen_width - HUD_WIDTH
    nav_map_w, nav_map_h = 40, 30
    map_off_x = (inner_view_w - nav_map_w) // 2
    map_off_y = content_y
    _render_nav_minimap(
        console, system,
        map_off_x=map_off_x, map_off_y=map_off_y,
        nav_map_w=nav_map_w, nav_map_h=nav_map_h,
        ship_pos=ship_pos,
    )
    if hasattr(system, "stations"):
        aoi_w = 28
        aoi_x = max(0, min(screen_width - aoi_w - 2, screen_width - aoi_w - 1))
        aoi_y = content_y
        aoi_h = max(8, screen_height - 12)
        _render_aoi_panel(
            console, system, ship_pos,
            x=aoi_x, y=aoi_y, width=aoi_w, height=aoi_h,
        )
    _render_nav_footer(
        console, screen_width, ship_pos,
        foot_y=map_off_y + nav_map_h + 1,
    )


def _render_nav_footer(console, screen_width: int, ship_pos: world.Position, *, foot_y: int) -> None:
    """Paint the NAVIGATION overlay footer (position + ESC hint)."""
    coord_line = f"You are at ({ship_pos.x}, {ship_pos.y})."
    max_w = screen_width - HUD_WIDTH - 2
    if len(coord_line) > max_w:
        coord_line = coord_line[:max_w - 1] + "..."
    console.print(
        x=ui.centered_x(coord_line, screen_width), y=foot_y,
        string=coord_line, fg=ui.COLOR_VALUE_WHITE,
    )
    hint = "Press ESC to close."
    console.print(
        x=ui.centered_x(hint, screen_width), y=foot_y + 2,
        string=hint, fg=ui.COLOR_INSTRUCTION,
    )
