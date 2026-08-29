"""Pygame presentation for the faction standings screen."""
from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any

from . import pygame_menu, pygame_ui
from .game_context import GameContext
from .pygame_runtime import PygameContext


class PygameFactionUnavailable(RuntimeError):
    """Raised when the faction standings renderer cannot return."""


@dataclass(frozen=True)
class FactionRow:
    """Renderer-neutral standing data for one faction."""

    label: str
    reputation: int
    attitude: str
    bar: str
    color: tuple[int, int, int]


@dataclass(frozen=True)
class FactionFrame:
    """One complete faction standings presentation."""

    title: str
    subtitle: str
    rows: tuple[FactionRow, ...]
    hint: str
    scale_labels: tuple[str, ...] = ("HOSTILE", "NEUTRAL", "ALLIED")


_ATTITUDE_CODES: dict[str, str] = {
    "Enemy": "E",
    "Disliked": "D",
    "Neutral": "N",
    "Liked": "L",
    "Allied": "A",
}

_ZONE_COLORS: dict[str, tuple[int, int, int]] = {
    "enemy": (255, 100, 100),
    "disliked": (255, 180, 90),
    "neutral": (205, 215, 230),
    "liked": (130, 210, 255),
    "allied": (130, 255, 160),
}


def enabled() -> bool:
    """Return whether the faction Pygame presentation is active."""
    return pygame_ui.presentation_enabled()


def _faction_rows(ctx: GameContext) -> tuple[FactionRow, ...]:
    """Build bright, renderer-neutral rows from live reputation state."""
    from .faction import _ALL_FACTIONS, get_attitude
    from .menus._ship_menu import _faction_progress_bar

    return tuple(
        FactionRow(
            label=faction_id.title(),
            reputation=(reputation := int(ctx.faction_reputation.get(faction_id, 0))),
            attitude=(attitude := get_attitude(reputation).title()),
            bar=_faction_progress_bar(reputation),
            color=_ZONE_COLORS.get(attitude.lower(), _ZONE_COLORS["neutral"]),
        )
        for faction_id in _ALL_FACTIONS
    )


def frame_for(ctx: GameContext) -> FactionFrame:
    """Build the current faction standings frame."""
    return FactionFrame(
        title="FACTION STANDINGS",
        subtitle="Your reputation across the frontier",
        rows=_faction_rows(ctx),
        hint=pygame_ui.modal_hint("ENTER / ESC back", pygame_ui.GUIDE_HINT),
    )


def _font_path(pygame: Any) -> str | None:
    """Reuse the approved readable font selection."""
    return pygame_menu._font_path(pygame)


def _fit_font(pygame: Any, frame: FactionFrame, width: int, height: int) -> Any:
    """Choose a readable font that fits every faction row and modal log."""
    height = pygame_ui.modal_footer_y(height)
    path = _font_path(pygame)
    row_text = "Merchant  +100  ---------------|###############  Allied"
    for size in range(26, 13, -1):
        font = pygame.font.Font(path, size)
        row_height = font.get_linesize() + 42
        # Reserve one hint line plus the log-panel clearance below the rows
        # so the footer never collides with the last standing row.
        hint_block = font.get_linesize() + pygame_ui.FOOTER_PAD
        if (
            row_height * max(1, len(frame.rows)) + hint_block <= height - 250
            and font.size(row_text)[0] <= width - 140
        ):
            return font
    return pygame.font.Font(path, 14)


def _draw_frame(
    pygame: Any, screen: Any, font: Any, frame: FactionFrame,
    *, context: PygameContext | None = None,
) -> None:
    """Draw faction standings in the shared framed-screen style."""
    palette = pygame_ui.DEFAULT_PALETTE
    width, height = screen.get_size()
    if context is not None:
        # Panel ends at the console-log boundary so its border never hides
        # behind the log panel or crowds the footer hint.
        panel_bottom = pygame_ui.modal_footer_y(height)
        panel = pygame_ui.Rect(32, 28, width - 64, max(1, panel_bottom - 28))
    else:
        panel = pygame_ui.Rect(32, 28, width - 64, height - 56)
    pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.title, panel, panel.y + 22,
        color=palette.title,
    )
    pygame_ui.draw_rule(
        pygame, screen, panel.x + 24, panel.y + 54,
        panel.width - 48, color=palette.border,
    )
    _draw_standing_rows(pygame, screen, font, frame, panel)
    hint_y = (
        pygame_ui.modal_footer_text_y(height, font.get_linesize() + 6)
        if context is not None
        else panel.y + panel.height - 48
    )
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.hint, panel, hint_y,
        color=palette.instruction,
    )


