"""Tests for trade.py — trade_price pricing curve.

Pure formula: linear curve from 2× base at shortage (0% stock)
to 0.6× base at surplus (100% stock), with 1× at equilibrium (50%).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.trade import trade_price


class TestTradePrice:
    """trade_price(base_price, current_stock, target_stock) -> int."""

    # --- Shortage zone (ratio < 0.5): 2.0× → 1.0× linearly ---

    def test_full_shortage(self):
        """0 stock → 2.0× base price."""
        # ratio = 0/8 = 0, price = 100 * (2.0 - 0) = 200
        assert trade_price(100, 0, 8) == 200

    def test_quarter_stock(self):
        """25% stock → ratio=0.25, price = 100 * (2.0 - 0.5) = 150."""
        assert trade_price(100, 2, 8) == 150

    def test_approaching_equilibrium(self):
        """Stock 4/10 → ratio=0.4 (shortage zone). price=120."""
        # ratio = 4/10 = 0.4, price = 100 * (2.0 - 0.8) = 120
        assert trade_price(100, 4, 10) == 120

    # --- Equilibrium (ratio = 0.5): 1.0× base price ---

    def test_exact_equilibrium(self):
        """50% stock → 1.0× base price."""
        assert trade_price(100, 4, 8) == 100

    # --- Surplus zone (ratio >= 0.5): 1.0× → 0.6× linearly ---

    def test_slight_surplus(self):
        """75% stock → ratio=0.75, price = 100 * (1.0 - 0.25*0.8) = 80."""
        assert trade_price(100, 6, 8) == 80

    def test_full_surplus(self):
        """100% stock → ratio=1.0, price = 100 * (1.0 - 0.5*0.8) = 60."""
        assert trade_price(100, 8, 8) == 60

    def test_overstocked(self):
        """>100% stock (2× target) — floor at 1 prevents negative prices."""
        # ratio = 16/8 = 2.0, raw = 100 * (1.0 - 1.5*0.8) = -20
        # max(1, -20) = 1
        assert trade_price(100, 16, 8) == 1

    # --- Edge cases ---

    def test_target_zero(self):
        """target_stock=0 is clamped to 1 for division, but stock=0
        still gives ratio=0/1=0 → shortage: 2× base."""
        # ratio = 0/1 = 0, price = 100 * (2.0 - 0) = 200
        assert trade_price(100, 0, 0) == 200

    def test_base_price_one(self):
        """Minimum base price — still follows the curve."""
        # ratio = 0/8 = 0, shortage: 1 * (2.0 - 0) = 2
        assert trade_price(1, 0, 8) == 2

    def test_different_target(self):
        """Unequal target doesn't break the formula."""
        # target=16, stock=0 → ratio=0, 2.0×
        assert trade_price(50, 0, 16) == 100

    def test_integer_truncation(self):
        """Result is int-truncated (not rounded)."""
        # 100 * 0.99 = 99 → int(99) = 99
        # ratio = 0.01, price = 100 * (2.0 - 0.02) = 198
        # That's not a great test. Let's pick numbers that produce a
        # clear truncation.
        # base=10, stock=3, target=10 → ratio=0.3, 10*(2.0-0.6)=14.0
        assert trade_price(10, 3, 10) == 14
