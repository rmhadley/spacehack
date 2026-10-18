"""The status inspect window (doc 103 q7, Build B).

A scrollable frame of one subject's current statuses with their
descriptions — the player's own container directly, every live enemy
beside it. Opens on ``v`` in combat (the ruled "view" key); TAB
inside cycles the subject (you, then each live enemy — the
target-cycle muscle memory); ESC closes. Costs no turn (the
console-log modal shape).
"""

from __future__ import annotations

from . import pygame_screen, pygame_ui
from .data.statuses import find_status
from .game_context import GameContext
from .ui import COLOR_STATUS_BUFF, COLOR_STATUS_DEBUFF

# The dim description ink the shared screen palette already uses.
_DIM = pygame_ui.DEFAULT_PALETTE.description

_YOU = "YOU"


def _subjects(ctx: GameContext, rules) -> list[tuple[str, dict]]:
    """The inspectable (label, container) pairs: you first, then every
    live enemy in panel order."""
    pairs = [(_YOU, getattr(ctx, "active_statuses", None) or {})]
    for enemy in rules.get_enemies(ctx):
        pairs.append((enemy.name, getattr(enemy, "statuses", None) or {}))
    return pairs


def _subject_lines(container: dict) -> tuple[tuple[str, ...], tuple]:
    """One subject's body lines + per-line colors: each status renders
    its name (polarity-coloured) + remaining rounds, then its ruled
    description (dim). Rounds rows carry the countdown; the fight
    class has none to show (the label-only shape)."""
    lines: list[str] = []
    colors: list[tuple[int, int, int]] = []
    for status_id, active in list(container.items()):
        try:
            spec = find_status(status_id)
        except KeyError:
            continue  # retired-row save data: skipped like every read
        remaining = (
            f"  {active.remaining_turns}"
            if spec.duration_class == "rounds" else ""
        )
        lines.append(f"{spec.name}{remaining}")
        colors.append(
            COLOR_STATUS_BUFF if spec.polarity else COLOR_STATUS_DEBUFF,
        )
        if spec.description:
            lines.append(spec.description)
            colors.append(_DIM)
    if not lines:
        return ("No statuses.",), (_DIM,)
    return tuple(lines), tuple(colors)


def _frame(subject: str, container: dict) -> pygame_screen.ScreenFrame:
    """The scrollable frame for one subject (the ruled title shape)."""
    body, colors = _subject_lines(container)
    return pygame_screen.ScreenFrame(
        title=f"STATUSES - {subject}",
        body=body,
        rows=(),
        footer=(pygame_ui.modal_hint(
            "TAB next", "ESC close", pygame_ui.GUIDE_HINT,
        ),),
        scrollable=True,
        body_colors=colors,
    )


async def open_status_inspect(ctx: GameContext, rules) -> str:
    """Run the status window until dismissed; TAB cycles subjects.

    Returns the closing outcome ("QUIT" propagates like the console
    log's). The subject re-reads LIVE each cycle — a status that
    lands or expires while the window is open reads current on the
    next rebuild."""
    subjects = _subjects(ctx, rules)
    index = 0
    while True:
        label, container = subjects[index]
        outcome, _action, _selected = await pygame_screen.run_for_context(
            ctx.context,
            _frame(label, container),
            caption="spacehack - statuses",
        )
        if outcome == "QUIT":
            return "QUIT"
        if outcome == "GUIDE":
            from .help import _run_help_guide
            await _run_help_guide(ctx)
        elif outcome == "TAB":
            index += 1
        # ESC and anything else: closed.
        else:
            return outcome
        # The fight moved underneath the modal either way — rebuild
        # and clamp (a cycled-onto enemy may have died mid-window).
        subjects = _subjects(ctx, rules)
        index %= len(subjects)
