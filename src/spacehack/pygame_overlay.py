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
from .game_context import GameContext
from .pygame_target_card import TargetCard, target_card_from_payload

from .engine import HUD_WIDTH, MSG_LOG_HEIGHT


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

    Legacy console captures report the default black background for every
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
class ShieldBubble:
    """One native shield effect around a ship in map-cell coordinates."""

    x: int
    y: int
    width: int = 1
    height: int = 1
    strength: float = 1.0


@dataclass(frozen=True)
class FloatingText:
    """One native floating combat number rendered by Pygame, not the bitmap.

    ``x``/``y`` are logical screen-cell coordinates (viewport-relative,
    like :class:`ShieldBubble`). ``age`` is the frame age (0 = spawn) and
    ``lifetime`` the total frame count; the renderer rises the text
    ``age``*2px and fades its colour toward dim grey as it ages.
    """

    text: str
    x: int
    y: int
    color: Color
    age: int
    lifetime: int


@dataclass(frozen=True)
class LightGlow:
    """One native radial light glow rendered by Pygame over the map region.

    ``x``/``y`` are logical screen-cell coordinates (viewport-relative,
    like :class:`FloatingText`). ``age`` is the frame age (0 = spawn) and
    ``lifetime`` the total frame count; the renderer fades the glow's
    intensity as it ages. Used for transient combat effects (weapon
    flashes, explosions) on the overlay layer, not the bitmap grid.
    """

    x: int
    y: int
    color: Color
    radius: int
    age: int
    lifetime: int


@dataclass(frozen=True)
class OverlayFrame:
    """Captured HUD, message-log, and native map-effect layers."""

    hud: tuple[OverlaySegment, ...]
    messages: tuple[OverlaySegment, ...]
    hud_x: int
    hud_top: int
    hud_height: int
    message_top: int
    message_height: int
    shields: tuple[ShieldBubble, ...] = ()
    floaters: tuple[FloatingText, ...] = ()
    glows: tuple[LightGlow, ...] = ()
    target: TargetCard | None = None


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


def _captured_message_segments(
    commands: Any, screen_width: int, screen_height: int,
) -> tuple[OverlaySegment, ...]:
    """Derive the bottom log band from captured console cells."""
    return _segments(
        commands,
        x_min=0,
        x_max=screen_width,
        y_min=screen_height - MSG_LOG_HEIGHT,
        y_max=screen_height,
    )


def _frame_from_commands(
    commands: Any,
    *,
    screen_width: int,
    screen_height: int,
    hud_view_height: int,
    hud_x_max: int | None = None,
    messages: tuple[OverlaySegment, ...] | None = None,
    shields: tuple[ShieldBubble, ...] = (),
    floaters: tuple[FloatingText, ...] = (),
    glows: tuple[LightGlow, ...] = (),
    target: TargetCard | None = None,
) -> OverlayFrame:
    """Build an overlay frame from an already-rendered console."""
    hud_x = screen_width - HUD_WIDTH
    # Combat consoles are one HUD-width wider; capture the extra HUD cells.
    hud_x_max = hud_x_max if hud_x_max is not None else screen_width
    return OverlayFrame(
        hud=_segments(
            commands,
            x_min=hud_x,
            x_max=hud_x_max,
            y_min=0,
            y_max=hud_view_height,
        ),
        messages=(
            messages
            if messages is not None
            else _captured_message_segments(commands, screen_width, screen_height)
        ),
        hud_x=hud_x,
        hud_top=0,
        hud_height=hud_view_height,
        message_top=screen_height - MSG_LOG_HEIGHT,
        message_height=MSG_LOG_HEIGHT,
        shields=tuple(shields),
        floaters=tuple(floaters),
        glows=tuple(glows),
        target=target,
    )


def _ship_shield_capacity(entity: Any, player_owned_ship: Any | None = None) -> int:
    """Return a space entity's installed shield capacity, or zero."""
    from . import ship as ship_module
    from .combat._stats import _calc_max_shields
    try:
        if getattr(entity, "owned", False) and getattr(entity, "ship_id", ""):
            _ship = ship_module.find_ship(entity.ship_id)
            _owned = (
                player_owned_ship
                if player_owned_ship is not None
                and getattr(player_owned_ship, "ship_id", "") == entity.ship_id
                else _ship
            )
            return _calc_max_shields(
                _ship, getattr(_owned, "modules", ()) or (),
            )
        npc_id = getattr(entity, "npc_ship_id", "")
        if npc_id:
            from .data.npc_ships import find_npc_ship
            npc = find_npc_ship(npc_id)
            # Match combat initialization: NPC modules define their
            # installed shield capacity; the player hull catalog's base
            # shields do not leak into an NPC's loadout. Out of combat
            # the modules read at base quality (no fly-time roll).
            return _calc_max_shields(
                npc, ship_module.base_module_entries(npc.modules),
            )
    except (KeyError, ImportError):
        return 0
    return 0


