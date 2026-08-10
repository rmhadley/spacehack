"""Opt-in Pygame presentation for the Quest Log modal.

The game process remains the source of truth for quest-log content: it renders
an existing Quest Log frame into a small capture console, then sends the
captured cell text and colours to an isolated Pygame worker. The worker owns
only presentation and modal key translation; it never receives mutable game
objects or changes mission state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sys
from typing import Any

from . import pygame_ui, pygame_world


class PygameQuestLogUnavailable(RuntimeError):
    """Raised when the optional Quest Log worker cannot return a choice."""


@dataclass(frozen=True)
class QuestSpan:
    """One naturally rendered colour run within a Quest Log row."""

    text: str
    fg: tuple[int, int, int]


@dataclass(frozen=True)
class QuestFrame:
    """Captured Quest Log rows for one selection/confirmation state."""

    rows: tuple[tuple[QuestSpan, ...], ...]
    selected: int
    confirm_abandon: bool


def _captured_rows(capture: pygame_world.CaptureConsole) -> tuple[tuple[QuestSpan, ...], ...]:
    """Convert final captured cells into naturally rendered row spans."""
    cells: dict[tuple[int, int], pygame_world.world.WorldDrawCommand] = {
        (command.x, command.y): command for command in capture.commands
    }
    rows: list[tuple[QuestSpan, ...]] = []
    for y in range(capture.height):
        row_cells = [
            (x, cells[(x, y)])
            for x in range(capture.width)
            if (x, y) in cells
        ]
        if not row_cells:
            rows.append(())
            continue
        max_x = row_cells[-1][0]
        spans: list[QuestSpan] = []
        current_fg: tuple[int, int, int] | None = None
        current_text = ""
        for x in range(max_x + 1):
            command = cells.get((x, y))
            char = command.char if command is not None else " "
            fg = command.fg if command is not None else (232, 236, 246)
            if fg != current_fg:
                if current_text:
                    spans.append(QuestSpan(current_text, current_fg or fg))
                current_fg = fg
                current_text = char
            else:
                current_text += char
        if current_text:
            spans.append(QuestSpan(current_text, current_fg or (232, 236, 246)))
        rows.append(tuple(spans))
    return tuple(rows)


def _capture_frame(ctx: Any, selected: int, confirm_abandon: bool) -> QuestFrame:
    """Render one authoritative tcod Quest Log state into portable rows."""
    from .menus._quest_log import render_quest_log
    from .engine import SCREEN_HEIGHT, SCREEN_WIDTH

    capture = pygame_world.CaptureConsole(SCREEN_WIDTH, SCREEN_HEIGHT)
    render_quest_log(
        capture,
        ctx,
        selected=selected,
        confirm_abandon=confirm_abandon,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
    )
    return QuestFrame(
        rows=_captured_rows(capture),
        selected=selected,
        confirm_abandon=confirm_abandon,
    )


def _frames_for(ctx: Any) -> tuple[QuestFrame, ...]:
    """Capture every reachable selection/confirmation presentation state."""
    count = len(ctx.player_active_missions)
    selections = tuple(range(count)) if count else (-1,)
    return tuple(
        _capture_frame(ctx, selected, confirm_abandon)
        for confirm_abandon in (False, True)
        for selected in selections
    )


def _frame_key(selected: int, confirm_abandon: bool) -> str:
    """Build a stable payload key for one Quest Log state."""
    return f"{selected}:{int(confirm_abandon)}"


def _worker_payload(frames: tuple[QuestFrame, ...]) -> dict[str, Any]:
    """Serialize captured frames for the isolated worker."""
    return {
        "frames": {
            _frame_key(frame.selected, frame.confirm_abandon): asdict(frame)
            for frame in frames
        },
        "screen_size": (1600, 960),
        "font_size": 18,
    }


def _frame_from_payload(raw: dict[str, Any]) -> QuestFrame:
    """Deserialize one captured frame from worker input."""
    return QuestFrame(
        rows=tuple(
            tuple(
                QuestSpan(text=span["text"], fg=tuple(span["fg"]))
                for span in row
            )
            for row in raw["rows"]
        ),
        selected=int(raw["selected"]),
        confirm_abandon=bool(raw["confirm_abandon"]),
    )


def _font_path(pygame: Any) -> str | None:
    """Choose the same readable font family as the Merchant migration."""
    from .pygame_merchant import _font_path as merchant_font_path

    return merchant_font_path(pygame)


def _fit_font(pygame: Any, frames: tuple[QuestFrame, ...], width: int, height: int) -> Any:
    """Choose the largest font that fits captured rows in the canvas."""
    path = _font_path(pygame)
    max_text_width = max(
        (sum(len(span.text) for span in row) for frame in frames for row in frame.rows),
        default=1,
    )
    max_rows = max((len(frame.rows) for frame in frames), default=1)
    for size in range(24, 11, -1):
        font = pygame.font.Font(path, size)
        if (
            font.get_linesize() * max_rows <= height - 24
            and font.size("M" * max_text_width)[0] <= width - 48
        ):
            return font
    return pygame.font.Font(path, 12)


def _draw_rows(pygame: Any, screen: Any, font: Any, frame: QuestFrame) -> None:
    """Render captured rows with natural font spacing and source colours."""
    for row_index, row in enumerate(frame.rows):
        x = 24
        y = 12 + row_index * font.get_linesize()
        for span in row:
            pygame_ui.draw_text(
                pygame, screen, font, span.text, x, y,
                color=span.fg, antialias=True,
            )
            x += pygame_ui.measure_font(font, span.text)


def _handle_key(pygame: Any, event: Any, selected: int, confirm: bool, count: int) -> tuple[str, int, bool]:
    """Map worker key events to the existing Quest Log contract."""
    if event.type == pygame.QUIT:
        return "QUIT", selected, confirm
    if event.type != pygame.KEYDOWN:
        return "IGNORE", selected, confirm
    if event.key == pygame.K_ESCAPE:
        return "BACK", selected, confirm
    if event.key in (pygame.K_UP, pygame.K_k) and count:
        return "IGNORE", (selected - 1) % count, confirm
    if event.key in (pygame.K_DOWN, pygame.K_j) and count:
        return "IGNORE", (selected + 1) % count, confirm
    if event.key == pygame.K_a and not confirm and count:
        return "IGNORE", selected, True
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and confirm and count:
        return "ABANDONED", selected, confirm
    question_key = getattr(pygame, "K_QUESTION", None)
    if question_key is not None and event.key == question_key:
        return "GUIDE", selected, confirm
    return "IGNORE", selected, confirm


def _run_worker(payload: dict[str, Any]) -> int:
    """Own the Quest Log window and return one modal outcome."""
    pygame = _load_pygame()
    raw_frames = payload["frames"]
    frames = {
        key: _frame_from_payload(raw)
        for key, raw in raw_frames.items()
    }
    if not frames:
        return 2
    pygame.init()
    pygame.font.init()
    try:
        width, height = tuple(payload.get("screen_size", (1600, 960)))
        all_frames = tuple(frames.values())
        font = _fit_font(pygame, all_frames, width, height)
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("spacehack - Quest Log")
        count = len({
            frame.selected for frame in all_frames
            if frame.selected >= 0 and not frame.confirm_abandon
        })
        selected = 0 if count else -1
        confirm = False
        clock = pygame.time.Clock()
        while True:
            frame = frames[_frame_key(selected, confirm)]
            screen.fill(pygame_ui.DEFAULT_PALETTE.background)
            _draw_rows(pygame, screen, font, frame)
            pygame.display.flip()
            for event in pygame.event.get():
                outcome, selected, confirm = _handle_key(
                    pygame, event, selected, confirm, count,
                )
                if outcome != "IGNORE":
                    print(json.dumps({"outcome": outcome, "selected": selected}))
                    return 0
            clock.tick(60)
    finally:
        pygame.display.quit()
        pygame.quit()


def _load_pygame() -> Any:
    """Load Pygame lazily without importing it in the normal game process."""
    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise PygameQuestLogUnavailable("Pygame is not installed") from exc
    return pygame


def run(ctx: Any) -> tuple[str, int]:
    """Run the opt-in Quest Log worker and return its modal outcome."""
    frames = _frames_for(ctx)
    try:
        response = pygame_ui.run_json_worker(
            pygame_ui.worker_command(f"{__package__}.pygame_quest_log"),
            _worker_payload(frames),
            unavailable_message="Pygame Quest Log unavailable",
            environment=pygame_ui.worker_environment(),
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        raise PygameQuestLogUnavailable(str(exc)) from exc
    try:
        return str(response["outcome"]), int(response["selected"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PygameQuestLogUnavailable(
            "Pygame Quest Log returned no usable choice"
        ) from exc


if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
