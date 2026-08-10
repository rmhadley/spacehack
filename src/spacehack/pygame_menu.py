"""Optional Pygame worker for selectable text menus.

The parent process supplies immutable menu frames and receives only an opaque
selected action. Domain modules map that action to their existing outcomes and
perform all gameplay mutations in-process.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sys
from typing import Any

from . import pygame_ui


class PygameMenuUnavailable(RuntimeError):
    """Raised when the optional selectable-menu worker cannot return."""


def enabled() -> bool:
    """Return whether the generic interactive-menu batch is enabled."""
    import os

    return bool(os.environ.get("SPACEHACK_PYGAME_INTERACTIVE"))


@dataclass(frozen=True)
class MenuItem:
    """One selectable presentation item with a domain-owned action ID."""

    label: str
    description: str
    action: str


@dataclass(frozen=True)
class MenuFrame:
    """One selected state for a selectable text menu."""

    title: str
    body: str
    items: tuple[MenuItem, ...]
    hints: tuple[str, ...]
    selected: int


def _font_path(pygame: Any) -> str | None:
    """Reuse the readable font selection from the Merchant worker."""
    from .pygame_merchant import _font_path as merchant_font_path

    return merchant_font_path(pygame)


def _frame_payload(frame: MenuFrame) -> dict[str, Any]:
    """Serialize one menu frame for the worker process."""
    return asdict(frame)


def _frame_from_payload(raw: dict[str, Any]) -> MenuFrame:
    """Deserialize one menu frame from worker input."""
    return MenuFrame(
        title=str(raw["title"]),
        body=str(raw["body"]),
        items=tuple(MenuItem(**item) for item in raw["items"]),
        hints=tuple(str(hint) for hint in raw["hints"]),
        selected=int(raw["selected"]),
    )


def _content_width(width: int) -> int:
    """Return the worker panel's usable text width."""
    return max(1, width - 132)


