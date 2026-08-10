"""Optional Pygame worker for two-panel split-screen terminals.

The parent process owns all domain state. This worker receives only a
presentation snapshot and returns an opaque panel/action selection.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import sys
from collections.abc import Callable
from typing import Any

from . import pygame_menu, pygame_ui


class PygameSplitUnavailable(RuntimeError):
    """Raised when the optional split-screen worker cannot return."""


def enabled() -> bool:
    """Return whether the shared interactive Pygame batch is enabled."""
    return pygame_menu.enabled()


@dataclass(frozen=True)
class SplitRow:
    """One selectable or divider row in a split panel."""

    label: str
    value: str
    detail: str
    action: str
    divider: bool = False


@dataclass(frozen=True)
class SplitFrame:
    """Presentation-only state for one split-screen terminal."""

    title: str
    left_label: str
    right_label: str
    left_rows: tuple[SplitRow, ...]
    right_rows: tuple[SplitRow, ...]
    footer_left: str
    footer_right: str
    hint: str
    focus: int = 0
    selected: int = 0


def _row_payload(row: SplitRow) -> dict[str, Any]:
    """Serialize one split row."""
    return asdict(row)


def _frame_payload(frame: SplitFrame) -> dict[str, Any]:
    """Serialize one split frame for the worker."""
    payload = asdict(frame)
    payload["left_rows"] = [_row_payload(row) for row in frame.left_rows]
    payload["right_rows"] = [_row_payload(row) for row in frame.right_rows]
    return payload


def _frame_from_payload(raw: dict[str, Any]) -> SplitFrame:
    """Deserialize one split frame from worker input."""
    return SplitFrame(
        title=str(raw["title"]),
        left_label=str(raw["left_label"]),
        right_label=str(raw["right_label"]),
        left_rows=tuple(SplitRow(**row) for row in raw.get("left_rows", ())),
        right_rows=tuple(SplitRow(**row) for row in raw.get("right_rows", ())),
        footer_left=str(raw.get("footer_left", "")),
        footer_right=str(raw.get("footer_right", "")),
        hint=str(raw.get("hint", "")),
        focus=int(raw.get("focus", 0)),
        selected=int(raw.get("selected", 0)),
    )


def _rows(frame: SplitFrame) -> tuple[SplitRow, ...]:
    """Return the currently focused row collection."""
    return frame.left_rows if frame.focus == 0 else frame.right_rows


def _selectable_indices(rows: tuple[SplitRow, ...]) -> tuple[int, ...]:
    """Return row indices that can produce an action."""
    return tuple(index for index, row in enumerate(rows) if not row.divider)


def _clamp_selected(frame: SplitFrame) -> int:
    """Clamp selection to a selectable row, or zero for an empty panel."""
    indices = _selectable_indices(_rows(frame))
    if not indices:
        return 0
    if frame.selected in indices:
        return frame.selected
    return min(indices, key=lambda index: abs(index - frame.selected))


def _content_width(width: int) -> int:
    """Return usable width for each panel."""
    return max(1, (width - 132) // 2)


def _frame_height(font: Any, frame: SplitFrame, width: int) -> int:
    """Measure the split frame for font fitting."""
    line = font.get_linesize()
    panel_width = _content_width(width)
    measure = lambda text: pygame_ui.measure_font(font, text)
    rows = (*frame.left_rows, *frame.right_rows)
    detail_lines = sum(
        len(pygame_ui.wrap_text(row.detail, panel_width, measure))
        for row in rows
        if row.detail
    )
    return 150 + max(len(frame.left_rows), len(frame.right_rows)) * (line + 8) + detail_lines * (line + 2)


def _fit_font(pygame: Any, frame: SplitFrame, width: int, height: int) -> Any:
    """Choose the largest readable font that fits the split frame."""
    path = pygame_menu._font_path(pygame)
    for size in range(24, 11, -1):
        font = pygame.font.Font(path, size)
        if _frame_height(font, frame, width) <= height - 120:
            return font
    return pygame.font.Font(path, 12)


def _draw_panel(
    pygame: Any,
    screen: Any,
    font: Any,
    frame: SplitFrame,
    rows: tuple[SplitRow, ...],
    *,
    panel: pygame_ui.Rect,
    label: str,
    selected: int,
    focused: bool,
) -> None:
    """Draw one panel and its currently selected detail."""
    palette = pygame_ui.DEFAULT_PALETTE
    pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
    pygame_ui.draw_text(
        pygame, screen, font, label, panel.x + 20, panel.y + 18,
        color=palette.title if focused else palette.description,
    )
    pygame_ui.draw_rule(
        pygame, screen, panel.x + 18, panel.y + 48,
        panel.width - 36, color=palette.border,
    )
    x = panel.x + 20
    y = panel.y + 66
    measure = lambda text: pygame_ui.measure_font(font, text)
    for index, row in enumerate(rows):
        if row.divider:
            pygame_ui.draw_text(
                pygame, screen, font,
                pygame_ui.fit_text(row.label, panel.width - 40, measure),
                x, y, color=palette.description,
            )
            y += font.get_linesize() + 5
            continue
        selected_row = focused and index == selected
        y = pygame_ui.draw_menu_row(
            pygame, screen, font,
            f"{row.label}  {row.value}".rstrip(),
            x, y, panel.width - 40,
            selected=selected_row,
            palette=palette,
        )
        if selected_row and row.detail:
            y = pygame_ui.draw_wrapped_text(
                pygame, screen, font, row.detail,
                x + 28, y - 4, panel.width - 68,
                color=palette.description, line_gap=2,
            )


def _draw_frame(pygame: Any, screen: Any, font: Any, frame: SplitFrame) -> None:
    """Paint the split-screen frame."""
    width, height = screen.get_size()
    screen.fill(pygame_ui.DEFAULT_PALETTE.background)
    title_rect = pygame_ui.Rect(32, 20, width - 64, 44)
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.title, title_rect, 24,
        color=pygame_ui.DEFAULT_PALETTE.title,
    )
    pygame_ui.draw_rule(
        pygame, screen, 56, 62, width - 112,
        color=pygame_ui.DEFAULT_PALETTE.border,
    )
    gap = 20
    panel_width = (width - 64 - gap) // 2
    panel_height = height - 156
    left = pygame_ui.Rect(32, 78, panel_width, panel_height)
    right = pygame_ui.Rect(32 + panel_width + gap, 78, panel_width, panel_height)
    selected = _clamp_selected(frame)
    _draw_panel(
        pygame, screen, font, frame, frame.left_rows,
        panel=left, label=frame.left_label, selected=selected,
        focused=frame.focus == 0,
    )
    _draw_panel(
        pygame, screen, font, frame, frame.right_rows,
        panel=right, label=frame.right_label, selected=selected,
        focused=frame.focus == 1,
    )
    pygame_ui.draw_text(
        pygame, screen, font, frame.footer_left, 40, height - 58,
        color=pygame_ui.DEFAULT_PALETTE.text,
    )
    footer_width = pygame_ui.measure_font(font, frame.footer_right)
    pygame_ui.draw_text(
        pygame, screen, font, frame.footer_right,
        width - footer_width - 40, height - 58,
        color=pygame_ui.DEFAULT_PALETTE.text,
    )
    pygame_ui.draw_text(
        pygame, screen, font,
        pygame_ui.fit_text(frame.hint, width - 80, lambda value: pygame_ui.measure_font(font, value)),
        40, height - 34, color=pygame_ui.DEFAULT_PALETTE.instruction,
    )


def _handle_key(pygame: Any, event: Any, frame: SplitFrame) -> tuple[str, int, int]:
    """Map a worker key to ``(outcome, focus, selected)``."""
    selected = _clamp_selected(frame)
    rows = _rows(frame)
    indices = _selectable_indices(rows)
    if event.type == pygame.QUIT:
        return "QUIT", frame.focus, selected
    if event.type != pygame.KEYDOWN:
        return "IGNORE", frame.focus, selected
    if event.key == pygame.K_ESCAPE:
        return "BACK", frame.focus, selected
    question = getattr(pygame, "K_QUESTION", None)
    if question is not None and event.key == question:
        return "GUIDE", frame.focus, selected
    if event.key == pygame.K_TAB:
        other = SplitFrame(
            frame.title, frame.left_label, frame.right_label,
            frame.left_rows, frame.right_rows, frame.footer_left,
            frame.footer_right, frame.hint, 1 - frame.focus, 0,
        )
        return "IGNORE", other.focus, _clamp_selected(other)
    if event.key in (pygame.K_UP, pygame.K_k) and indices:
        position = indices.index(selected)
        return "IGNORE", frame.focus, indices[(position - 1) % len(indices)]
    if event.key in (pygame.K_DOWN, pygame.K_j) and indices:
        position = indices.index(selected)
        return "IGNORE", frame.focus, indices[(position + 1) % len(indices)]
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and indices:
        return "SELECT", frame.focus, selected
    return "IGNORE", frame.focus, selected


def _run_worker(payload: dict[str, Any]) -> int:
    """Own one split-screen window and print one terminal result."""
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
            current = SplitFrame(
                frame.title, frame.left_label, frame.right_label,
                frame.left_rows, frame.right_rows, frame.footer_left,
                frame.footer_right, frame.hint, frame.focus,
                _clamp_selected(frame),
            )
            _draw_frame(pygame, screen, font, current)
            pygame.display.flip()
            for event in pygame.event.get():
                outcome, focus, selected = _handle_key(pygame, event, current)
                if outcome == "IGNORE":
                    frame = SplitFrame(
                        frame.title, frame.left_label, frame.right_label,
                        frame.left_rows, frame.right_rows, frame.footer_left,
                        frame.footer_right, frame.hint, focus, selected,
                    )
                    continue
                row = _rows(current)
                action = row[selected].action if outcome == "SELECT" else ""
                print(json.dumps({
                    "outcome": outcome,
                    "action": action,
                    "focus": focus,
                    "selected": selected,
                }))
                return 0
            clock.tick(60)
    finally:
        pygame.display.quit()
        pygame.quit()


def run_interactive(
    ctx: Any,
    build_frame: Callable[[], SplitFrame],
    apply_action: Callable[[str, int, int], bool],
    *,
    caption: str,
) -> str | None:
    """Repeat split selections while the parent applies domain actions.

    ``build_frame`` and ``apply_action`` execute in the game process;
    the worker never receives mutable game state. ``apply_action`` returns
    True when the terminal should remain open after the mutation.
    """
    try:
        frame = build_frame()
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return None
    focus = frame.focus
    selected = frame.selected
    while True:
        try:
            frame = replace(frame, focus=focus, selected=selected)
            outcome, action, focus, selected = run(frame, caption=caption)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            return None
        except PygameSplitUnavailable:
            return None
        if outcome == "GUIDE":
            from .help import _run_help_guide
            _run_help_guide(ctx)
            try:
                frame = build_frame()
            except (AttributeError, IndexError, KeyError, TypeError, ValueError):
                return None
            continue
        if outcome == "SELECT":
            try:
                keep_open = apply_action(action, focus, selected)
            except (AttributeError, IndexError, KeyError, TypeError, ValueError):
                return None
            if keep_open:
                try:
                    frame = build_frame()
                except (AttributeError, IndexError, KeyError, TypeError, ValueError):
                    return None
                continue
            return "BACK"
        return outcome


def run(
    frame: SplitFrame,
    *,
    caption: str = "spacehack - terminal",
    screen_size: tuple[int, int] = (1600, 960),
) -> tuple[str, str, int, int]:
    """Run the split worker and return outcome, action, focus, selection."""
    try:
        response = pygame_ui.run_json_worker(
            pygame_ui.worker_command(f"{__package__}.pygame_split"),
            {
                **_frame_payload(frame),
                "caption": caption,
                "screen_size": screen_size,
            },
            unavailable_message="Pygame split terminal unavailable",
            environment=pygame_ui.worker_environment(),
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        raise PygameSplitUnavailable(str(exc)) from exc
    try:
        outcome = str(response["outcome"])
        action = str(response.get("action", ""))
        focus = int(response.get("focus", frame.focus))
        selected = int(response.get("selected", frame.selected))
    except (KeyError, TypeError, ValueError) as exc:
        raise PygameSplitUnavailable("Pygame split terminal returned no usable choice") from exc
    if outcome not in {"BACK", "QUIT", "GUIDE", "SELECT"}:
        raise PygameSplitUnavailable("Pygame split terminal returned an unknown choice")
    return outcome, action, focus, selected


if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
