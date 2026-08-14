"""Tests for the combat HUD shield row and WEAPONS header (space combat)."""

from __future__ import annotations

from src.spacehack import hud
from src.spacehack.framebuffer import FrameBuffer

_WHITE = (255, 255, 255)


def _shield_row(player_state: dict) -> tuple[str, list[int]]:
    """Render the shield row into a wide frame; return (row, white cells)."""
    console = FrameBuffer(40, 3)
    hud._render_hull_shield_rows(console, 0, 0, player_state)
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    white = [x for x in range(40) if console.cell(x, 0).bg == _WHITE]
    return row, white


def test_shield_bar_matches_hull_bar_width():
    """Shield row uses the same 10-cell bar as Hull, with total regen +N."""
    row, white = _shield_row({
        "hull": 100, "max_hull": 100, "shields": 12, "max_shields": 20,
        "shield_regen_rate": 1, "shield_recharge_bonus": 3,
    })
    assert row == "Shd  ######.... 12/20 +4"
    assert white == [5]


def test_three_digit_values_keep_full_bar():
    """135/135 keeps the full 10-cell bar; the +N suffix stays visible."""
    row, _ = _shield_row({
        "hull": 135, "max_hull": 135, "shields": 135, "max_shields": 135,
        "shield_regen_rate": 1, "shield_recharge_bonus": 3,
    })
    assert row == "Shd  ########## 135/135 +4"
    assert row.endswith("+4")


def test_white_fill_tracks_s_key_rate_only():
    """Free regen must not grow the level indicator (S maps 1:1)."""
    _row, white = _shield_row({
        "hull": 100, "max_hull": 100, "shields": 12, "max_shields": 20,
        "shield_regen_rate": 2, "shield_recharge_bonus": 5,
    })
    assert len(white) == 2


def test_no_suffix_when_no_regen_at_all():
    """Nothing contributes regen -> no +N and no white fill."""
    row, white = _shield_row({
        "hull": 100, "max_hull": 100, "shields": 12, "max_shields": 20,
        "shield_regen_rate": 0, "shield_recharge_bonus": 0,
    })
    assert row == "Shd  ######.... 12/20"
    assert white == []


def test_weapons_header_keeps_offset_layout_and_is_not_clipped():
    """Header keeps its fixed-offset layout; POW's W survives past 20 cells."""
    console = FrameBuffer(40, 3)
    player_state = {
        "ap_remaining": 3, "power_pool": 20,
        "weapon_ammo": {i: -1 for i in range(4)},
    }
    hud._render_weapons_block(
        console, 0, 0,
        ("plasma_cannon",) * 4, [True] * 4, player_state, None,
    )
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert row == "WEAPONS [4] 2AP 16POW"
    assert row.endswith("16POW")


def test_world_hud_divider_spans_the_full_panel():
    """Dividers use the panel's real ~36 half-width glyph capacity, not 20."""
    console = FrameBuffer(40, 1)
    hud._render_divider(console, 0, 0)
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert len(row) == hud.HUD_TEXT_MAX
    assert set(row) == {"-"}


def test_enemy_name_is_not_clipped_to_nine_chars():
    """Enemy names keep up to _ENEMY_NAME_MAX chars instead of 9."""
    class Enemy:
        name = "Pirate Interceptor"
        max_shields = 0
        shields = 0
        max_hull = 30
        hull = 20

    console = FrameBuffer(40, 1)
    hud._render_enemy_row(console, 0, 0, Enemy(), True, None, None)
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert row == ">Pirate Interceptor"


def test_xp_line_spans_the_full_panel():
    """The XP row fills HUD_TEXT_MAX whether or not points are pending."""
    line, _ = hud._xp_hud_line(3, 150, 300, 2)
    assert len(line) == hud.HUD_TEXT_MAX
    line, _ = hud._xp_hud_line(3, 150, 300, 0)
    assert len(line) == hud.HUD_TEXT_MAX


def test_shield_row_survives_the_wider_combat_console():
    """A 26-cell shield line (hud_x=80) reaches the overlay uncut in a
    SCREEN_WIDTH+HUD_WIDTH console (the combat console width)."""
    from src.spacehack.engine import HUD_WIDTH, SCREEN_WIDTH
    console = FrameBuffer(SCREEN_WIDTH + HUD_WIDTH, 3)
    player_state = {
        "hull": 135, "max_hull": 135, "shields": 135, "max_shields": 135,
        "shield_regen_rate": 0, "shield_recharge_bonus": 8,
    }
    hud._render_hull_shield_rows(console, SCREEN_WIDTH - HUD_WIDTH, 0, player_state)
    row = "".join(console.cell(x, 0).char for x in range(SCREEN_WIDTH - HUD_WIDTH, SCREEN_WIDTH + HUD_WIDTH))
    assert row.rstrip() == "Shd  ########## 135/135 +8"
