"""The in-game console log.

The HUD shows only the most recent ``capacity`` entries, while the backing
history retains every entry for the player's full-run console viewer and
save/load round trips.
"""
from __future__ import annotations

from dataclasses import dataclass

from .framebuffer import FrameBuffer


# Readable neutral log text. Secondary lines are still visibly dimmer,
# but avoid dark blue so they remain legible against the black playfield.
COLOR_MESSAGE: tuple[int, int, int] = (255, 255, 250)
COLOR_MESSAGE_DIM: tuple[int, int, int] = (225, 235, 225)         # bright desaturated green-grey

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

    def __init__(self, capacity: int = 6) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._messages: list[MessageEntry] = []

    def add(self, msg: str) -> None:
        """Append ``msg`` to the log with default color."""
        self._messages.append(MessageEntry(text=msg, fg=COLOR_MESSAGE))

    def add_colored(self, msg: str, fg: tuple[int, int, int]) -> None:
        """Append ``msg`` with an explicit foreground color."""
        self._messages.append(MessageEntry(text=msg, fg=fg))

    def recent(self, n: int | None = None) -> list[MessageEntry]:
        """Return the last ``n`` entries, oldest first.

        ``n`` defaults to ``self.capacity`` for easy HUD rendering.
        """
        n = n if n is not None else self.capacity
        if n <= 0:
            return []
        return self._messages[-n:]

    def history(self) -> list[MessageEntry]:
        """Return the complete log history, oldest first."""
        return list(self._messages)

    def load_history(self, entries: list[MessageEntry]) -> None:
        """Replace the history with validated entries from a save file."""
        self._messages = list(entries)

    def __len__(self) -> int:
        return len(self._messages)


def render_message_log(
    console: FrameBuffer,
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
        line = ("> " + entry.text)[:max(0, screen_width)]
        console.print(
            x=0,
            y=row,
            string=line,
            fg=entry.fg,
        )
