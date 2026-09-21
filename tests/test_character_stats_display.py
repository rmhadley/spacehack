"""Stats-tab skill display tests (doc 47 phase 4, SETTLED 29).

Ship skills read base + installed-module bonuses — the same effective
sum combat uses — with the bonus annotated ("36 (+9)"); ground stats
and bonus-less skills show the plain value.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.character_screen import _stats_frame
from src.spacehack.ship import OwnedShip, StoredEquipment


def _ctx(modules=()):
    return SimpleNamespace(
        stats=SimpleNamespace(gunnery=25, piloting=20, engineering=15),
        ground_stats=SimpleNamespace(reflexes=8, strength=10, stamina=9),
        player_owned_ship=OwnedShip(
            ship_id="starter", modules=tuple(modules),
        ),
        player_skill_points=0,
        player_traits=[],
    )


def _row_texts(ctx):
    frame = _stats_frame(ctx, "CHARACTER", 0, 100, 0)
    return [row.text for row in frame.rows]


def test_ship_skills_show_effective_with_annotated_bonus():
    rows = _row_texts(_ctx(modules=[
        StoredEquipment("module", "targeting_computer"),  # gunnery +10
    ]))
    assert rows[0] == "Gunnery      35 (+10)"
    assert rows[1] == "Piloting      20"
    assert rows[2] == "Engineering   15"


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
        assert rows[0] == f"Gunnery      {25 + gunnery_delta} ({gunnery_delta:+d})"
    else:
        assert rows[0] == "Gunnery       25"


def test_ground_stats_stay_plain():
    rows = _row_texts(_ctx())
    assert rows[3] == "Reflexes       8"
    assert rows[4] == "Strength      10"
    assert rows[5] == "Stamina        9"


def test_negative_bonuses_annotate_with_sign(monkeypatch):
    """A module that DRAWS a skill (none shipped today — a future
    drawback-capable axis or catalog row) renders effective (-N)."""
    import dataclasses

    from src.spacehack.data.modules import _registry, find_module

    probe = dataclasses.replace(find_module("targeting_computer"), gunnery_bonus=-12)
    monkeypatch.setitem(_registry(), "neg_probe", probe)
    rows = _row_texts(_ctx(modules=[StoredEquipment("module", "neg_probe")]))
    assert rows[0] == "Gunnery      13 (-12)"
    assert rows[1] == "Piloting      20"


def test_skill_bonus_free_modules_leave_plain_rows():
    rows = _row_texts(_ctx(modules=[
        StoredEquipment("module", "armor_mk4"),  # hull/power only
    ]))
    assert rows[0] == "Gunnery       25"
    assert rows[1] == "Piloting      20"


def test_spend_marker_still_reads_the_base_value():
    ctx = _ctx(modules=[StoredEquipment("module", "targeting_computer")])
    ctx.player_skill_points = 1
    rows = _row_texts(ctx)
    assert rows[0] == "Gunnery      35 (+10)  [+]"
    capped = _ctx(modules=[StoredEquipment("module", "targeting_computer")])
    capped.stats = SimpleNamespace(gunnery=100, piloting=20, engineering=15)
    capped.player_skill_points = 1
    assert _row_texts(capped)[0] == "Gunnery      110 (+10)  MAX"
