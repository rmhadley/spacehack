"""Faction reputation: attitude determination from reputation scores.

Provides :func:`get_attitude` which maps a faction reputation score to
a five-zone attitude string (``"enemy"``, ``"disliked"``, ``"neutral"``,
``"liked"``, ``"allied"``), and :func:`starting_reputation` which computes
initial faction standings from the player's species + class combo.

Design doc: ``docs/design/in_progress/01_DESIGN_FACTION_REPUTATION.md``

Five-zone thresholds:

    -100 to -76  → enemy
     -75 to -26  → disliked
     -25 to +25  → neutral
     +26 to +75  → liked
     +76 to +100 → allied

Starting reputation is computed from species + class adjustment tables.
All call sites that need to decide whether a specific NPC ship is
hostile/neutral/friendly to the player route through :func:`get_attitude`
rather than hardcoding ``faction == 'pirate'``.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 5-zone attitude thresholds
# ---------------------------------------------------------------------------

def get_attitude(reputation: int) -> str:
    """Return ``"enemy"``, ``"disliked"``, ``"neutral"``, ``"liked"``,
    or ``"allied"`` for a given reputation score.

    Pure function — no I/O, no context dependency.  Callers are
    expected to look up the faction's reputation from
    ``ctx.faction_reputation[faction]`` themselves and pass the
    score here.
    """
    if reputation <= -76:
        return "enemy"
    if reputation <= -26:
        return "disliked"
    if reputation >= 76:
        return "allied"
    if reputation >= 26:
        return "liked"
    return "neutral"


# ---------------------------------------------------------------------------
# Starting reputation (species + class)
# ---------------------------------------------------------------------------

# Per-faction baseline before species/class adjustments.
# These represent the neutral starting point before character identity
# modifies them — pirates start deeply negative (everyone's enemies),
# militia start slightly positive (law-and-order baseline).
_DEFAULT_REP: dict[str, int] = {
    "pirate": -100,
    "merchant": 0,
    "civilian": 0,
    "militia": 50,
}

# Species adjustments (added on top of defaults + class).
_SPECIES_REP: dict[str, dict[str, int]] = {
    "human": {},  # humans get no faction adjustments
    "martian": {
        "militia": +10,   # Martians serve in system patrols
        "pirate": -10,     # Mariner Valley raids
    },
}

# Class adjustments (added on top of defaults + species).
_CLASS_REP: dict[str, dict[str, int]] = {
    "pirate": {
        "pirate": +30,
        "merchant": -10,
        "civilian": -10,
        "militia": -20,
    },
    "merchant": {
        "pirate": +10,
        "merchant": +10,
        "civilian": +5,
        "militia": +5,
    },
    "bounty_hunter": {
        "pirate": -20,
        "merchant": +5,
        "civilian": +5,
        "militia": +15,
    },
}

# All factions the system tracks (used to seed the dict with zeroes
# for any faction not covered by the adjustment tables).
_ALL_FACTIONS: tuple[str, ...] = ("pirate", "merchant", "civilian", "militia")

# Guild → faction mapping for mission board pay scaling.
# When a player talks to an NPC from guild X, the board's faction
# reputation determines the pay adjustment (never access).
_GUILD_FACTION: dict[str, str] = {
    "merchants": "merchant",
    "bhguild": "militia",   # bounty hunters work with militia/patrols
    "militia": "militia",
    "bar": "pirate",       # bar missions are pirate-aligned
    "lab": "civilian",
    "depot": "civilian",
}


def spec_is_hostile(ctx, spec) -> bool:
    """True if a ground NPC char spec is hostile toward the player.

    Monsters (``always_hostile=True``) are always hostile regardless
    of faction reputation — killing them must never touch rep. Everyone
    else follows the faction attitude zones (enemy/disliked).

    Duck-typed: callers may pass any spec object with
    ``always_hostile`` / ``faction`` attributes (e.g. an
    :class:`~spacehack.data.npc_chars.NpcCharSpec`). Shared by
    ``combat._encounter.detect_ground_combat`` and
    ``ground_npcs._is_hostile``.
    """
    if getattr(spec, "always_hostile", False):
        return True
    _rep = ctx.faction_reputation.get(getattr(spec, "faction", ""), 0)
    return get_attitude(_rep) in ("enemy", "disliked")


def starting_reputation(species_id: str, class_id: str) -> dict[str, int]:
    """Return the starting ``{faction: reputation}`` dict for a
    given species + class combo.

    Computed as::

        _DEFAULT_REP[faction] + species_adjustment + class_adjustment

    clamped to [-100, 100].  Unrecognised species/class ids fall
    through to zero adjustments (default starting rep).
    """
    sp_adj: dict[str, int] = _SPECIES_REP.get(species_id, {})
    cl_adj: dict[str, int] = _CLASS_REP.get(class_id, {})
    result: dict[str, int] = {}
    for faction in _ALL_FACTIONS:
        base = _DEFAULT_REP.get(faction, 0)
        adj = sp_adj.get(faction, 0) + cl_adj.get(faction, 0)
        result[faction] = max(-100, min(100, base + adj))
    return result


# ---------------------------------------------------------------------------
# Reputation change sources — delta tables
# ---------------------------------------------------------------------------

# Mission completion rep deltas, keyed by mission type (from MissionSpec.mission_type).
# Each entry maps faction -> delta. These are the BASE values at tier 1;
# the caller multiplies by a tier factor (x1 / x1.25 / x1.5 / x1.75 for
# tiers 1-4) and adds the early-completion bonus (+25%) on top. Values
# were halved in the reputation balance pass so rep accrues slowly;
# the +50 soft cap in modify_rep halves gains in the liked -> allied range.
_MISSION_REP_DELTAS: dict[str, dict[str, int]] = {
    "delivery": {
        "merchant": +2,
    },
    "bounty": {
        "pirate": -1,
        "merchant": +1,
        "civilian": +1,
        "militia": +2,
    },
    "intercept": {
        "pirate": +2,
        "merchant": -5,
        "civilian": -1,
        "militia": -2,
    },
    "smuggling": {
        "pirate": +1,
        "merchant": -2,
        "civilian": -2,
        "militia": -4,
    },
    "extortion": {
        "pirate": +2,
        "merchant": -2,
        "civilian": -1,
        "militia": -1,
    },
    "salvage": {
        "pirate": +1,
        "merchant": -1,
        "civilian": 0,
        "militia": -1,
    },
}

# Log message colours for rep changes.
_REP_GAIN_COLOR: tuple[int, int, int] = (100, 235, 115)    # green
_REP_LOSS_COLOR: tuple[int, int, int] = (255, 95, 95)      # red


# Combat rep deltas — keyed by the defeated enemy's faction (pirate, merchant,
# civilian, militia). Applied per-kill when an enemy ship is destroyed.
# Halved in the reputation-balance pass: pirate-killing used to be a
# universal faucet feeding militia/merchant/civilian bars at once, and
# killing lawmen needs to stay punitive but no longer grants huge pirate
# swings per kill. The +50 soft cap applies on top (see modify_rep).
_COMBAT_KILL_DELTAS: dict[str, dict[str, int]] = {
    "pirate": {
        "pirate": -1,
        "merchant": +1,
        "civilian": +1,
        "militia": +1,
    },
    "merchant": {
        "pirate": +2,
        "merchant": -4,
        "civilian": -1,
        "militia": -2,
    },
    "civilian": {
        "pirate": +2,
        "merchant": -2,
        "civilian": -4,
        "militia": -2,
    },
    "militia": {
        "pirate": +4,
        "merchant": -2,
        "civilian": -2,
        "militia": -6,
    },
}

# Unprovoked attack rep penalty — applied when the player initiates combat
# via comms ("Attack" option) rather than being auto-hailed or bumping into
# an enemy.
_COMBAT_UNPROVOKED_DELTAS: dict[str, int] = {
    "pirate": +2,
    "merchant": -2,
    "civilian": -2,
    "militia": -3,
}


# ---------------------------------------------------------------------------
# Mission pay adjustment
# ---------------------------------------------------------------------------

def guild_to_faction(guild: str) -> str:
    """Map a guild ID ("merchants", "bhguild", etc.) to its faction key.

    Returns "civilian" for unrecognised guilds so the player can always
    get *some* missions from unknown NPC types.
    """
    return _GUILD_FACTION.get(guild, "civilian")


def adjust_reward_pct(attitude: str) -> int:
    """Return the percentage modifier (can be negative) to apply to
    mission reward credits based on faction attitude.

    Pure function — no I/O, no context dependency. Mission ACCESS is
    never gated by reputation — standing only scales pay:

    * enemy → 0% (base pay — missions still offered)
    * disliked → -15%
    * neutral → 0%
    * liked → +10%
    * allied → +20%
    """
    _modifiers = {
        "enemy": 0,      # never reached — enemy = no missions
        "disliked": -15,
        "neutral": 0,
        "liked": +10,
        "allied": +20,
    }
    return _modifiers.get(attitude, 0)


# ---------------------------------------------------------------------------
# Monthly decay
# ---------------------------------------------------------------------------

_DECAY_RATES: dict[str, int] = {
    "enemy": +3,      # drift toward neutral from deep negative
    "disliked": +2,
    "neutral": 0,
    "liked": -2,
    "allied": -3,     # drift toward neutral from deep positive
}


def decay_rate(attitude: str) -> int:
    """Return the monthly rep drift for the given attitude zone.

    Pure function — no I/O, no context dependency.

    Positive values move reputation toward 0 from negative zones;
    negative values move toward 0 from positive zones.
    """
    return _DECAY_RATES.get(attitude, 0)


def apply_monthly_decay(ctx) -> None:
    """Apply one month of faction reputation decay toward neutral.

    Decay stops at the zone boundary to prevent crossing from
    positive to negative (or vice versa) through decay alone.
    Only player actions can change the sign of a reputation.
    """
    for _fac in _ALL_FACTIONS:
        _rep = ctx.faction_reputation.get(_fac, 0)
        _attitude = get_attitude(_rep)
        _drift = decay_rate(_attitude)
        if _drift == 0:
            continue
        # Stop at boundary: drift should never flip the sign.
        # Only player actions can change reputation from negative
        # to positive or vice versa.
        _new = _rep + _drift
        if _rep < 0 and _new >= 0:
            _new = -1
        elif _rep > 0 and _new <= 0:
            _new = 1
        if _new != _rep:
            modify_rep(ctx, _fac, _new - _rep)


# ---------------------------------------------------------------------------
# Trade price modifiers
# ---------------------------------------------------------------------------

_BUY_MODIFIERS: dict[str, float] = {
    "enemy": 1.0,       # can't trade — never reached
    "disliked": 1.0,    # can't trade — never reached
    "neutral": 1.0,
    "liked": 0.95,      # 5% discount
    "allied": 0.90,     # 10% discount
}

_SELL_MODIFIERS: dict[str, float] = {
    "enemy": 1.0,
    "disliked": 1.0,
    "neutral": 1.0,
    "liked": 1.05,      # 5% bonus
    "allied": 1.10,     # 10% bonus
}


def buy_price_modifier(attitude: str) -> float:
    """Return the multiplier for buy prices based on faction attitude.

    1.0 = no change, 0.95 = 5% discount, etc.
    """
    return _BUY_MODIFIERS.get(attitude, 1.0)


def sell_price_modifier(attitude: str) -> float:
    """Return the multiplier for sell prices based on faction attitude.

    1.0 = no change, 1.05 = 5% bonus, etc.
    """
    return _SELL_MODIFIERS.get(attitude, 1.0)


# ---------------------------------------------------------------------------
# modify_rep — central rep mutation helper
# ---------------------------------------------------------------------------

# Soft cap for positive reputation. Gains that would push the score
# above +50 are applied at half strength, so the upper half of each
# bar (liked → allied) is a deliberate, slow grind rather than a
# sprint. Negative reputation has no cap — villainy still moves fast.
_SOFT_CAP: int = 50


def _soft_cap_delta(current: int, delta: int) -> int:
    """Return ``delta`` with the portion landing above the +50 cap halved.

    Pure helper — no I/O. Gains fully below the cap pass through
    unchanged; gains straddling the cap are split (full below, half
    above, rounding the half portion up); gains entirely above the
    cap are halved.
    """
    if delta <= 0:
        return delta
    if current >= _SOFT_CAP:
        return (delta + 1) // 2
    _room = _SOFT_CAP - current
    if delta <= _room:
        return delta
    return _room + (delta - _room + 1) // 2


def modify_rep(ctx, faction: str, delta: int) -> None:
    """Apply a reputation delta to ``faction``, handling the +50 soft
    cap, clamping, logging, and zone-boundary crossing announcements.

    Mutates ``ctx.faction_reputation[faction]`` and appends to
    ``ctx.log``. A no-op if ``delta`` is zero or ``faction`` is
    not one of the four tracked factions.

    Positive gains are halved once they push the score above +50
    (see :func:`_soft_cap_delta`); losses and negative-direction
    movement are unchanged.

    Log format:
      Within same zone:  ``+5 rep with Merchant faction (now +23)``
      Crossing a boundary: ``-8 rep with Militia faction (now -15, Liked → Disliked)``
    """
    if delta == 0:
        return
    if faction not in _ALL_FACTIONS:
        return

    old_val: int = ctx.faction_reputation.get(faction, 0)
    old_attitude: str = get_attitude(old_val)

    if delta > 0:
        delta = _soft_cap_delta(old_val, delta)

    new_val: int = max(-100, min(100, old_val + delta))
    ctx.faction_reputation[faction] = new_val

    new_attitude: str = get_attitude(new_val)

    # Build log message.
    sign = "+" if delta > 0 else ""
    msg = f"{sign}{delta} rep with {faction.title()} faction (now {new_val:+d})"
    if new_attitude != old_attitude:
        msg += f", {old_attitude.title()} → {new_attitude.title()}"

    color = _REP_GAIN_COLOR if delta > 0 else _REP_LOSS_COLOR
    ctx.log.add_colored(msg, color)
