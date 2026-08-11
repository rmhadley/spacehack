"""Mechanic terminal pricing tests (pure helpers in menus/_mechanic.py)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.data.ships import find_ship
from src.spacehack.menus import _mechanic
from src.spacehack.menus._mechanic import _REPAIR_COST_PCT, _repair_preview
from src.spacehack.ship import OwnedShip


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


class TestMechanicFrameTabs:
    """Tabbed mechanic frame: REPAIRS / AMMO / LOADOUT."""

    def _ctx(self, weapons):
        return SimpleNamespace(
            player_owned_ship=OwnedShip(ship_id="scout", weapons=weapons),
            stats=SimpleNamespace(credits=1000),
        )

    def test_repairs_tab_lists_refuel_and_repair(self):
        ctx = self._ctx(("light_laser",))
        tabs = _mechanic._mechanic_tabs([])
        frame = _mechanic._mechanic_frame(ctx, find_ship("scout"), 0, 0, tabs, [])

        assert tabs == ("REPAIRS", "LOADOUT")
        assert frame.active_tab == 0
        assert [row.action for row in frame.rows] == ["REFUEL", "REPAIR"]

    def test_ammo_tab_only_with_missile_launcher(self):
        ctx = self._ctx(("light_laser", "light_missile"))
        missile_slots = [1]
        tabs = _mechanic._mechanic_tabs(missile_slots)

        assert tabs == ("REPAIRS", "AMMO", "LOADOUT")
        frame = _mechanic._mechanic_frame(ctx, find_ship("scout"), 1, 0, tabs, missile_slots)
        assert frame.active_tab == 1
        assert frame.rows
        assert all(row.action.startswith("AMMO:") for row in frame.rows)

    def test_loadout_tab_shows_parts_and_manage_row(self):
        ctx = self._ctx(("light_laser", "light_missile"))
        tabs = _mechanic._mechanic_tabs([1])
        loadout_index = tabs.index("LOADOUT")
        frame = _mechanic._mechanic_frame(
            ctx, find_ship("scout"), loadout_index, 0, tabs, [1],
        )

        assert frame.active_tab == loadout_index
        assert any(row.action == "LOADOUT" for row in frame.rows)
        assert any("WEAPON SLOTS" in row.text for row in frame.rows)
