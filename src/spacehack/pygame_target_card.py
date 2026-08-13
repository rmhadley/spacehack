"""Native floating info card for a targeted combatant.

The card is renderer-neutral data (:class:`TargetCard`) plus its
placement and drawing. Content rows are formatted by each combat mode's
presentation module (ground/space); this module only anchors the card
near the target and paints the rows, dodging the player and hostiles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import pygame_ui
from .engine import TILE_HEIGHT, TILE_WIDTH

Color = tuple[int, int, int]


@dataclass(frozen=True)
class TargetCard:
    """Native floating info card anchored to a targeted combatant.

    ``rows`` is the pre-formatted card body: a tuple of rows, each row a
    tuple of ``(text, color)`` segments. ``x``/``y`` are the target's
    viewport-relative cell; ``avoid_cells`` are cells the card must not
    cover (player + visible hostiles); ``player_cell`` drives the
    away-from-player placement preference.
    """

    rows: tuple[tuple[tuple[str, Color], ...], ...]
    x: int
    y: int
    avoid_cells: tuple[tuple[int, int], ...] = ()
    player_cell: tuple[int, int] | None = None


# Standard palette shared by every domain's row builders so the card
# reads as one affordance regardless of combat type.
TARGET_CARD_TITLE: Color = (255, 220, 100)
TARGET_CARD_TEXT: Color = (232, 236, 246)
TARGET_CARD_DIM: Color = (170, 170, 185)
_TARGET_CARD_PAD_X: int = 12
_TARGET_CARD_PAD_Y: int = 8


def title_row(text: str) -> tuple[tuple[str, Color], ...]:
    """One gold title row."""
    return ((text, TARGET_CARD_TITLE),)


def text_row(text: str) -> tuple[tuple[str, Color], ...]:
    """One body-text row."""
    return ((text, TARGET_CARD_TEXT),)


def dim_row(text: str) -> tuple[tuple[str, Color], ...]:
    """One dimmed row (weapon names, hints)."""
    return ((text, TARGET_CARD_DIM),)


def hint_row() -> tuple[tuple[str, Color], ...]:
    """The final ``[V] hide`` toggle hint row."""
    return (("[V] hide", TARGET_CARD_DIM),)


def _card_cells(panel_w: int, panel_h: int) -> tuple[int, int]:
    """Card footprint in cell units (pixel size rounded up to whole cells)."""
    return (
        (panel_w + TILE_WIDTH - 1) // TILE_WIDTH,
        (panel_h + TILE_HEIGHT - 1) // TILE_HEIGHT,
    )


def _card_rect_clear(
    x: int,
    y: int,
    cw: int,
    ch: int,
    avoid: set[tuple[int, int]],
    map_width: int,
    map_height: int,
) -> bool:
    """Whether a card at cell ``(x, y)`` is in-bounds and covers no avoided cell."""
    if x < 0 or y < 0 or x + cw > map_width or y + ch > map_height:
        return False
    return not any(x <= ax < x + cw and y <= ay < y + ch for ax, ay in avoid)


def _preferred_positions(
    tx: int,
    ty: int,
    cw: int,
    ch: int,
    px: int | None = None,
    py: int | None = None,
) -> tuple[tuple[int, int], ...]:
    """Candidate top-left cells, ordered away-from-player first.

    Favors the side of the target opposite the player (so the card never
    covers the player), then the perpendicular axis, then the two
    toward-player sides. Without a player cell it falls back to the fixed
    order above/below/right/left. Every candidate leaves one empty tile
    between the card and the target.
    """
    positions = {
        "above": (tx - cw // 2, ty - 1 - ch),
        "below": (tx - cw // 2, ty + 2),
        "right": (tx + 2, ty - ch // 2),
        "left": (tx - 1 - cw, ty - ch // 2),
    }
    if px is None or py is None:
        return (positions["above"], positions["below"], positions["right"], positions["left"])
    away_x = tx - px
    away_y = ty - py
    h_away, h_toward = ("right", "left") if away_x > 0 else ("left", "right")
    v_away, v_toward = ("below", "above") if away_y > 0 else ("above", "below")
    if abs(away_x) >= abs(away_y):
        order = (h_away, v_away, h_toward, v_toward)
    else:
        order = (v_away, h_away, v_toward, h_toward)
    return tuple(positions[direction] for direction in order)


def _clamp_card_cell(
    x: int, y: int, cw: int, ch: int, map_width: int, map_height: int,
) -> tuple[int, int]:
    """Clamp a card's top-left cell inside the viewport."""
    return (
        max(0, min(x, map_width - cw)),
        max(0, min(y, map_height - ch)),
    )


