"""Tests for trade.py economy functions — seeding, stock drift.

tick_economy drifts toward target by ±1 per tick. Wrong by 1 is
invisible to manual playtesting for dozens of trades.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.trade import _seed_economy, _target_stock_for, tick_economy, NEUTRAL_TARGET


def _mock_ctx(economy_state=None):
    ctx = MagicMock()
    ctx.economy_state = economy_state or {}
    ctx.player_owned_ship = None
    return ctx


# ---------------------------------------------------------------------------
# _seed_economy
# ---------------------------------------------------------------------------

class TestSeedEconomy:
    def test_seeds_produced_at_target(self):
        """Produced goods start at their target stock (surplus)."""
        spec = SimpleNamespace(
            produces=[("food", 10), ("water", 8)],
            demands=[],
        )
        ctx = _mock_ctx()
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec), \
             mock.patch("src.spacehack.trade.neutral_goods", return_value=[]):
            _seed_economy(ctx, "test_planet")
            assert ctx.economy_state["test_planet"]["food"] == 10
            assert ctx.economy_state["test_planet"]["water"] == 8

    def test_seeds_demanded_at_zero(self):
        """Demanded goods start at 0 (shortage)."""
        spec = SimpleNamespace(produces=[], demands=[("ore", 5)])
        ctx = _mock_ctx()
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec), \
             mock.patch("src.spacehack.trade.neutral_goods", return_value=[]):
            _seed_economy(ctx, "test_planet")
            assert ctx.economy_state["test_planet"]["ore"] == 0

    def test_seeds_neutral_at_half_target(self):
        """Neutral goods start at NEUTRAL_TARGET // 2 (equilibrium)."""
        spec = SimpleNamespace(produces=[], demands=[])
        ctx = _mock_ctx()
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec), \
             mock.patch("src.spacehack.trade.neutral_goods", return_value=["electronics"]):
            _seed_economy(ctx, "test_planet")
            assert ctx.economy_state["test_planet"]["electronics"] == NEUTRAL_TARGET // 2

    def test_idempotent(self):
        """Second call does not overwrite existing state."""
        spec = SimpleNamespace(produces=[("food", 10)], demands=[])
        ctx = _mock_ctx({"test_planet": {"food": 7}})
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec), \
             mock.patch("src.spacehack.trade.neutral_goods", return_value=[]):
            _seed_economy(ctx, "test_planet")
            assert ctx.economy_state["test_planet"]["food"] == 7  # unchanged

    def test_demanded_does_not_overwrite_produced(self):
        """A good in both produces and demands keeps produced target."""
        spec = SimpleNamespace(
            produces=[("dual_good", 10)],
            demands=[("dual_good", 5)],
        )
        ctx = _mock_ctx()
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec), \
             mock.patch("src.spacehack.trade.neutral_goods", return_value=[]):
            _seed_economy(ctx, "test_planet")
            # Produced is processed first, demanded skips existing keys.
            assert ctx.economy_state["test_planet"]["dual_good"] == 10


# ---------------------------------------------------------------------------
# _target_stock_for
# ---------------------------------------------------------------------------

class TestTargetStockFor:
    def test_produced(self):
        spec = SimpleNamespace(produces=[("food", 10)], demands=[])
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec):
            assert _target_stock_for("test", "food") == 10

    def test_demanded(self):
        spec = SimpleNamespace(produces=[], demands=[("ore", 5)])
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec):
            assert _target_stock_for("test", "ore") == 5

    def test_neutral_fallback(self):
        spec = SimpleNamespace(produces=[], demands=[])
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec):
            assert _target_stock_for("test", "electronics") == NEUTRAL_TARGET


# ---------------------------------------------------------------------------
# tick_economy
# ---------------------------------------------------------------------------

class TestTickEconomy:
    def test_drift_toward_target(self):
        """Stock below target increases by 1."""
        ctx = _mock_ctx({"planet_a": {"food": 3}})
        with mock.patch("src.spacehack.trade._target_stock_for", return_value=8):
            tick_economy(ctx)
            assert ctx.economy_state["planet_a"]["food"] == 4

    def test_drift_toward_target_down(self):
        """Stock above target decreases by 1."""
        ctx = _mock_ctx({"planet_a": {"food": 12}})
        with mock.patch("src.spacehack.trade._target_stock_for", return_value=8):
            tick_economy(ctx)
            assert ctx.economy_state["planet_a"]["food"] == 11

    def test_at_target_no_drift(self):
        """Stock at target stays unchanged."""
        ctx = _mock_ctx({"planet_a": {"food": 8}})
        with mock.patch("src.spacehack.trade._target_stock_for", return_value=8):
            tick_economy(ctx)
            assert ctx.economy_state["planet_a"]["food"] == 8

    def test_clamped_to_target_when_close(self):
        """Stock within 1 of target snaps to target."""
        ctx = _mock_ctx({"planet_a": {"food": 7}})
        with mock.patch("src.spacehack.trade._target_stock_for", return_value=8):
            tick_economy(ctx)
            assert ctx.economy_state["planet_a"]["food"] == 8

    def test_multiple_planets(self):
        ctx = _mock_ctx({
            "planet_a": {"food": 5},
            "planet_b": {"water": 10},
        })
        def _fake_target(pid, gid):
            return {"planet_a": {"food": 8}, "planet_b": {"water": 6}}[pid][gid]
        with mock.patch("src.spacehack.trade._target_stock_for", side_effect=_fake_target):
            tick_economy(ctx)
            assert ctx.economy_state["planet_a"]["food"] == 6  # up toward 8
            assert ctx.economy_state["planet_b"]["water"] == 9  # down toward 6

    def test_unseeded_planets_skipped(self):
        ctx = _mock_ctx({})
        tick_economy(ctx)  # should not crash
        assert ctx.economy_state == {}
