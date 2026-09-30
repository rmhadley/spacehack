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

from tests.support.module_entries import module_entry

from src.spacehack.ship import (
    total_ammo_cargo,
    hull_integrity_pct,
    hull_cur_max,
    effective_speed,
    effective_max_cargo,
    smuggler_hold_capacity,
    _sell_price,
    ship_display_name,
)

# ship.py functions use local imports from data modules at call time.
# Mock the source modules, not the ship module itself. The bonus-reading
# helpers resolve modules through data.quality.effective_module_spec
# (doc 47.3), so that binding is the patch point for spec mocks.
_MODULE_PATCH = "src.spacehack.data.modules.find_module"
_EFFECTIVE_PATCH = "src.spacehack.data.quality.effective_module_spec"
_SHIP_PATCH = "src.spacehack.ship.find_ship"


def _module(module_id: str, quality: int = 0):
    """One installed-module entry (the OwnedShip.modules shape)."""
    return module_entry(module_id, quality)


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
        with mock.patch(_EFFECTIVE_PATCH, return_value=_SPEED_MOCK):
            assert effective_speed(cat, owned) == 5

    def test_with_module(self):
        cat = SimpleNamespace(speed=5)
        owned = SimpleNamespace(modules=(_module("compact_reactor"),))
        with mock.patch(_EFFECTIVE_PATCH, return_value=_SPEED_MOCK):
            assert effective_speed(cat, owned) == 7

    def test_min_1(self):
        cat = SimpleNamespace(speed=0)
        owned = SimpleNamespace(modules=())
        with mock.patch(_EFFECTIVE_PATCH, return_value=_SPEED_MOCK):
            assert effective_speed(cat, owned) == 1


# ---------------------------------------------------------------------------
# effective_max_cargo
# ---------------------------------------------------------------------------

_CARGO_MOCK = SimpleNamespace(cargo_bonus=30)


class TestEffectiveMaxCargo:
    def test_base_only(self):
        cat = SimpleNamespace(max_cargo=100)
        owned = SimpleNamespace(modules=())
        with mock.patch(_EFFECTIVE_PATCH, return_value=_CARGO_MOCK):
            assert effective_max_cargo(cat, owned) == 100

    def test_with_module(self):
        cat = SimpleNamespace(max_cargo=100)
        owned = SimpleNamespace(modules=(_module("expanded_cargo"),))
        with mock.patch(_EFFECTIVE_PATCH, return_value=_CARGO_MOCK):
            assert effective_max_cargo(cat, owned) == 130

    def test_min_0(self):
        cat = SimpleNamespace(max_cargo=0)
        owned = SimpleNamespace(modules=())
        with mock.patch(_EFFECTIVE_PATCH, return_value=_CARGO_MOCK):
            assert effective_max_cargo(cat, owned) == 0


# ---------------------------------------------------------------------------
# smuggler_hold_capacity
# ---------------------------------------------------------------------------

_SMUGGLE_MOCK = SimpleNamespace(smuggler_cargo=10)


class TestSmugglerHoldCapacity:
    def test_no_modules(self):
        owned = SimpleNamespace(modules=())
        with mock.patch(_EFFECTIVE_PATCH, return_value=_SMUGGLE_MOCK):
            assert smuggler_hold_capacity(owned) == 0

    def test_with_smuggler(self):
        owned = SimpleNamespace(modules=(_module("smuggler_hold"),))
        with mock.patch(_EFFECTIVE_PATCH, return_value=_SMUGGLE_MOCK):
            assert smuggler_hold_capacity(owned) == 10


# ---------------------------------------------------------------------------
# _sell_price
# ---------------------------------------------------------------------------

class TestSellPrice:
    """50% of buy price, minimum 1 credit; module tiers scale it."""

    def test_weapon(self):
        """light_laser: price=30 → 15."""
        assert _sell_price("weapon", "light_laser") == 15

    def test_module(self):
        """compact_reactor: price=50 → 25."""
        assert _sell_price("module", "compact_reactor") == 25

    def test_module_quality_scales_half_catalog(self):
        """shield_mk2 (150): 75 base; 86/98/109/165 across the ladder
        (doc 47.3 SETTLED 4 — the armory formula, half-up)."""
        assert _sell_price("module", "shield_mk2") == 75
        assert _sell_price("module", "shield_mk2", 1) == 86   # 86.75
        assert _sell_price("module", "shield_mk2", 2) == 98   # 97.5 -> 98
        assert _sell_price("module", "shield_mk2", 3) == 109  # 109.25
        assert _sell_price("module", "shield_mk2", 4) == 165  # 165.5 -> 165

    def test_weapon_quality_scales_like_modules(self):
        """Flown weapons scale with their tier (doc 48.7 player side) —
        the module formula, half-up. light_laser (30): 15 base, 22 at
        tier 3."""
        assert _sell_price("weapon", "light_laser") == 15
        assert _sell_price("weapon", "light_laser", 3) == 22

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
# hull_cur_max
# ---------------------------------------------------------------------------

