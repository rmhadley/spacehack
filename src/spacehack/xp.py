"""Player XP, leveling, and skill point allocation.

Owns the single entry point for all XP gains (:func:`add_xp`) and
the level-up logic (thresholds, skill point grants, trait triggers).

Design doc: ``docs/design/complete/02_DESIGN_XP_LEVELING.md``
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

# Skill points granted per level-up. Sized for six stats on the 0-100
# scale: 9 points x 29 levels = 261 total, enough for a dedicated
# L30 specialist to max out 3 of the 6 stats from a base-10 start
# (3 stats x ~85 points each).
SKILL_POINTS_PER_LEVEL: int = 9


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
        ctx.player_skill_points += SKILL_POINTS_PER_LEVEL

        _msg = f"Level {ctx.player_level}! {SKILL_POINTS_PER_LEVEL} skill points earned."
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

# All six skills (Gunnery/Piloting/Engineering + Reflexes/Strength/Stamina)
# cap at 100. The level cap of 30 limits how many points you can earn.
_SKILL_CAP: int = 100


def _apply_skill_point(ctx: GameContext, skill: str) -> bool:
    """Spend one skill point on *skill*.

    Ship skills (gunnery/piloting/engineering) route to ``ctx.stats``.
    Ground stats (reflexes/strength/stamina) route to ``ctx.ground_stats``.
    All six cap at 100.

    Each point adds +1. Returns True if spent, False if no points
    available or skill is at cap.
    """
    if ctx.player_skill_points <= 0:
        return False

    if skill in _GROUND_STAT_NAMES:
        _target = ctx.ground_stats
    else:
        _target = ctx.stats
    _cap = _SKILL_CAP

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
    return trait_id in getattr(ctx, "player_traits", ())


def sharpshooter_hit_bonus(ctx: GameContext) -> int:
    """Sharpshooter trait: +10% hit chance in combat."""
    return 10 if has_trait(ctx, "sharpshooter") else 0


def ace_pilot_ap_bonus(ctx: GameContext) -> int:
    """Ace Pilot trait: +1 AP per turn in combat."""
    return 1 if has_trait(ctx, "ace_pilot") else 0


def ground_damage_reduction(ctx: GameContext) -> int:
    """Juggernaut trait: reduce each incoming ground hit by 1."""
    return 1 if has_trait(ctx, "juggernaut") else 0


def apply_ground_damage_reduction(ctx: GameContext, damage: int) -> int:
    """Reduce one ground damage event without allowing zero damage."""
    return max(1, damage - ground_damage_reduction(ctx))


def ground_evade_bonus(ctx: GameContext) -> int:
    """Evasive trait: add a flat baseline dodge chance on the ground."""
    return 5 if has_trait(ctx, "evasive") else 0


def pack_mule_capacity_bonus(ctx: GameContext) -> int:
    """Pack Mule trait: add two reserve-pack slots."""
    return 2 if has_trait(ctx, "pack_mule") else 0


def ground_max_hp_bonus(ctx: GameContext) -> int:
    """Ironclad trait: add six maximum ground HP."""
    return 6 if has_trait(ctx, "ironclad") else 0


def systems_expert_power_bonus(ctx: GameContext) -> int:
    """Systems Expert trait: add ten maximum ship power."""
    return 10 if has_trait(ctx, "systems_expert") else 0


def demolitionist_splash_bonus(ctx: GameContext) -> int:
    """Demolitionist trait: add 25 percentage points to splash damage."""
    return 25 if has_trait(ctx, "demolitionist") else 0


def laser_specialist_hit_bonus(ctx: GameContext) -> int:
    """Laser Specialist trait: add 10% to laser hit chance."""
    return 10 if has_trait(ctx, "laser_specialist") else 0


def missileer_hit_bonus(ctx: GameContext) -> int:
    """Missileer trait: add 10% to missile hit chance."""
    return 10 if has_trait(ctx, "missileer") else 0


def plasma_savant_ap_discount(ctx: GameContext) -> int:
    """Plasma Savant trait: reduce plasma weapon AP cost by one."""
    return 1 if has_trait(ctx, "plasma_savant") else 0


# ---------------------------------------------------------------------------
# Trait qualification
# ---------------------------------------------------------------------------

_SKILL_FIELDS: frozenset[str] = frozenset({
    "gunnery", "piloting", "engineering", "reflexes", "strength", "stamina",
})
_GROUND_SKILL_FIELDS: frozenset[str] = frozenset({"reflexes", "strength", "stamina"})


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
                _target = (
                    getattr(ctx, "ground_stats", None)
                    if _field in _GROUND_SKILL_FIELDS else ctx.stats
                )
                if _target is None:
                    _met = False
                    break
                if getattr(_target, _field, 0) < _min:
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
