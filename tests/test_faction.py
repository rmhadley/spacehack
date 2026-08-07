"""Tests for faction.py — attitude, starting reputation, modifier tables.

All functions here are pure (no context, no I/O) and are already
called out as testable in knowledge.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.faction import (
    get_attitude,
    starting_reputation,
    adjust_reward_pct,
    decay_rate,
    buy_price_modifier,
    sell_price_modifier,
    guild_to_faction,
)


# ---------------------------------------------------------------------------
# get_attitude
# ---------------------------------------------------------------------------

class TestGetAttitude:
    """Five-zone mapping: enemy ≤ -76 < disliked ≤ -26 < neutral < +26 ≤ liked < +76 ≤ allied."""

    def test_enemy(self):
        assert get_attitude(-100) == "enemy"
        assert get_attitude(-76) == "enemy"

    def test_disliked(self):
        assert get_attitude(-75) == "disliked"
        assert get_attitude(-26) == "disliked"

    def test_neutral(self):
        assert get_attitude(-25) == "neutral"
        assert get_attitude(0) == "neutral"
        assert get_attitude(25) == "neutral"

    def test_liked(self):
        assert get_attitude(26) == "liked"
        assert get_attitude(75) == "liked"

    def test_allied(self):
        assert get_attitude(76) == "allied"
        assert get_attitude(100) == "allied"


# ---------------------------------------------------------------------------
# starting_reputation
# ---------------------------------------------------------------------------

# Expected {faction: rep} for every species×class combo.
# Computed from: _DEFAULT_REP + _SPECIES_REP[species] + _CLASS_REP[class]
# clamped to [-100, 100].
_EXPECTED_STARTING_REP: dict[str, dict[str, dict[str, int]]] = {
    "human": {
        "pirate": {
            "pirate": -70, "merchant": -10, "civilian": -10, "militia": 30,
        },
        "merchant": {
            "pirate": -90, "merchant": 10, "civilian": 5, "militia": 55,
        },
        "bounty_hunter": {
            "pirate": -100, "merchant": 5, "civilian": 5, "militia": 65,
        },
    },
    "martian": {
        "pirate": {
            "pirate": -80, "merchant": -10, "civilian": -10, "militia": 40,
        },
        "merchant": {
            "pirate": -100, "merchant": 10, "civilian": 5, "militia": 65,
        },
        "bounty_hunter": {
            "pirate": -100, "merchant": 5, "civilian": 5, "militia": 75,
        },
    },
}


class TestStartingReputation:
    """Every species×class combo produces the expected faction standings."""

    def test_all_combos(self):
        for species, classes in _EXPECTED_STARTING_REP.items():
            for class_id, expected in classes.items():
                result = starting_reputation(species, class_id)
                for faction, rep in expected.items():
                    assert result[faction] == rep, (
                        f"{species} {class_id} vs {faction}: "
                        f"expected {rep}, got {result[faction]}"
                    )

    def test_unknown_ids_fallback(self):
        """Unrecognised species/class → zero adjustments, uses defaults."""
        result = starting_reputation("unknown_sp", "unknown_cl")
        # pirate: -100 + 0 + 0 = -100
        # merchant: 0
        # civilian: 0
        # militia: 50
        assert result["pirate"] == -100
        assert result["merchant"] == 0
        assert result["civilian"] == 0
        assert result["militia"] == 50

    def test_clamped_to_range(self):
        """No reputation exceeds [-100, 100]."""
        result = starting_reputation("martian", "bounty_hunter")
        for faction, rep in result.items():
            assert -100 <= rep <= 100, f"{faction} rep {rep} out of range"


# ---------------------------------------------------------------------------
# adjust_reward_pct
# ---------------------------------------------------------------------------

class TestAdjustRewardPct:
    def test_enemy(self):
        assert adjust_reward_pct("enemy") == 0

    def test_disliked(self):
        assert adjust_reward_pct("disliked") == -15

    def test_neutral(self):
        assert adjust_reward_pct("neutral") == 0

    def test_liked(self):
        assert adjust_reward_pct("liked") == 10

    def test_allied(self):
        assert adjust_reward_pct("allied") == 20

    def test_unknown(self):
        assert adjust_reward_pct("nonexistent") == 0


# ---------------------------------------------------------------------------
# decay_rate
# ---------------------------------------------------------------------------

class TestDecayRate:
    def test_enemy_drifts_up(self):
        assert decay_rate("enemy") == 3

    def test_disliked_drifts_up(self):
        assert decay_rate("disliked") == 2

    def test_neutral_no_drift(self):
        assert decay_rate("neutral") == 0

    def test_liked_drifts_down(self):
        assert decay_rate("liked") == -2

    def test_allied_drifts_down(self):
        assert decay_rate("allied") == -3

    def test_unknown(self):
        assert decay_rate("nonexistent") == 0


# ---------------------------------------------------------------------------
# buy_price_modifier / sell_price_modifier
# ---------------------------------------------------------------------------

class TestBuyPriceModifier:
    def test_neutral(self):
        assert buy_price_modifier("neutral") == 1.0

    def test_liked(self):
        assert buy_price_modifier("liked") == 0.95

    def test_allied(self):
        assert buy_price_modifier("allied") == 0.90

    def test_unknown(self):
        assert buy_price_modifier("nonexistent") == 1.0


class TestSellPriceModifier:
    def test_neutral(self):
        assert sell_price_modifier("neutral") == 1.0

    def test_liked(self):
        assert sell_price_modifier("liked") == 1.05

    def test_allied(self):
        assert sell_price_modifier("allied") == 1.10

    def test_unknown(self):
        assert sell_price_modifier("nonexistent") == 1.0


# ---------------------------------------------------------------------------
# guild_to_faction
# ---------------------------------------------------------------------------

class TestGuildToFaction:
    def test_merchants(self):
        assert guild_to_faction("merchants") == "merchant"

    def test_bhguild(self):
        assert guild_to_faction("bhguild") == "militia"

    def test_militia(self):
        assert guild_to_faction("militia") == "militia"

    def test_bar(self):
        assert guild_to_faction("bar") == "pirate"

    def test_lab(self):
        assert guild_to_faction("lab") == "civilian"

    def test_depot(self):
        assert guild_to_faction("depot") == "civilian"

    def test_unknown_fallback(self):
        assert guild_to_faction("nonexistent") == "civilian"
