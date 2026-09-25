"""Reusable Pygame presentation for bounded quantity selection.

The shared runtime owns only the quantity selector. The game process retains
all inventory and credit mutations and receives one integer or a cancellation.
"""
from __future__ import annotations

from typing import Any

from . import pygame_ui
from .pygame_runtime import PygameContext


class PygameQuantityUnavailable(RuntimeError):
    """Raised when the quantity selector cannot return a usable result."""


class PygameQuantityQuit(RuntimeError):
    """Raised when the player closes the quantity window."""


# Canonical stepper hint (doc 52.2 fast keys): fine +/-1, coarse +/-10,
# page jumps to the bounds — the modal's hint line is the only teacher
# (the guide documents no quantity keys).
QUANTITY_HINT = pygame_ui.modal_hint(
    "LEFT/RIGHT +/-1, UP/DOWN +/-10, PGUP/PGDN min-max",
    "ENTER confirm", "ESC cancel", pygame_ui.GUIDE_HINT,
)


def _key_delta(pygame: Any, key: int) -> int:
    """Signed step for one adjust key: arrows/vim fine 1, coarse 10."""
    table = {
        getattr(pygame, "K_LEFT", -1): -1,
        getattr(pygame, "K_h", -1): -1,
        getattr(pygame, "K_MINUS", -1): -1,
        getattr(pygame, "K_RIGHT", -1): 1,
        getattr(pygame, "K_l", -1): 1,
        getattr(pygame, "K_PLUS", -1): 1,
        getattr(pygame, "K_EQUALS", -1): 1,
        getattr(pygame, "K_UP", -1): 10,
        getattr(pygame, "K_k", -1): 10,
        getattr(pygame, "K_DOWN", -1): -10,
        getattr(pygame, "K_j", -1): -10,
    }
    return table.get(key, 0)


def _handle_key(pygame: Any, event: Any, quantity: int, maximum: int) -> tuple[str, int]:
    """Map one Pygame event to ``(outcome, quantity)``."""
    if event.type == pygame.QUIT:
        return "QUIT", quantity
    if event.type != pygame.KEYDOWN:
        return "IGNORE", quantity
    if event.key == pygame.K_ESCAPE:
        return "BACK", quantity
    if pygame_ui.is_guide_key(pygame, event):
        return "GUIDE", quantity
    if event.key == getattr(pygame, "K_PAGEUP", -1):
        return "IGNORE", maximum
    if event.key == getattr(pygame, "K_PAGEDOWN", -1):
        return "IGNORE", 1
    delta = _key_delta(pygame, event.key)
    if delta:
        return "IGNORE", min(maximum, max(1, quantity + delta))
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return "CONFIRM", quantity
    return "IGNORE", quantity


def _draw_quantity(
    pygame: Any,
    screen: Any,
    font: Any,
    label: str,
    quantity: int,
    maximum: int,
    price: int,
) -> None:
    """Paint one quantity selector frame inside the shared window."""
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
        pygame, screen, font, QUANTITY_HINT,
        panel, 500, color=palette.instruction,
    )


def _clamped_prefill(maximum: int, prefill: int | None) -> int:
    """Opening quantity: the caller's prefill clamped into [1, maximum].

    BUY callers prefill at min(affordable, space-to-cap) so the common
    case is confirm (doc 52.2); sells and jettison pass ``None`` — the
    modal cannot tell a buy from a sell, so affordability is never
    computed here.
    """
    if prefill is None:
        return 1
    return max(1, min(maximum, prefill))


async def run_shared(
    context: PygameContext,
    ctx: Any,
    label: str,
    maximum: int,
    price: int = 0,
    prefill: int | None = None,
) -> int | None:
    """Run quantity selection inside the existing shared Pygame window."""
    runtime = getattr(context, "_runtime", None)
    engine = getattr(runtime, "engine", None)
    if engine is None or engine.logical_surface is None:
        raise PygameQuantityUnavailable("Shared Pygame runtime is not open")
    pygame = engine.pygame
    screen = engine.logical_surface
    font = pygame.font.Font(pygame_ui._font_path(pygame), 24)
    quantity = _clamped_prefill(maximum, prefill)
    while True:
        _draw_quantity(
            pygame, screen, font, label, quantity, maximum, price,
        )
        pygame_ui.draw_context_log(pygame, screen, context)
        engine.present()
        for event in pygame.event.get():
            outcome, quantity = _handle_key(pygame, event, quantity, maximum)
            if outcome == "IGNORE":
                continue
            if outcome == "CONFIRM":
                return quantity
            if outcome == "QUIT":
                raise PygameQuantityQuit("Quantity window closed")
            if outcome == "GUIDE":
                from .help import _run_help_guide
                await _run_help_guide(ctx)
                break
            return None
        else:
            await context.pump(0.016)
            continue


async def run_for_context(
    context: PygameContext,
    ctx: Any,
    label: str,
    maximum: int,
    price: int = 0,
    *,
    caption: str = "spacehack - quantity",
    prefill: int | None = None,
) -> int | None:
    """Run quantity selection in the already-open shared Pygame window."""
    from . import pygame_runtime

    if not pygame_runtime.is_shared_context(context):
        raise PygameQuantityUnavailable("Shared Pygame runtime is not open")
    return await run_shared(context, ctx, label, maximum, price, prefill)


