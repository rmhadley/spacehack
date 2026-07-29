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
    while True:
        _needed = _xp_to_next(ctx.player_level)
        if ctx.player_xp < xp_for_level(ctx.player_level) + _needed:
            break
        ctx.player_level += 1
        ctx.player_skill_points += 2

        _msg = f"Level {ctx.player_level}! 2 skill points earned."
        if ctx.player_level in (20, 30):
            _msg += " Choose a trait (C key)."
        ctx.log.add_colored(_msg, _ml.COLOR_COMBAT_EVENT)

        # Trait selection at milestones (deferred to Phase 4).
        if ctx.player_level in (20, 30):
            pass  # TODO: Phase 4 — _open_trait_selection(ctx)


# ---------------------------------------------------------------------------
# Skill point allocation
# ---------------------------------------------------------------------------

def _apply_skill_point(ctx: GameContext, skill: str) -> bool:
    """Spend one skill point on *skill* (gunnery/piloting/engineering).

    Each point adds +1. Soft-capped at 100. Returns True if the point
    was spent, False if no points available or skill is at cap.

    Updates both ``ctx.player_*_bonus`` (persistent counter) and
    ``ctx.stats`` (HudStats — single source of truth for combat/HUD).
    """
    if ctx.player_skill_points <= 0:
        return False

    _current = getattr(ctx.stats, skill, 0)
    if _current >= 100:
        return False  # soft cap

    _bonus_field = f"player_{skill}_bonus"
    _current_bonus = getattr(ctx, _bonus_field, 0)
    setattr(ctx, _bonus_field, _current_bonus + 1)
    ctx.player_skill_points -= 1

    # Keep ctx.stats in sync — combat + HUD read from here.
    setattr(ctx.stats, skill, _current + 1)
    return True


def has_trait(ctx: GameContext, trait_id: str) -> bool:
    """Check if the player has taken *trait_id*."""
    return trait_id in ctx.player_traits
