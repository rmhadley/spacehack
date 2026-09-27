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

# Hard level cap — the game guide states max level is 60.  Once the
# player hits this, XP still accumulates (for display) but no further
# level-ups or skill points are awarded.
MAX_PLAYER_LEVEL: int = 60

# Skill points granted per level-up. Sized for six stats on the 0-100
# scale: 5 points x 59 levels = 295 total, enough for a dedicated
# L60 specialist to max out 3 of the 6 stats from a base-10 start
# (3 stats x ~85 points each) with ~25 points left over. Fast Learner
# (doc 49's human origin trait) raises the grant to 6: 354 endgame.
SKILL_POINTS_PER_LEVEL: int = 5


def xp_for_level(level: int) -> int:
    """Return the XP required to reach *level* (cumulative)."""
    _total = 0
    for n in range(2, level + 1):
        _total += 40 + n * 25
    return _total


def _xp_to_next(level: int) -> int:
    """XP needed to reach the next level from the current one."""
    return 40 + (level + 1) * 25


# ---------------------------------------------------------------------------
# add_xp — single entry point for all XP gains
# ---------------------------------------------------------------------------

async def add_xp(ctx: GameContext, amount: int) -> None:
    """Award *amount* XP and handle level-ups.

    Called from mission completion, combat kills, and future XP sources.
    Logs the gain, checks for level-ups, and triggers trait selection at
    milestones 40 and 50. Level 60 is reserved for a future capstone
    trait (specialization based on the two traits locked in at 40/50).
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
        _points = fast_learner_skill_points(ctx)
        ctx.player_skill_points += _points

        _msg = f"Level {ctx.player_level}! {_points} skill points earned."
        if ctx.player_level in (40, 50):
            _msg += " Choose a trait (C key)."
        ctx.log.add_colored(_msg, _ml.COLOR_COMBAT_EVENT)

        # Trait selection at milestones (level 60 reserved for a future
        # capstone specialization built on the two traits chosen here).
        if ctx.player_level in (40, 50):
            from .trait_screen import open_trait_selection
            await open_trait_selection(ctx)


# ---------------------------------------------------------------------------
# Skill point allocation
# ---------------------------------------------------------------------------

# Ground stat names that route to ctx.ground_stats instead of ctx.stats.
_GROUND_STAT_NAMES: frozenset[str] = frozenset({"reflexes", "strength", "stamina"})

# All six skills (Gunnery/Piloting/Engineering + Reflexes/Strength/Stamina)
# cap at 100. The level cap of 60 limits how many points you can earn.
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


def ground_max_hp_total(ctx: GameContext) -> int:
    """The ONE ground max-HP formula (doc 49 SETTLED 3-A fold).

    ``20 + stamina//2 + worn-armor HP bonuses + Ironclad + the
    species hp_bonus`` — shared by combat init
    (``_rules_ground._player_hp_state``), new-game setup
    (``game_loop._configure_new_context``), and the balance harness so
    the three can never drift apart.
    """
    from .character import species_hp_bonus
    from .ground_equipment import sum_armor_bonus
    _species_id = (getattr(ctx, "character_info", None) or {}).get("species_id", "")
    return (
        20 + ctx.ground_stats.stamina // 2
        + sum_armor_bonus(ctx.equipped_ground_armor.values(), "hp_bonus")
        + ground_max_hp_bonus(ctx)
        + species_hp_bonus(_species_id)
    )


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
# Origin traits (doc 49) — granted by species at creation; mechanics
# read at the usage sites, same bonus-helper pattern as above.
# ---------------------------------------------------------------------------

def sturdy_armor_bonus(ctx: GameContext) -> int:
    """Sturdy origin trait: +2 armor defense, even with nothing worn."""
    return 2 if has_trait(ctx, "sturdy") else 0


def sturdy_melee_bonus(ctx: GameContext) -> int:
    """Sturdy origin trait: +2 flat melee damage (fists included)."""
    return 2 if has_trait(ctx, "sturdy") else 0


def nimble_ap_bonus(ctx: GameContext) -> int:
    """Nimble origin trait: +1 ground AP per round (stacks with Ace
    Pilot and cybernetic legs through the same bonus sum)."""
    return 1 if has_trait(ctx, "nimble") else 0


def momentum_hit_bonus(ctx: GameContext) -> int:
    """Momentum origin trait: +5% space hit chance, always on."""
    return 5 if has_trait(ctx, "momentum") else 0


def momentum_kill_refund(ctx: GameContext) -> bool:
    """Momentum origin trait: a space kill refunds the volley's AP cost."""
    return has_trait(ctx, "momentum")


