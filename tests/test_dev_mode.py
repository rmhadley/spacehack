"""Tests for developer-only playtesting shortcuts."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import tcod.event

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.dev_mode import (
    advance_main_quest,
    apply_dev_ground_loadout,
    _best_ground_armor,
)
from src.spacehack.input_helpers import _is_shift_o_press


def _key_o(mod: int) -> tcod.event.KeyDown:
    """Build an O key event with the requested modifier mask."""
    return tcod.event.KeyDown(
        scancode=tcod.event.Scancode.O,
        sym=tcod.event.KeySym.O,
        mod=mod,
    )


def test_shift_o_predicate_requires_shift_modifier():
    """Only shifted O activates the dev shortcut."""
    _shift = tcod.event.Modifier.LSHIFT.value

    assert _is_shift_o_press(_key_o(_shift))
    assert _is_shift_o_press(_key_o(tcod.event.Modifier.RSHIFT.value))
    assert not _is_shift_o_press(_key_o(0))
    assert not _is_shift_o_press(SimpleNamespace())


def test_advance_main_quest_unlocks_mars_door_interaction():
    """The shortcut creates the exact prerequisite state for door opening."""
    _ctx = SimpleNamespace(
        main_quest_progress={},
        log=MagicMock(),
    )

    advance_main_quest(_ctx)

    assert _ctx.main_quest_progress == {
        "prologue_signal": "completed",
        "prologue_mars_unlocked": "completed",
        "prologue_mars_entrance": "completed",
        "prologue_seek_help": "completed",
        "prologue_open": "active",
    }
    _ctx.log.add.assert_called_once_with(
        "[DEV MODE] Act 0 skipped - the Mars door can now be opened."
    )


def test_best_ground_armor_selects_highest_defense_per_slot():
    """Developer armor selection covers every slot with strongest gear."""
    assert _best_ground_armor() == {
        "head": "heavy_helmet",
        "body": "heavy_vest",
        "hands": "tactical_gloves",
        "legs": "heavy_legs",
        "feet": "combat_boots",
    }


def test_dev_ground_loadout_equips_two_rifles_and_best_armor(monkeypatch):
    """Dev mode grants the complete ground loadout and logs it."""
    monkeypatch.setenv("SPACEHACK_DEV", "1")
    _ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        log=MagicMock(),
    )

    apply_dev_ground_loadout(_ctx)

    assert _ctx.equipped_ground_weapons == ["kinetic_rifle", "kinetic_rifle"]
    assert _ctx.equipped_ground_armor == {
        "head": "heavy_helmet",
        "body": "heavy_vest",
        "hands": "tactical_gloves",
        "legs": "heavy_legs",
        "feet": "combat_boots",
    }
    _ctx.log.add.assert_called_once_with(
        "[DEV MODE] Two kinetic rifles + best armor equipped."
    )


def test_dev_ground_loadout_does_nothing_without_dev_flag(monkeypatch):
    """Normal new games retain their default empty ground loadout."""
    monkeypatch.delenv("SPACEHACK_DEV", raising=False)
    _ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        log=MagicMock(),
    )

    apply_dev_ground_loadout(_ctx)

    assert _ctx.equipped_ground_weapons == []
    assert _ctx.equipped_ground_armor == {}
    _ctx.log.add.assert_not_called()


def test_advance_main_quest_does_not_reopen_completed_door():
    """Repeating the shortcut cannot move an already-open door backward."""
    _ctx = SimpleNamespace(
        main_quest_progress={"prologue_open": "completed"},
        log=MagicMock(),
    )

    advance_main_quest(_ctx)

    assert _ctx.main_quest_progress["prologue_open"] == "completed"
