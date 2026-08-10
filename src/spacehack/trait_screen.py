"""Trait selection modal — shown at level 20 and 30 milestones.

Opened by :func:`spacehack.xp.add_xp` when the player reaches a
milestone.  Presents all qualifying traits (filtered by counters
and not-already-chosen) and lets the player pick one with ENTER.

Design doc: ``docs/design/in_progress/02_DESIGN_XP_LEVELING.md``
"""

from __future__ import annotations

import tcod.console
import tcod.event

from . import ui
from . import message_log
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from .game_context import GameContext
from .input_helpers import _try_open_guide
from .xp import _qualifying_traits


def _pygame_trait_enabled() -> bool:
    """Return whether the generic Pygame screen worker is enabled."""
    from . import pygame_screen

    return pygame_screen.enabled()


def _run_pygame_trait_selection(ctx: GameContext, candidates: list) -> bool | None:
    """Run mandatory trait selection through Pygame."""
    from . import pygame_screen

    frame = pygame_screen.ScreenFrame(
        title=f"TRAIT SELECTION - Level {ctx.player_level}",
        body=("Choose one trait. Selection is required before gameplay resumes.",),
        rows=tuple(
            pygame_screen.ScreenRow(
                text=trait.name,
                detail=trait.description,
                action=f"TRAIT:{trait.id}",
            )
            for trait in candidates
        ),
        footer=("UP/DOWN or j/k select   ENTER choose",),
    )
    outcome, action, _selected = pygame_screen.run_for_context(
        ctx.context, frame, caption="spacehack - trait selection",
    )
    if outcome in {"BACK", "TAB"}:
        return _run_pygame_trait_selection(ctx, candidates)
    if outcome == "QUIT":
        raise SystemExit
    if outcome == "SELECT" and action.startswith("TRAIT:"):
        trait_id = action.split(":", 1)[1]
        picked = next((trait for trait in candidates if trait.id == trait_id), None)
        if picked is None:
            return None
        ctx.player_traits.append(picked.id)
        ctx.log.add_colored(
            f"Trait gained: {picked.name} - {picked.description}",
            message_log.COLOR_COMBAT_EVENT,
        )
        return True
    return None


def open_trait_selection(ctx: GameContext) -> None:
    """Open the trait selection modal.

    Lists all traits the player qualifies for (via
    :func:`_qualifying_traits`).  If none qualify, logs a message
    and returns without showing the modal — the player can open the
    Character screen later to pick when they do qualify.
    """
    _candidates = _qualifying_traits(ctx)
    if not _candidates:
        ctx.log.add_colored(
            "No qualifying traits available yet - check the Character screen later.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        return

    result = _run_pygame_trait_selection(ctx, _candidates)
    if result is None:
        raise RuntimeError("Trait selection returned no outcome")
    return
