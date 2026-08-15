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
    assert row == "HP      ########## 10/10"


def test_dungeon_stat_rows_show_current_ground_armor():
    """Dungeon HUD stat rows expose the combined armor defense."""
    console = FrameBuffer(40, 4)
    ctx = SimpleNamespace(ground_hp=10, ground_max_hp=10)
    stats = SimpleNamespace(credits=100, gunnery=4, piloting=3, engineering=2)

    hud._render_city_stat_rows(
        console, 0, 0,
        ctx=ctx, stats=stats, owned_ship=None, ship_catalog=None,
        ground_stats=None, ground_armor=3,
    )

    row = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    assert row == "Armor   3"


def test_city_hud_shows_current_ground_armor():
    """The Earth/city HUD exposes the equipped ground armor total."""
    ctx = SimpleNamespace(
        character_info={"species_name": "Human", "class_name": "Merchant"},
        stats=hud.HudStats(10, 10, 100),
        player_owned_ship=None,
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        ground_stats=None,
        ground_hp=10,
        ground_max_hp=10,
        equipped_ground_armor={"body": "light_vest"},
        time_day=1,
        time_month=1,
        time_year=2200,
    )
    console = FrameBuffer(120, 54)

    hud.render_hud(
        console, ctx, screen_width=100, hud_view_height=54, mode="city",
    )

    rows = [
        "".join(console.cell(x, y).char for x in range(80, 120)).rstrip()
        for y in range(54)
    ]
    assert "Armor   2" in rows


def test_city_stat_values_line_up_in_one_column():
    """HP / Cargo / Credits values all start at the same column."""
    console = FrameBuffer(40, 3)
    ctx = SimpleNamespace(ground_hp=10, ground_max_hp=10)
    stats = SimpleNamespace(credits=1234, gunnery=4, piloting=3, engineering=2)
    hud._render_city_stat_rows(
        console, 0, 0,
        ctx=ctx, stats=stats, owned_ship=None, ship_catalog=None, ground_stats=None,
    )
    rows = ["".join(console.cell(x, y).char for x in range(40)) for y in range(3)]
    assert rows[0][19] == "1"  # 10/10
    assert rows[1][19] == "0"  # 0/0 (no ship -> empty bar)
    assert rows[2][19] == "1"  # 1234


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
    assert row0.startswith("Fuel    ####") and row0.endswith("90/100")
    assert row1.startswith("Hull    #####") and row1.endswith("67%")


def test_skill_lines_pair_two_per_row():
    """Skills render two per row, values right-aligned in fixed slots."""
    console = FrameBuffer(40, 3)
    next_y = hud._render_skill_line(
        console, 0, 0, SimpleNamespace(gunnery=4, piloting=3, engineering=2),
    )
    row0 = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    row1 = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    assert "GUNNERY" in row0 and "PILOTING" in row0
    assert "ENGINEERING" in row1 and "PILOTING" not in row1
    # Values right-align to the same columns across both rows.
    assert row0[13] == "4" and row0[29] == "3"
    assert row1[13] == "2"
    assert next_y == 2


def test_skill_grid_merges_ship_and_ground_stats():
    """All six skills share one aligned 3-row grid, two per row."""
    console = FrameBuffer(40, 4)
    next_y = hud._render_skill_line(
        console, 0, 0,
        SimpleNamespace(gunnery=4, piloting=3, engineering=2),
        ground_stats=SimpleNamespace(reflexes=10, strength=9, stamina=8),
    )
    rows = [
        "".join(console.cell(x, y).char for x in range(40)).rstrip()
        for y in range(4)
    ]
    assert "GUNNERY" in rows[0] and "PILOTING" in rows[0]
    assert "ENGINEERING" in rows[1] and "REFLEXES" in rows[1]
    assert "STRENGTH" in rows[2] and "STAMINA" in rows[2]
    # Values stay in the same right-aligned columns across all three rows.
    assert rows[0][13] == "4" and rows[0][29] == "3"
    assert rows[1][13] == "2" and rows[1][28:30] == "10"
    assert rows[2][13] == "9" and rows[2][29] == "8"
    assert next_y == 3


def test_skill_values_right_align_with_three_digit_room():
    """3-digit values fill the value column without shifting the layout."""
    console = FrameBuffer(40, 1)
    hud._render_skill_line(
        console, 0, 0, SimpleNamespace(gunnery=134, piloting=3, engineering=2),
    )
    row0 = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert row0[11:14] == "134"   # 3-digit value fills the value column
    assert row0[29] == "3"        # 1-digit value still lands at column 29


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


def test_dungeon_help_lines_show_reload_control():
    """Dungeon exploration controls include the direct reload hotkey."""
    console = FrameBuffer(40, 5)

    hud._render_city_help_lines(console, 0, 0, "dungeon")

    text = "\n".join(
        "".join(console.cell(x, y).char for x in range(40)).rstrip()
        for y in range(5)
    )
    assert "[R] Reload" in text


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


def test_ap_pool_str_shows_fractional_carry():
    """AP pool renders the banked tenths as a fraction: 4/4.5, 5/5."""
    assert hud.ap_pool_str(4, 0) == "4"
    assert hud.ap_pool_str(4, 5) == "4.5"
    assert hud.ap_pool_str(5, 0) == "5"
    assert hud.ap_pool_str(2, 7) == "2.7"


def test_ap_row_shows_pool_with_carry():
    """The AP row uses the fractional pool as its denominator."""
    console = FrameBuffer(40, 3)
    player_state = {
        "ap_remaining": 3, "ap_total": 4, "ap_carry_tenths": 5,
        "power_pool": 10, "max_power": 10, "power_gen": 1,
    }
    hud._render_ap_evade_pow_rows(console, 0, 0, player_state, None)
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert row.startswith("AP: 3/4.5")
