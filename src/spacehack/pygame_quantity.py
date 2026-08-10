"""Reusable Pygame worker for bounded quantity selection.

The worker owns only the quantity selector. The parent process retains all
inventory and credit mutations and receives one integer or a cancellation.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from . import pygame_ui


class PygameQuantityUnavailable(RuntimeError):
    """Raised when the quantity worker cannot return a usable result."""


class PygameQuantityQuit(RuntimeError):
    """Raised when the player closes the quantity window."""


def _handle_key(pygame: Any, event: Any, quantity: int, maximum: int) -> tuple[str, int]:
    """Map one Pygame event to ``(outcome, quantity)``."""
    if event.type == pygame.QUIT:
        return "QUIT", quantity
    if event.type != pygame.KEYDOWN:
        return "IGNORE", quantity
    if event.key == pygame.K_ESCAPE:
        return "BACK", quantity
    question = getattr(pygame, "K_QUESTION", None)
    if question is not None and event.key == question:
        return "GUIDE", quantity
    if event.key in (pygame.K_UP, pygame.K_k, getattr(pygame, "K_PLUS", -1), getattr(pygame, "K_EQUALS", -1)):
        return "IGNORE", min(maximum, quantity + 1)
    if event.key in (pygame.K_DOWN, pygame.K_j, getattr(pygame, "K_MINUS", -1)):
        return "IGNORE", max(1, quantity - 1)
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return "CONFIRM", quantity
    return "IGNORE", quantity


def _run_worker(payload: dict[str, Any]) -> int:
    """Own a quantity window and print one JSON outcome."""
    try:
        import pygame
    except ModuleNotFoundError:
        return 2
    pygame.init()
    pygame.font.init()
    try:
        width, height = tuple(payload.get("screen_size", (1600, 960)))
        from .pygame_menu import _font_path
        path = _font_path(pygame)
        font = pygame.font.Font(path, 24)
        title = str(payload.get("label", "Quantity"))
        maximum = max(1, int(payload.get("maximum", 1)))
        price = int(payload.get("price", 0))
        quantity = 1
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(str(payload.get("caption", "spacehack - quantity")))
        clock = pygame.time.Clock()
        while True:
            palette = pygame_ui.DEFAULT_PALETTE
            screen.fill(palette.background)
            panel = pygame_ui.Rect(120, 240, width - 240, 360)
            pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
            pygame_ui.draw_centered_text(pygame, screen, font, title, panel, 285, color=palette.title)
            pygame_ui.draw_centered_text(
                pygame, screen, font, f"Quantity: {quantity} / {maximum}",
                panel, 365, color=palette.text,
            )
            if price:
                pygame_ui.draw_centered_text(
                    pygame, screen, font, f"{price}$ each   Total: {price * quantity}$",
                    panel, 410, color=palette.description,
                )
            pygame_ui.draw_centered_text(
                pygame, screen, font,
                "UP/DOWN or j/k adjust   ENTER confirm   ESC cancel",
                panel, 500, color=palette.instruction,
            )
            pygame.display.flip()
            for event in pygame.event.get():
                outcome, quantity = _handle_key(pygame, event, quantity, maximum)
                if outcome != "IGNORE":
                    print(json.dumps({"outcome": outcome, "quantity": quantity}))
                    return 0
            clock.tick(60)
    finally:
        pygame.display.quit()
        pygame.quit()


def run_shared(
    context: Any,
    ctx: Any,
    label: str,
    maximum: int,
    price: int = 0,
) -> int | None:
    """Run quantity selection inside the existing shared Pygame window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameQuantityUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    from .pygame_menu import _font_path
    font = pygame.font.Font(_font_path(pygame), 24)
    quantity = 1
    while True:
        palette = pygame_ui.DEFAULT_PALETTE
        screen.fill(palette.background)
        panel = pygame_ui.Rect(120, 240, screen.get_width() - 240, 360)
        pygame_ui.draw_panel(pygame, screen, panel, palette=palette)
        pygame_ui.draw_centered_text(pygame, screen, font, label, panel, 285, color=palette.title)
        pygame_ui.draw_centered_text(
            pygame, screen, font, f"Quantity: {quantity} / {maximum}",
            panel, 365, color=palette.text,
        )
        if price:
            pygame_ui.draw_centered_text(
                pygame, screen, font, f"{price}$ each   Total: {price * quantity}$",
                panel, 410, color=palette.description,
            )
        pygame_ui.draw_centered_text(
            pygame, screen, font,
            "UP/DOWN or j/k adjust   ENTER confirm   ESC cancel",
            panel, 500, color=palette.instruction,
        )
        engine.present()
        event = pygame.event.wait()
        outcome, quantity = _handle_key(pygame, event, quantity, maximum)
        if outcome == "IGNORE":
            continue
        if outcome == "CONFIRM":
            return quantity
        if outcome == "QUIT":
            raise PygameQuantityQuit("Quantity window closed")
        if outcome == "GUIDE":
            from .help import _run_help_guide
            _run_help_guide(ctx)
            continue
        return None


def run_for_context(
    context: Any,
    ctx: Any,
    label: str,
    maximum: int,
    price: int = 0,
    *,
    caption: str = "spacehack - quantity",
) -> int | None:
    """Use the shared window when active, otherwise the worker window."""
    from . import pygame_runtime

    if pygame_runtime.shared_enabled():
        return run_shared(context, ctx, label, maximum, price)
    return run(ctx, label, maximum, price, caption=caption)


def run(
    ctx: Any,
    label: str,
    maximum: int,
    price: int = 0,
    *,
    caption: str = "spacehack - quantity",
) -> int | None:
    """Return a confirmed quantity, or ``None`` for cancel/fallback."""
    if maximum < 1:
        return None
    try:
        response = pygame_ui.run_json_worker(
            pygame_ui.worker_command(f"{__package__}.pygame_quantity"),
            {
                "label": label,
                "maximum": maximum,
                "price": price,
                "caption": caption,
                "screen_size": (1600, 960),
            },
            unavailable_message="Pygame quantity selector unavailable",
            environment=pygame_ui.worker_environment(),
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        raise PygameQuantityUnavailable(str(exc)) from exc
    outcome = str(response.get("outcome", ""))
    if outcome == "QUIT":
        raise PygameQuantityQuit("Quantity window closed")
    if outcome == "GUIDE":
        from .help import _run_help_guide
        _run_help_guide(ctx)
        return run(ctx, label, maximum, price, caption=caption)
    if outcome != "CONFIRM":
        return None
    try:
        quantity = int(response["quantity"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PygameQuantityUnavailable("Pygame quantity selector returned invalid data") from exc
    if not 1 <= quantity <= maximum:
        raise PygameQuantityUnavailable("Pygame quantity selector returned an invalid quantity")
    return quantity


if __name__ == "__main__":
    raise SystemExit(_run_worker(json.load(sys.stdin)) if "--worker" in sys.argv else 2)
