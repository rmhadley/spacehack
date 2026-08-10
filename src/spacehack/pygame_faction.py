"""Pygame presentation for the faction standings screen."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sys
from typing import Any

from . import pygame_menu, pygame_ui


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


_ZONE_COLORS: dict[str, tuple[int, int, int]] = {
    "enemy": (255, 100, 100),
    "disliked": (255, 180, 90),
    "neutral": (205, 215, 230),
    "liked": (130, 210, 255),
    "allied": (130, 255, 160),
}


def enabled() -> bool:
    """Return whether the faction Pygame presentation is active."""
    from . import pygame_runtime

    return pygame_ui.migration_enabled("SPACEHACK_PYGAME_FACTIONS") or pygame_runtime.shared_enabled()


def _faction_rows(ctx: Any) -> tuple[FactionRow, ...]:
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


def frame_for(ctx: Any) -> FactionFrame:
    """Build the current faction standings frame."""
    return FactionFrame(
        title="FACTION STANDINGS",
        subtitle="Your reputation across the frontier",
        rows=_faction_rows(ctx),
        hint="ENTER / ESC back   ? guide",
    )


def _frame_payload(frame: FactionFrame) -> dict[str, Any]:
    """Serialize one faction frame."""
    return asdict(frame)


def _frame_from_payload(raw: dict[str, Any]) -> FactionFrame:
    """Deserialize one faction frame."""
    return FactionFrame(
        title=str(raw["title"]),
        subtitle=str(raw["subtitle"]),
        rows=tuple(
            FactionRow(
                label=str(row["label"]),
                reputation=int(row["reputation"]),
                attitude=str(row["attitude"]),
                bar=str(row["bar"]),
                color=tuple(int(channel) for channel in row["color"]),
            )
            for row in raw.get("rows", ())
        ),
        hint=str(raw.get("hint", "ENTER / ESC back")),
    )


def _font_path(pygame: Any) -> str | None:
    """Reuse the approved readable font selection."""
    return pygame_menu._font_path(pygame)


def _fit_font(pygame: Any, frame: FactionFrame, width: int, height: int) -> Any:
    """Choose a readable font that fits every faction row."""
    path = _font_path(pygame)
    row_text = "Merchant  +100  ---------------|###############  Allied"
    for size in range(26, 13, -1):
        font = pygame.font.Font(path, size)
        row_height = font.get_linesize() + 42
        if row_height * max(1, len(frame.rows)) <= height - 250 and font.size(row_text)[0] <= width - 140:
            return font
    return pygame.font.Font(path, 14)


def _draw_frame(pygame: Any, screen: Any, font: Any, frame: FactionFrame) -> None:
    """Draw faction standings in the shared framed-screen style."""
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
    x = panel.x + 42
    content_width = panel.width - 84
    y = panel.y + 82
    pygame_ui.draw_text(
        pygame, screen, font, frame.subtitle, x, y,
        color=palette.description,
    )
    y += font.get_linesize() + 24
    row_height = font.get_linesize() + 42
    for row in frame.rows:
        pygame_ui.draw_text(
            pygame, screen, font, row.label, x, y,
            color=row.color,
        )
        value = f"{row.reputation:+d}  {row.attitude}"
        value_width = pygame_ui.measure_font(font, value)
        pygame_ui.draw_text(
            pygame, screen, font, value,
            x + content_width - value_width, y,
            color=row.color,
        )
        bar_y = y + font.get_linesize() + 9
        pygame_ui.draw_text(
            pygame, screen, font, row.bar, x, bar_y,
            color=row.color,
        )
        y += row_height
    hint_y = panel.y + panel.height - 48
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.hint, panel, hint_y,
        color=palette.instruction,
    )


def _handle_key(pygame: Any, event: Any) -> str:
    """Map one Pygame event to the faction modal contract."""
    if event.type == pygame.QUIT:
        return "QUIT"
    if event.type != pygame.KEYDOWN:
        return "IGNORE"
    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
        return "BACK"
    question = getattr(pygame, "K_QUESTION", None)
    if question is not None and event.key == question:
        return "GUIDE"
    return "IGNORE"


def _load_pygame() -> Any:
    """Load Pygame lazily for the isolated worker."""
    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise PygameFactionUnavailable("Pygame is not installed") from exc
    return pygame


def _run_worker(payload: dict[str, Any]) -> int:
    """Own one worker window and print its terminal outcome."""
    pygame = _load_pygame()
    frame = _frame_from_payload(payload["frame"])
    pygame.init()
    pygame.font.init()
    try:
        width, height = tuple(payload.get("screen_size", (1600, 960)))
        font = _fit_font(pygame, frame, width, height)
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("spacehack - factions")
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


def run_shared(context: Any, ctx: Any) -> str:
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
        _draw_frame(pygame, screen, font, frame)
        engine.present()
        event = pygame.event.wait()
        outcome = _handle_key(pygame, event)
        if outcome == "GUIDE":
            return outcome
        if outcome != "IGNORE":
            return outcome


def run_for_context(context: Any, ctx: Any) -> str:
    """Use the shared window when active, otherwise the worker window."""
    from . import pygame_runtime

    if pygame_runtime.shared_enabled():
        return run_shared(context, ctx)
    return run(ctx)


def run(ctx: Any) -> str:
    """Run the isolated faction worker and return its outcome."""
    try:
        response = pygame_ui.run_json_worker(
            pygame_ui.worker_command(f"{__package__}.pygame_faction"),
            {
                "frame": _frame_payload(frame_for(ctx)),
                "screen_size": (1600, 960),
            },
            unavailable_message="Pygame faction standings unavailable",
            environment=pygame_ui.worker_environment(),
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        raise PygameFactionUnavailable(str(exc)) from exc
    outcome = str(response.get("outcome", ""))
    if outcome not in {"BACK", "QUIT", "GUIDE"}:
        raise PygameFactionUnavailable("Pygame faction standings returned an unknown choice")
    return outcome


if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