def _draw_faction_card(
    pygame: Any, screen: Any, font: Any, row: FactionRow,
    rect: Any,
) -> None:
    """Paint a bordered, color-coded faction card."""
    pygame.draw.rect(screen, (12, 16, 25), pygame.Rect(rect.x, rect.y, rect.width, rect.height), border_radius=6)
    pygame.draw.rect(screen, row.color, pygame.Rect(rect.x, rect.y, 5, rect.height), border_radius=3)
    pygame.draw.rect(screen, pygame_ui.DEFAULT_PALETTE.border, pygame.Rect(rect.x, rect.y, rect.width, rect.height), width=1, border_radius=6)
    x = rect.x + 18
    y = rect.y + 12
    pygame_ui.draw_text(pygame, screen, font, row.label.upper(), x, y, color=row.color)
    attitude_code = _ATTITUDE_CODES.get(row.attitude, "?")
    value = f"{row.reputation:+d}  {attitude_code}"
    pygame_ui.draw_text(
        pygame, screen, font, value,
        rect.x + rect.width - pygame_ui.measure_font(font, value) - 16,
        y, color=row.color,
    )
    bar_x = x
    bar_y = y + font.get_linesize() + 10
    bar_width = rect.width - 36
    pygame.draw.rect(screen, (35, 42, 58), pygame.Rect(bar_x, bar_y, bar_width, 12), border_radius=6)
    center_x = bar_x + bar_width // 2
    pygame.draw.line(screen, (190, 200, 220), (center_x, bar_y - 3), (center_x, bar_y + 15), width=2)
    fill_width = round((abs(row.reputation) / 100) * (bar_width // 2))
    if row.reputation < 0:
        pygame.draw.rect(screen, row.color, pygame.Rect(center_x - fill_width, bar_y, fill_width, 12), border_radius=6)
    else:
        pygame.draw.rect(screen, row.color, pygame.Rect(center_x, bar_y, fill_width, 12), border_radius=6)


def _draw_faction_row(
    pygame: Any, screen: Any, font: Any, row: FactionRow,
    x: int, y: int, content_width: int, first: bool,
) -> None:
    """Paint one separated faction card."""
    _draw_faction_card(
        pygame, screen, font, row,
        pygame_ui.Rect(x, y, content_width, font.get_linesize() + 56),
    )


def _draw_standing_rows(
    pygame: Any, screen: Any, font: Any, frame: FactionFrame, panel: pygame_ui.Rect,
) -> None:
    """Paint subtitle, standing scale, and reputation bars."""
    palette = pygame_ui.DEFAULT_PALETTE
    x = panel.x + 42
    content_width = panel.width - 84
    y = panel.y + 82
    pygame_ui.draw_text(
        pygame, screen, font, frame.subtitle, x, y,
        color=palette.description,
    )
    y += font.get_linesize() + 14
    scale = "  <------  " + "  /  ".join(frame.scale_labels) + "  ------>"
    pygame_ui.draw_centered_text(
        pygame, screen, font, scale,
        pygame_ui.Rect(x, y, content_width, font.get_linesize()), y,
        color=palette.description,
    )
    y += font.get_linesize() + 16
    row_height = font.get_linesize() + 42
    for index, row in enumerate(frame.rows):
        _draw_faction_row(
            pygame, screen, font, row, x, y, content_width, first=index == 0,
        )
        y += row_height


def _draw_shared_frame(
    pygame: Any, screen: Any, font: Any, frame: FactionFrame,
    context: PygameContext,
) -> None:
    """Draw a faction frame while preserving legacy test doubles."""
    if "context" in inspect.signature(_draw_frame).parameters:
        _draw_frame(pygame, screen, font, frame, context=context)
        pygame_ui.draw_context_log(pygame, screen, context)
        return
    _draw_frame(pygame, screen, font, frame)
    pygame_ui.draw_context_log(pygame, screen, context)


def _handle_key(pygame: Any, event: Any) -> str:
    """Map one Pygame event to the faction modal contract."""
    if event.type == pygame.QUIT:
        return "QUIT"
    if event.type != pygame.KEYDOWN:
        return "IGNORE"
    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
        return "BACK"
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE"
    return "IGNORE"


def run_shared(context: PygameContext, ctx: GameContext) -> str:
    """Run faction standings inside the existing shared Pygame window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameFactionUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    frame = frame_for(ctx)
    width, height = screen.get_size()
    font = _fit_font(pygame, frame, width, height)
    while True:
        screen.fill(pygame_ui.DEFAULT_PALETTE.background)
        _draw_shared_frame(pygame, screen, font, frame, context)
        engine.present()
        event = pygame.event.wait()
        outcome = _handle_key(pygame, event)
        if outcome == "GUIDE":
            return outcome
        if outcome != "IGNORE":
            return outcome


def run_for_context(context: PygameContext, ctx: GameContext) -> str:
    """Run faction standings in the already-open shared Pygame window."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(context):
        raise PygameFactionUnavailable("Shared Pygame runtime is not open")
    return run_shared(context, ctx)


