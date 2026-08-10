"""Reusable Pygame worker for text-heavy interactive screens.

The parent supplies immutable rows and opaque actions. The worker owns only
presentation and input; all game state remains in the parent process.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sys
from typing import Any

from . import pygame_menu, pygame_ui


class PygameScreenUnavailable(RuntimeError):
    """Raised when the optional text-screen worker cannot return."""


def enabled() -> bool:
    """Return whether generic text screens can render in this runtime."""
    from . import pygame_runtime

    return pygame_ui.migration_enabled("SPACEHACK_PYGAME_SCREEN") or pygame_runtime.shared_enabled()


@dataclass(frozen=True)
class ScreenRow:
    """One selectable or informational row."""

    text: str
    detail: str = ""
    action: str = ""
    selectable: bool = True


@dataclass(frozen=True)
class ScreenFrame:
    """Presentation-only screen state."""

    title: str
    body: tuple[str, ...]
    rows: tuple[ScreenRow, ...]
    footer: tuple[str, ...] = ()
    selected: int = 0
    page_offset: int = 0


def _frame_payload(frame: ScreenFrame) -> dict[str, Any]:
    """Serialize one screen frame."""
    return asdict(frame)


def _frame_from_payload(raw: dict[str, Any]) -> ScreenFrame:
    """Deserialize one screen frame."""
    return ScreenFrame(
        title=str(raw["title"]),
        body=tuple(str(line) for line in raw.get("body", ())),
        rows=tuple(ScreenRow(**row) for row in raw.get("rows", ())),
        footer=tuple(str(line) for line in raw.get("footer", ())),
        selected=int(raw.get("selected", 0)),
        page_offset=int(raw.get("page_offset", 0)),
    )


def _selectable(frame: ScreenFrame) -> tuple[int, ...]:
    """Return selectable row indices."""
    return tuple(i for i, row in enumerate(frame.rows) if row.selectable)


def _clamp(frame: ScreenFrame) -> int:
    """Clamp selection to a selectable row."""
    indices = _selectable(frame)
    if not indices:
        return 0
    if frame.selected in indices:
        return frame.selected
    return min(indices, key=lambda i: abs(i - frame.selected))


def _handle_key(pygame: Any, event: Any, frame: ScreenFrame) -> tuple[str, int]:
    """Map one event to outcome and selection."""
    selected = _clamp(frame)
    indices = _selectable(frame)
    if event.type == pygame.QUIT:
        return "QUIT", selected
    if event.type != pygame.KEYDOWN:
        return "IGNORE", selected
    if event.key == pygame.K_ESCAPE:
        return "BACK", selected
    if event.key == getattr(pygame, "K_TAB", None):
        return "TAB", selected
    if event.key == getattr(pygame, "K_PAGEDOWN", None):
        return "PAGE_DOWN", selected
    if event.key == getattr(pygame, "K_PAGEUP", None):
        return "PAGE_UP", selected
    question = getattr(pygame, "K_QUESTION", None)
    if question is not None and event.key == question:
        return "GUIDE", selected
    if event.key in (pygame.K_UP, pygame.K_k) and indices:
        pos = indices.index(selected)
        return "IGNORE", indices[(pos - 1) % len(indices)]
    if event.key in (pygame.K_DOWN, pygame.K_j) and indices:
        pos = indices.index(selected)
        return "IGNORE", indices[(pos + 1) % len(indices)]
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return ("SELECT", selected) if indices else ("BACK", selected)
    return "IGNORE", selected


def _body_lines(font: Any, frame: ScreenFrame, width: int) -> tuple[str, ...]:
    """Wrap body paragraphs using the candidate font metrics."""
    measure = lambda text: pygame_ui.measure_font(font, text)
    lines: list[str] = []
    for text in frame.body:
        lines.extend(pygame_ui.wrap_text(text, width, measure) or ("",))
    return tuple(lines)


def _non_body_height(font: Any, frame: ScreenFrame, width: int) -> int:
    """Measure rows, fixed detail region, spacing, and footer."""
    measure = lambda value: pygame_ui.measure_font(font, value)
    detail_width = width
    detail_lines = pygame_ui.max_wrapped_lines(
        (row.detail for row in frame.rows if row.selectable),
        detail_width,
        measure,
    )
    row_height = sum(
        font.get_linesize() + 14 if row.selectable else font.get_linesize() + 4
        for row in frame.rows
    )
    detail_height = max(1, detail_lines) * (font.get_linesize() + 2)
    footer_height = (max(1, len(frame.footer)) + 1) * (font.get_linesize() + 3)
    return row_height + detail_height + 12 + footer_height


def _body_budget(
    font: Any,
    frame: ScreenFrame,
    width: int,
    height: int,
    start_y: int,
) -> int:
    """Return body lines available while reserving rows and footer."""
    footer_start = height - 70
    reserved = _non_body_height(font, frame, width - 28)
    available = footer_start - start_y - 8 - reserved
    return max(0, available // (font.get_linesize() + 3))


def _layout_height(font: Any, frame: ScreenFrame, width: int) -> int:
    """Measure the worst selectable state using renderer widths."""
    body_lines = _body_lines(font, frame, width)
    return len(body_lines) * (font.get_linesize() + 3) + 8 + _non_body_height(
        font, frame, width - 28,
    )


def _fit_font(pygame: Any, frame: ScreenFrame, width: int, height: int) -> Any:
    """Choose the largest readable font that fits wrapped content."""
    path = pygame_menu._font_path(pygame)
    content_width = max(1, width - 80)
    available_height = max(1, height - 70 - 84)
    for size in range(24, 11, -1):
        font = pygame.font.Font(path, size)
        if _layout_height(font, frame, content_width) <= available_height:
            return font
    return pygame.font.Font(path, 12)


def _draw_frame(pygame: Any, screen: Any, font: Any, frame: ScreenFrame) -> None:
    """Paint the current text screen."""
    palette = pygame_ui.DEFAULT_PALETTE
    width, height = screen.get_size()
    screen.fill(palette.background)
    x = 40
    y = 84
    measure = lambda text: pygame_ui.measure_font(font, text)
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.title,
        pygame_ui.Rect(24, 16, width - 48, 42), 24,
        color=palette.title,
    )
    pygame_ui.draw_rule(pygame, screen, 48, 62, width - 96, color=palette.border)
    body_lines = _body_lines(font, frame, width - 80)
    visible_body = body_lines[frame.page_offset:]
    body_step = font.get_linesize() + 3
    body_budget = _body_budget(font, frame, width - 80, height, y)
    for line in visible_body[:body_budget]:
        pygame_ui.draw_text(
            pygame, screen, font, line, x, y, color=palette.description,
        )
        y += body_step
    if body_lines and frame.page_offset > 0:
        pygame_ui.draw_text(
            pygame, screen, font, f"[page offset {frame.page_offset}]",
            x, 64, color=palette.instruction,
        )
    y += 8
    body_overflow = len(visible_body) > body_budget
    selected = _clamp(frame)
    footer_start = height - 70
    for index, row in enumerate(frame.rows):
        row_height = font.get_linesize() + 14 if row.selectable else font.get_linesize() + 4
        if y + row_height > footer_start:
            break
        if row.selectable:
            y = pygame_ui.draw_menu_row(
                pygame, screen, font, row.text, x, y, width - 80,
                selected=index == selected, palette=palette,
            )
        else:
            pygame_ui.draw_text(
                pygame, screen, font,
                pygame_ui.fit_text(row.text, width - 80, measure),
                x, y, color=palette.description,
            )
            y += font.get_linesize() + 4
    detail_width = width - 108
    detail = frame.rows[selected].detail if 0 <= selected < len(frame.rows) else ""
    detail_height = pygame_ui.wrapped_text_height(
        detail, detail_width, measure, font.get_linesize(), 2,
    )
    measure_detail_height = max(
        (
            pygame_ui.wrapped_text_height(
                row.detail, detail_width, measure, font.get_linesize(), 2,
            )
            for row in frame.rows
            if row.selectable
        ),
        default=font.get_linesize() + 2,
    )
    if y + detail_height <= footer_start:
        pygame_ui.draw_wrapped_text(
            pygame, screen, font, detail, x + 28, y,
            detail_width, color=palette.description, line_gap=2,
        )
    y = max(y + measure_detail_height + 8, footer_start)
    footer_lines = frame.footer
    if body_overflow:
        footer_lines = ("PAGE UP/DOWN scroll for more",) + footer_lines
    for line in footer_lines:
        pygame_ui.draw_text(
            pygame, screen, font, pygame_ui.fit_text(line, width - 80, measure),
            x, y, color=palette.instruction,
        )
        y += font.get_linesize() + 3


def _run_worker(payload: dict[str, Any]) -> int:
    """Own one Pygame text screen and print one outcome."""
    try:
        import pygame
    except ModuleNotFoundError:
        return 2
    frame = _frame_from_payload(payload)
    pygame.init()
    pygame.font.init()
    try:
        width, height = tuple(payload.get("screen_size", (1600, 960)))
        font = _fit_font(pygame, frame, width, height)
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(str(payload.get("caption", "spacehack")))
        clock = pygame.time.Clock()
        while True:
            current = ScreenFrame(
                frame.title, frame.body, frame.rows, frame.footer,
                _clamp(frame), frame.page_offset,
            )
            _draw_frame(pygame, screen, font, current)
            pygame.display.flip()
            for event in pygame.event.get():
                outcome, selected = _handle_key(pygame, event, current)
                if outcome in {"IGNORE", "PAGE_DOWN", "PAGE_UP"}:
                    body_lines = _body_lines(font, current, width - 80)
                    offset = frame.page_offset
                    if outcome == "PAGE_DOWN":
                        offset = min(max(0, len(body_lines) - 1), offset + 8)
                    elif outcome == "PAGE_UP":
                        offset = max(0, offset - 8)
                    frame = ScreenFrame(
                        frame.title, frame.body, frame.rows, frame.footer,
                        selected, offset,
                    )
                    continue
                row = current.rows[selected] if outcome == "SELECT" else None
                print(json.dumps({
                    "outcome": outcome,
                    "action": row.action if row else "",
                    "selected": selected,
                }))
                return 0
            clock.tick(60)
    finally:
        pygame.display.quit()
        pygame.quit()


def run_shared(
    context: Any,
    frame: ScreenFrame,
    *,
    caption: str = "spacehack",
) -> tuple[str, str, int]:
    """Run a text screen inside the already-open shared Pygame window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameScreenUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    width, height = screen.get_size()
    font = _fit_font(pygame, frame, width, height)
    while True:
        current = ScreenFrame(
            frame.title, frame.body, frame.rows, frame.footer,
            _clamp(frame), frame.page_offset,
        )
        _draw_frame(pygame, screen, font, current)
        engine.present()
        event = pygame.event.wait()
        outcome, selected = _handle_key(pygame, event, current)
        if outcome in {"IGNORE", "PAGE_DOWN", "PAGE_UP"}:
            body_lines = _body_lines(font, current, width - 80)
            offset = frame.page_offset
            if outcome == "PAGE_DOWN":
                offset = min(max(0, len(body_lines) - 1), offset + 8)
            elif outcome == "PAGE_UP":
                offset = max(0, offset - 8)
            frame = ScreenFrame(
                frame.title, frame.body, frame.rows, frame.footer,
                selected, offset,
            )
            continue
        row = current.rows[selected] if outcome == "SELECT" else None
        return outcome, row.action if row else "", selected


