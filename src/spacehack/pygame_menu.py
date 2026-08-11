"""Pygame selectable-menu presentation and isolated worker protocol.

The parent process supplies immutable menu frames and receives only an opaque
selected action. Domain modules map that action to their existing outcomes and
perform all gameplay mutations in-process.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import inspect
import json
import sys
from typing import Any

from . import pygame_ui


class PygameMenuUnavailable(RuntimeError):
    """Raised when selectable-menu presentation cannot return."""


def enabled() -> bool:
    """Return whether generic menus can render in this runtime."""
    return pygame_ui.presentation_enabled()


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
    art: tuple[str, ...] = ()
    art_color: tuple[int, int, int] | None = None
    art_colors: tuple[tuple[int, int, int], ...] = ()
    initial_selected: int | None = None


def _font_path(pygame: Any) -> str | None:
    """Reuse the readable font selection from the Merchant screen."""
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
        art=tuple(str(line) for line in raw.get("art", ())),
        art_color=(
            tuple(int(channel) for channel in raw["art_color"])
            if raw.get("art_color") is not None
            else None
        ),
        art_colors=tuple(
            tuple(int(channel) for channel in color)
            for color in raw.get("art_colors", ())
        ),
        initial_selected=(
            int(raw["initial_selected"])
            if raw.get("initial_selected") is not None
            else None
        ),
    )


def _initial_selected(frames: tuple[MenuFrame, ...]) -> int:
    """Return a valid initial cursor index for a menu frame set."""
    if not frames:
        return 0
    count = len(frames[0].items)
    if count == 0:
        return 0
    initial = frames[0].initial_selected
    requested = initial if initial is not None else frames[0].selected
    return max(0, min(count - 1, requested))


def _content_width(width: int) -> int:
    """Return the worker panel's usable text width."""
    return max(1, width - 132)


