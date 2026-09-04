"""Interactive new-player guide opened with the ``?`` key.

The manual content lives in :mod:`spacehack.data.guide`; this module owns
only the guide's lookup and Pygame presentation behavior.
"""

from __future__ import annotations

from typing import Any

from .data.guide import GUIDE_SECTIONS, GuideSection
from .game_context import GameContext


def _guide_index(topic: str | int | None) -> int | None:
    """Resolve a contextual guide topic by title or section index."""
    if topic is None:
        return None
    if isinstance(topic, int):
        return topic if 0 <= topic < len(GUIDE_SECTIONS) else None
    normalized = topic.strip().casefold()
    return next(
        (
            index
            for index, section in enumerate(GUIDE_SECTIONS)
            if section.title.casefold() == normalized
        ),
        None,
    )


def _section_frame(section: GuideSection) -> Any:
    """Build one scrollable guide-section frame."""
    from . import pygame_screen, pygame_ui

    return pygame_screen.ScreenFrame(
        title=section.title,
        body=tuple(section.body.split("\n")),
        rows=(),
        footer=(
            pygame_ui.modal_hint(
                "ESC topic list", pygame_ui.GUIDE_HINT,
            ),
        ),
        scrollable=True,
    )


def _guide_list_frame():
    """The guide's top-level topic list."""
    from . import pygame_screen, pygame_ui

    return pygame_screen.ScreenFrame(
        title="SPACEHACK GUIDE",
        body=("Select a topic. Open it with ENTER.",),
        rows=tuple(
            pygame_screen.ScreenRow(
                text=section.title,
                action=f"SECTION:{index}",
            )
            for index, section in enumerate(GUIDE_SECTIONS)
        ),
        footer=(
            pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER open", "ESC close",
            ),
        ),
    )


def _run_pygame_help(
    ctx: GameContext,
    initial_topic: str | int | None = None,
) -> bool | None:
    """Run the guide through the shared Pygame screen."""
    from . import pygame_screen

    list_frame = _guide_list_frame()
    initial_index = _guide_index(initial_topic)
    frame = list_frame
    if initial_index is not None:
        frame = _section_frame(GUIDE_SECTIONS[initial_index])
    while True:
        outcome, action, _selected = pygame_screen.run_for_context(
            ctx.context, frame, caption="spacehack - guide",
        )
        if outcome == "SELECT" and action.startswith("SECTION:"):
            try:
                index = int(action.split(":", 1)[1])
                section = GUIDE_SECTIONS[index]
            except (ValueError, IndexError):
                return None
            frame = _section_frame(section)
            continue
        if outcome == "TAB":
            frame = list_frame
            continue
        if outcome == "QUIT":
            return True
        if frame is not list_frame:
            frame = list_frame
            continue
        if outcome == "BACK":
            return True


def _run_help_guide(ctx: GameContext) -> None:
    """Open the game guide as a modal, optionally at a contextual topic."""
    topic = getattr(ctx, "_guide_topic", None)
    if hasattr(ctx, "_guide_topic"):
        delattr(ctx, "_guide_topic")
    result = _run_pygame_help(ctx, topic)
    if result is None:
        raise RuntimeError("Guide returned no outcome")


def _open_context_guide(ctx: GameContext, topic: str) -> None:
    """Open the guide directly at the topic most relevant to a modal."""
    ctx._guide_topic = topic
    _run_help_guide(ctx)
