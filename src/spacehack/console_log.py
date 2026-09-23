"""Full-run console history viewer.

The compact HUD log remains visible during play. This module exposes the
complete append-only history through the shared text-screen presentation.
"""
from __future__ import annotations

from .game_context import GameContext
from . import message_log, pygame_screen, pygame_ui


def _frame(ctx: GameContext) -> pygame_screen.ScreenFrame:
    """Build the console history screen from the live log."""
    entries = ctx.log.history()
    if not entries:
        return pygame_screen.ScreenFrame(
            title="CONSOLE LOG",
            body=("No console messages yet.",),
            rows=(),
            footer=(pygame_ui.modal_hint(
                "ESC close", pygame_ui.GUIDE_HINT,
            ),),
            scrollable=True,
            start_at_end=True,
        )
    return pygame_screen.ScreenFrame(
        title="CONSOLE LOG",
        body=tuple(f"> {entry.text}" for entry in entries),
        rows=(),
        footer=(pygame_ui.modal_hint(
            "ESC close", pygame_ui.GUIDE_HINT,
        ),),
        scrollable=True,
        body_colors=tuple(entry.fg for entry in entries),
        # Inline runs carry the "> " prefix so run text joins to the
        # body line exactly (the runs-fit-or-plain guard measures it).
        body_runs=tuple(
            message_log.prefixed_runs(entry) for entry in entries
        ),
        start_at_end=True,
    )


async def open_console_log(ctx: GameContext) -> str:
    """Open the full console history until the player dismisses it."""
    while True:
        outcome, _action, _selected = await pygame_screen.run_for_context(
            ctx.context,
            _frame(ctx),
            caption="spacehack - console log",
        )
        if outcome == "GUIDE":
            from .help import _run_help_guide
            await _run_help_guide(ctx)
            continue
        return outcome
