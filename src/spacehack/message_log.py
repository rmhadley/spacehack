"""The in-game console log.

The HUD shows only the most recent ``capacity`` entries, while the backing
history retains every entry for the player's full-run console viewer and
save/load round trips.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


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
    # Optional inline colour runs (quality item names, 2026-09-23):
    # the joined run text MUST equal ``text``; ``fg`` stays the line
    # colour for run-less painters and the fallback colour of any
    # run painted without one.
    runs: tuple[tuple[str, tuple[int, int, int]], ...] | None = None


_REPEAT_SUFFIX = re.compile(r"^(.*) x(\d+)$")


def prefixed_runs(entry, prefix: str = "> ") -> tuple | None:
    """Return an entry's runs with the console prefix prepended, or
    ``None`` for run-less entries (the shared builder for the message
    band and the console-history viewer; ``getattr`` keeps fake
    entries without ``runs`` working)."""
    runs = getattr(entry, "runs", None)
    if not runs:
        return None
    return ((prefix, tuple(entry.fg)), *runs)


def with_runs(
    *parts, base: tuple[int, int, int] = COLOR_MESSAGE,
) -> tuple[str, tuple[tuple[str, tuple[int, int, int]], ...] | None]:
    """Build ``(plain text, runs)`` for one log/screen line from parts.

    A part is a plain string or a ``(text, colour)`` run (as produced
    by ``data.quality.quality_mark``); plain parts paint at ``base``,
    which must match the line colour the entry is added with. When no
    part leaves ``base`` the line needs no runs and returns
    ``(text, None)`` — the painter's plain path. Adjacent same-colour
    parts merge so equivalent lines compare equal for coalescing.
    """
    runs: list[tuple[str, tuple[int, int, int]]] = []
    for part in parts:
        text, colour = part if isinstance(part, tuple) else (part, base)
        if colour is None:
            colour = base
        if runs and runs[-1][1] == colour:
            runs[-1] = (runs[-1][0] + text, colour)
        else:
            runs.append((text, colour))
    text = "".join(run_text for run_text, _colour in runs)
    if all(colour == base for _text, colour in runs):
        return text, None
    return text, tuple(runs)


def _repeat_parts(text: str) -> tuple[str, int]:
    """Split a displayed message into its base text and repeat count.

    Coalesced entries are stored as ``"<base> x<count>"``; this recovers
    both parts so a further repeat increments the count in place.
    """
    match = _REPEAT_SUFFIX.match(text)
    if match:
        return match.group(1), int(match.group(2))
    return text, 1


class MessageLog:
    """A log of recent in-game events.

    Consecutive identical messages (same text and color) are coalesced into
    a single entry with an ``x<count>`` suffix, e.g.
    ``"A wall blocks your path. x3"``.

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

    def add(self, msg: str, runs=None) -> None:
        """Append ``msg`` to the log with default color.

        ``runs`` (built by :func:`with_runs`) colours segments of the
        line; the joined run text must equal ``msg``.
        """
        self._append(msg, COLOR_MESSAGE, runs)

    def add_colored(self, msg: str, fg: tuple[int, int, int], runs=None) -> None:
        """Append ``msg`` with an explicit foreground color and optional
        inline runs."""
        self._append(msg, fg, runs)

    def _append(self, msg: str, fg: tuple[int, int, int], runs=None) -> None:
        """Append ``msg``, coalescing a consecutive identical repeat.

        When the previous entry shows the same message in the same color
        and the same runs, it is rewritten as ``"<msg> x<count>"``
        instead of growing the log.
        """
        if self._messages:
            last = self._messages[-1]
            base, count = _repeat_parts(last.text)
            if last.fg == fg and last.runs == runs and base == msg:
                last.text = f"{msg} x{count + 1}"
                return
        self._messages.append(MessageEntry(text=msg, fg=fg, runs=runs))

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