def _frame_height(font: Any, frame: MenuFrame, content_width: int) -> int:
    """Measure one frame using the same wrapping rules as the renderer."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    line_height = font.get_linesize()
    body_lines = pygame_ui.wrap_text(frame.body, content_width, measure)
    height = len(body_lines) * (line_height + 3) + 10
    for index, item in enumerate(frame.items):
        height += line_height + 14
        if index == frame.selected and item.description:
            description_lines = pygame_ui.wrap_text(
                item.description, content_width - 28, measure,
            )
            height += max(1, len(description_lines)) * (line_height + 2)
    height += 8 + len(frame.hints) * (line_height + 4)
    return height


def _fit_font(pygame: Any, frames: tuple[MenuFrame, ...], width: int, height: int) -> Any:
    """Choose the largest font that fits wrapped content in every frame."""
    path = _font_path(pygame)
    content_width = _content_width(width)
    available_height = max(1, height - 132)
    for size in range(24, 11, -1):
        font = pygame.font.Font(path, size)
        if all(
            _frame_height(font, frame, content_width) <= available_height
            for frame in frames
        ) and font.size("M")[0] <= content_width:
            return font
    return pygame.font.Font(path, 12)


def _draw_frame(pygame: Any, screen: Any, font: Any, frame: MenuFrame) -> None:
    """Paint a menu frame with natural font spacing."""
    palette = pygame_ui.DEFAULT_PALETTE
    width, height = screen.get_size()
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
    x = panel.x + 34
    content_width = _content_width(width)
    y = panel.y + 76
    measure = lambda text: pygame_ui.measure_font(font, text)
    for line in pygame_ui.wrap_text(frame.body, content_width, measure):
        pygame_ui.draw_text(pygame, screen, font, line, x, y, color=palette.description)
        y += font.get_linesize() + 3
    y += 10
    for index, item in enumerate(frame.items):
        y = pygame_ui.draw_menu_row(
            pygame, screen, font, item.label, x, y, content_width,
            selected=index == frame.selected, palette=palette,
        )
        if index == frame.selected and item.description:
            y = pygame_ui.draw_wrapped_text(
                pygame, screen, font, item.description, x + 28, y - 4,
                content_width - 28, color=palette.description, line_gap=2,
            )
    y += 8
    for hint in frame.hints:
        pygame_ui.draw_text(
            pygame, screen, font, pygame_ui.fit_text(hint, content_width, measure),
            x, y, color=palette.instruction,
        )
        y += font.get_linesize() + 4


def _handle_key(pygame: Any, event: Any, selected: int, count: int) -> tuple[str, int]:
    """Map one worker event to navigation or a terminal menu outcome."""
    if event.type == pygame.QUIT:
        return "QUIT", selected
    if event.type != pygame.KEYDOWN:
        return "IGNORE", selected
    if event.key == pygame.K_ESCAPE:
        return "BACK", selected
    question_key = getattr(pygame, "K_QUESTION", None)
    if question_key is not None and event.key == question_key:
        return "GUIDE", selected
    if event.key in (pygame.K_UP, pygame.K_k) and count:
        return "IGNORE", (selected - 1) % count
    if event.key in (pygame.K_DOWN, pygame.K_j) and count:
        return "IGNORE", (selected + 1) % count
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and count:
        return "SELECT", selected
    return "IGNORE", selected


def _run_worker(payload: dict[str, Any]) -> int:
    """Own one selectable Pygame window and print its terminal result."""
    try:
        import pygame
    except ModuleNotFoundError:
        return 2
    raw_frames = payload.get("frames", [])
    frames = tuple(_frame_from_payload(raw) for raw in raw_frames)
    if not frames:
        return 2
    pygame.init()
    pygame.font.init()
    try:
        width, height = tuple(payload.get("screen_size", (1600, 960)))
        font = _fit_font(pygame, frames, width, height)
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(str(payload.get("caption", "spacehack")))
        selected = max(0, frames[0].selected)
        count = len(frames[0].items)
        clock = pygame.time.Clock()
        while True:
            frame = frames[selected % len(frames)]
            screen.fill(pygame_ui.DEFAULT_PALETTE.background)
            _draw_frame(pygame, screen, font, frame)
            pygame.display.flip()
            for event in pygame.event.get():
                outcome, selected = _handle_key(pygame, event, selected, count)
                if outcome != "IGNORE":
                    action = (
                        frame.items[selected].action
                        if outcome == "SELECT" and frame.items
                        else ""
                    )
                    print(json.dumps({
                        "outcome": outcome,
                        "action": action,
                        "selected": selected,
                    }))
                    return 0
            clock.tick(60)
    finally:
        pygame.display.quit()
        pygame.quit()


def run(
    frames: tuple[MenuFrame, ...],
    *,
    caption: str = "spacehack",
    screen_size: tuple[int, int] = (1600, 960),
) -> tuple[str, str, int]:
    """Run the selectable worker and return ``(outcome, action, index)``."""
    try:
        response = pygame_ui.run_json_worker(
            pygame_ui.worker_command(f"{__package__}.pygame_menu"),
            {
                "frames": [_frame_payload(frame) for frame in frames],
                "caption": caption,
                "screen_size": screen_size,
            },
            unavailable_message="Pygame selectable menu unavailable",
            environment=pygame_ui.worker_environment(),
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        raise PygameMenuUnavailable(str(exc)) from exc
    try:
        outcome = str(response["outcome"])
        action = str(response.get("action", ""))
        selected = int(response.get("selected", 0))
    except (KeyError, TypeError, ValueError) as exc:
        raise PygameMenuUnavailable("Pygame menu returned no usable choice") from exc
    if outcome not in {"BACK", "QUIT", "GUIDE", "SELECT"}:
        raise PygameMenuUnavailable("Pygame menu returned an unknown choice")
    return outcome, action, selected


if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
