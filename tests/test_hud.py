"""Tests for the combat HUD shield row and WEAPONS header (space combat)."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import hud, hud_combat, hud_core
from src.spacehack.ground_equipment import (
    GroundWeaponInstance,
    StoredGroundEquipment,
)
from src.spacehack.framebuffer import FrameBuffer

_WHITE = (255, 255, 255)


def _shield_row(player_state: dict) -> tuple[str, list[int]]:
    """Render the shield row into a wide frame; return (row, white cells)."""
    console = FrameBuffer(40, 3)
    hud_combat._render_hull_shield_rows(console, 0, 0, player_state)
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    white = [x for x in range(40) if console.cell(x, 0).bg == _WHITE]
    return row, white


def test_ground_player_fg_health_zones():
    """The player glyph color tracks ground HP thresholds."""
    from src.spacehack.hud import (
        ground_player_fg,
        COLOR_PLAYER_HEALTHY,
        COLOR_PLAYER_WOUNDED,
        COLOR_PLAYER_CRITICAL,
    )
    assert ground_player_fg(20, 20) == COLOR_PLAYER_HEALTHY   # full
    assert ground_player_fg(10, 20) == COLOR_PLAYER_HEALTHY   # exactly half
    assert ground_player_fg(9, 20) == COLOR_PLAYER_WOUNDED    # just under half
    assert ground_player_fg(5, 20) == COLOR_PLAYER_WOUNDED    # exactly a quarter
    assert ground_player_fg(4, 20) == COLOR_PLAYER_CRITICAL   # below a quarter
    assert ground_player_fg(1, 23) == COLOR_PLAYER_CRITICAL
    assert ground_player_fg(0, 0) == COLOR_PLAYER_HEALTHY     # degenerate max


def test_ground_player_fg_species_healthy_color_alarms_universal():
    """Doc 49: the species color owns only the HEALTHY state; wounded
    amber / critical red read the same for every species."""
    from src.spacehack.hud import (
        ground_player_fg,
        COLOR_PLAYER_WOUNDED,
        COLOR_PLAYER_CRITICAL,
    )
    martian_green = (130, 225, 90)
    diamond_blue = (185, 215, 245)
    assert ground_player_fg(29, 29, martian_green) == martian_green
    assert ground_player_fg(15, 29, martian_green) == martian_green  # above half
    assert ground_player_fg(14, 29, martian_green) == COLOR_PLAYER_WOUNDED
    assert ground_player_fg(7, 29, martian_green) == COLOR_PLAYER_CRITICAL
    assert ground_player_fg(14, 29, diamond_blue) == COLOR_PLAYER_WOUNDED
    assert ground_player_fg(7, 29, diamond_blue) == COLOR_PLAYER_CRITICAL
    assert ground_player_fg(0, 0, martian_green) == martian_green


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
    hud_combat._render_weapons_block(
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
    hud_combat._render_enemy_row(console, 0, 0, Enemy(), True, None, None)
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert row == ">Pirate Interceptor"


def test_xp_line_spans_the_full_panel():
    """The XP row fills HUD_TEXT_MAX whether or not points are pending."""
    line, _ = hud._xp_hud_line(3, 150, 300, 2)
    assert len(line) == hud.HUD_TEXT_MAX
    line, _ = hud._xp_hud_line(3, 150, 300, 0)
    assert len(line) == hud.HUD_TEXT_MAX


def test_city_hp_row_uses_the_bar_layout():
    """The core HP row uses the aligned bar shape and fills the panel width."""
    console = FrameBuffer(40, 3)
    next_y = hud_core.paint_hp_armor_rows(console, 0, 0, hp=10, max_hp=10, armor=0)
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert row == "HP      ########## 10/10"
    assert next_y == 2


def _ground_weapons_ctx(**extra):
    """Dungeon-HUD ctx carrying the ground loadout fields (doc 52.3)."""
    ctx = SimpleNamespace(
        character_info={"species_name": "Human", "class_name": "Merchant"},
        stats=hud.HudStats(100),
        player_owned_ship=None,
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        ground_stats=None,
        ground_hp=10,
        ground_max_hp=10,
        equipped_ground_armor={},
        time_day=1,
        time_month=1,
        time_year=2200,
    )
    for key, value in extra.items():
        setattr(ctx, key, value)
    return ctx


def test_dungeon_hud_renders_the_weapons_block():
    """Doc 52.3: the dungeon HUD shows the same weapons/ammo family as
    combat — active rows with magazine state, dim holster names, and
    the shared caliber lines."""
    ctx = _ground_weapons_ctx(
        equipped_ground_weapons=[GroundWeaponInstance("kinetic_pistol", 5)],
        holstered_ground_weapons=[GroundWeaponInstance("laser_pistol", None)],
        bandolier={"kinetic_pistol": 132, "energy_cell": 61},
    )
    console = FrameBuffer(120, 54)

    hud.render_hud(
        console, ctx, screen_width=100, hud_view_height=54, mode="dungeon",
    )

    rows = [
        "".join(console.cell(x, y).char for x in range(80, 120)).rstrip()
        for y in range(54)
    ]
    assert "WEAPONS" in rows
    assert "Kinetic Pistol [5/12]" in rows
    assert any(row.startswith("HOLSTER  Laser Pistol") for row in rows)
    assert "PST 132/160" in rows
    assert "CEL 61/250" in rows


def test_city_hud_renders_the_weapons_block():
    """City mode renders the same weapons block as dungeons — streets
    became hostile-capable in doc 53, so magazine state and the caliber
    reserve must be visible there (supersedes the doc 52.3 city fold).

    Doc 104: the block is the C anchor at the pinned row directly under
    the core's status slot; terminals moved into the D band BELOW it
    (they used to sit above the status row)."""
    ctx = _ground_weapons_ctx(
        equipped_ground_weapons=[GroundWeaponInstance("kinetic_pistol", 5)],
        holstered_ground_weapons=[GroundWeaponInstance("laser_pistol", None)],
        bandolier={"kinetic_pistol": 132},
    )
    console = FrameBuffer(120, 54)

    hud.render_hud(
        console, ctx, screen_width=100, hud_view_height=54, mode="city",
        has_trade_terminal=True, has_mech_terminal=True,
        has_armory_terminal=True, has_kiosk=True,
    )

    rows = [
        "".join(console.cell(x, y).char for x in range(80, 120)).rstrip()
        for y in range(54)
    ]
    assert "Kinetic Pistol [5/12]" in rows
    assert any(row.startswith("HOLSTER  Laser Pistol") for row in rows)
    assert "PST 132/160" in rows
    assert any(row.startswith("[R] Reload") for row in rows)
    _weapons_y = rows.index("WEAPONS")
    assert _weapons_y == 11                     # the pinned C anchor
    assert rows[_weapons_y - 1].strip() == ""   # the blank status slot above
    for _terminal in ("A  Armory", "%  Mechanic", "=  Trade", "$  Terminus Tech"):
        assert rows.index(_terminal) > _weapons_y  # terminals live in D now
    assert "[ESC] Pause" in "\n".join(rows)


def test_city_weapons_block_follows_the_core_without_terminals():
    """No terminal hints on screen = the weapons block attaches
    directly under the core's status slot at the pinned anchor row —
    no orphan divider between two absent sections."""
    ctx = _ground_weapons_ctx(
        equipped_ground_weapons=[GroundWeaponInstance("kinetic_pistol", 5)],
    )
    console = FrameBuffer(120, 54)

    hud.render_hud(
        console, ctx, screen_width=100, hud_view_height=54, mode="city",
    )

    rows = [
        "".join(console.cell(x, y).char for x in range(80, 120)).rstrip()
        for y in range(54)
    ]
    _weapons_y = rows.index("WEAPONS")
    assert _weapons_y == 11
    assert rows[_weapons_y - 1].strip() == ""


def test_city_weapons_block_silent_on_bare_fists():
    """Bare fists stay silent on the city screen too (doc 51 SETTLED 2)."""
    ctx = _ground_weapons_ctx(
        equipped_ground_weapons=[], holstered_ground_weapons=[],
    )
    console = FrameBuffer(120, 54)

    hud.render_hud(
        console, ctx, screen_width=100, hud_view_height=54, mode="city",
    )

    rows = [
        "".join(console.cell(x, y).char for x in range(80, 120)).rstrip()
        for y in range(54)
    ]
    assert "WEAPONS" not in rows


def test_dungeon_weapons_block_silent_on_bare_fists():
    """Both sets empty = the fists floor: no WEAPONS header, no ammo
    lines (doc 51 SETTLED 2's silence, held by the 52.3 block)."""
    ctx = _ground_weapons_ctx(
        equipped_ground_weapons=[], holstered_ground_weapons=[],
    )
    console = FrameBuffer(120, 54)

    hud.render_hud(
        console, ctx, screen_width=100, hud_view_height=54, mode="dungeon",
    )

    rows = [
        "".join(console.cell(x, y).char for x in range(80, 120)).rstrip()
        for y in range(54)
    ]
    assert "WEAPONS" not in rows


def test_dungeon_stat_rows_show_current_ground_armor():
    """The core's second meter row reads the combined armor defense."""
    console = FrameBuffer(40, 4)
    hud_core.paint_hp_armor_rows(console, 0, 0, hp=10, max_hp=10, armor=3)
    row = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    assert row == "Armor   3"


def test_city_hud_shows_current_ground_armor():
    """The Earth/city HUD exposes the equipped ground armor total."""
    ctx = SimpleNamespace(
        character_info={"species_name": "Human", "class_name": "Merchant"},
        stats=hud.HudStats(100),
        player_owned_ship=None,
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        ground_stats=None,
        ground_hp=10,
        ground_max_hp=10,
        equipped_ground_armor={"body": StoredGroundEquipment("armor", "light_vest")},
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
    """HP / Cargo values share the core's value column; Armor's value
    lands at the label column's end."""
    console = FrameBuffer(40, 3)
    y = hud_core.paint_hp_armor_rows(console, 0, 0, hp=10, max_hp=10, armor=3)
    hud_core.paint_cargo_row(console, 0, y, used=0, max_cargo=0)
    rows = ["".join(console.cell(x, y).char for x in range(40)) for y in range(3)]
    assert rows[0][19] == "1"  # 10/10
    assert rows[1][8] == "3"   # Armor
    assert rows[2][19] == "0"  # 0/0 (no ship -> empty bar)


def test_space_fuel_hull_rows_use_bars():
    """Space Fuel/Hull rows use 10-cell bars and cur/max values."""
    console = FrameBuffer(40, 2)
    stats = SimpleNamespace(gunnery=1, piloting=1, engineering=1)
    console = FrameBuffer(40, 4)
    hud._render_ship_stat_rows(
        console, 0, 0,
        fuel=90, max_fuel=100, hull=67, max_hull=100, cargo_used=0, max_cargo=10,
        eff_spd=5,
        stats=stats, ground_stats=None,
    )
    row0 = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    row1 = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    row3 = "".join(console.cell(x, 3).char for x in range(40)).rstrip()
    assert row0.startswith("Fuel    ####") and row0.endswith("90/100")
    assert row1.startswith("Hull    #####") and row1.endswith("67/100")
    # Doc 56 SETTLED 18: the slot summaries retired — Spd only.
    assert row3 == "Spd 5"


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
    console = FrameBuffer(40, 5)
    next_y = hud_combat._render_combat_actions(console, 0, 0, ("a", "b", "c"))
    row0 = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    row1 = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    _flat = "".join(
        console.cell(x, y).char for y in range(5) for x in range(40)
    )
    assert row0 == "ACTIONS"
    assert "Target" in row1 and "Move" in row1
    assert "Board" in _flat                     # 7 pairs render 2/row
    assert next_y == 5                          # header + 4 pair rows


def test_space_weapon_row_includes_range():
    """Space weapon stats show the RNG band, matching ground combat."""
    from src.spacehack.data.weapons import find_weapon
    ws = find_weapon("heavy_laser")
    console = FrameBuffer(40, 3)
    hud_combat._render_weapon_row(
        console, 0, 0, 0, "heavy_laser", ws, 0, True, {"heavy_laser": 68},
    )
    stats_row = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    assert stats_row == "     DMG 16 HIT 68% RNG 1-5"


def test_shield_row_survives_the_wider_combat_console():
    """A 26-cell shield line (hud_x=80) reaches the overlay uncut in a
    SCREEN_WIDTH+HUD_WIDTH console (the combat console width)."""
    from src.spacehack.engine import HUD_WIDTH, SCREEN_WIDTH
    console = FrameBuffer(SCREEN_WIDTH + HUD_WIDTH, 3)
    player_state = {
        "hull": 135, "max_hull": 135, "shields": 135, "max_shields": 135,
        "shield_regen_rate": 0, "shield_recharge_bonus": 8,
    }
    hud_combat._render_hull_shield_rows(console, SCREEN_WIDTH - HUD_WIDTH, 0, player_state)
    row = "".join(console.cell(x, 0).char for x in range(SCREEN_WIDTH - HUD_WIDTH, SCREEN_WIDTH + HUD_WIDTH))
    assert row.rstrip() == "Shd  ########## 135/135 +8"


def test_ap_pool_str_shows_fractional_carry():
    """AP pool renders the banked twentieths as a fraction: 4/4.5, 5/5."""
    assert hud.ap_pool_str(4, 0) == "4"
    assert hud.ap_pool_str(4, 10) == "4.5"
    assert hud.ap_pool_str(4, 5) == "4.25"
    assert hud.ap_pool_str(4, 1) == "4.05"
    assert hud.ap_pool_str(5, 0) == "5"
    assert hud.ap_pool_str(2, 15) == "2.75"


def test_ap_row_shows_pool_with_carry():
    """The AP row uses the fractional pool as its denominator."""
    console = FrameBuffer(40, 3)
    player_state = {
        "ap_remaining": 3, "ap_total": 4, "ap_carry_twentieths": 10,
        "power_pool": 10, "max_power": 10, "power_gen": 1,
    }
    hud_combat._render_ap_evade_pow_rows(console, 0, 0, player_state, None)
    row = "".join(console.cell(x, 0).char for x in range(40)).rstrip()
    assert row.startswith("AP: 3/4.5")


def test_board_hint_advertised_always():
    """The [d] Board hint renders UNCONDITIONALLY in the space combat
    HUD (user ruling 2026-10-02, superseding doc 40 6a's conditional
    display): the key answers at any time with the unmet condition,
    so hiding the hint until conditions pass only hid the mechanic
    from players who never think to press it."""
    console = FrameBuffer(40, 6)
    hud_combat._render_combat_actions(console, 0, 0, ("a",))
    _flat = "".join(
        console.cell(x, y).char
        for y in range(6) for x in range(40)
    )
    assert "[d]" in _flat and "Board" in _flat


def test_help_lines_show_weapon_set_swap_in_city_and_dungeon():
    """Doc 51: the X swap hint sits on the explore HUDs (city + dungeon);
    the space list (the twin surface) must not advertise the dead key."""
    for mode in ("city", "dungeon"):
        console = FrameBuffer(40, 7)
        hud._render_city_help_lines(console, 0, 0, mode)
        text = "\n".join(
            "".join(console.cell(x, y).char for x in range(40)).rstrip()
            for y in range(7)
        )
        assert "[X] Swap Sets" in text
    assert all(key != "X" for key, _label in hud._SPACE_HELP_LINES)


def test_esc_pause_joins_the_help_pairs():
    """[ESC] Pause (doc 104 item 12 + prose ledger #1): ESC's hint
    reads in every mode's key-hint block — city, dungeon, and the
    space list — replacing the retired 'ESC to quit' footer line."""
    for mode in ("city", "dungeon"):
        console = FrameBuffer(40, 8)
        hud._render_city_help_lines(console, 0, 0, mode)
        text = "\n".join(
            "".join(console.cell(x, y).char for x in range(40)).rstrip()
            for y in range(8)
        )
        assert "[ESC] Pause" in text
    console = FrameBuffer(40, 6)
    hud._render_help_lines(console, 0, 0, hud._SPACE_HELP_LINES)
    text = "\n".join(
        "".join(console.cell(x, y).char for x in range(40)).rstrip()
        for y in range(6)
    )
    assert "[ESC] Pause" in text


def test_cargo_used_max_threads_the_merchant_hold():
    """Both HUD branches share this read (doc 49 phase 2): a merchant
    sees the +10, a plain pilot the class-free capacity, and a missing
    ctx degrades to the catalog read."""
    from types import SimpleNamespace

    from src.spacehack import ship as ship_module
    from src.spacehack.hud import _cargo_used_max

    spec = ship_module.find_ship("starter")
    owned = ship_module.OwnedShip(ship_id="starter")
    merchant = SimpleNamespace(player_traits=["merchant"])
    plain = SimpleNamespace(player_traits=[])
    assert _cargo_used_max(owned, spec, plain) == (0, 50)
    assert _cargo_used_max(owned, spec, merchant) == (0, 60)
    assert _cargo_used_max(owned, spec) == (0, 50)


def test_space_weapon_row_dmg_reads_flown_tier():
    """The combat HUD's DMG matches what the volley rolls — an
    overclocked weapon shows its scaled damage, not the catalog row."""
    from src.spacehack.data.weapons import find_weapon
    ws = find_weapon("medium_laser")
    console = FrameBuffer(40, 3)
    hud_combat._render_weapon_row(
        console, 0, 0, 0, "medium_laser", ws, 0, True,
        {"medium_laser": 62}, weapon_quality=2,
    )
    stats_row = "".join(console.cell(x, 1).char for x in range(40)).rstrip()
    assert stats_row == "     DMG 8 HIT 62% RNG 1-5"


def test_weapon_toggle_hint_conditional_on_mounted_count():
    """The neighboring conditional stays conditional (unlike [d]):
    the digit-swap hint renders only when there is something to
    swap between (reviewer pin, 2026-10-02)."""
    console = FrameBuffer(40, 6)
    hud_combat._render_combat_actions(console, 0, 0, ("a", "b"))
    _flat = "".join(
        console.cell(x, y).char for y in range(6) for x in range(40)
    )
    assert "Toggle Wpn" in _flat

    console = FrameBuffer(40, 6)
    hud_combat._render_combat_actions(console, 0, 0, ("a",))
    _flat = "".join(
        console.cell(x, y).char for y in range(6) for x in range(40)
    )
    assert "Toggle Wpn" not in _flat


def test_combat_status_row_paints_labelled_rows_and_consumes_one_row():
    """The space panel's status-row twin (doc 103 q7 + the OPENER
    ruling): empty containers consume no row; labelled rows paint in
    their class shape (rounds carry their remaining, fight-class rows
    are label-only) inside the panel's ~40 half-width characters."""
    from src.spacehack.combat import _statuses
    from src.spacehack.data.statuses import PIRATE_OPENER_ID
    from src.spacehack.engine import HUD_WIDTH, SCREEN_WIDTH

    ctx = SimpleNamespace(active_statuses={})
    _statuses.apply(ctx.active_statuses, "regen", source="Med Pack")
    _statuses.apply(ctx.active_statuses, PIRATE_OPENER_ID)
    frame = FrameBuffer(SCREEN_WIDTH + HUD_WIDTH, 12)
    hud_x = SCREEN_WIDTH - HUD_WIDTH

    assert hud_combat._render_status_row(frame, hud_x, 5, ctx) is True
    _row = "".join(
        frame.cell(x, 5).char for x in range(hud_x, hud_x + HUD_WIDTH * 2)
    ).rstrip()
    assert _row == "REGEN 3  OPENER"

    _statuses.dispel(ctx.active_statuses, lambda _a: True)
    assert hud_combat._render_status_row(
        FrameBuffer(SCREEN_WIDTH + HUD_WIDTH, 12), hud_x, 5, ctx,
    ) is False


def test_exploration_status_slot_paints_segments_and_stays_fixed():
    """The exploration status slot (doc 103 q7 + doc 104 item 13's
    fixed-slot law): labelled rows paint with their remaining, and an
    empty container leaves the row BLANK — the row is still consumed,
    so the slot never pops at a mode boundary."""
    from src.spacehack.combat import _statuses
    from src.spacehack.engine import HUD_WIDTH, SCREEN_WIDTH
    from src.spacehack import hud as _hud

    ctx = SimpleNamespace(active_statuses={})
    _statuses.apply(ctx.active_statuses, "staggered", theater="ground")
    _statuses.apply(ctx.active_statuses, "regen", theater="ground")
    frame = FrameBuffer(SCREEN_WIDTH + HUD_WIDTH, 12)
    hud_x = SCREEN_WIDTH - HUD_WIDTH

    _y = hud_core.paint_status_slot(frame, hud_x, 5, _hud._status_segments(ctx))
    _row = "".join(
        frame.cell(x, 5).char for x in range(hud_x, hud_x + HUD_WIDTH * 2)
    ).rstrip()
    assert _row == "STAGGERED 2  REGEN 3"
    assert _y == 6  # one row consumed

    _statuses.dispel(ctx.active_statuses, lambda _a: True)
    _empty_frame = FrameBuffer(SCREEN_WIDTH + HUD_WIDTH, 12)
    assert hud_core.paint_status_slot(
        _empty_frame, hud_x, 5, _hud._status_segments(ctx),
    ) == 6  # the empty slot still consumes its row
    _empty_row = "".join(
        _empty_frame.cell(x, 5).char for x in range(hud_x, hud_x + HUD_WIDTH * 2)
    ).rstrip()
    assert _empty_row == ""  # blank, never a placeholder glyph


def test_v_opens_the_you_only_window_exploring(monkeypatch):
    """The exploring v wiring (doc 103 Build C): city and dungeon
    dispatch to the you-only entry; space never does (its combat
    loop owns v in fights)."""
    from tests.support.asyncutil import run as _run
    from src.spacehack import game_loop, status_inspect
    from types import SimpleNamespace as _NS

    _opened: list = []

    async def _fake_window(ctx):
        _opened.append(ctx)
        return "ESC"

    monkeypatch.setattr(
        status_inspect, "open_status_inspect_exploring", _fake_window,
    )

    def _state(mode: str):
        return _NS(
            ctx=_NS(active_statuses={}, log=_NS(add=lambda *_a, **_k: None)),
            current_mode=mode, current_city_id="", space_player=None,
        )

    _v = _NS(kind="keydown", key_name="v")
    assert _run(game_loop._handle_common_modal_event(_state("city"), _v)) == "HANDLED"
    assert _run(game_loop._handle_common_modal_event(_state("dungeon"), _v)) == "HANDLED"
    assert len(_opened) == 2
    # Space exploration never routes v here (None = unhandled by this
    # layer; the combat loop's own table owns it in fights).
    _opened.clear()
    assert _run(game_loop._handle_common_modal_event(_state("space"), _v)) is None
    assert _opened == []


def test_the_exploring_frame_has_no_tab_hint():
    """One subject — the TAB footer hint would mislead (advisor
    note): the exploring footer carries only ESC + guide hints."""
    from src.spacehack.status_inspect import _SOLO_FOOTER, _frame

    _footer = _frame("YOU", {}, _SOLO_FOOTER).footer
    assert len(_footer) == 1
    assert "TAB" not in _footer[0]
    assert "ESC close" in _footer[0]
