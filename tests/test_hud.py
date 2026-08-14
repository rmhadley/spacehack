"""Tests for the combat HUD shield row (space combat player block)."""

from __future__ import annotations

from src.spacehack import hud
from src.spacehack.framebuffer import FrameBuffer

_WHITE = (255, 255, 255)


def _shield_row(player_state: dict) -> tuple[str, list[int]]:
    """Render the shield row into a 20-cell frame; return (row, white cells)."""
    console = FrameBuffer(20, 3)
    hud._render_hull_shield_rows(console, 0, 0, player_state)
    row = "".join(console.cell(x, 0).char for x in range(20))
    white = [x for x in range(20) if console.cell(x, 0).bg == _WHITE]
    return row, white


def test_suffix_shows_total_regen_and_white_fill_tracks_s_key_only():
    """+4 = S rate 1 + free 3; only the 1 S-key cell gets the white fill."""
    row, white = _shield_row({
        "hull": 100, "max_hull": 100, "shields": 12, "max_shields": 20,
        "shield_regen_rate": 1, "shield_recharge_bonus": 3,
    })
    assert row == "Shd  ###... 12/20 +4"
    assert white == [5]


def test_three_digit_values_shrink_bar_so_suffix_never_clips():
    """135/135 +4 used to clip the +4 off the right edge (HUD_WIDTH=20)."""
    row, _ = _shield_row({
        "hull": 135, "max_hull": 135, "shields": 135, "max_shields": 135,
        "shield_regen_rate": 1, "shield_recharge_bonus": 3,
    })
    assert row == "Shd  #### 135/135 +4"
    assert row.endswith("+4")


def test_no_suffix_when_no_regen_at_all():
    """Nothing contributes regen -> no +N and no white fill."""
    row, white = _shield_row({
        "hull": 100, "max_hull": 100, "shields": 12, "max_shields": 20,
        "shield_regen_rate": 0, "shield_recharge_bonus": 0,
    })
    assert row == "Shd  #####.... 12/20"
    assert white == []


def test_white_fill_never_exceeds_s_key_rate():
    """Free regen must not grow the level indicator (S maps 1:1)."""
    _row, white = _shield_row({
        "hull": 100, "max_hull": 100, "shields": 12, "max_shields": 20,
        "shield_regen_rate": 2, "shield_recharge_bonus": 5,
    })
    assert len(white) == 2