def run_for_context(
    context: Any,
    frame: ScreenFrame,
    *,
    caption: str = "spacehack",
) -> tuple[str, str, int]:
    """Use the shared window when active, otherwise the worker window."""
    from . import pygame_runtime

    if pygame_runtime.shared_enabled():
        return run_shared(context, frame, caption=caption)
    return run(frame, caption=caption)


def run(frame: ScreenFrame, *, caption: str = "spacehack") -> tuple[str, str, int]:
    """Run the worker and return ``(outcome, action, selected)``."""
    try:
        response = pygame_ui.run_json_worker(
            pygame_ui.worker_command(f"{__package__}.pygame_screen"),
            {
                **_frame_payload(frame),
                "caption": caption,
                "screen_size": (1600, 960),
            },
            unavailable_message="Pygame text screen unavailable",
            environment=pygame_ui.worker_environment(),
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        raise PygameScreenUnavailable(str(exc)) from exc
    try:
        outcome = str(response["outcome"])
        action = str(response.get("action", ""))
        selected = int(response.get("selected", frame.selected))
    except (KeyError, TypeError, ValueError) as exc:
        raise PygameScreenUnavailable("Pygame text screen returned no usable choice") from exc
    if outcome not in {
        "BACK", "QUIT", "GUIDE", "SELECT", "TAB", "PAGE_DOWN", "PAGE_UP",
    }:
        raise PygameScreenUnavailable("Pygame text screen returned an unknown choice")
    return outcome, action, selected


if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
