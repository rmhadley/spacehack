"""Tests for faction.modify_rep — clamping, boundary crossing, zone transitions.

modify_rep mutates ctx.faction_reputation + ctx.log. The pure
computation — clamping to [-100, 100] and the get_attitude(old) !=
get_attitude(new) boundary check — is testable by mocking ctx.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.faction import modify_rep


def _mock_ctx(rep: dict[str, int] | None = None):
    ctx = MagicMock()
    ctx.faction_reputation = rep or {}
    ctx.log = MagicMock()
    return ctx


class TestSoftCap:
    """The +50 soft cap halves positive gains that push past 50."""

    def test_gains_fully_below_cap_pass_through(self):
        from src.spacehack.faction import _soft_cap_delta
        assert _soft_cap_delta(20, 10) == 10
        assert _soft_cap_delta(0, 50) == 50

    def test_gains_straddling_cap_split_full_then_half(self):
        from src.spacehack.faction import _soft_cap_delta
        # 1 full point to reach 50, then 3 more at half (round up): 1+2.
        assert _soft_cap_delta(49, 4) == 3
        # 10 full points to reach 50, then 10 more at half: 10+5.
        assert _soft_cap_delta(40, 20) == 15

    def test_gains_entirely_above_cap_halved(self):
        from src.spacehack.faction import _soft_cap_delta
        assert _soft_cap_delta(50, 20) == 10
        assert _soft_cap_delta(60, 10) == 5
        assert _soft_cap_delta(100, 6) == 3

    def test_negative_deltas_uncapped(self):
        from src.spacehack.faction import _soft_cap_delta
        assert _soft_cap_delta(80, -20) == -20
        assert _soft_cap_delta(0, -5) == -5

    def test_modify_rep_applies_cap_and_logs_applied_value(self):
        ctx = _mock_ctx({"merchant": 49})
        modify_rep(ctx, "merchant", 4)
        assert ctx.faction_reputation["merchant"] == 52  # 49 + 3, not 53


class TestTierScaledDelta:
    """Mission rep deltas scale by tier x1 / x1.25 / x1.5 / x1.75."""

    def test_tier_multipliers(self):
        from src.spacehack.mission._lifecycle import _tier_scaled_delta
        assert _tier_scaled_delta(4, 1) == 4   # x1
        assert _tier_scaled_delta(4, 2) == 5   # x1.25
        assert _tier_scaled_delta(4, 3) == 6   # x1.5
        assert _tier_scaled_delta(4, 4) == 7   # x1.75

    def test_negative_deltas_scale_symmetrically(self):
        from src.spacehack.mission._lifecycle import _tier_scaled_delta
        assert _tier_scaled_delta(-4, 4) == -7
        assert _tier_scaled_delta(-1, 3) == -2

    def test_rounds_half_away_from_zero(self):
        from src.spacehack.mission._lifecycle import _tier_scaled_delta
        assert _tier_scaled_delta(2, 3) == 3   # 3.0 exactly, no drift
        assert _tier_scaled_delta(1, 4) == 2   # 1.75 -> 2
        assert _tier_scaled_delta(3, 2) == 4   # 3.75 -> 4

    def test_tier_clamped_to_1_4(self):
        from src.spacehack.mission._lifecycle import _tier_scaled_delta
        assert _tier_scaled_delta(3, 0) == 3   # below 1 -> x1
        assert _tier_scaled_delta(3, 9) == 5   # above 4 -> x1.75


class TestModifyRep:
    def test_positive_delta(self):
        ctx = _mock_ctx({"pirate": -50})
        modify_rep(ctx, "pirate", 20)
        assert ctx.faction_reputation["pirate"] == -30
        ctx.log.add_colored.assert_called_once()

    def test_negative_delta(self):
        ctx = _mock_ctx({"merchant": 30})
        modify_rep(ctx, "merchant", -15)
        assert ctx.faction_reputation["merchant"] == 15

    def test_clamped_low(self):
        ctx = _mock_ctx({"pirate": -95})
        modify_rep(ctx, "pirate", -20)
        assert ctx.faction_reputation["pirate"] == -100

    def test_clamped_high(self):
        ctx = _mock_ctx({"militia": 95})
        modify_rep(ctx, "militia", 20)
        assert ctx.faction_reputation["militia"] == 100

    def test_zero_delta_noop(self):
        ctx = _mock_ctx({"pirate": -50})
        modify_rep(ctx, "pirate", 0)
        assert ctx.faction_reputation["pirate"] == -50
        ctx.log.add_colored.assert_not_called()

    def test_unknown_faction_noop(self):
        ctx = _mock_ctx({"pirate": -50})
        modify_rep(ctx, "unknown_faction", 10)
        assert "unknown_faction" not in ctx.faction_reputation

    def test_boundary_crossing(self):
        """Crossing from disliked to neutral triggers zone-transition log."""
        ctx = _mock_ctx({"merchant": -30})  # disliked (-26 is threshold)
        modify_rep(ctx, "merchant", 10)  # → -20 (neutral)
        assert ctx.faction_reputation["merchant"] == -20
        # Verify boundary was crossed: old=-30 (disliked), new=-20 (neutral)
        msg = ctx.log.add_colored.call_args[0][0]
        assert "now -20" in msg
        assert "Disliked" in msg  # old zone
        assert "Neutral" in msg   # new zone

    def test_no_boundary_crossing(self):
        """Staying in same zone doesn't mention a transition."""
        ctx = _mock_ctx({"merchant": -50})  # disliked
        modify_rep(ctx, "merchant", 10)  # → -40 (still disliked)
        msg = ctx.log.add_colored.call_args[0][0]
        assert "now -40" in msg
        assert "→" not in msg  # no zone transition

    def test_boundary_crossing_allied_to_liked(self):
        ctx = _mock_ctx({"militia": 80})  # allied
        modify_rep(ctx, "militia", -10)  # → 70 (liked)
        msg = ctx.log.add_colored.call_args[0][0]
        assert "Allied" in msg
        assert "Liked" in msg
