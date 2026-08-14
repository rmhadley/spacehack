"""Tests for the combat HUD shield row and WEAPONS header (space combat)."""

from __future__ import annotations

from types import SimpleNamespace

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


def test_city_hp_row_uses_the_bar_layout():
    """City HP row uses the combat-style bar and fills the panel width."""
    console = FrameBuffer(40, 3)
    ctx = SimpleNamespace(ground_hp=10, ground_max_hp=10)
    stats = SimpleNamespace(credits=100, gunnery=4, piloting=3, engineering=2)
    hud._render_city_stat_rows(
        console, 0, 0,
        ctx=ctx, stats=stats, owned_ship=None, ship_catalog=None, ground_stats=None,
    )
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert row == "HP  ########## 10/10"


def test_space_fuel_hull_rows_use_bars():
    """Space Fuel/Hull rows use 10-cell bars instead of bare text."""
    console = FrameBuffer(40, 2)
    stats = SimpleNamespace(gunnery=1, piloting=1, engineering=1)
    hud._render_ship_stat_rows(
        console, 0, 0,
        fuel=90, max_fuel=100, hull_pct=67, cargo_used=0, max_cargo=10,
        weapons_n=0, weapon_slots=2, modules_n=0, module_slots=1, eff_spd=5,
        stats=stats, ground_stats=None,
    )
    row0 = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    row1 = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    assert row0.startswith("Fuel  ####") and row0.endswith("90/100")
    assert row1.startswith("Hull  #####") and row1.endswith("67%")


def test_skill_lines_span_the_panel():
    """Skill rows use full labels to spread across the panel."""
    console = FrameBuffer(40, 1)
    hud._render_skill_line(
        console, 0, 0, SimpleNamespace(gunnery=4, piloting=3, engineering=2),
    )
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert row == "GUNNERY 4 PILOTING 3 ENGINEERING 2"


def test_help_lines_pair_two_per_row():
    """Key hints render two per row, halving the help block height."""
    console = FrameBuffer(40, 3)
    next_y = hud._render_help_lines(console, 0, 0, [
        ("Q", "Quest Log"), ("I", "Cargo"),
        ("C", "Character"), ("F", "Factions"), ("\\", "Console"),
    ])
    row0 = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    row1 = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    assert "Quest Log" in row0 and "Cargo" in row0
    assert "Character" in row1 and "Factions" in row1
    assert next_y == 3


def test_combat_actions_pair_two_per_row():
    """Combat key hints render two per row."""
    console = FrameBuffer(40, 4)
    next_y = hud._render_combat_actions(console, 0, 0, ("a", "b", "c"))
    row0 = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    row1 = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    assert row0 == "ACTIONS"
    assert "Target" in row1 and "Move" in row1
    assert next_y == 4


def test_space_weapon_row_includes_range():
    """Space weapon stats show the RNG band, matching ground combat."""
    from src.spacehack.data.weapons import find_weapon
    ws = find_weapon("heavy_laser")
    console = FrameBuffer(40, 3)
    hud._render_weapon_row(
        console, 0, 0, 0, "heavy_laser", ws, 0, True, {"heavy_laser": 68},
    )
    stats_row = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    assert stats_row == "     DMG 12 HIT 68% RNG 1-5"


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
