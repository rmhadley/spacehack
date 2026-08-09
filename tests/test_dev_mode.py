"""Tests for developer-only playtesting shortcuts."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import tcod.event

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import src.spacehack.dev_mode as dev_mode
from src.spacehack.dev_mode import (
    advance_main_quest,
    apply_dev_ground_loadout,
    main_quest_faction_menu,
    _best_ground_armor,
    _dev_faction_label,
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


def test_main_quest_faction_menu_lists_all_four_chains():
    """The Act 0 shortcut exposes every normal faction path."""
    _menu = main_quest_faction_menu()

    assert _menu.options == (
        ("militia", "Militia"),
        ("merchants", "Merchants"),
        ("bar", "Free Captains"),
        ("lab", "Research Lab"),
    )
    assert set(_menu.descriptions) == {"militia", "merchants", "bar", "lab"}


def test_choose_main_quest_faction_delegates_to_picker(monkeypatch):
    """The UI wrapper returns the picker result without mutating game state."""
    _expected = (dev_mode.Outcome.CONFIRM, "lab")
    _seen = []

    def _fake_pick(context, menu):
        _seen.append((context, menu))
        return _expected

    monkeypatch.setattr(dev_mode, "_run_pick", _fake_pick)
    _context = object()

    assert dev_mode.choose_main_quest_faction(_context) == _expected
    assert _seen[0][0] is _context
    assert _seen[0][1].selected_id == "militia"


@pytest.mark.parametrize("faction_id", ("militia", "merchants", "bar", "lab"))
def test_advance_main_quest_records_selected_faction(faction_id):
    """The shortcut creates door state and mirrors normal faction lock-in."""
    _ctx = SimpleNamespace(
        main_quest_progress={},
        main_quest_chain="",
        main_quest_backing=set(),
        log=MagicMock(),
    )

    advance_main_quest(_ctx, faction_id)

    assert _ctx.main_quest_chain == faction_id
    assert _ctx.main_quest_backing == {faction_id}
    assert _ctx.main_quest_progress == {
        "prologue_signal": "completed",
        "prologue_mars_unlocked": "completed",
        "prologue_mars_entrance": "completed",
        "prologue_seek_help": "completed",
        "prologue_open": "active",
    }
    _ctx.log.add.assert_called_once_with(
        f"[DEV MODE] Act 0 skipped as {_dev_faction_label(faction_id)} - "
        "the Mars door can now be opened."
    )


def test_advance_main_quest_rejects_unknown_faction():
    """Invalid developer input cannot create an impossible quest chain."""
    _ctx = SimpleNamespace(
        main_quest_progress={},
        main_quest_chain="",
        main_quest_backing=set(),
        log=MagicMock(),
    )

    with pytest.raises(ValueError, match="Unknown developer faction"):
        advance_main_quest(_ctx, "pirates")


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
        main_quest_chain="militia",
        main_quest_backing={"militia"},
        log=MagicMock(),
    )

    advance_main_quest(_ctx, "militia")

    assert _ctx.main_quest_progress["prologue_open"] == "completed"
