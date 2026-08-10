"""Opt-in Pygame Merchant offerings screen.

This is the first live presentation-migration seam. The game process builds
renderer-neutral frames from live mission data, then a short-lived worker
process owns the Pygame window and event loop. The worker returns the same
accept/back choice as the existing tcod modal without sharing SDL ownership
with tcod. The backend is optional and falls back cleanly when unavailable.
"""
from __future__ import annotations

import json
import os
import subprocess
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
    panel = pygame_ui.Rect(28, 24, width - 56, height - 48)
    pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
    pygame_ui.draw_centered_text(
        pygame, screen, font, frame.title, panel, 52,
        color=palette.title, antialias=antialias,
    )
    pygame_ui.draw_rule(
        pygame, screen, panel.x + 24, 94, panel.width - 48,
        color=palette.border,
    )
    x = panel.x + 34
    content_width = panel.width - 68
    y = 120
    row_step = font.get_linesize() + 14
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
    for hint in frame.hints:
        pygame_ui.draw_text(
            pygame, screen, font, hint, x, y,
            color=palette.instruction, antialias=antialias,
        )
        y += row_step


def _worker_payload(frames: tuple[MerchantFrame, ...]) -> dict[str, Any]:
    """Serialize renderer-neutral frames for the worker process."""
    return {"frames": [asdict(frame) for frame in frames]}


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
        screen = pygame.display.set_mode((1280, 760))
        pygame.display.set_caption("spacehack - Merchant Guild")
        font = pygame.font.Font(_font_path(pygame), 30)
        palette = pygame_ui.DEFAULT_PALETTE
        selected = 0
        clock = pygame.time.Clock()
        while True:
            frame = frames[selected % len(frames)]
            screen.fill(palette.background)
            _draw_frame(
                pygame, screen, font, frame,
                palette=palette, antialias=True,
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
    screen_size: tuple[int, int] = (1280, 760),
    font_size: int = 30,
    antialias: bool = True,
) -> tuple[str, int]:
    """Run the isolated Pygame Merchant worker and return its choice.

    ``screen_size``, ``font_size``, and ``antialias`` remain in the signature
    for the next presentation-migration step; the first live worker uses the
    comparison spike's proven 1280x760, 30px antialiased configuration.
    """
    del screen_size, font_size, antialias
    from .data.classes import find_class
    from .menus._missions import _mission_board_label

    frames = _all_frames(
        npc,
        offerings,
        _mission_board_label,
        lambda class_id: find_class(class_id).name,
    )
    command = [sys.executable, "-m", f"{__package__}.pygame_merchant", "--worker"]
    environment = {**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"}
    try:
        result = subprocess.run(
            command,
            input=json.dumps(_worker_payload(frames)),
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PygameMerchantUnavailable(
            "Pygame worker could not start; using the tcod Merchant modal."
        ) from exc
    if result.returncode != 0:
        raise PygameMerchantUnavailable(
            "Pygame worker failed; using the tcod Merchant modal."
        )
    try:
        response = json.loads(result.stdout.strip().splitlines()[-1])
        return str(response["outcome"]), int(response["selected"])
    except (IndexError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise PygameMerchantUnavailable(
            "Pygame worker returned no usable choice; using tcod."
        ) from exc


if __name__ == "__main__":
    raise SystemExit(_worker_main() if "--worker" in sys.argv else 2)
