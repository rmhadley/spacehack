"""Randart generator tests (doc 47 phase 4).

Determinism is the contract: a randart is its seed — the same seed +
module recomposes the identical manifest forever (SETTLED 21's
stable-composition lineage).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.spacehack.data import randarts
from src.spacehack.data.modules import ModuleSpec


def test_roll_randart_is_deterministic_per_seed_and_module():
    for module_id in ("shield_mk1", "reactor_mk2", "smuggler_hold_mk3"):
        for seed in (1, 42, 2**30):
            first = randarts.roll_randart(module_id, seed)
            second = randarts.roll_randart(module_id, seed)
            assert first == second


def test_roll_randart_differs_across_seeds():
    names = {
        randarts.roll_randart("shield_mk1", seed).name
        for seed in range(30)
    }
    assert len(names) > 1


def test_roll_randart_axes_count_is_two_to_four():
    for seed in range(40):
        axes = randarts.roll_randart("targeting_computer", seed).axes
        assert 2 <= len(axes) <= 4


def test_roll_randart_axes_are_distinct_fields_in_range_and_nonzero():
    lows = {field: low for field, low, _high in randarts.RANDART_AXES}
    highs = {field: high for field, _low, high in randarts.RANDART_AXES}
    for seed in range(40):
        axes = randarts.roll_randart("shield_capacitor", seed).axes
        fields = [field for field, _delta in axes]
        assert len(set(fields)) == len(fields)
        for field, delta in axes:
            assert lows[field] <= delta <= highs[field]
            assert delta != 0


def test_randart_axes_cover_every_module_bonus_field():
    """The axes table is one signed entry per ModuleSpec bonus field —
    a field the table misses could never roll."""
    bonus_fields = {
        field.name
        for field in ModuleSpec.__dataclass_fields__.values()
        if field.name.endswith("_bonus") or field.name == "smuggler_cargo"
    }
    assert {field for field, _low, _high in randarts.RANDART_AXES} == bonus_fields
    assert set(randarts.AXIS_LABELS) == {
        field for field, _low, _high in randarts.RANDART_AXES
    }


@pytest.mark.parametrize("low,high", [(-2, 4), (-10, 30), (-1, 2), (5, 25), (1, 3)])
def test_roll_delta_spans_its_range_and_skips_zero(low, high):
    class _Seq:
        """Deterministic full-span walk."""

        def __init__(self):
            self.next = 0

        def randrange(self, span):
            roll = self.next % span
            self.next += 1
            return roll

    seq = _Seq()
    seen = {
        randarts._roll_delta(seq, low, high)
        for _ in range((high - low + 1) * 4)
    }
    assert seen == {
        value for value in range(low, high + 1) if value != 0
    }


def test_drawback_axes_can_roll_and_so_can_pure_boons():
    """SETTLED 20: mixed signs — some seeds land a negative axis,
    some land all-positive spreads."""
    signs = {
        any(delta < 0 for _field, delta in randarts.roll_randart("shield_mk1", seed).axes)
        for seed in range(60)
    }
    assert signs == {True, False}


def test_axis_line_matches_the_detail_row_voice():
    assert randarts.axis_line("max_shield_bonus", 6) == "+6 max shields"
    assert randarts.axis_line("power_gen_bonus", -1) == "-1 power generated per turn"


@pytest.mark.parametrize(
    "raw,expected",
    [(7, 7), ("123", 123), (None, None), (0, None), (-5, None), ("junk", None)],
)
def test_parse_randart_seed_migrates_malformed_values(raw, expected):
    assert randarts.parse_randart_seed(raw) == expected


def test_name_fragments_are_two_word_clean_pairings():
    """Every pool entry is a single CP437-safe word; the composed name
    is Prefix + Suffix."""
    for pool in (randarts.RANDART_PREFIXES, randarts.RANDART_SUFFIXES):
        for fragment in pool:
            assert fragment.isascii() and " " not in fragment
    manifest = randarts.roll_randart("shield_mk1", 3)
    prefix, suffix = manifest.name.split(" ")
    assert prefix in randarts.RANDART_PREFIXES
    assert suffix in randarts.RANDART_SUFFIXES
