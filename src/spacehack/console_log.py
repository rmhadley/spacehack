"""Full-run console history viewer.

The compact HUD log remains visible during play. This module exposes the
complete append-only history through the shared text-screen presentation.
"""
from __future__ import annotations

from .game_context import GameContext
from . import message_log, pygame_screen, pygame_ui


def _history_lines(log: message_log.MessageLog) -> tuple[tuple[str, tuple[int, int, int]], ...]:
    """Format the complete log as oldest-first modal lines with colors."""
    entries = log.history()
    if not entries:
        return (("No console messages yet.", message_log.COLOR_MESSAGE),)
    return tuple((f"> {entry.text}", entry.fg) for entry in entries)


def _frame(ctx: GameContext) -> pygame_screen.ScreenFrame:
    """Build the console history screen from the live log."""
    history = _history_lines(ctx.log)
    return pygame_screen.ScreenFrame(
        title="CONSOLE LOG",
        body=tuple(line for line, _color in history),
        rows=(),
        footer=(pygame_ui.modal_hint(
            "PAGE UP/DOWN or j/k scroll", "ESC close", pygame_ui.GUIDE_HINT,
        ),),
        scrollable=True,
        body_colors=tuple(color for _line, color in history),
    )


def open_console_log(ctx: GameContext) -> str:
    """Open the full console history until the player dismisses it."""
    while True:
        outcome, _action, _selected = pygame_screen.run_for_context(
            ctx.context,
            _frame(ctx),
            caption="spacehack - console log",
        )
        if outcome == "GUIDE":
            from .help import _run_help_guide
            _run_help_guide(ctx)
            continue
        return outcome
