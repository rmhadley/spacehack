"""Tests for developer-only playtesting shortcuts."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import tcod.event

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.dev_mode import advance_main_quest
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


def test_advance_main_quest_does_not_reopen_completed_door():
    """Repeating the shortcut cannot move an already-open door backward."""
    _ctx = SimpleNamespace(
        main_quest_progress={"prologue_open": "completed"},
        log=MagicMock(),
    )

    advance_main_quest(_ctx)

    assert _ctx.main_quest_progress["prologue_open"] == "completed"