def _shield_bubble(
    x: int,
    y: int,
    *,
    camera_x: int,
    camera_y: int,
    width: int = 1,
    height: int = 1,
    strength: float = 1.0,
) -> ShieldBubble:
    """Build one bubble in the viewport's logical-cell coordinates."""
    return ShieldBubble(
        x - camera_x,
        y - camera_y,
        max(1, width),
        max(1, height),
        max(0.0, min(1.0, strength)),
    )


def _bubble_intersects_region(
    bubble: ShieldBubble,
    *,
    region_x: int,
    region_y: int,
    region_w: int,
    region_h: int,
) -> bool:
    """Return whether a bubble footprint intersects a map viewport."""
    return not (
        bubble.x + bubble.width <= region_x
        or bubble.x >= region_x + region_w
        or bubble.y + bubble.height <= region_y
        or bubble.y >= region_y + region_h
    )


def _ship_bubble(
    entity: Any,
    player_owned_ship: Any | None,
    *,
    camera_x: int,
    camera_y: int,
    region_x: int,
    region_y: int,
) -> ShieldBubble | None:
    """Build one viewport bubble for a shield-capable ship, else ``None``."""
    if not (
        getattr(entity, "owned", False) and getattr(entity, "ship_id", "")
    ) and not getattr(entity, "npc_ship_id", ""):
        return None
    if _ship_shield_capacity(entity, player_owned_ship) <= 0:
        return None
    return _shield_bubble(
        entity.pos.x + region_x,
        entity.pos.y + region_y,
        camera_x=camera_x,
        camera_y=camera_y,
        width=getattr(entity, "width", 1),
        height=getattr(entity, "height", 1),
    )


def shield_bubbles_for_map(
    game_map: Any,
    *,
    camera_x: int,
    camera_y: int,
    region_w: int,
    region_h: int,
    region_x: int = 0,
    region_y: int = 0,
    player_owned_ship: Any | None = None,
) -> tuple[ShieldBubble, ...]:
    """Build shield effects for every shield-capable ship in a space view.

    Normal space exploration has no persistent per-ship current-shield
    field, so a ship's installed shield capacity is its active shield
    state between encounters. Combat supplies live shield amounts through
    :func:`combat._rules_space.presentation_shield_bubbles` instead.
    """
    bubbles: list[ShieldBubble] = []
    for entity in getattr(game_map, "entities", ()):
        bubble = _ship_bubble(
            entity,
            player_owned_ship,
            camera_x=camera_x,
            camera_y=camera_y,
            region_x=region_x,
            region_y=region_y,
        )
        if bubble is not None and _bubble_intersects_region(
            bubble,
            region_x=region_x,
            region_y=region_y,
            region_w=region_w,
            region_h=region_h,
        ):
            bubbles.append(bubble)
    return tuple(bubbles)


def _render_hud_capture(
    console: Any,
    ctx: GameContext,
    *,
    screen_width: int,
    hud_view_height: int,
    location: str,
    mode: str,
    has_trade_terminal: bool,
    has_mech_terminal: bool,
    has_armory_terminal: bool,
) -> None:
    """Paint the domain HUD into ``console`` with the terminal flags."""
    from . import hud

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


def _message_segments(
    ctx: GameContext,
    screen_width: int,
    screen_height: int,
) -> tuple[OverlaySegment, ...]:
    """Build the bottom log band from the raw log, without cell truncation.

    A cell console would hard-cut each line at ``screen_width`` cells, but
    the native Pygame font is narrower than the 16px cells, so the message
    band can fit nearly twice as many characters. Building the segments
    from the full text lets :func:`_paint_segment` fit them to the real
    pixel width (with an ellipsis) — matching the menu log band
    (:func:`pygame_ui.draw_message_band`) exactly. Rows come from the
    shared :func:`pygame_ui.log_band_rows` builder.
    """
    n = MSG_LOG_HEIGHT
    msg_y_top = screen_height - n
    rows = pygame_ui.log_band_rows(ctx.log)
    offset = n - len(rows)
    segments = []
    for i, (text, color, runs) in enumerate(rows):
        y = msg_y_top + offset + i
        if runs is None:
            segments.append(OverlaySegment(0, y, text, color))
            continue
        # Runs chain on the same row: each segment starts at the cell
        # where the previous run's text ended (glyph-accurate chaining
        # in _segment_position).
        cell_x = 0
        for run_text, run_color in runs:
            if run_text:
                segments.append(OverlaySegment(cell_x, y, run_text, run_color))
                cell_x += len(run_text)
    return tuple(segments)


