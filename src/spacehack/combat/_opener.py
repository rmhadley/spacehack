"""The Pirate opener's status plumbing (doc 49 SETTLED 5, migrated by
doc 103 Build A q4) — the ``fight`` duration class's first consumer.

The once-per-fight window is TWO collective statuses: the player-side
``pirate_opener`` on the player's container (consumed by the shared
fire loop at the player's first attack — the rules modules'
``mark_opener_spent``) and the enemy-side ``opener_window`` on EVERY
engaged enemy container (any enemy volley or attack consumes every
copy). The trait math itself (``xp.pirate_opener_*``) is UNCHANGED
pure bool-param functions; the rules modules derive the bool pair
here and pass it through.

Why one shared module: the collective window's apply / consume /
read law must never drift between the two rules modules, the three
stamp sites, and the blast read — the ground/space twin-pair risk.
"""

from __future__ import annotations

from . import _statuses
from ..data.statuses import OPENER_WINDOW_ID, PIRATE_OPENER_ID


def flags(enemies, player_container) -> tuple[bool, bool]:
    """``(enemy_fired, opener_spent)`` for the trait math: the enemy
    side closed when NOT every engaged enemy still holds its copy
    (consume removes every copy at once, so all-hold means nobody has
    fired; dead instances stay in the state lists and a death never
    closed today's window; an EMPTY list reads window-open — today's
    fresh-fight default); the player side spent when the status is
    gone (never applied reads spent — the trait gate dominates)."""
    return (
        not window_open(enemies),
        not _statuses.has(player_container, PIRATE_OPENER_ID),
    )


def window_open(enemies) -> bool:
    """Whether no enemy has fired yet: every engaged enemy still holds
    the collective window status."""
    return all(
        _statuses.has(_enemy.statuses, OPENER_WINDOW_ID)
        for _enemy in enemies
    )


def arm(ctx, enemies, theater: str) -> None:
    """Fight-init application — only where the trait arms (doc 103
    q4's positive modeling: window-open statuses from fight
    construction; a fresh fight's flags are both False, so arming
    reduces to the trait check)."""
    from ..xp import pirate_opener_armed

    if not pirate_opener_armed(ctx, enemy_fired=False, opener_spent=False):
        return
    _container = getattr(ctx, "active_statuses", None)
    if _container is not None:
        _statuses.apply(_container, PIRATE_OPENER_ID, theater=theater)
    grant_window(enemies, theater)


def grant_window(instances, theater: str) -> None:
    """Apply the enemy-side window status to each instance."""
    for _inst in instances:
        _statuses.apply(_inst.statuses, OPENER_WINDOW_ID, theater=theater)


def consume_player_window(player_container) -> None:
    """The player's first attack spends the player-side window (the
    ``mark_opener_spent`` implementations' body)."""
    _statuses.consume(player_container, PIRATE_OPENER_ID)


def consume_enemy_windows(enemies) -> None:
    """Any enemy volley or attack consumes EVERY copy — one collective
    window (the ``enemy_fired`` stamp sites' body). A consume on an
    instance that never held one (a post-close joiner) is a no-op."""
    for _enemy in enemies:
        _statuses.consume(_enemy.statuses, OPENER_WINDOW_ID)


def inherit(joined, enemies, theater: str) -> None:
    """A mid-fight joiner inherits the window status while the window
    is open: the collective read is ``every engaged enemy holds
    one``, so a joiner without a copy would read as an enemy volley
    that never happened — a bit-identity break, not a cosmetic one.
    ``enemies`` is the engaged set BEFORE the joins."""
    if window_open(enemies):
        grant_window(joined, theater)
