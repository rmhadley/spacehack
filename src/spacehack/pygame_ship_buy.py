"""Opt-in Pygame presentation for the Ship Buy modal.

The parent process renders the existing Ship Buy screen into captured cell
commands, while an isolated Pygame worker supplies the readable font and simple
ENTER/ESC interaction. Purchase state remains entirely in the tcod game
process and caller; this module only returns a modal outcome.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sys
from typing import Any

from . import pygame_quest_log, pygame_ui


class PygameShipBuyUnavailable(RuntimeError):
    """Raised when the optional Ship Buy worker cannot return a choice."""


@dataclass(frozen=True)
class ShipBuyFrame:
    """Captured rows and affordability metadata for one Ship Buy frame."""

    rows: tuple[tuple[pygame_quest_log.QuestSpan, ...], ...]
    can_buy: bool


def _capture_frame(ctx: Any, ship: Any, effective_price: int | None) -> ShipBuyFrame:
    """Render the authoritative tcod Ship Buy modal into portable rows."""
    from .engine import SCREEN_HEIGHT, SCREEN_WIDTH
    from .menus._ship_buy import render_ship_buy

    capture = pygame_quest_log.pygame_world.CaptureConsole(SCREEN_WIDTH, SCREEN_HEIGHT)
    render_ship_buy(
        capture,
        ctx,
        ship,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        effective_price=effective_price,
    )
    return ShipBuyFrame(
        rows=pygame_quest_log._captured_rows(capture),
        can_buy=ctx.stats.credits >= (
            effective_price if effective_price is not None else ship.price
        ),
    )


def _worker_payload(frame: ShipBuyFrame) -> dict[str, Any]:
    """Serialize one captured Ship Buy frame for the worker."""
    return {
        "frame": asdict(frame),
        "screen_size": (1600, 960),
        "font_size": 20,
    }


def _frame_from_payload(raw: dict[str, Any]) -> ShipBuyFrame:
    """Deserialize one captured Ship Buy frame."""
    return ShipBuyFrame(
        rows=tuple(
            tuple(
                pygame_quest_log.QuestSpan(
                    text=span["text"], fg=tuple(span["fg"]),
                )
                for span in row
            )
            for row in raw["rows"]
        ),
        can_buy=bool(raw["can_buy"]),
    )


def _fit_font(pygame: Any, frame: ShipBuyFrame, width: int, height: int) -> Any:
    """Choose the largest font that fits the captured rows."""
    path = pygame_quest_log._font_path(pygame)
    max_text_width = max(
        (sum(len(span.text) for span in row) for row in frame.rows),
        default=1,
    )
    for size in range(26, 11, -1):
        font = pygame.font.Font(path, size)
        if (
            font.get_linesize() * len(frame.rows) <= height - 24
            and font.size("M" * max_text_width)[0] <= width - 48
        ):
            return font
    return pygame.font.Font(path, 12)


def _draw_frame(pygame: Any, screen: Any, font: Any, frame: ShipBuyFrame) -> None:
    """Draw captured Ship Buy rows with natural font spacing."""
    for row_index, row in enumerate(frame.rows):
        x = 24
        y = 12 + row_index * font.get_linesize()
        for span in row:
            pygame_ui.draw_text(
                pygame, screen, font, span.text, x, y,
                color=span.fg, antialias=True,
            )
            x += pygame_ui.measure_font(font, span.text)


def _handle_key(pygame: Any, event: Any, can_buy: bool) -> str:
    """Map worker key events to Ship Buy modal outcomes."""
    if event.type == pygame.QUIT:
        return "QUIT"
    if event.type != pygame.KEYDOWN:
        return "IGNORE"
    if event.key == pygame.K_ESCAPE:
        return "BACK"
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return "BUY" if can_buy else "TOO_EXPENSIVE"
    question_key = getattr(pygame, "K_QUESTION", None)
    if question_key is not None and event.key == question_key:
        return "GUIDE"
    return "IGNORE"


def _load_pygame() -> Any:
    """Load Pygame only in the isolated worker."""
    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise PygameShipBuyUnavailable("Pygame is not installed") from exc
    return pygame


def _run_worker(payload: dict[str, Any]) -> int:
    """Own the Pygame Ship Buy window and return one outcome."""
    pygame = _load_pygame()
    frame = _frame_from_payload(payload["frame"])
    pygame.init()
    pygame.font.init()
    try:
        width, height = tuple(payload.get("screen_size", (1600, 960)))
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("spacehack - Ship Buy")
        font = _fit_font(pygame, frame, width, height)
        clock = pygame.time.Clock()
        while True:
            screen.fill(pygame_ui.DEFAULT_PALETTE.background)
            _draw_frame(pygame, screen, font, frame)
            pygame.display.flip()
            for event in pygame.event.get():
                outcome = _handle_key(pygame, event, frame.can_buy)
                if outcome != "IGNORE":
                    print(json.dumps({"outcome": outcome}))
                    return 0
            clock.tick(60)
    finally:
        pygame.display.quit()
        pygame.quit()


def run(ctx: Any, ship: Any, effective_price: int | None = None) -> str:
    """Run the worker and return its outcome string."""
    frame = _capture_frame(ctx, ship, effective_price)
    try:
        response = pygame_ui.run_json_worker(
            pygame_ui.worker_command(f"{__package__}.pygame_ship_buy"),
            _worker_payload(frame),
            unavailable_message="Pygame Ship Buy unavailable",
            environment=pygame_ui.worker_environment(),
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        raise PygameShipBuyUnavailable(str(exc)) from exc
    try:
        return str(response["outcome"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PygameShipBuyUnavailable(
            "Pygame Ship Buy returned no usable choice"
        ) from exc


if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
