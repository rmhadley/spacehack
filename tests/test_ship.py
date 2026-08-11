"""Tests for ship.py — pure stat helper functions.

These compute derived stats from catalog lookups + owned ship state.
All are deterministic given their inputs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.ship import (
    total_ammo_cargo,
    hull_integrity_pct,
    effective_speed,
    effective_max_cargo,
    smuggler_hold_capacity,
    _sell_price,
    ship_display_name,
)

# ship.py functions use local imports from data modules at call time.
# Mock the source modules, not the ship module itself.
_MODULE_PATCH = "src.spacehack.data.modules.find_module"
_SHIP_PATCH = "src.spacehack.ship.find_ship"


# ---------------------------------------------------------------------------
# total_ammo_cargo
# ---------------------------------------------------------------------------

class TestTotalAmmoCargo:
    """Cargo used by missile ammo: cargo_per_round × ammo_capacity per weapon."""

    def test_empty(self):
        assert total_ammo_cargo(()) == 0

    def test_energy_only(self):
        """Energy weapons contribute 0 cargo."""
        # light_laser has slot_type="energy"
        assert total_ammo_cargo(("light_laser",)) == 0

    def test_missile(self):
        """light_missile: cargo_per_round=2, ammo_capacity=4 → 8."""
        assert total_ammo_cargo(("light_missile",)) == 8

    def test_mixed(self):
        """One energy + one missile."""
        assert total_ammo_cargo(("light_laser", "light_missile")) == 8

    def test_unknown_weapon(self):
        """Unknown IDs are skipped silently."""
        assert total_ammo_cargo(("nonexistent",)) == 0


# ---------------------------------------------------------------------------
# effective_speed
# ---------------------------------------------------------------------------

_SPEED_MOCK = SimpleNamespace(speed_bonus=2)


class TestEffectiveSpeed:
    def test_base_only(self):
        cat = SimpleNamespace(speed=5)
        owned = SimpleNamespace(modules=())
        with mock.patch(_MODULE_PATCH, return_value=_SPEED_MOCK):
            assert effective_speed(cat, owned) == 5

    def test_with_module(self):
        cat = SimpleNamespace(speed=5)
        owned = SimpleNamespace(modules=("compact_reactor",))
        with mock.patch(_MODULE_PATCH, return_value=_SPEED_MOCK):
            assert effective_speed(cat, owned) == 7

    def test_min_1(self):
        cat = SimpleNamespace(speed=0)
        owned = SimpleNamespace(modules=())
        with mock.patch(_MODULE_PATCH, return_value=_SPEED_MOCK):
            assert effective_speed(cat, owned) == 1


# ---------------------------------------------------------------------------
# effective_max_cargo
# ---------------------------------------------------------------------------

_CARGO_MOCK = SimpleNamespace(cargo_bonus=30)


class TestEffectiveMaxCargo:
    def test_base_only(self):
        cat = SimpleNamespace(max_cargo=100)
        owned = SimpleNamespace(modules=())
        with mock.patch(_MODULE_PATCH, return_value=_CARGO_MOCK):
            assert effective_max_cargo(cat, owned) == 100

    def test_with_module(self):
        cat = SimpleNamespace(max_cargo=100)
        owned = SimpleNamespace(modules=("expanded_cargo",))
        with mock.patch(_MODULE_PATCH, return_value=_CARGO_MOCK):
            assert effective_max_cargo(cat, owned) == 130

    def test_min_0(self):
        cat = SimpleNamespace(max_cargo=0)
        owned = SimpleNamespace(modules=())
        with mock.patch(_MODULE_PATCH, return_value=_CARGO_MOCK):
            assert effective_max_cargo(cat, owned) == 0


# ---------------------------------------------------------------------------
# smuggler_hold_capacity
# ---------------------------------------------------------------------------

_SMUGGLE_MOCK = SimpleNamespace(smuggler_cargo=10)


class TestSmugglerHoldCapacity:
    def test_no_modules(self):
        owned = SimpleNamespace(modules=())
        with mock.patch(_MODULE_PATCH, return_value=_SMUGGLE_MOCK):
            assert smuggler_hold_capacity(owned) == 0

    def test_with_smuggler(self):
        owned = SimpleNamespace(modules=("smuggler_hold",))
        with mock.patch(_MODULE_PATCH, return_value=_SMUGGLE_MOCK):
            assert smuggler_hold_capacity(owned) == 10


# ---------------------------------------------------------------------------
# _sell_price
# ---------------------------------------------------------------------------

class TestSellPrice:
    """50% of buy price, minimum 1 credit."""

    def test_weapon(self):
        """light_laser: price=30 → 15."""
        assert _sell_price("weapon", "light_laser") == 15

    def test_module(self):
        """compact_reactor: price=50 → 25."""
        assert _sell_price("module", "compact_reactor") == 25

    def test_min_1(self):
        """Item with price=1 → 0 after floor division, clamped to 1."""
        with mock.patch(_MODULE_PATCH, return_value=SimpleNamespace(price=1)):
            assert _sell_price("module", "cheap_item") == 1

    def test_unknown_item(self):
        assert _sell_price("weapon", "nonexistent") == 0

    def test_unknown_type(self):
        assert _sell_price("unknown", "anything") == 0


# ---------------------------------------------------------------------------
# hull_integrity_pct
# ---------------------------------------------------------------------------

class TestHullIntegrityPct:
    """100% minus hull damage, clamped to 0-100."""

    def test_pristine(self):
        assert hull_integrity_pct(SimpleNamespace(hull_damage_pct=0)) == 100

    def test_partial_damage(self):
        assert hull_integrity_pct(SimpleNamespace(hull_damage_pct=5)) == 95

    def test_destroyed(self):
        assert hull_integrity_pct(SimpleNamespace(hull_damage_pct=100)) == 0

    def test_missing_attr_is_pristine(self):
        assert hull_integrity_pct(SimpleNamespace()) == 100

    def test_negative_damage_clamped_to_full(self):
        assert hull_integrity_pct(SimpleNamespace(hull_damage_pct=-10)) == 100

    def test_damage_over_100_clamped_to_zero(self):
        assert hull_integrity_pct(SimpleNamespace(hull_damage_pct=150)) == 0


# ---------------------------------------------------------------------------
# ship_display_name
# ---------------------------------------------------------------------------


class TestShipDisplayName:
    def test_none(self):
        assert ship_display_name(None) == "Ship"

    def test_display_name(self):
        """Rolled name takes priority."""
        owned = SimpleNamespace(display_name="Ghost of Ceres", ship_id="scout_a")
        with mock.patch(_SHIP_PATCH, return_value=SimpleNamespace(name="Scout A")):
            assert ship_display_name(owned) == "Ghost of Ceres"

    def test_fallback_to_catalog(self):
        """No display_name → use catalog name."""
        owned = SimpleNamespace(display_name=None, ship_id="scout_a")
        with mock.patch(_SHIP_PATCH, return_value=SimpleNamespace(name="Scout A")):
            assert ship_display_name(owned) == "Scout A"

    def test_empty_display_name(self):
        """Empty string is falsy → falls back to catalog."""
        owned = SimpleNamespace(display_name="", ship_id="scout_a")
        with mock.patch(_SHIP_PATCH, return_value=SimpleNamespace(name="Scout A")):
            assert ship_display_name(owned) == "Scout A"
