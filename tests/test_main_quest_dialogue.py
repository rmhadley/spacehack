"""Regression tests for main-quest NPC handoff state changes."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack.data.main_quest import find_main_quest_step
from src.spacehack.main_quest import _core
from src.spacehack.mission import ActiveMission


def test_smuggle_handover_consumes_cargo_inventory(monkeypatch):
    """Handing over a recorder removes it from ordinary ship cargo."""
    _step = find_main_quest_step("lab_q6_return")
    _ship = SimpleNamespace(
        mission_reserved=1,
        inventory={"reference_recorder": 2},
    )
    _mission = ActiveMission(
        mission_id="mq:lab_q6_return",
        main_quest_step_id="lab_q6_return",
    )
    _ctx = SimpleNamespace(
        player_owned_ship=_ship,
        player_active_missions=[_mission],
        log=SimpleNamespace(add_colored=lambda *_args: None),
    )
    monkeypatch.setattr(_core, "complete_step", lambda _ctx, _step_id: True)

    assert _core._complete_smuggle_handover(_ctx, _step)

    assert _ship.inventory == {"reference_recorder": 1}
    assert _ship.mission_reserved == 0
    assert _ctx.player_active_missions == []
