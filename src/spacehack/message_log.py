"""Bottom-of-screen message log.

The log keeps an unbounded list of strings, but only the last ``capacity``
are shown (and only the last ``capacity * 4`` are kept in memory so the
list can't grow without bound during a long run).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import tcod.console


# Bright cool-white for live messages, muted blue for less-emphasised
# log lines. Replaces the previous flat greys so the message log no
# longer blends into the HUD on a black background.
COLOR_MESSAGE: tuple[int, int, int] = (230, 230, 240)
COLOR_MESSAGE_DIM: tuple[int, int, int] = (100, 140, 150)         # desaturated teal (distinct from COLOR_INSTRUCTION's periwinkle)

# Combat log colors
COLOR_PLAYER_ACTION: tuple[int, int, int] = (100, 235, 115)       # bright green for player actions
COLOR_ENEMY_ACTION: tuple[int, int, int] = (255, 95, 95)          # bright red for enemy actions
COLOR_COMBAT_EVENT: tuple[int, int, int] = (255, 200, 80)         # gold for system events (combat start, victory, etc.)

# Alert / important-event color
COLOR_IMPORTANT_EVENT: tuple[int, int, int] = (255, 70, 70)       # bright red for non-combat alerts (sensor contacts, militia scans)


@dataclass
class MessageEntry:
    """A single log message with its foreground color."""
    text: str
    fg: tuple[int, int, int] = COLOR_MESSAGE


class MessageLog:
    """An append-only log of recent in-game events.

    Supports colored messages via :meth:`add_colored`. The plain
    :meth:`add` method uses :data:`COLOR_MESSAGE` for backward
    compatibility.

    Undersized tests only inspect the last entry; capacity controls
    the displayed slice (``recent(capacity)``).
    """

    #: Maximum number of messages to retain in memory.
    KEEP_BACKLOG: int = 64

    def __init__(self, capacity: int = 6) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._messages: deque[MessageEntry] = deque(maxlen=self.KEEP_BACKLOG)

    def add(self, msg: str) -> None:
        """Append ``msg`` to the log with default color."""
        self._messages.append(MessageEntry(text=msg, fg=COLOR_MESSAGE))

    def add_colored(self, msg: str, fg: tuple[int, int, int]) -> None:
        """Append ``msg`` with an explicit foreground color."""
        self._messages.append(MessageEntry(text=msg, fg=fg))

    def recent(self, n: int | None = None) -> list[MessageEntry]:
        """Return the last ``n`` entries, oldest first.

        ``n`` defaults to ``self.capacity`` for easy rendering.
        """
        n = n if n is not None else self.capacity
        if n <= 0:
            return []
        return list(self._messages)[-n:]

    def __len__(self) -> int:
        return len(self._messages)


def render_message_log(
    console: tcod.console.Console,
    log: MessageLog,
    *,
    screen_width: int,
    screen_height: int,
    capacity: int | None = None,
) -> None:
    """Paint the bottom ``log.capacity`` (or ``capacity``) rows of the
    screen with the most recent messages, oldest at the top row.

    Each message uses its own foreground color (set via
    :meth:`MessageLog.add_colored` or the default from
    :meth:`MessageLog.add`).
    """
    n = capacity if capacity is not None else log.capacity
    msg_y_top = screen_height - n

    entries = log.recent(n)
    # Pad with empty entries to always paint n rows so prior-frame text
    # from a longer historical log doesn't linger in the message area.
    padded: list[MessageEntry | None] = [None] * (n - len(entries)) + entries

    for i, entry in enumerate(padded):
        row = msg_y_top + i
        if entry is None or not entry.text:
            continue
        line = "> " + entry.text
        console.print(
            x=0,
            y=row,
            string=line,
            fg=entry.fg,
        )