def _closest_clear_cell(
    tx: int,
    ty: int,
    cw: int,
    ch: int,
    avoid: set[tuple[int, int]],
    map_width: int,
    map_height: int,
) -> tuple[int, int]:
    """Fall back to the nearest in-bounds, non-occluding top-left cell."""
    best: tuple[int, int] | None = None
    best_dist: int | None = None
    for y in range(map_height - ch + 1):
        for x in range(map_width - cw + 1):
            if not _card_rect_clear(x, y, cw, ch, avoid, map_width, map_height):
                continue
            dist = abs(x + cw // 2 - tx) + abs(y + ch // 2 - ty)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = (x, y)
    if best is None:
        return _clamp_card_cell(tx - cw // 2, ty - 1 - ch, cw, ch, map_width, map_height)
    return best


def _target_keep_clear(tx: int, ty: int) -> set[tuple[int, int]]:
    """The target cell and its 8 neighbors the card must not touch."""
    return {(tx + dx, ty + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


def _target_card_cells(
    card: TargetCard,
    *,
    cw: int,
    ch: int,
    map_width: int,
    map_height: int,
) -> tuple[int, int]:
    """Choose the card's top-left cell, dodging visible chars/enemies.

    Favors the side of the target opposite the player, then falls back to
    below/right/left and finally the closest clear cell. Every candidate
    (including the fallback) must leave at least one empty tile between
    the card and the target.
    """
    avoid = set(card.avoid_cells) | _target_keep_clear(card.x, card.y)
    _pc = card.player_cell
    px, py = _pc if _pc is not None else (None, None)
    for x, y in _preferred_positions(card.x, card.y, cw, ch, px, py):
        if _card_rect_clear(x, y, cw, ch, avoid, map_width, map_height):
            return x, y
    return _closest_clear_cell(card.x, card.y, cw, ch, avoid, map_width, map_height)


def _target_card_rect(
    card: TargetCard,
    *,
    panel_w: int,
    panel_h: int,
    map_width: int,
    map_height: int,
) -> pygame_ui.Rect:
    """Place the card's pixel rect from its chosen top-left cell."""
    cw, ch = _card_cells(panel_w, panel_h)
    cell_x, cell_y = _target_card_cells(
        card, cw=cw, ch=ch, map_width=map_width, map_height=map_height,
    )
    return pygame_ui.Rect(cell_x * TILE_WIDTH, cell_y * TILE_HEIGHT, panel_w, panel_h)


def _target_card_panel(card: TargetCard, font: Any):
    """Return ``(rows, panel_w, panel_h, line_height)`` for a target card."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    rows = card.rows
    row_widths = [sum(measure(text) for text, _c in row) for row in rows]
    line_height = font.get_linesize()
    panel_w = max(row_widths) + 2 * _TARGET_CARD_PAD_X
    panel_h = len(rows) * line_height + 2 * _TARGET_CARD_PAD_Y
    return rows, panel_w, panel_h, line_height


def _paint_target_card_rows(
    pygame: Any,
    screen: Any,
    font: Any,
    rows: tuple[tuple[tuple[str, Color], ...], ...],
    measure: Any,
    rect: pygame_ui.Rect,
    line_height: int,
) -> None:
    """Paint the card's segment rows inside its panel rect."""
    pygame_ui.draw_panel(pygame, screen, rect)
    x = rect.x + _TARGET_CARD_PAD_X
    y = rect.y + _TARGET_CARD_PAD_Y
    for row in rows:
        for text, color in row:
            pygame_ui.draw_text(
                pygame, screen, font, text, x, y, color=color,
            )
            x += measure(text)
        x = rect.x + _TARGET_CARD_PAD_X
        y += line_height


def _draw_target_card(
    pygame: Any,
    screen: Any,
    card: TargetCard,
    *,
    map_width: int,
    map_height: int,
) -> None:
    """Paint the targeted combatant's info card as a native floating panel.

    Drawn over the map region (clipped to it) near the target cell, dodging
    the player and other visible hostiles, so the full stat block has room
    the 20-char HUD column never had.
    """
    font = pygame_ui.cell_font(pygame, line_height=TILE_HEIGHT)
    rows, panel_w, panel_h, line_height = _target_card_panel(card, font)
    rect = _target_card_rect(
        card,
        panel_w=panel_w,
        panel_h=panel_h,
        map_width=map_width,
        map_height=map_height,
    )
    clip = pygame.Rect(0, 0, map_width * TILE_WIDTH, map_height * TILE_HEIGHT)
    screen.set_clip(clip)
    try:
        measure = lambda text: pygame_ui.measure_font(font, text)
        _paint_target_card_rows(
            pygame, screen, font, rows, measure, rect, line_height,
        )
    finally:
        screen.set_clip(None)


def _rgb(value: Any) -> tuple[int, int, int]:
    """Coerce a serialized color (tuple or list) to an ``(r, g, b)`` tuple."""
    return (int(value[0]), int(value[1]), int(value[2]))


def target_card_from_payload(data: dict[str, Any]) -> TargetCard | None:
    """Deserialize the optional target card, or ``None``."""
    target_data = data.get("target")
    if target_data is None:
        return None
    return TargetCard(
        rows=tuple(
            tuple((str(_seg[0]), _rgb(_seg[1])) for _seg in row)
            for row in target_data["rows"]
        ),
        x=int(target_data["x"]),
        y=int(target_data["y"]),
        avoid_cells=tuple(
            (int(_c[0]), int(_c[1])) for _c in target_data.get("avoid_cells", ())
        ),
        player_cell=(
            (int(target_data["player_cell"][0]), int(target_data["player_cell"][1]))
            if target_data.get("player_cell") is not None
            else None
        ),
    )