def _frame_height(font: Any, frame: MenuFrame, content_width: int) -> int:
    """Measure one frame with a fixed description region."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    line_height = font.get_linesize()
    body_lines = pygame_ui.wrap_text(frame.body, content_width, measure)
    description_lines = pygame_ui.max_wrapped_lines(
        (item.description for item in frame.items),
        content_width - 28,
        measure,
    )
    height = len(body_lines) * (line_height + 3) + 10
    if frame.art:
        height += len(frame.art) * line_height + 10
    height += len(frame.items) * (line_height + 14)
    height += max(1, description_lines) * (line_height + 2)
    height += 8 + len(frame.hints) * (line_height + 4)
    return height


def _fit_font(
    pygame: Any,
    frames: tuple[MenuFrame, ...],
    width: int,
    height: int,
    *,
    reserve_log: bool = False,
) -> Any:
    """Choose the largest font that fits wrapped content in every frame."""
    path = _font_path(pygame)
    content_width = _content_width(width)
    available_height = max(1, height - 132)
    if reserve_log:
        available_height -= pygame_ui.LOG_PANEL_HEIGHT + pygame_ui.FOOTER_PAD
    for size in range(24, 11, -1):
        font = pygame.font.Font(path, size)
        if all(
            _frame_height(font, frame, content_width) <= available_height
            for frame in frames
        ) and max(
            (font.size(line)[0] for frame in frames for line in frame.art),
            default=0,
        ) <= content_width:
            return font
    return pygame.font.Font(path, 12)


def _fit_shared_font(
    pygame: Any,
    frames: tuple[MenuFrame, ...],
    width: int,
    height: int,
) -> Any:
    """Fit a shared menu while supporting legacy four-argument patches."""
    if "reserve_log" in inspect.signature(_fit_font).parameters:
        return _fit_font(pygame, frames, width, height, reserve_log=True)
    return _fit_font(pygame, frames, width, height)


def _draw_art(
    pygame: Any,
    screen: Any,
    font: Any,
    panel: pygame_ui.Rect,
    frame: MenuFrame,
    y: int,
    content_width: int,
    measure: Any,
) -> int:
    """Paint optional centered ASCII art and return the next content y."""
    if not frame.art:
        return y
    default_color = frame.art_color or pygame_ui.DEFAULT_PALETTE.description
    for index, line in enumerate(frame.art):
        line_color = (
            frame.art_colors[index]
            if index < len(frame.art_colors)
            else default_color
        )
        pygame_ui.draw_centered_text(
            pygame,
            screen,
            font,
            pygame_ui.fit_text(line, content_width, measure),
            panel,
            y,
            color=line_color,
        )
        y += font.get_linesize()
    return y + 10


def _draw_frame(
    pygame: Any,
    screen: Any,
    font: Any,
    frame: MenuFrame,
    *,
    context: Any | None = None,
) -> None:
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
    content_bottom = (
        pygame_ui.modal_footer_y(height)
        if context is not None
        else panel.y + panel.height - 20
    )
    y = panel.y + 76
    measure = lambda text: pygame_ui.measure_font(font, text)
    y = _draw_art(
        pygame, screen, font, panel, frame, y, content_width, measure,
    )
    for line in pygame_ui.wrap_text(frame.body, content_width, measure):
        pygame_ui.draw_text(pygame, screen, font, line, x, y, color=palette.description)
        y += font.get_linesize() + 3
    y += 10
    for index, item in enumerate(frame.items):
        row_height = font.get_linesize() + 14
        if y + row_height > content_bottom:
            break
        pygame_ui.draw_menu_row(
            pygame, screen, font, item.label, x, y, content_width,
            selected=index == frame.selected, palette=palette,
        )
        y += row_height
    y += 8
    description_width = content_width - 28
    if y < content_bottom:
        pygame_ui.draw_wrapped_text(
            pygame, screen, font,
            frame.items[frame.selected].description if frame.items else "",
            x + 28, y, description_width,
            color=palette.description, line_gap=2,
        )
    description_lines = pygame_ui.max_wrapped_lines(
        (item.description for item in frame.items),
        description_width,
        measure,
    )
    y += max(1, description_lines) * (font.get_linesize() + 2)
    y += 8
    for hint in frame.hints:
        if y + font.get_linesize() > content_bottom:
            break
        pygame_ui.draw_text(
            pygame, screen, font, pygame_ui.fit_text(hint, content_width, measure),
            x, y, color=palette.instruction,
        )
        y += font.get_linesize() + 4
    if context is not None:
        pygame_ui.draw_context_log(pygame, screen, context, palette=palette)


def _draw_shared_frame(
    pygame: Any, screen: Any, font: Any, frame: MenuFrame, context: Any,
) -> None:
    """Draw a shared frame while preserving legacy renderer test doubles."""
    if "context" in inspect.signature(_draw_frame).parameters:
        _draw_frame(pygame, screen, font, frame, context=context)
        return
    _draw_frame(pygame, screen, font, frame)
    pygame_ui.draw_context_log(pygame, screen, context)


def _handle_key(pygame: Any, event: Any, selected: int, count: int) -> tuple[str, int]:
    """Map one worker event to navigation or a terminal menu outcome."""
    if event.type == pygame.QUIT:
        return "QUIT", selected
    if event.type != pygame.KEYDOWN:
        return "IGNORE", selected
    if event.key == pygame.K_ESCAPE:
        return "BACK", selected
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE", selected
    if event.key in (pygame.K_UP, pygame.K_k) and count:
        return "IGNORE", (selected - 1) % count
    if event.key in (pygame.K_DOWN, pygame.K_j) and count:
        return "IGNORE", (selected + 1) % count
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return ("SELECT", selected) if count else ("DISMISS", selected)
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
        font = _fit_shared_font(pygame, frames, width, height)
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(str(payload.get("caption", "spacehack")))
        selected = _initial_selected(frames)
        count = len(frames[0].items)
        clock = pygame.time.Clock()
        while True:
            frame = frames[selected % len(frames)]
            screen.fill(pygame_ui.DEFAULT_PALETTE.background)
            _draw_frame(pygame, screen, font, frame)
            pygame.display.flip()
            for event in pygame.event.get():
                outcome, selected = _handle_key(
                    pygame, event, selected, count,
                )
                if outcome == "IGNORE":
                    continue
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


def run_shared(
    context: Any,
    frames: tuple[MenuFrame, ...],
    *,
    caption: str = "spacehack",
) -> tuple[str, str, int]:
    """Run a menu inside the already-open shared Pygame window.

    ``context`` is the :class:`pygame_runtime.PygameContext` owned by the
    main game runtime. This path deliberately reuses its logical surface and
    event pump instead of starting an additional window.
    """
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameMenuUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    frames = tuple(frames)
    if not frames:
        raise PygameMenuUnavailable("Shared Pygame menu has no frames")
    width, height = screen.get_size()
    font = _fit_shared_font(pygame, frames, width, height)
    selected = _initial_selected(frames)
    count = len(frames[0].items)
    while True:
        frame = frames[selected % len(frames)]
        screen.fill(pygame_ui.DEFAULT_PALETTE.background)
        _draw_shared_frame(pygame, screen, font, frame, context)
        engine.present()
        event = pygame.event.wait()
        outcome, selected = _handle_key(pygame, event, selected, count)
        if outcome == "IGNORE":
            continue
        action = (
            frame.items[selected].action
            if outcome == "SELECT" and frame.items
            else ""
        )
        return outcome, action, selected


def run_for_context(
    context: Any,
    frames: tuple[MenuFrame, ...],
    *,
    caption: str = "spacehack",
) -> tuple[str, str, int]:
    """Run the menu in the already-open shared Pygame window."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(context):
        raise PygameMenuUnavailable("Shared Pygame runtime is not open")
    return run_shared(context, frames, caption=caption)


def run(frames: tuple[MenuFrame, ...],

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
    if outcome not in {"BACK", "QUIT", "GUIDE", "SELECT", "DISMISS"}:
        raise PygameMenuUnavailable("Pygame menu returned an unknown choice")
    return outcome, action, selected


if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
