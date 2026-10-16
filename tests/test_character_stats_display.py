"""Stats-tab skill display tests (doc 47 phase 4, SETTLED 29; the
split-family pins added by doc 102 Brief 4.3).

Ship skills read base + installed-module bonuses — the same effective
sum combat uses — with the bonus annotated ("36 (+9)"); ground stats
and bonus-less skills show the plain value. Since Brief 4.3 the tab
is a SplitFrame: label = the padded skill name, value cell = the
display + the xN chrome count + the spend marker; the right pane
mirrors the selected bay's chrome.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.character_screen import _SKILL_DESCRIPTIONS, _stats_frame
from src.spacehack.ship import OwnedShip, StoredEquipment


def _ctx(modules=(), installed_chrome=()):
    return SimpleNamespace(
        stats=SimpleNamespace(gunnery=25, piloting=20, engineering=15),
        ground_stats=SimpleNamespace(reflexes=8, strength=10, stamina=9),
        player_owned_ship=OwnedShip(
            ship_id="starter", modules=tuple(modules),
        ),
        player_skill_points=0,
        player_traits=[],
        character_info={},
        player_level=1,
        ego_burn=0,
        installed_chrome=list(installed_chrome),
    )


def _row_texts(ctx):
    """The painted stat rows: label + the split family's two-space
    join + value cell (mirrors ``_draw_menu_style_row``)."""
    frame = _stats_frame(ctx, "CHARACTER", 0, 100, 0)
    return [
        f"{row.label}  {row.value}".rstrip()
        for row in frame.left_rows if row.selectable
    ]


def test_ship_skills_show_effective_with_annotated_bonus():
    rows = _row_texts(_ctx(modules=[
        StoredEquipment("module", "targeting_computer"),  # gunnery +10
    ]))
    assert rows[0] == "Gunnery        35 (+10)"
    assert rows[1] == "Piloting       20"
    assert rows[2] == "Engineering    15"


def test_quality_and_randart_bonuses_reach_the_display():
    from src.spacehack.data.randarts import roll_randart

    seed = 4242
    manifest = roll_randart("targeting_computer", seed)
    deltas = dict(manifest.axes)
    ship = _ctx(modules=[
        StoredEquipment(
            "module", "targeting_computer", quality=4, randart_seed=seed,
        ),
    ])
    rows = _row_texts(ship)
    gunnery_delta = 22 + deltas.get("gunnery_bonus", 0)  # 10 base x 2.2
    if gunnery_delta:
        assert rows[0] == f"Gunnery        {25 + gunnery_delta} ({gunnery_delta:+d})"
    else:
        assert rows[0] == "Gunnery        25"


def test_ground_stats_stay_plain():
    rows = _row_texts(_ctx())
    assert rows[3] == "Reflexes        8"
    assert rows[4] == "Strength       10"
    assert rows[5] == "Stamina         9"


def test_negative_bonuses_annotate_with_sign(monkeypatch):
    """A module that DRAWS a skill (none shipped today — a future
    drawback-capable axis or catalog row) renders effective (-N)."""
    import dataclasses

    from src.spacehack.data.modules import _registry, find_module

    probe = dataclasses.replace(find_module("targeting_computer"), gunnery_bonus=-12)
    monkeypatch.setitem(_registry(), "neg_probe", probe)
    rows = _row_texts(_ctx(modules=[StoredEquipment("module", "neg_probe")]))
    assert rows[0] == "Gunnery        13 (-12)"
    assert rows[1] == "Piloting       20"


def test_skill_bonus_free_modules_leave_plain_rows():
    rows = _row_texts(_ctx(modules=[
        StoredEquipment("module", "armor_mk4"),  # hull/power only
    ]))
    assert rows[0] == "Gunnery        25"
    assert rows[1] == "Piloting       20"


def test_spend_marker_still_reads_the_base_value():
    ctx = _ctx(modules=[StoredEquipment("module", "targeting_computer")])
    ctx.player_skill_points = 1
    rows = _row_texts(ctx)
    assert rows[0] == "Gunnery        35 (+10)  [+]"
    capped = _ctx(modules=[StoredEquipment("module", "targeting_computer")])
    capped.stats = SimpleNamespace(gunnery=100, piloting=20, engineering=15)
    capped.player_skill_points = 1
    assert _row_texts(capped)[0] == "Gunnery       110 (+10)  MAX"


def test_modified_skill_numbers_stay_in_the_plain_value_column():
    """A bonus annotation must not shift the number column (2026-09-23
    playtest: "Engineering 35 (+10)" sat one char left of its rows)."""
    rows = _row_texts(_ctx(modules=[
        StoredEquipment("module", "targeting_computer"),  # gunnery +10
    ]))
    plain = rows[1]           # Piloting 20
    boosted = rows[0]         # Gunnery 35 (+10)
    assert plain.index("20") == boosted.index("35")


# ---------------------------------------------------------------------------
# Brief 4.3 — the split family (prose ledger 16)
# ---------------------------------------------------------------------------

def test_stats_tab_adopts_the_split_family():
    from src.spacehack.pygame_split import SplitFrame

    frame = _stats_frame(_ctx(), "CHARACTER", 0, 100, 0)
    assert isinstance(frame, SplitFrame)
    assert (frame.left_label, frame.right_label) == ("Skills", "Chrome")
    assert frame.screen_tabs == ("STATS", "EQUIPMENT", "CARGO")
    assert frame.active_screen_tab == 0
    # The right pane is display-only: no row is selectable.
    assert all(not row.selectable for row in frame.right_rows)


def test_chrome_count_rides_the_value_cell():
    ctx = _ctx(installed_chrome=["terminus_optics"])
    rows = _row_texts(ctx)
    assert rows[0] == "Gunnery        25 x1"
    assert rows[1] == "Piloting       20"    # other bays unaffected
    ctx.player_skill_points = 1
    assert _row_texts(ctx)[0] == "Gunnery        25 x1  [+]"
    ctx.installed_chrome.append("terminus_smartlink")
    assert _row_texts(ctx)[3] == "Reflexes        8 x1  [+]"


def test_chrome_pane_lists_the_selected_bay_led_by_the_description():
    ctx = _ctx(installed_chrome=["terminus_optics", "terminus_smartlink"])
    # No gear line in this ctx: header rows 0-1, stat rows 2-7.
    gunnery = _stats_frame(ctx, "CHARACTER", 0, 100, 2)
    assert [row.label for row in gunnery.right_rows] == [
        _SKILL_DESCRIPTIONS["gunnery"],
        "Terminus Optics  Space crit chance 15%.",
    ]
    reflexes = _stats_frame(ctx, "CHARACTER", 0, 100, 5)
    assert [row.label for row in reflexes.right_rows] == [
        _SKILL_DESCRIPTIONS["reflexes"],
        "Terminus SmartLink  Ranged crit chance 15%.",
    ]


def test_header_selection_clamps_to_the_nearest_stat():
    """The dynamic runner seeds arbitrary indices (first build 0);
    a header row reads as the nearest stat, never a crash."""
    frame = _stats_frame(_ctx(), "CHARACTER", 0, 100, 0)
    assert frame.right_rows[0].label == _SKILL_DESCRIPTIONS["gunnery"]


def test_empty_bay_reads_nothing_installed():
    frame = _stats_frame(_ctx(), "CHARACTER", 0, 100, 0)
    assert [row.label for row in frame.right_rows] == [
        _SKILL_DESCRIPTIONS["gunnery"], "Nothing installed.",
    ]


def test_footers_carry_the_ruled_readout_and_state():
    ctx = _ctx()
    frame = _stats_frame(ctx, "CHARACTER", 0, 100, 0)
    assert frame.footer_left == "Ego 6  Burnt Ego 0  Install Room 6"
    assert frame.footer_right == "State: Natural"
    ctx.ego_burn = 4
    assert _stats_frame(ctx, "CHARACTER", 0, 100, 0).footer_right == (
        "State: Tainted"
    )


def test_row_budgets_stay_within_the_split_viewport():
    """The font-ladder constraint: header + stat rows (and the pane)
    fit the capped viewport the split reserves (MAX_VISIBLE_ROWS)."""
    from src.spacehack.pygame_split import MAX_VISIBLE_ROWS

    ctx = _ctx(installed_chrome=[
        "terminus_optics", "terminus_piloting_jack", "terminus_neural_stim",
        "terminus_nano_mesh", "terminus_muscle_fibers", "terminus_smartlink",
    ])
    ctx.transponder_cutout = True  # the Gear header line joins
    frame = _stats_frame(ctx, "CHARACTER", 0, 100, 0)
    assert len(frame.left_rows) == 9            # XP, Traits, Gear + 6 stats
    assert len(frame.right_rows) == 2           # description + one piece
    assert len(frame.left_rows) <= MAX_VISIBLE_ROWS
    assert len(frame.right_rows) <= MAX_VISIBLE_ROWS


def test_header_rows_carry_the_old_body_verbatim():
    frame = _stats_frame(_ctx(), "CHARACTER", 12, 100, 0)
    header = [row.label for row in frame.left_rows if not row.selectable]
    assert header == [
        "XP: 12 / 100    Skill points available: 0",
        "Traits: None",
    ]
