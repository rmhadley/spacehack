"""Spec-sheet ledger tests for the ship-buy modal (doc 45 phase 3).

The modal body is a numbers-only ledger off the Ship spec with a
base-vs-base ``yours:`` comparison column; flow and outcome mapping
are pinned separately (test_pygame_ui, test_ship_purchase).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.spacehack import ship as ship_module
from src.spacehack.data.ships import find_ship, list_ships
from src.spacehack.menus import _ship_buy

_STAT_LABELS = (
    "Speed", "Hull", "Shields", "Power/turn",
    "Weapon slots", "Module slots", "Cargo", "Fuel tank",
)


def _ctx(owned_ship_id=None, credits=100_000):
    return SimpleNamespace(
        stats=SimpleNamespace(credits=credits),
        player_owned_ship=(
            ship_module.OwnedShip(ship_id=owned_ship_id)
            if owned_ship_id else None
        ),
    )


def _body(ship_id, owned_ship_id=None, effective_price=None):
    ship = find_ship(ship_id)
    return _ship_buy._ship_buy_body(
        _ctx(owned_ship_id), ship, effective_price, ship.price,
    )


def test_ledger_shows_every_spec_stat_line():
    lines = _body("cruiser")

    by_label = {
        label: next(line for line in lines if line.startswith(label))
        for label in _STAT_LABELS
    }
    assert "9 moves/day" in by_label["Speed"]
    assert "60" in by_label["Hull"]
    assert "25 + 3/turn" in by_label["Shields"]
    assert "5" in by_label["Power/turn"]
    assert "6" in by_label["Weapon slots"]
    assert "4" in by_label["Module slots"]
    assert "200" in by_label["Cargo"]
    assert "80" in by_label["Fuel tank"]


def test_compare_column_matches_owned_base_spec():
    lines = _body("cruiser", owned_ship_id="scout")

    by_label = {
        label: next(line for line in lines if line.startswith(label))
        for label in _STAT_LABELS
    }

    def _yours(label):
        return by_label[label].rsplit("yours: ", 1)[-1]

    scout = find_ship("scout")
    assert _yours("Speed") == f"{scout.speed} moves/day"
    assert _yours("Hull") == str(scout.base_hull)
    assert _yours("Shields") == f"{scout.base_shield_max} + {scout.base_shield_recharge}/turn"
    assert _yours("Power/turn") == str(scout.base_power_gen)
    assert _yours("Weapon slots") == str(scout.weapon_slots)
    assert _yours("Module slots") == str(scout.module_slots)
    assert _yours("Cargo") == str(scout.max_cargo)
    assert _yours("Fuel tank") == str(scout.max_fuel)


def test_shipless_buy_has_no_compare_column():
    lines = _body("cruiser")

    assert lines and not any("yours:" in line for line in lines)


def test_includes_lines_name_the_starting_loadout():
    lines = _body("cruiser")

    from src.spacehack.data.modules import find_module
    from src.spacehack.data.weapons import find_weapon

    weapons_line = next(line for line in lines if line.startswith("Includes: "))
    expected = ", ".join(
        find_weapon(item).name for item in find_ship("cruiser").start_weapons
    )
    assert expected in weapons_line
    assert any(
        find_module(item).name in line
        for line in lines
        for item in find_ship("cruiser").start_modules
    )


def test_shieldless_hull_shows_the_empty_marker():
    lines = _body("starter", owned_ship_id="cruiser")

    shield_line = next(line for line in lines if line.startswith("Shields"))
    offered = shield_line[len("Shields"):].split("yours: ", 1)[0].strip()
    assert offered == "-"
    assert shield_line.rsplit("yours: ", 1)[-1] == "25 + 3/turn"


@pytest.mark.parametrize("ship", list_ships(), ids=lambda ship: ship.id)
@pytest.mark.parametrize("owned_ship_id", [None, "scout"], ids=["shipless", "owning"])
def test_ledger_renders_for_the_whole_catalog(ship, owned_ship_id):
    lines = _body(ship.id, owned_ship_id=owned_ship_id)

    for label in _STAT_LABELS:
        assert any(line.startswith(label) for line in lines), (ship.id, label)
    assert all(ord(char) < 128 for line in lines for char in line)
    has_yours = any("yours:" in line for line in lines)
    assert has_yours == (owned_ship_id is not None)
