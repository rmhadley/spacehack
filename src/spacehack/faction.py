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
