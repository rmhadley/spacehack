"""The status inspect window (doc 103 q7, Build B): the subject
lines, the frame shape, and the keymap ruling (v = the window, the
card toggle on e). Pure presentation-data pins — the modal itself is
the shared pygame_screen vehicle the console log already exercises.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.combat import _loop, _statuses
from src.spacehack.status_inspect import (
    _CYCLE_FOOTER, _DIM, _frame, _subject_lines, _subjects,
)
from src.spacehack.ui import COLOR_STATUS_BUFF, COLOR_STATUS_DEBUFF


def test_subject_lines_render_name_remaining_description():
    player = {}
    _statuses.apply(player, "staggered")
    _statuses.apply(player, "regen")

    lines, colors = _subject_lines(player)

    assert lines == (
        "Staggered  2", "-1 AP per round.",
        "Regeneration  3", "+2 HP per round.",
    )
    assert colors == (
        COLOR_STATUS_DEBUFF, _DIM,
        COLOR_STATUS_BUFF, _DIM,
    )


def test_subject_lines_fight_class_is_label_only():
    """The HUD's label-only shape carries into the window: a
    fight-class row has no countdown to show."""
    player = {}
    _statuses.apply(player, "pirate_opener")

    lines, colors = _subject_lines(player)

    assert lines == (
        "Pirate Opener", "+10% hit and +25% damage on your first attack this fight.",
    )
    assert colors[0] == COLOR_STATUS_BUFF


def test_subject_lines_empty_state_is_the_ruled_line():
    lines, colors = _subject_lines({})
    assert lines == ("No statuses.",)  # ledger #13
    assert len(colors) == 1


def test_subject_lines_skip_retired_row_ids():
    player = {"retired_row": _statuses.ActiveStatus("retired_row", 3)}
    assert _subject_lines(player)[0] == ("No statuses.",)


def test_frame_carries_the_ruled_title_and_scroll():
    frame = _frame("YOU", {}, _CYCLE_FOOTER)
    assert frame.title == "STATUSES - YOU"
    assert frame.scrollable is True
    assert _frame("ROCK SCAVENGER", {}, _CYCLE_FOOTER).title == "STATUSES - ROCK SCAVENGER"


def test_subjects_you_first_then_live_enemies():
    rules = SimpleNamespace(
        get_enemies=lambda _ctx: [
            SimpleNamespace(name="Rock Scavenger", statuses={"staggered": None}),
            SimpleNamespace(name="Dust Prowler", statuses={}),
        ],
    )
    ctx = SimpleNamespace(active_statuses={})

    pairs = _subjects(ctx, rules)

    assert [label for label, _ in pairs] == [
        "YOU", "Rock Scavenger", "Dust Prowler",
    ]
    assert pairs[1][1] == {"staggered": None}  # the enemy container read


def test_the_keymap_ruling_v_opens_e_toggles():
    """The Build B amendment: v = the status window, the floating
    card toggle moved to e, i stays reserved (unmapped)."""
    assert _loop._key_action("v") == "STATUS"
    assert _loop._key_action("e") == "TOGGLE_CARD"
    assert _loop._key_action("i") == ""
