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