def capture(
    ctx: GameContext,
    *,
    mode: str,
    location: str,
    screen_width: int,
    screen_height: int,
    hud_view_height: int,
    has_trade_terminal: bool = False,
    has_mech_terminal: bool = False,
    has_armory_terminal: bool = False,
    shields: tuple[ShieldBubble, ...] = (),
) -> OverlayFrame:
    """Capture the authoritative HUD and message log into overlay segments."""
    from .pygame_world import CaptureConsole

    # The HUD console is one HUD-width wider than the window (like the
    # combat console) so HUD lines can use the panel's full ~36 half-width
    # characters instead of clipping at HUD_WIDTH cells.
    capture_console = CaptureConsole(screen_width + HUD_WIDTH, screen_height)
    _render_hud_capture(
        capture_console, ctx,
        screen_width=screen_width, hud_view_height=hud_view_height,
        location=location, mode=mode,
        has_trade_terminal=has_trade_terminal, has_mech_terminal=has_mech_terminal,
        has_armory_terminal=has_armory_terminal,
    )
    return _frame_from_commands(
        tuple(capture_console.commands),
        screen_width=screen_width, screen_height=screen_height,
        hud_view_height=hud_view_height,
        hud_x_max=screen_width + HUD_WIDTH,
        messages=_message_segments(ctx, screen_width, screen_height),
        shields=shields,
    )


def _segments_from_payload(data: dict[str, Any], key: str) -> tuple[OverlaySegment, ...]:
    """Deserialize one segment collection (``hud``/``messages``)."""
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


def _shields_from_payload(data: dict[str, Any]) -> tuple[ShieldBubble, ...]:
    """Deserialize the shield-bubble layer."""
    return tuple(
        ShieldBubble(
            x=int(item["x"]),
            y=int(item["y"]),
            width=int(item.get("width", 1)),
            height=int(item.get("height", 1)),
            strength=float(item.get("strength", 1.0)),
        )
        for item in data.get("shields", ())
    )


def _floaters_from_payload(data: dict[str, Any]) -> tuple[FloatingText, ...]:
    """Deserialize the floating-text layer."""
    return tuple(
        FloatingText(
            text=str(item["text"]),
            x=int(item["x"]),
            y=int(item["y"]),
            color=tuple(item["color"]),
            age=int(item.get("age", 0)),
            lifetime=int(item.get("lifetime", 1)),
        )
        for item in data.get("floaters", ())
    )


def frame_from_payload(data: dict[str, Any]) -> OverlayFrame:
    """Deserialize an overlay frame sent to an isolated Pygame worker."""
    return OverlayFrame(
        hud=_segments_from_payload(data, "hud"),
        messages=_segments_from_payload(data, "messages"),
        hud_x=int(data["hud_x"]),
        hud_top=int(data["hud_top"]),
        hud_height=int(data["hud_height"]),
        message_top=int(data["message_top"]),
        message_height=int(data["message_height"]),
        shields=_shields_from_payload(data),
        floaters=_floaters_from_payload(data),
        target=target_card_from_payload(data),
    )


def present_exploration(
    ctx: GameContext,
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
    shields: tuple[ShieldBubble, ...] = (),
) -> bool:
    """Present an exploration frame with native HUD/log text."""
    if getattr(ctx.context, "_runtime", None) is None:
        raise RuntimeError("Shared Pygame runtime is not open")

    frame = capture(
        ctx,
        mode=mode, location=location,
        screen_width=screen_width, screen_height=screen_height,
        hud_view_height=hud_view_height,
        has_trade_terminal=has_trade_terminal, has_mech_terminal=has_mech_terminal,
        has_armory_terminal=has_armory_terminal,
        shields=shields,
    )
    ctx.context.present(console, overlay=frame)
    return True


def payload(frame: OverlayFrame) -> dict[str, Any]:
    """Serialize an overlay frame for renderer tests or future workers."""
    return asdict(frame)



# Painting lives in the sibling module (architecture-ratchet split,
# 2026-09-23); re-exported so every existing caller keeps its
# pygame_overlay.* import path.
from .pygame_overlay_paint import (  # noqa: F401 — re-export surface
    _bubble_ring_width,
    _draw_floaters,
    _draw_shield_bubbles,
    _draw_glows,
    _draw_hud_panel,
    _draw_message_panel,
    _draw_segments,
    draw,
    draw_map_effects,
    draw_panels,
)
