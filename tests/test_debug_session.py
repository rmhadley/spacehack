"""Tests for the headless savegame debugging harness."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from src.spacehack import debug_session, saveload, world
from src.spacehack.game_context import GameContext
from src.spacehack.hud import HudStats
from src.spacehack.message_log import MessageLog


def _build_ctx() -> GameContext:
    """Build a small valid city context for a temporary save fixture."""
    game_map = world.GameMap(
        10,
        10,
        [[world.FLOOR for _ in range(10)] for _ in range(10)],
        [],
    )
    player = world.Entity("@", (255, 255, 255), world.Position(30, 20), "Player")
    game_map.entities.append(player)
    return GameContext(
        context=MagicMock(),
        character_info={
            "species_id": "human",
            "species_name": "Human",
            "class_id": "pirate",
            "class_name": "Pirate",
        },
        log=MessageLog(capacity=6),
        game_map=game_map,
        player=player,
        stats=HudStats(hp=30, max_hp=30, credits=100),
    )


def _save_fixture(monkeypatch, tmp_path: Path) -> Path:
    """Write a production-format city save to a temporary path."""
    path = tmp_path / "fixture.json"
    monkeypatch.setattr(saveload, "_autosave_path", lambda: path)
    from src.spacehack.engine import RNG

    RNG.seed(123)
    saveload.save_game(_build_ctx(), mode="city", city_id="earth", system_id="sol")
    return path


def test_loads_arbitrary_save_path_without_writing_source(monkeypatch, tmp_path):
    path = _save_fixture(monkeypatch, tmp_path)
    before = path.read_bytes()

    session = debug_session.HeadlessSaveSession.load(path)

    assert session.mode == "city"
    assert session.ctx.player.pos == world.Position(30, 20)
    assert path.read_bytes() == before


def test_summary_and_validation_are_mode_aware(monkeypatch, tmp_path):
    path = _save_fixture(monkeypatch, tmp_path)

    session = debug_session.HeadlessSaveSession.load(path)
    summary = session.summary()
    report = session.validate()

    assert report.valid
    assert report.errors == ()
    assert summary["mode"] == "city"
    assert summary["city"] == "earth"
    assert summary["player"] == {"x": 30, "y": 20}
    assert summary["map"] == {"width": 160, "height": 100}
    assert summary["rng_restored"]


def test_move_uses_production_collision_and_snapshot_diff(monkeypatch, tmp_path):
    path = _save_fixture(monkeypatch, tmp_path)
    session = debug_session.HeadlessSaveSession.load(path)
    before = session.snapshot()

    result = session.run(["move:left"])
    after = session.snapshot()
    changes = debug_session.snapshot_diff(before, after)

    assert result[0]["result"] == "moved"
    assert result[0]["from"] == [30, 20]
    assert result[0]["to"] == [29, 20]
    assert {change["path"] for change in changes} >= {"player.x", "entities"}


def test_city_rejects_dungeon_only_actions(monkeypatch, tmp_path):
    path = _save_fixture(monkeypatch, tmp_path)
    session = debug_session.HeadlessSaveSession.load(path)

    try:
        session.run(["explore"])
    except debug_session.SaveSessionError as exc:
        assert "require a dungeon save" in str(exc)
    else:
        raise AssertionError("explore unexpectedly ran on a city save")


def test_validation_reports_missing_required_fields(monkeypatch, tmp_path):
    path = _save_fixture(monkeypatch, tmp_path)
    payload = json.loads(path.read_text())
    del payload["stats"]
    path.write_text(json.dumps(payload))

    report = debug_session.validate_path(path)

    assert not report.valid
    assert any("missing required field: stats" in error for error in report.errors)


def test_validation_rejects_loader_fallback_from_declared_dungeon(monkeypatch, tmp_path):
    path = _save_fixture(monkeypatch, tmp_path)
    payload = json.loads(path.read_text())
    payload["current_mode"] = "dungeon"
    payload.pop("dungeon", None)
    path.write_text(json.dumps(payload))

    report = debug_session.validate_path(path)

    assert not report.valid
    assert "dungeon mode has no dungeon object" in report.errors


def test_validation_rejects_unknown_system_fallback(monkeypatch, tmp_path):
    path = _save_fixture(monkeypatch, tmp_path)
    payload = json.loads(path.read_text())
    payload["current_system_id"] = "missing-system"
    path.write_text(json.dumps(payload))

    report = debug_session.validate_path(path)

    assert not report.valid
    assert any("restored system 'sol'" in error for error in report.errors)


def test_city_move_notifies_tutorial(monkeypatch, tmp_path):
    path = _save_fixture(monkeypatch, tmp_path)
    session = debug_session.HeadlessSaveSession.load(path)
    notified = []
    monkeypatch.setattr(
        "src.spacehack.tutorial.notify_move",
        lambda ctx: notified.append(ctx),
    )

    result = session.run(["move:left"])

    assert result[0]["result"] == "moved"
    assert notified == [session.ctx]


def test_cli_returns_failure_for_missing_save(capsys, tmp_path):
    status = debug_session.main(["validate", str(tmp_path / "missing.json")])

    assert status == 1
    assert '"valid": false' in capsys.readouterr().out


def test_cli_refuses_output_path_equal_to_source(monkeypatch, tmp_path, capsys):
    path = _save_fixture(monkeypatch, tmp_path)
    before = path.read_bytes()

    status = debug_session.main(["snapshot", str(path), "--out", str(path)])

    assert status == 1
    assert path.read_bytes() == before
    assert "output path must differ" in capsys.readouterr().err


def test_run_stops_after_combat_pending(monkeypatch, tmp_path):
    path = _save_fixture(monkeypatch, tmp_path)
    session = debug_session.HeadlessSaveSession.load(path)
    monkeypatch.setattr(debug_session, "_post_player_step", lambda _session: True)

    results = session.run(["move:left", "advance:1"])

    assert results == [{
        "action": "move:left",
        "result": "combat_pending",
        "from": [30, 20],
        "to": [29, 20],
        "blocker": None,
    }]
    assert session.ctx.time_day == 1


def test_snapshot_diff_handles_added_and_removed_leaves():
    before = {"a": {"keep": 1, "removed": True}}
    after = {"a": {"keep": 2, "added": "yes"}}

    changes = debug_session.snapshot_diff(before, after)

    assert changes == [
        {"path": "a.added", "before": None, "after": "yes"},
        {"path": "a.keep", "before": 1, "after": 2},
        {"path": "a.removed", "before": True, "after": None},
    ]
