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

from src.spacehack.trade import (
    _seed_economy,
    _target_stock_for,
    tick_economy,
    _good_headroom,
    _market_intel_enabled,
    _best_sell_planet,
    good_market_role,
    NEUTRAL_TARGET,
)


def _mock_ctx(economy_state=None):
    ctx = MagicMock()
    ctx.economy_state = economy_state or {}
    ctx.player_owned_ship = None
    return ctx


# ---------------------------------------------------------------------------
# good_market_role (demand / surplus / neutral classification)
# ---------------------------------------------------------------------------

class TestGoodMarketRole:
    def test_demand(self):
        spec = SimpleNamespace(demands=[("ore", 5)], produces=[])
        assert good_market_role(spec, "ore") == "demand"

    def test_surplus(self):
        spec = SimpleNamespace(demands=[], produces=[("food", 10)])
        assert good_market_role(spec, "food") == "surplus"

    def test_neutral(self):
        spec = SimpleNamespace(demands=[], produces=[])
        assert good_market_role(spec, "textiles") == "neutral"

    def test_dual_good_counts_as_demand(self):
        """A good in both lists is 'wanted' — the stronger selling cue."""
        spec = SimpleNamespace(demands=[("dual", 5)], produces=[("dual", 10)])
        assert good_market_role(spec, "dual") == "demand"


# ---------------------------------------------------------------------------
# _market_intel_enabled (merchant-rep gate on price cues)
# ---------------------------------------------------------------------------

class TestMarketIntelGate:
    def _ctx(self, rep):
        ctx = MagicMock()
        ctx.faction_reputation = {"merchant": rep}
        return ctx

    def test_negative_rep_withholds(self):
        assert _market_intel_enabled(self._ctx(-80)) is False
        assert _market_intel_enabled(self._ctx(-30)) is False

    def test_neutral_and_above_share(self):
        assert _market_intel_enabled(self._ctx(0)) is True
        assert _market_intel_enabled(self._ctx(40)) is True
        assert _market_intel_enabled(self._ctx(90)) is True

    def test_missing_reputation_defaults_to_neutral(self):
        ctx = SimpleNamespace(economy_state={})
        assert _market_intel_enabled(ctx) is True


# ---------------------------------------------------------------------------
# _good_headroom (liked-tier market detail)
# ---------------------------------------------------------------------------

class TestGoodHeadroom:
    def test_demand_room(self):
        ctx = _mock_ctx({"test_planet": {"ore": 5}})
        spec = SimpleNamespace(demands=[("ore", 25)], produces=[])
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec):
            assert _good_headroom(ctx, "test_planet", "ore") == \
                "Can absorb ~20 more units before prices cool."

    def test_demand_met(self):
        ctx = _mock_ctx({"test_planet": {"ore": 25}})
        spec = SimpleNamespace(demands=[("ore", 25)], produces=[])
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec):
            assert "cooling" in _good_headroom(ctx, "test_planet", "ore")

    def test_surplus_stock(self):
        ctx = _mock_ctx({"test_planet": {"food": 8}})
        spec = SimpleNamespace(demands=[], produces=[("food", 10)])
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec):
            assert _good_headroom(ctx, "test_planet", "food") == \
                "8 units in stock; prices stay low."

    def test_surplus_sold_out(self):
        ctx = _mock_ctx({"test_planet": {"food": 0}})
        spec = SimpleNamespace(demands=[], produces=[("food", 10)])
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec):
            assert "restocking" in _good_headroom(ctx, "test_planet", "food")

    def test_neutral_stable(self):
        ctx = _mock_ctx({"test_planet": {}})
        spec = SimpleNamespace(demands=[], produces=[])
        with mock.patch("src.spacehack.trade.find_planet_spec", return_value=spec):
            assert _good_headroom(ctx, "test_planet", "textiles") == "Stable market."


# ---------------------------------------------------------------------------
# _best_sell_planet (allied-tier guild-network routing)
# ---------------------------------------------------------------------------

class TestBestSellPlanet:
    def test_picks_highest_multiplier(self):
        ctx = _mock_ctx({})
        with mock.patch("src.spacehack.trade._can_sell_here", return_value=True), \
             mock.patch(
                 "src.spacehack.trade._price_multiplier",
                 side_effect=lambda _c, pid, _g: {"a": 1.2, "b": 1.8, "c": 1.0}[pid],
             ):
            assert _best_sell_planet(ctx, "earth", "ore", ["a", "b", "c"]) == "b"

    def test_skips_unsellable_contraband(self):
        ctx = _mock_ctx({})
        with mock.patch(
                "src.spacehack.trade._can_sell_here",
                side_effect=lambda pid, _g: pid != "b"), \
             mock.patch(
                 "src.spacehack.trade._price_multiplier",
                 side_effect=lambda _c, pid, _g: {"a": 1.2, "b": 1.8}[pid],
             ):
            assert _best_sell_planet(ctx, "earth", "weapons", ["a", "b"]) == "a"

    def test_none_when_nothing_sellable(self):
        ctx = _mock_ctx({})
        with mock.patch("src.spacehack.trade._can_sell_here", return_value=False):
            assert _best_sell_planet(ctx, "earth", "weapons", ["a", "b"]) is None


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
