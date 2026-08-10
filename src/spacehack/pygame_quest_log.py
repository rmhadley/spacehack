"""Pygame presentation for the Quest Log modal.

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
    hint: str = ""


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


# The legacy terminal renderer anchors its own header via ui.screen_header
# (title row 2, divider row 3, blank gap row 4), so its real content begins
# at row 5. The Pygame presentation draws its own header, so the captured
# header block is dropped to avoid a double header.
_LEGACY_HEADER_BLOCK = 5

# Legacy footer-hint lines painted by the terminal renderer
# (menus/_quest_log.py). They are pulled out of the captured content so the
# Pygame footer can draw them in the modern position instead of as a body
# row. Prefixes are matched (not exact) so a hint that wraps or carries
# extra spacing still extracts; keep these in sync if the terminal hint
# strings are ever reworded in menus/_quest_log.py.
_HINT_PREFIXES = (
    "ARROW KEYS navigate",
    "Press ENTER to abandon",
    "Press ESC to close",
)


def _quest_rows(capture: pygame_world.CaptureConsole) -> tuple[tuple[QuestSpan, ...], ...]:
    """Keep quest content, excluding the legacy header and message-log band."""
    from .engine import MSG_LOG_HEIGHT, SCREEN_HEIGHT

    rows = _captured_rows(capture)[:SCREEN_HEIGHT - MSG_LOG_HEIGHT]
    rows = rows[_LEGACY_HEADER_BLOCK:]
    while rows and not any(span.text.strip() for span in rows[-1]):
        rows = rows[:-1]
    return rows


def _split_hint(rows: tuple[tuple[QuestSpan, ...], ...]) -> tuple[tuple[tuple[QuestSpan, ...], ...], str]:
    """Return ``(content_rows, hint)``, moving a trailing hint row out."""
    if not rows:
        return rows, ""
    text = "".join(span.text for span in rows[-1]).strip()
    if text.startswith(_HINT_PREFIXES):
        return rows[:-1], text
    return rows, ""


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
    rows, hint = _split_hint(_quest_rows(capture))
    return QuestFrame(
        rows=rows,
        selected=selected,
        confirm_abandon=confirm_abandon,
        hint=hint,
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
        hint=str(raw.get("hint", "")),
    )


def _font_path(pygame: Any) -> str | None:
    """Choose the same readable font family as the Merchant screen."""
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


def _draw_rows(
    pygame: Any, screen: Any, font: Any, frame: QuestFrame,
    *, context: Any | None = None,
) -> None:
    """Render captured rows inside the shared high-contrast panel treatment."""
    width, height = screen.get_size()
    palette = pygame_ui.DEFAULT_PALETTE
    panel_bottom = (
        pygame_ui.modal_footer_y(height)
        if context is not None else height - 28
    )
    panel = pygame_ui.Rect(32, 28, width - 64, max(1, panel_bottom - 28))
    pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
    pygame_ui.draw_centered_text(
        pygame, screen, font, "QUEST LOG", panel, panel.y + 22,
        color=palette.title, antialias=True,
    )
    pygame_ui.draw_rule(
        pygame, screen, panel.x + 24, panel.y + 54,
        panel.width - 48, color=palette.border,
    )
    content = pygame_ui.Rect(
        panel.x + 34, panel.y + 76,
        max(1, panel.width - 68), max(1, panel.height - 100),
    )
    screen.set_clip(pygame.Rect(content.x, content.y, content.width, content.height))
    try:
        for row_index, row in enumerate(frame.rows):
            x = content.x
            y = content.y + row_index * font.get_linesize()
            for span in row:
                pygame_ui.draw_text(
                    pygame, screen, font, span.text, x, y,
                    color=span.fg, antialias=True,
                )
                x += pygame_ui.measure_font(font, span.text)
    finally:
        screen.set_clip(None)
    if frame.hint:
        hint_y = (
            pygame_ui.modal_content_bottom(height, 2)
            if context is not None else panel.y + panel.height - 48
        )
        pygame_ui.draw_centered_text(
            pygame, screen, font, frame.hint, panel, hint_y,
            color=palette.instruction, antialias=True,
        )


def _handle_key(pygame: Any, event: Any, selected: int, confirm: bool, count: int) -> tuple[str, int, bool]:
    """Map worker key events to the existing Quest Log contract."""
    if event.type == pygame.QUIT:
        return "QUIT", selected, confirm
    if event.type != pygame.KEYDOWN:
        return "IGNORE", selected, confirm
    if event.key == pygame.K_ESCAPE:
        return "BACK", selected, confirm
    if not confirm and event.key in (pygame.K_UP, pygame.K_k) and count:
        return "IGNORE", (selected - 1) % count, confirm
    if not confirm and event.key in (pygame.K_DOWN, pygame.K_j) and count:
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
        selected = int(payload.get("selected", 0)) if count else -1
        confirm = bool(payload.get("confirm_abandon", False))
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
                    print(json.dumps({
                        "outcome": outcome,
                        "selected": selected,
                        "confirm_abandon": confirm,
                    }))
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


def run_shared(
    context: Any,
    ctx: Any,
    selected: int = 0,
    confirm_abandon: bool = False,
) -> tuple[str, int, bool]:
    """Run the stateful Quest Log inside the existing shared window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameQuestLogUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    all_frames = _frames_for(ctx)
    if not all_frames:
        raise PygameQuestLogUnavailable("Quest Log has no renderable frames")
    width, height = screen.get_size()
    font = _fit_font(pygame, all_frames, width, height)
    count = len(ctx.player_active_missions)
    selected = selected if count else -1
    confirm = confirm_abandon
    while True:
        frame = _capture_frame(ctx, selected, confirm)
        screen.fill(pygame_ui.DEFAULT_PALETTE.background)
        _draw_rows(pygame, screen, font, frame, context=context)
        pygame_ui.draw_context_log(pygame, screen, ctx.context)
        engine.present()
        event = pygame.event.wait()
        outcome, selected, confirm = _handle_key(
            pygame, event, selected, confirm, count,
        )
        if outcome == "IGNORE":
            continue
        return outcome, selected, confirm


def run_for_context(
    ctx: Any,
    selected: int = 0,
    confirm_abandon: bool = False,
) -> tuple[str, int, bool]:
    """Run Quest Log in the already-open shared Pygame window."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(ctx.context):
        raise PygameQuestLogUnavailable("Shared Pygame runtime is not open")
    return run_shared(ctx.context, ctx, selected, confirm_abandon)


def run(
    ctx: Any,
    selected: int = 0,
    confirm_abandon: bool = False,
) -> tuple[str, int, bool]:
    """Run the Quest Log worker and return its modal outcome."""
    frames = _frames_for(ctx)
    try:
        response = pygame_ui.run_json_worker(
            pygame_ui.worker_command(f"{__package__}.pygame_quest_log"),
            {
                **_worker_payload(frames),
                "selected": selected,
                "confirm_abandon": confirm_abandon,
            },
            unavailable_message="Pygame Quest Log unavailable",
            environment=pygame_ui.worker_environment(),
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        raise PygameQuestLogUnavailable(str(exc)) from exc
    try:
        return (
            str(response["outcome"]),
            int(response["selected"]),
            bool(response.get("confirm_abandon", confirm_abandon)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PygameQuestLogUnavailable(
            "Pygame Quest Log returned no usable choice"
        ) from exc


if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
