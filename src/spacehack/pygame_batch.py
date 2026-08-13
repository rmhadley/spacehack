"""Shared Pygame presentation for read-only modal screens.

Screen modules render their existing captured rows into immutable spans and send
only immutable presentation data here. This worker owns the isolated Pygame
window and translates read-only modal keys back to the parent.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sys
from typing import Any

from . import pygame_quest_log, pygame_ui
from .pygame_runtime import PygameContext

class PygameBatchUnavailable(RuntimeError):
    """Raised when a batched Pygame modal cannot return a result."""

def enabled() -> bool:
    """Return whether read-only screens can render in this runtime."""
    return pygame_ui.presentation_enabled()

@dataclass(frozen=True)
class BatchFrame:
    """A captured full-screen frame identified by its interaction state."""

    rows: tuple[tuple[pygame_quest_log.QuestSpan, ...], ...]
    key: str

def capture_rows(capture: Any) -> tuple[tuple[pygame_quest_log.QuestSpan, ...], ...]:
    """Convert a capture console into naturally rendered text spans."""
    return pygame_quest_log._captured_rows(capture)

def _capture_console(width: int | None = None, height: int | None = None) -> Any:
    """Create a capture console matching the game's native canvas."""
    from .engine import SCREEN_HEIGHT, SCREEN_WIDTH
    from .pygame_world import CaptureConsole

    return CaptureConsole(width or SCREEN_WIDTH, height or SCREEN_HEIGHT)

def capture_frame(render: Any) -> BatchFrame:
    """Capture one authoritative read-only render callback."""
    capture = _capture_console()
    render(capture)
    return BatchFrame(rows=capture_rows(capture), key="readonly")

def frame_payload(frame: BatchFrame) -> dict[str, Any]:
    """Serialize one captured read-only frame for the worker."""
    return {
        "frame": asdict(frame),
        "screen_size": (1600, 960),
    }

def _frame_from_payload(raw: dict[str, Any]) -> BatchFrame:
    """Deserialize one captured read-only frame."""
    return BatchFrame(
        key=str(raw.get("key", "readonly")),
        rows=tuple(
            tuple(
                pygame_quest_log.QuestSpan(
                    text=span["text"], fg=tuple(span["fg"]),
                )
                for span in row
            )
            for row in raw["rows"]
        ),
    )

def _font_path(pygame: Any) -> str | None:
    """Reuse the approved readable font selection."""
    return pygame_quest_log._font_path(pygame)

def _fit_font(pygame: Any, frame: BatchFrame, width: int, height: int) -> Any:
    """Choose a font that fits the captured frame and modal log."""
    height = pygame_ui.modal_footer_y(height)
    path = _font_path(pygame)
    max_width = max(
        (sum(len(span.text) for span in row) for row in frame.rows),
        default=1,
    )
    max_rows = max(1, len(frame.rows))
    for size in range(24, 11, -1):
        font = pygame.font.Font(path, size)
        if (
            font.get_linesize() * max_rows <= height - 24
            and font.size("M" * max_width)[0] <= width - 48
        ):
            return font
    return pygame.font.Font(path, 12)

def _draw_frame(
    pygame: Any, screen: Any, font: Any, frame: BatchFrame,
    *, context: PygameContext | None = None,
) -> None:
    """Render captured rows with natural font spacing."""
    for row_index, row in enumerate(frame.rows):
        x = 24
        y = 12 + row_index * font.get_linesize()
        for span in row:
            pygame_ui.draw_text(
                pygame, screen, font, span.text, x, y, color=span.fg,
            )
            x += pygame_ui.measure_font(font, span.text)

def _handle_key(pygame: Any, event: Any) -> str:
    """Translate read-only modal keys into parent outcomes."""
    if event.type == pygame.QUIT:
        return "QUIT"
    if event.type != pygame.KEYDOWN:
        return "IGNORE"
    if event.key == pygame.K_ESCAPE:
        return "BACK"
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE"
    return "IGNORE"

def _load_pygame() -> Any:
    """Load Pygame lazily in the worker process."""
    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise PygameBatchUnavailable("Pygame is not installed") from exc
    return pygame

def _run_worker(payload: dict[str, Any]) -> int:
    """Own one read-only modal window and return a JSON outcome."""
    pygame = _load_pygame()
    frame = _frame_from_payload(payload["frame"])
    pygame.init()
    pygame.font.init()
    try:
        width, height = tuple(payload.get("screen_size", (1600, 960)))
        font = _fit_font(pygame, frame, width, height)
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("spacehack - spacehack")
        clock = pygame.time.Clock()
        while True:
            screen.fill(pygame_ui.DEFAULT_PALETTE.background)
            _draw_frame(pygame, screen, font, frame)
            pygame.display.flip()
            for event in pygame.event.get():
                outcome = _handle_key(pygame, event)
                if outcome != "IGNORE":
                    print(json.dumps({"outcome": outcome}))
                    return 0
            clock.tick(60)
    finally:
        pygame.display.quit()
        pygame.quit()

def run_shared(context: PygameContext, render: Any) -> str:
    """Render a read-only capture in the existing shared Pygame window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameBatchUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    frame = capture_frame(render)
    width, height = screen.get_size()
    font = _fit_font(pygame, frame, width, height)
    while True:
        screen.fill(pygame_ui.DEFAULT_PALETTE.background)
        _draw_frame(pygame, screen, font, frame, context=context)
        pygame_ui.draw_context_log(pygame, screen, context)
        engine.present()
        event = pygame.event.wait()
        outcome = _handle_key(pygame, event)
        if outcome != "IGNORE":
            return outcome

def run_for_context(context: PygameContext, render: Any) -> str:
    """Run the read-only screen in the shared Pygame window."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(context):
        raise PygameBatchUnavailable("Shared Pygame runtime is not open")
    return run_shared(context, render)

if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
