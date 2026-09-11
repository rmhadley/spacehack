"""Spanned spec-sheet tests for the ship-buy modal (doc 45 phase 3).

The sheet is a sectioned ledger with CP437-safe bar gauges (scaled
against the catalog's best per stat, ``|`` marking the player's ship)
and a base-vs-base ``yours:`` column coloured by trade verdict; paint
runs are the parallel colour view of the plain body lines. Flow and
outcome mapping are pinned separately (test_pygame_ui,
test_ship_purchase).
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from src.spacehack import pygame_ui, ship as ship_module
from src.spacehack.data.ships import find_ship, list_ships
from src.spacehack.menus import _ship_buy

_SECTIONS = ("PERFORMANCE", "COMBAT", "CAPACITY")
_STAT_LABELS = (
    "Speed", "Fuel tank", "Hull", "Shields", "Power/turn",
    "Weapon slots", "Module slots", "Cargo",
)


def _ctx(owned_ship_id=None, credits=100_000):
    return SimpleNamespace(
        stats=SimpleNamespace(credits=credits),
        player_owned_ship=(
            ship_module.OwnedShip(ship_id=owned_ship_id)
            if owned_ship_id else None
        ),
    )


def _frame(ship_id, owned_ship_id=None, effective_price=None):
    ship = find_ship(ship_id)
    return _ship_buy._ship_buy_frame(
        _ctx(owned_ship_id), ship, effective_price, 0,
    )


def _stat_line(body, label):
    return next(
        line for line in body if line.lstrip().startswith(label)
    )


def _offered_value(body, label):
    """The value column: text between the label and the 10-cell bar."""
    match = re.search(
        rf"\s*{re.escape(label)}\s+(.*?)\s*[#|-]{{10}}", "\n".join(body),
    )
    assert match, label
    return match.group(1)


def test_ledger_shows_sections_and_every_spec_stat():
    frame = _frame("cruiser")

    for section in _SECTIONS:
        assert section in frame.body
    for label in _STAT_LABELS:
        assert _stat_line(frame.body, label)
    assert _offered_value(frame.body, "Speed") == "9 moves/day"
    assert _offered_value(frame.body, "Hull") == "60"
    assert _offered_value(frame.body, "Shields") == "25 + 3/turn"
    assert _offered_value(frame.body, "Cargo") == "200"


def test_compare_column_matches_owned_base_spec():
    frame = _frame("cruiser", owned_ship_id="scout")
    scout = find_ship("scout")

    def _yours(label):
        line = _stat_line(frame.body, label)
        return line.rsplit("yours: ", 1)[-1]

    assert _yours("Speed") == str(scout.speed)
    assert _yours("Fuel tank") == str(scout.max_fuel)
    assert _yours("Hull") == str(scout.base_hull)
    assert _yours("Shields") == f"{scout.base_shield_max} + {scout.base_shield_recharge}/turn"
    assert _yours("Power/turn") == str(scout.base_power_gen)
    assert _yours("Weapon slots") == str(scout.weapon_slots)
    assert _yours("Module slots") == str(scout.module_slots)
    assert _yours("Cargo") == str(scout.max_cargo)


def test_shipless_buy_has_no_compare_column_and_no_marker():
    frame = _frame("cruiser")

    assert not any("yours:" in line for line in frame.body)
    stat_lines = [
        line for line in frame.body
        if line.lstrip().startswith(_STAT_LABELS)
    ]
    assert len(stat_lines) == len(_STAT_LABELS)
    assert not any("|" in line for line in stat_lines)


def test_includes_lines_name_the_starting_loadout():
    frame = _frame("cruiser")

    from src.spacehack.data.modules import find_module
    from src.spacehack.data.weapons import find_weapon

    cruiser = find_ship("cruiser")
    expected_weapons = ", ".join(
        find_weapon(item).name for item in cruiser.start_weapons
    )
    assert any(
        line == f"Includes: {expected_weapons}" for line in frame.body
    )
    assert any(
        find_module(item).name in line
        for line in frame.body
        for item in cruiser.start_modules
    )


def test_shieldless_hull_shows_the_empty_marker():
    frame = _frame("starter", owned_ship_id="cruiser")

    assert _offered_value(frame.body, "Shields") == "-"
    shields = _stat_line(frame.body, "Shields")
    assert shields.rsplit("yours: ", 1)[-1] == "25 + 3/turn"


def test_trade_in_frame_keeps_body_and_runs_aligned():
    frame = _frame("freighter", owned_ship_id="starter", effective_price=5000)

    assert any("Trade-in value: 35000$" in line for line in frame.body)
    # The appended trade-in line rides a None run: parallel lengths hold.
    assert len(frame.body_runs) == len(frame.body)
    assert frame.body_runs[frame.body.index(
        next(line for line in frame.body if line.startswith("Trade-in"))
    )] is None


def test_stat_bar_scales_fill_and_marker_against_catalog_best():
    assert _ship_buy._stat_bar(9, 10, 14) == "######-|--"
    assert _ship_buy._stat_bar(14, 14, 14) == "#########|"  # yours clamps
    assert _ship_buy._stat_bar(0, 0, 40) == "|---------"
    assert _ship_buy._stat_bar(25, None, 40) == "######----"  # no marker


def test_verdict_colors_rank_gain_regression_and_equal():
    palette = pygame_ui.DEFAULT_PALETTE

    assert _ship_buy._verdict_color(61, 60) is palette.positive
    assert _ship_buy._verdict_color(59, 60) is palette.negative
    assert _ship_buy._verdict_color(60, 60) is palette.muted


def test_verdict_colors_paint_the_yours_runs():
    frame = _frame("cruiser", owned_ship_id="starter")
    palette = pygame_ui.DEFAULT_PALETTE

    def _yours_run_color(label):
        index = frame.body.index(_stat_line(frame.body, label))
        yours_run = next(
            run for run in frame.body_runs[index] if run[0].startswith("yours:")
        )
        return yours_run[1]

    assert _yours_run_color("Speed") is palette.negative      # 9 vs 10
    assert _yours_run_color("Fuel tank") is palette.muted     # 80 vs 80
    assert _yours_run_color("Hull") is palette.positive       # 60 vs 15
    assert _yours_run_color("Shields") is palette.positive    # 25 vs 0


@pytest.mark.parametrize("ship", list_ships(), ids=lambda ship: ship.id)
@pytest.mark.parametrize("owned_ship_id", [None, "scout"], ids=["shipless", "owning"])
def test_sheet_renders_aligned_for_the_whole_catalog(ship, owned_ship_id):
    frame = _frame(ship.id, owned_ship_id=owned_ship_id)

    for label in _STAT_LABELS:
        assert _stat_line(frame.body, label), (ship.id, label)
    assert all(ord(char) < 128 for line in frame.body for char in line)
    has_yours = any("yours:" in line for line in frame.body)
    assert has_yours == (owned_ship_id is not None)
    # Paint runs are the parallel view: every run line concatenates
    # to exactly its plain body line (the no-drift invariant).
    assert len(frame.body_runs) <= len(frame.body)
    for line, runs in zip(frame.body, frame.body_runs):
        if runs is not None:
            assert "".join(text for text, _color in runs) == line


def test_body_runs_survive_unwrapped_and_drop_when_wrapped():
    from src.spacehack.pygame_screen import (
        ScreenFrame, _body_lines_with_colors,
    )
    from tests.support.fake_pygame import FakeFont

    font = FakeFont(char_width=10)  # 10px per char
    runs = (("hello ", (1, 2, 3)), ("world", (4, 5, 6)))
    frame = ScreenFrame(
        title="T", body=("hello world", "x" * 25), rows=(),
        body_runs=(runs, (("wrapped", (7, 8, 9)),)),
    )

    built = _body_lines_with_colors(font, frame, 115)

    # "hello world" (11 chars = 110px) fits one line: runs survive.
    assert built[0] == ("hello world", None, runs)
    # The 25-char line (250px) wraps: its runs paint plain.
    assert len(built) > 2
    assert all(entry[2] is None for entry in built[1:])
