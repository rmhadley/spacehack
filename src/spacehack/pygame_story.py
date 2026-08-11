"""Pygame presentation adapters for story popups.

Story modules provide immutable text and opaque action IDs. This module owns
only the shared Pygame presentation; quest state remains in the caller.
"""
from __future__ import annotations

from . import pygame_menu, pygame_ui


def enabled() -> bool:
    """Return whether the interactive Pygame presentation is enabled."""
    return pygame_menu.enabled()


def dismiss(
    ctx,
    *,
    title: str,
    body: str,
    caption: str,
    art: tuple[str, ...] = (),
    art_color: tuple[int, int, int] | None = None,
    art_colors: tuple[tuple[int, int, int], ...] = (),
) -> str:
    """Run a dismiss-only story popup in the shared Pygame window."""
    frame = pygame_menu.MenuFrame(
        title=title,
        body=body,
        items=(),
        hints=(pygame_ui.modal_hint(
            "ENTER continue", "ESC close", pygame_ui.GUIDE_HINT,
        ),),
        selected=0,
        art=art,
        art_color=art_color,
        art_colors=art_colors,
    )
    outcome, _action, _selected = pygame_menu.run_for_context(getattr(ctx, "context", ctx), (frame,), caption=caption)
    if outcome == "GUIDE":
        from .help import _run_help_guide
        _run_help_guide(ctx)
        return "__GUIDE__"
    return outcome


def confirm(
    ctx,
    *,
    title: str,
    body: str,
    accept_label: str,
    cancel_label: str,
    caption: str,
) -> str | None:
    """Run a two-outcome confirmation and return its terminal result."""
    item = pygame_menu.MenuItem(accept_label, "", "CONFIRM")
    frame = pygame_menu.MenuFrame(
        title=title,
        body=body,
        items=(item,),
        hints=(pygame_ui.modal_hint(
            f"ENTER {accept_label.lower()}",
            f"ESC {cancel_label.lower()}", pygame_ui.GUIDE_HINT,
        ),),
        selected=0,
    )
    outcome, action, _selected = pygame_menu.run_for_context(getattr(ctx, "context", ctx), (frame,), caption=caption)
    if outcome == "GUIDE":
        from .help import _run_help_guide
        _run_help_guide(ctx)
        return confirm(
            ctx,
            title=title,
            body=body,
            accept_label=accept_label,
            cancel_label=cancel_label,
            caption=caption,
        )
    if outcome == "SELECT" and action == "CONFIRM":
        return "CONFIRM"
    if outcome == "QUIT":
        return "QUIT"
    return "BACK"


def choose(
    ctx,
    *,
    title: str,
    body: str,
    options: tuple[tuple[str, str], ...],
    caption: str,
) -> str:
    """Run a small story choice and return its opaque action ID."""
    items = tuple(
        pygame_menu.MenuItem(label, "", action)
        for label, action in options
    )
    frames = tuple(
        pygame_menu.MenuFrame(
            title=title,
            body=body,
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER select", "ESC back",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=index,
        )
        for index in range(max(1, len(items)))
    )
    outcome, action, _selected = pygame_menu.run_for_context(getattr(ctx, "context", ctx), frames, caption=caption)
    if outcome == "SELECT":
        valid_actions = {option_action for _label, option_action in options}
        return action if action in valid_actions else None
    if outcome == "GUIDE":
        from .help import _run_help_guide
        _run_help_guide(ctx)
        return "__GUIDE__"
    if outcome == "BACK":
        return "__BACK__"
    if outcome == "QUIT":
        return "__QUIT__"
    return "__DISMISS__"