class TestHullCurMax:
    """Status displays show hull as cur/max points, matching combat math."""

    def test_pristine_returns_full_max(self):
        assert hull_cur_max(
            SimpleNamespace(ship_id="scout", modules=(), hull_damage_pct=0),
            SimpleNamespace(base_hull=25),
        ) == (25, 25)

    def test_damage_reduces_current_floor_at_one(self):
        assert hull_cur_max(
            SimpleNamespace(ship_id="scout", modules=(), hull_damage_pct=25),
            SimpleNamespace(base_hull=25),
        ) == (18, 25)
        assert hull_cur_max(
            SimpleNamespace(ship_id="scout", modules=(), hull_damage_pct=100),
            SimpleNamespace(base_hull=25),
        ) == (1, 25)  # combat floors current at 1

    def test_module_max_hull_bonus_raises_max(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.data.quality.effective_module_spec",
            lambda _mid, _quality=0, _seed=None: SimpleNamespace(max_hull_bonus=10),
        )
        owned = SimpleNamespace(
            ship_id="scout", modules=(_module("some_armor"),), hull_damage_pct=0,
        )
        assert hull_cur_max(owned, SimpleNamespace(base_hull=25)) == (35, 35)

    def test_unknown_module_ids_are_skipped(self):
        from src.spacehack.data.quality import effective_module_spec

        try:
            effective_module_spec("no_such_module")
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError from effective_module_spec")
        assert hull_cur_max(
            SimpleNamespace(
                ship_id="scout", modules=(_module("no_such_module"),), hull_damage_pct=0,
            ),
            SimpleNamespace(base_hull=30),
        ) == (30, 30)


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


class TestWeaponQualityPass:
    """Flown weapons are quality-bearing instances (doc 48.7 player
    side): bare ids normalize to base entries, tiers survive
    save/load, install, and store-back."""

    def test_bare_ids_normalize_to_base_entries(self):
        from src.spacehack.ship import OwnedShip

        owned = OwnedShip(ship_id="starter", weapons=("light_laser",))
        assert len(owned.weapons) == 1
        assert owned.weapons[0].item_id == "light_laser"
        assert owned.weapons[0].quality == 0

    def test_parse_weapon_entry_shapes(self):
        from src.spacehack.ship import parse_weapon_entry

        assert parse_weapon_entry("light_laser").item_id == "light_laser"
        raised = parse_weapon_entry({"item_id": "heavy_laser", "quality": 2})
        assert (raised.item_id, raised.quality) == ("heavy_laser", 2)
        assert parse_weapon_entry({"item_id": "not_a_weapon"}) is None

    def test_save_round_trip_preserves_weapon_quality(self):
        from src.spacehack import saveload
        from src.spacehack.ship import OwnedShip, StoredEquipment

        owned = OwnedShip(
            ship_id="starter",
            weapons=(StoredEquipment("weapon", "medium_laser", quality=2),),
        )
        rebuilt = saveload._parse_owned_ship({
            "player_owned_ship": saveload._d(owned),
        })
        assert rebuilt.weapons[0].item_id == "medium_laser"
        assert rebuilt.weapons[0].quality == 2

    def test_legacy_save_with_bare_weapon_ids_migrates_to_base(self):
        from src.spacehack import saveload

        rebuilt = saveload._parse_owned_ship({
            "player_owned_ship": {"ship_id": "starter", "weapons": ["light_laser"]},
        })
        assert rebuilt.weapons[0].item_id == "light_laser"
        assert rebuilt.weapons[0].quality == 0

    def test_install_and_store_preserve_quality(self):
        from src.spacehack.data.ships import find_ship
        from src.spacehack.ship import (
            OwnedShip, StoredEquipment, install_stored_equipment, store_weapon,
        )

        owned = OwnedShip(ship_id="starter", weapons=(), modules=())
        spec = find_ship("starter")
        storage = [StoredEquipment("weapon", "heavy_laser", quality=2)]
        assert install_stored_equipment(owned, storage, 0, spec)
        assert owned.weapons[0].quality == 2
        assert store_weapon(owned, storage, 0)
        assert storage[0].item_id == "heavy_laser"
        assert storage[0].quality == 2
