"""Opt-in Pygame Merchant offerings screen.

This is the first live presentation-migration seam. The game process builds
renderer-neutral frames from live mission data, then a short-lived worker
process owns the Pygame window and event loop. The worker returns the same
accept/back choice as the existing tcod modal without sharing SDL ownership
with tcod. The backend is optional and falls back cleanly when unavailable.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import pygame_ui


class PygameMerchantUnavailable(RuntimeError):
    """Raised when the optional Pygame Merchant backend cannot start."""


@dataclass(frozen=True)
class MerchantFrame:
    """Renderer-neutral content and selection state for one frame."""

    title: str
    options: tuple[str, ...]
    description: str
    hints: tuple[str, ...]
    selected: int


@dataclass(frozen=True)
class MerchantLayout:
    """Responsive pixel bounds for one Merchant screen."""

    panel: pygame_ui.Rect
    content: pygame_ui.Rect
    title_y: int
    rule_y: int


def _default_screen_size() -> tuple[int, int]:
    """Match the game's native 100x60 grid at its 16px cell size."""
    from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_HEIGHT, TILE_WIDTH

    return SCREEN_WIDTH * TILE_WIDTH, SCREEN_HEIGHT * TILE_HEIGHT


def _merchant_layout(width: int, height: int, line_height: int) -> MerchantLayout:
    """Build responsive panel and content bounds for a Pygame viewport."""
    margin_x = max(28, width // 40)
    margin_y = max(24, height // 30)
    panel = pygame_ui.Rect(
        margin_x,
        margin_y,
        max(1, width - margin_x * 2),
        max(1, height - margin_y * 2),
    )
    title_y = panel.y + 24
    rule_y = title_y + line_height + 10
    content_y = rule_y + 24
    content = pygame_ui.Rect(
        panel.x + 34,
        content_y,
        max(1, panel.width - 68),
        max(1, panel.y + panel.height - content_y - 24),
    )
    return MerchantLayout(panel, content, title_y, rule_y)


def _content_height(font: Any, frame: MerchantFrame, width: int) -> int:
    """Return the rendered height needed for a frame's content."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    description_lines = pygame_ui.wrap_text(frame.description, width, measure)
    row_height = font.get_linesize() + 14
    text_step = font.get_linesize() + 4
    hint_step = font.get_linesize() + 14
    return (
        len(frame.options) * row_height
        + 8
        + max(1, len(description_lines)) * text_step
        + 8
        + len(frame.hints) * hint_step
    )


def _fit_font(
    pygame: Any,
    font_path: str | None,
    requested_size: int,
    frames: tuple[MerchantFrame, ...],
    width: int,
    height: int,
) -> Any:
    """Choose the largest requested font that fits every Merchant frame."""
    for size in range(max(16, requested_size), 15, -1):
        font = pygame.font.Font(font_path, size)
        layout = _merchant_layout(width, height, font.get_linesize())
        if all(
            _content_height(font, frame, layout.content.width) <= layout.content.height
            for frame in frames
        ):
            return font
    return pygame.font.Font(font_path, 16)


def _load_pygame() -> Any:
    """Import Pygame only inside the isolated worker process."""
    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise PygameMerchantUnavailable(
            "Pygame is not installed; using the tcod Merchant modal."
        ) from exc
    return pygame


def _font_path(pygame: Any) -> str | None:
    """Choose a readable monospace font, preferring a system font."""
    for family in ("DejaVu Sans Mono", "Liberation Mono", "Courier New"):
        path = pygame.font.match_font(family)
        if path:
            return path
    bundled = Path(__file__).parent / "data" / "Hack-Regular.ttf"
    return str(bundled) if bundled.is_file() else None


def _frame_for(
    npc: Any,
    offerings: tuple[Any, ...],
    selected: int,
    label_for,
    class_name,
) -> MerchantFrame:
    """Build renderer-neutral Merchant content from live mission specs."""
    safe_selected = selected % len(offerings) if offerings else 0
    options = tuple(label_for(mission) for mission in offerings)
    hints = (
        "ARROW KEYS / j,k navigate - ENTER accept - ESC walk away.",
    )
    if offerings:
        picked = offerings[safe_selected]
        hints += (f"Reward: {picked.reward_credits}$ + {picked.reward_xp}xp",)
        if picked.recommended_class_id:
            hints += (f"Best suited for: {class_name(picked.recommended_class_id)}",)
        if picked.recommended_ship_min_cargo > 0:
            hints += (f"Ship cargo recommended: {picked.recommended_ship_min_cargo}+",)
    return MerchantFrame(
        title=f"{npc.name} - available work",
        options=options,
        description=offerings[safe_selected].description if offerings else "",
        hints=hints,
        selected=safe_selected,
    )


def _all_frames(
    npc: Any,
    offerings: tuple[Any, ...],
    label_for,
    class_name,
) -> tuple[MerchantFrame, ...]:
    """Build the selected-state frames sent to the isolated worker."""
    count = max(1, len(offerings))
    return tuple(
        _frame_for(npc, offerings, selected, label_for, class_name)
        for selected in range(count)
    )


def _handle_key(pygame: Any, event: Any, selected: int, count: int) -> tuple[str, int]:
    """Map one Pygame event to the existing Merchant modal outcomes."""
    if event.type == pygame.QUIT:
        return "BACK", selected
    if event.type != pygame.KEYDOWN:
        return "IGNORE", selected
    if event.key == pygame.K_ESCAPE:
        return "BACK", selected
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return "ACCEPT", selected
    if count and event.key in (pygame.K_UP, pygame.K_k):
        return "IGNORE", (selected - 1) % count
    if count and event.key in (pygame.K_DOWN, pygame.K_j):
        return "IGNORE", (selected + 1) % count
    return "IGNORE", selected


def _draw_frame(
    pygame: Any,
    screen: Any,
    font: Any,
    frame: MerchantFrame,
    *,
    palette: pygame_ui.Palette,
    antialias: bool,
) -> None:
    """Paint one complete Merchant frame with shared Pygame primitives."""
    width, height = screen.get_size()
    layout = _merchant_layout(width, height, font.get_linesize())
    pygame_ui.draw_panel(pygame, screen, layout.panel, palette=palette)
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.title, layout.panel, layout.title_y,
        color=palette.title, antialias=antialias,
    )
    pygame_ui.draw_rule(
        pygame, screen, layout.panel.x + 24, layout.rule_y,
        layout.panel.width - 48, color=palette.border,
    )
    x = layout.content.x
    content_width = layout.content.width
    y = layout.content.y
    row_step = font.get_linesize() + 14
    screen.set_clip(
        pygame.Rect(
            layout.content.x,
            layout.content.y,
            layout.content.width,
            layout.content.height,
        )
    )
    try:
        for index, label in enumerate(frame.options):
            y = pygame_ui.draw_menu_row(
                pygame, screen, font, label, x, y, content_width,
                selected=index == frame.selected,
                palette=palette, antialias=antialias,
            )
        y += 8
        y = pygame_ui.draw_wrapped_text(
            pygame, screen, font, frame.description, x, y, content_width,
            color=palette.description, line_gap=4, antialias=antialias,
        )
        y += 8
        measure = lambda text: pygame_ui.measure_font(font, text)
        for hint in frame.hints:
            fitted_hint = pygame_ui.fit_text(hint, content_width, measure)
            pygame_ui.draw_text(
                pygame, screen, font, fitted_hint, x, y,
                color=palette.instruction, antialias=antialias,
            )
            y += row_step
    finally:
        screen.set_clip(None)


def _worker_payload(
    frames: tuple[MerchantFrame, ...],
    screen_size: tuple[int, int],
    font_size: int,
    antialias: bool,
) -> dict[str, Any]:
    """Serialize frames and display settings for the worker process."""
    return {
        "frames": [asdict(frame) for frame in frames],
        "screen_size": screen_size,
        "font_size": font_size,
        "antialias": antialias,
    }


def _run_worker(payload: dict[str, Any]) -> int:
    """Own the Pygame window and return a process exit status."""
    pygame = _load_pygame()
    frames = tuple(
        MerchantFrame(
            title=frame["title"],
            options=tuple(frame["options"]),
            description=frame["description"],
            hints=tuple(frame["hints"]),
            selected=frame["selected"],
        )
        for frame in payload["frames"]
    )
    if not frames:
        return 2
    pygame.init()
    pygame.font.init()
    try:
        screen_size = tuple(payload.get("screen_size", (1600, 960)))
        requested_size = int(payload.get("font_size", 24))
        antialias = bool(payload.get("antialias", True))
        screen = pygame.display.set_mode(screen_size)
        pygame.display.set_caption("spacehack - Merchant Guild")
        font_path = _font_path(pygame)
        font = _fit_font(
            pygame,
            font_path,
            requested_size,
            frames,
            screen_size[0],
            screen_size[1],
        )
        palette = pygame_ui.DEFAULT_PALETTE
        selected = 0
        clock = pygame.time.Clock()
        while True:
            frame = frames[selected % len(frames)]
            screen.fill(palette.background)
            _draw_frame(
                pygame, screen, font, frame,
                palette=palette, antialias=antialias,
            )
            pygame.display.flip()
            for event in pygame.event.get():
                outcome, selected = _handle_key(
                    pygame, event, selected, len(frames),
                )
                if outcome != "IGNORE":
                    print(json.dumps({"outcome": outcome, "selected": selected}))
                    return 0
            clock.tick(60)
    finally:
        pygame.display.quit()
        pygame.quit()


def _worker_main() -> int:
    """Read one JSON payload, run the isolated renderer, and exit."""
    try:
        payload = json.load(sys.stdin)
        return _run_worker(payload)
    except Exception:
        return 2


def run(
    npc: Any,
    offerings: tuple[Any, ...],
    *,
    screen_size: tuple[int, int] | None = None,
    font_size: int = 24,
    antialias: bool = True,
) -> tuple[str, int]:
    """Run the isolated Pygame Merchant worker and return its choice.

    The default size matches the existing tcod canvas. The worker may reduce
    the requested font to keep every row, description, and hint inside its
    content region.
    """
    if screen_size is None:
        screen_size = _default_screen_size()
    from .data.classes import find_class
    from .menus._missions import _mission_board_label

    frames = _all_frames(
        npc,
        offerings,
        _mission_board_label,
        lambda class_id: find_class(class_id).name,
    )
    try:
        response = pygame_ui.run_json_worker(
            pygame_ui.worker_command(f"{__package__}.pygame_merchant"),
            _worker_payload(frames, screen_size, font_size, antialias),
            unavailable_message="Pygame worker unavailable; using the tcod Merchant modal.",
            environment=pygame_ui.worker_environment(),
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        raise PygameMerchantUnavailable(str(exc)) from exc
    try:
        return str(response["outcome"]), int(response["selected"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PygameMerchantUnavailable(
            "Pygame worker returned no usable choice; using tcod."
        ) from exc


if __name__ == "__main__":
    raise SystemExit(_worker_main() if "--worker" in sys.argv else 2)
