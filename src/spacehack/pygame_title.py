"""Pygame presentation for the title Start/Continue menu."""
from __future__ import annotations

from typing import Any

from . import pygame_menu, pygame_ui, ui


def enabled() -> bool:
    """Return whether the shared Pygame title presentation is active."""
    from . import pygame_runtime

    return pygame_ui.migration_enabled("SPACEHACK_PYGAME_TITLE") or pygame_runtime.shared_enabled()


_TITLE_ACTIONS = {
    "NEW_GAME": ui.TitleMenuOutcome.NEW_GAME,
    "CONTINUE": ui.TitleMenuOutcome.CONTINUE,
    "TUTORIAL": ui.TitleMenuOutcome.TUTORIAL,
    "EXIT": ui.TitleMenuOutcome.EXIT,
}


def _items(save_available: bool) -> tuple[pygame_menu.MenuItem, ...]:
    """Return the selectable title actions, omitting unavailable Continue."""
    items = [
        pygame_menu.MenuItem(
            "START NEW GAME", "Create a new pilot and choose your identity.", "NEW_GAME",
        ),
    ]
    if save_available:
        items.append(
            pygame_menu.MenuItem(
                "CONTINUE", "Resume the autosaved run from its exact last state.", "CONTINUE",
            )
        )
    items.extend((
        pygame_menu.MenuItem(
            "TUTORIAL", "Learn the frontier systems in a guided run.", "TUTORIAL",
        ),
        pygame_menu.MenuItem(
            "EXIT", "Close spacehack.", "EXIT",
        ),
    ))
    return tuple(items)


def frames(save_available: bool) -> tuple[pygame_menu.MenuFrame, ...]:
    """Build every selection state for the shared title menu."""
    items = _items(save_available)
    art = tuple(getattr(ui, "_TITLE_ART", ()))
    return tuple(
        pygame_menu.MenuFrame(
            title="SPACEHACK",
            body="The frontier is waiting.",
            items=items,
            hints=("ARROW KEYS / j,k navigate   ENTER select   ESC exit",),
            selected=selected,
            art=art,
            art_color=pygame_ui.DEFAULT_PALETTE.title,
        )
        for selected in range(len(items))
    )


def run_for_context(context: Any, save_available: bool) -> tuple[ui.TitleMenuOutcome, int] | None:
    """Run the title menu in the existing Pygame window, or request fallback."""
    try:
        outcome, action, selected = pygame_menu.run_for_context(
            context,
            frames(save_available),
            caption="spacehack",
        )
    except pygame_menu.PygameMenuUnavailable:
        return None
    if outcome == "QUIT":
        return ui.TitleMenuOutcome.EXIT, selected
    if outcome == "BACK":
        return ui.TitleMenuOutcome.EXIT, selected
    if outcome != "SELECT":
        return None
    title_outcome = _TITLE_ACTIONS.get(action)
    if title_outcome is None:
        return None
    return title_outcome, selected
