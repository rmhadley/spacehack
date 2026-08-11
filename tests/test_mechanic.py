"""Mechanic terminal pricing tests (pure helpers in menus/_mechanic.py)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.data.ships import find_ship
from src.spacehack.menus._mechanic import _REPAIR_COST_PCT, _repair_preview


class TestRepairPreview:
    """Full repair = _REPAIR_COST_PCT% of ship value, scaled by damage."""

    def test_pristine_hull_is_free(self):
        owned = SimpleNamespace(hull_damage_pct=0)
        assert _repair_preview(owned, find_ship("starter")) == 0

    def test_skiff_full_repair_is_10_percent_of_value(self):
        # Skiff price 500: a 0->100 rebuild costs 50$, not the ship's value.
        owned = SimpleNamespace(hull_damage_pct=100)
        assert _repair_preview(owned, find_ship("starter")) == (
            find_ship("starter").price * _REPAIR_COST_PCT // 100
        )

    def test_partial_damage_scales_linearly(self):
        # 30% damage on a 500$ Skiff = 15$.
        owned = SimpleNamespace(hull_damage_pct=30)
        assert _repair_preview(owned, find_ship("starter")) == 15

    def test_scout_full_repair(self):
        # 50% damage on a 5000$ Scout = 250$.
        owned = SimpleNamespace(hull_damage_pct=50)
        assert _repair_preview(owned, find_ship("scout")) == 250

    def test_damage_clamped_to_100(self):
        owned = SimpleNamespace(hull_damage_pct=150)
        assert _repair_preview(owned, find_ship("starter")) == _repair_preview(
            SimpleNamespace(hull_damage_pct=100), find_ship("starter"),
        )

    def test_negative_damage_never_charges(self):
        owned = SimpleNamespace(hull_damage_pct=-10)
        assert _repair_preview(owned, find_ship("starter")) == 0