def longshot_range_bonus(ctx: GameContext) -> int:
    """Longshot origin trait: +1 max range on ranged weapons (ground
    and space). Melee reach and min ranges never move."""
    return 1 if has_trait(ctx, "longshot") else 0


def fast_learner_skill_points(ctx: GameContext) -> int:
    """Fast Learner origin trait (doc 49): 6 skill points per level
    instead of 5 — a permanent lead, unlike an xp% bonus that
    converges at the level cap."""
    if has_trait(ctx, "fast_learner"):
        return SKILL_POINTS_PER_LEVEL + 1
    return SKILL_POINTS_PER_LEVEL


# ---------------------------------------------------------------------------
# Class traits (doc 49 phase 2) — granted by class at creation; mechanics
# read at the usage sites, same bonus-helper pattern as the origin traits.
# ---------------------------------------------------------------------------

# Pirate opener tuning knobs (SETTLED 5, playtest-tunable): the bonus on
# the player's first attack of an encounter while no enemy has fired.
PIRATE_OPENER_HIT_BONUS = 10    # percentage points of hit chance
PIRATE_OPENER_DAMAGE_PCT = 125  # damage multiplier, in percent


def pirate_smuggler_hold_bonus(ctx: GameContext) -> int:
    """Pirate class trait: +10 concealable volume on every ship (a
    flat term beside module bonuses and the epilogue perk's 10%)."""
    return 10 if has_trait(ctx, "pirate") else 0


def pirate_opener_armed(
    ctx: GameContext, *, enemy_fired: bool, opener_spent: bool,
) -> bool:
    """The Pirate opener window is open: the player holds the trait,
    no enemy has fired yet, and the first attack hasn't been spent
    (doc 49 SETTLED 5, ruling b — once per encounter, both theaters)."""
    return (
        has_trait(ctx, "pirate")
        and not enemy_fired
        and not opener_spent
    )


def pirate_opener_hit_bonus(
    ctx: GameContext, *, enemy_fired: bool, opener_spent: bool,
) -> int:
    """Pirate opener: the opening attack's hit bonus, else 0."""
    if pirate_opener_armed(ctx, enemy_fired=enemy_fired, opener_spent=opener_spent):
        return PIRATE_OPENER_HIT_BONUS
    return 0


def pirate_opener_damage_pct(
    ctx: GameContext, *, enemy_fired: bool, opener_spent: bool,
) -> int:
    """Pirate opener: the opening attack's damage multiplier in
    percent (100 = no bonus)."""
    if pirate_opener_armed(ctx, enemy_fired=enemy_fired, opener_spent=opener_spent):
        return PIRATE_OPENER_DAMAGE_PCT
    return 100


def merchant_cargo_bonus(ctx: GameContext) -> int:
    """Merchant class trait: +10 cargo on every ship (doc 49 SETTLED 6)."""
    return 10 if has_trait(ctx, "merchant") else 0


def merchant_buy_price_mod(ctx: GameContext) -> float:
    """Merchant class trait: -5% goods buy price (multiplies the
    attitude chain — a separate source from earned reputation)."""
    return 0.95 if has_trait(ctx, "merchant") else 1.0


def merchant_sell_price_mod(ctx: GameContext) -> float:
    """Merchant class trait: +5% goods sell price (multiplies the
    attitude chain; never compounds with the buy side — sell derives
    from the class-free buy core)."""
    return 1.05 if has_trait(ctx, "merchant") else 1.0


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
