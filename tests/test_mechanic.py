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

    def test_loadout_tab_matches_the_hangar_readout(self):
        """Doc 56 SETTLED 21: the mechanic tab carries the same overview
        + gear list as the hangar, with the Manage row kept on top —
        the letter grid lives only in the editor."""
        from src.spacehack.ship import StoredEquipment
        ctx = self._ctx((
            StoredEquipment("weapon", "light_laser", grid_x=0, grid_y=0),
            StoredEquipment("weapon", "light_missile", grid_x=1, grid_y=0),
        ))
        ctx.stats = SimpleNamespace(
            credits=1000, gunnery=10, piloting=10, engineering=10,
        )
        ctx.player_traits = []
        tabs = _mechanic._mechanic_tabs([1])
        loadout_index = tabs.index("LOADOUT")
        frame = _mechanic._mechanic_frame(
            ctx, find_ship("scout"), loadout_index, 0, tabs, [1],
        )

        assert frame.active_tab == loadout_index
        assert frame.scrollable is True  # full racks page, not shrink
        # The manage row leads under its own header...
        assert frame.rows[0].text == "PARTS MARKET"
        assert frame.rows[1].action == "LOADOUT"
        assert len(frame.rows) == 2
        # ...then the shared readout: overview numbers + the gear list.
        assert frame.body[0] == "OVERVIEW"
        assert frame.body[1].startswith("Hull ")
        assert "Light Laser - Dmg 4" in frame.body[4]
        assert "Light Missile - Dmg 14" in frame.body[5]
        assert not any("SLOTS" in line.upper() for line in frame.body)

    def test_ammo_rows_label_the_weapon_not_the_slot(self):
        # Doc 56 phase 3: "Slot n:" vocabulary retires with the slots.
        ctx = self._ctx(("light_laser", "light_missile"))
        row = _mechanic._ammo_row(ctx.player_owned_ship, 1, ctx)
        assert row.text.startswith("Light Missile")
        assert "Slot" not in row.text
        assert row.text.endswith("(4/4)")


class TestLoadoutWeaponQualityDisplay:
    """The flown instance's tier still reads on the loadout surfaces
    (user report 2026-09-28): the grid editor's hover readout and the
    parts market's rows scale to the instance (the letter itself
    colours by tier — pinned in test_grid_editor)."""

    def test_market_weapon_detail_scales_at_tier(self):
        from src.spacehack.data.weapons import find_weapon
        from src.spacehack.menus._grid_editor import _weapon_detail

        spec = find_weapon("medium_laser")
        assert "Dmg 8" in _weapon_detail(spec, quality=2)
        assert "Dmg 6" in _weapon_detail(spec)

    def test_stored_row_scales_damage_at_tier(self):
        """The parts market's STORAGE panel row scales its stat line to
        the stored instance's tier (reviewer catch 2026-09-28 — the
        tier-coloured name rode base stats one panel left of the
        mechanic tab)."""
        from src.spacehack.menus._loadout import _stored_row
        from src.spacehack.ship import StoredEquipment

        row = _stored_row(StoredEquipment("weapon", "medium_laser", quality=2), 0)
        assert "Dmg 8" in row.detail
