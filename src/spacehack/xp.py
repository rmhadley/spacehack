"""Player XP, leveling, and skill point allocation.

Owns the single entry point for all XP gains (:func:`add_xp`) and
the level-up logic (thresholds, skill point grants, trait triggers).

Design doc: ``docs/design/in_progress/02_DESIGN_XP_LEVELING.md``
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_context import GameContext

from . import message_log as _ml


# ---------------------------------------------------------------------------
# Level thresholds
# ---------------------------------------------------------------------------

# Hard level cap — the game guide states max level is 30.  Once the
# player hits this, XP still accumulates (for display) but no further
# level-ups or skill points are awarded.
MAX_PLAYER_LEVEL: int = 30


def xp_for_level(level: int) -> int:
    """Return the XP required to reach *level* (cumulative)."""
    _total = 0
    for n in range(2, level + 1):
        _total += 50 + n * 20
    return _total


def _xp_to_next(level: int) -> int:
    """XP needed to reach the next level from the current one."""
    return 50 + (level + 1) * 20


# ---------------------------------------------------------------------------
# add_xp — single entry point for all XP gains
# ---------------------------------------------------------------------------

def add_xp(ctx: GameContext, amount: int) -> None:
    """Award *amount* XP and handle level-ups.

    Called from mission completion, combat kills, and future XP sources.
    Logs the gain, checks for level-ups, and triggers trait selection at
    milestones 20 and 30.
    """
    if amount <= 0:
        return

    ctx.player_xp += amount
    ctx.log.add_colored(f"+{amount} XP", _ml.COLOR_PLAYER_ACTION)

    # Check for level-ups (may gain multiple levels at once).
    while ctx.player_level < MAX_PLAYER_LEVEL:
        _needed = _xp_to_next(ctx.player_level)
        if ctx.player_xp < xp_for_level(ctx.player_level) + _needed:
            break
        ctx.player_level += 1
        ctx.player_skill_points += 2

        _msg = f"Level {ctx.player_level}! 2 skill points earned."
        if ctx.player_level in (20, 30):
            _msg += " Choose a trait (C key)."
        ctx.log.add_colored(_msg, _ml.COLOR_COMBAT_EVENT)

        # Trait selection at milestones.
        if ctx.player_level in (20, 30):
            from .trait_screen import open_trait_selection
            open_trait_selection(ctx)


# ---------------------------------------------------------------------------
# Skill point allocation
# ---------------------------------------------------------------------------

# Ground stat names that route to ctx.ground_stats instead of ctx.stats.
_GROUND_STAT_NAMES: frozenset[str] = frozenset({"reflexes", "strength", "stamina"})

# Caps for ship skills vs ground stats.
_SHIP_SKILL_CAP: int = 100
_GROUND_STAT_CAP: int = 30


def _apply_skill_point(ctx: GameContext, skill: str) -> bool:
    """Spend one skill point on *skill*.

    Ship skills (gunnery/piloting/engineering) route to ``ctx.stats``
    and cap at 100. Ground stats (reflexes/strength/stamina) route to
    ``ctx.ground_stats`` and cap at 30.

    Each point adds +1. Returns True if spent, False if no points
    available or skill is at cap.
    """
    if ctx.player_skill_points <= 0:
        return False

    if skill in _GROUND_STAT_NAMES:
        _target = ctx.ground_stats
        _cap = _GROUND_STAT_CAP
    else:
        _target = ctx.stats
        _cap = _SHIP_SKILL_CAP

    _current = getattr(_target, skill, 0)
    if _current >= _cap:
        return False

    _bonus_field = f"player_{skill}_bonus"
    _current_bonus = getattr(ctx, _bonus_field, 0)
    setattr(ctx, _bonus_field, _current_bonus + 1)
    ctx.player_skill_points -= 1

    # Update the source-of-truth container.
    setattr(_target, skill, _current + 1)
    return True


def has_trait(ctx: GameContext, trait_id: str) -> bool:
    """Check if the player has taken *trait_id*."""
    return trait_id in ctx.player_traits


# ---------------------------------------------------------------------------
# Trait qualification
# ---------------------------------------------------------------------------

_SKILL_FIELDS: frozenset[str] = frozenset({"gunnery", "piloting", "engineering"})


def _qualifying_traits(ctx: GameContext) -> list:
    """Return traits the player qualifies for (not already chosen).

    Scans :data:`data.traits.core.ALL_TRAITS`, checks each trait's
    counter requirements against ``ctx.player_counters`` (for
    playstyle counters) and ``ctx.stats`` (for skill fields like
    gunnery). Excludes traits already in ``ctx.player_traits``.
    """
    from .data.traits.core import ALL_TRAITS
    _qualified: list = []
    _have = set(ctx.player_traits)
    for _trait in ALL_TRAITS:
        if _trait.id in _have:
            continue
        _met = True
        for _field, _min in _trait.counters:
            if _field in _SKILL_FIELDS:
                if getattr(ctx.stats, _field, 0) < _min:
                    _met = False
                    break
            else:
                if getattr(ctx.player_counters, _field, 0) < _min:
                    _met = False
                    break
        if _trait.rep_required is not None:
            _faction, _attitude = _trait.rep_required
            from .faction import get_attitude as _ga
            _rep = ctx.faction_reputation.get(_faction, 0)
            if _ga(_rep) != _attitude:
                _met = False
        if _met:
            _qualified.append(_trait)
    return _qualified
