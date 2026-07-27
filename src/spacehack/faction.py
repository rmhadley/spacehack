"""Faction reputation: attitude determination from reputation scores.

Provides a single :func:`get_attitude` helper that maps a faction's
reputation score to an attitude string (``"hostile"``, ``"neutral"``,
or ``"friendly"``).  All call sites that need to decide whether a
specific NPC ship is hostile/neutral/friendly to the player route
through this function rather than hardcoding ``faction == 'pirate'``.

Default reputation thresholds (from DESIGN_NPC_SHIPS_COMMS.md):

    -100 to -51  → hostile
     -50 to  50  → neutral
      51 to 100  → friendly

The defaults on :attr:`GameContext.faction_reputation` are chosen so
that the initial state matches the hardcoded assumptions pirates were
previously treated with (all pirates hostile, everyone else neutral).
"""

from __future__ import annotations


def get_attitude(reputation: int) -> str:
    """Return ``"hostile"``, ``"neutral"``, or ``"friendly"`` for a
    given reputation score.

    Pure function — no I/O, no context dependency.  Callers are
    expected to look up the faction's reputation from
    ``ctx.faction_reputation[faction]`` themselves and pass the
    score here.
    """
    if reputation <= -51:
        return "hostile"
    if reputation >= 51:
        return "friendly"
    return "neutral"
