"""Tests for the game-clock helpers in time.py."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack.time import month_index


def test_month_index_combines_year_and_month():
    """A unique integer increases across month AND year rollovers."""
    assert month_index(SimpleNamespace(time_year=2200, time_month=1)) == 2200 * 12 + 1
    assert month_index(SimpleNamespace(time_year=2200, time_month=12)) == 2200 * 12 + 12
    assert month_index(SimpleNamespace(time_year=2201, time_month=1)) == 2201 * 12 + 1


def test_month_index_falls_back_to_start_date_for_light_doubles():
    """Missing clock fields resolve to the canonical 2200-01 start date."""
    assert month_index(SimpleNamespace()) == 2200 * 12 + 1
