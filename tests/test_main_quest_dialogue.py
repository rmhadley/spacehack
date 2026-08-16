"""Regression tests for main-quest NPC handoff state changes."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack.data.main_quest import find_main_quest_step
from src.spacehack.main_quest import _act0, _core, _objectives
from src.spacehack.mission import ActiveMission


def test_lab_q1_sample_readout_renders_with_giver_portrait(monkeypatch):
    """The door-bump step carries a giver dialogue so its completion flavor

    reaches the readout popup (show_step_readout requires a dialogue NPC).
    """
    _step = find_main_quest_step("lab_q1_sample")
    assert _step.dialogues
    assert _step.completion_flavor

    _ctx = SimpleNamespace(main_quest_chain="lab", main_quest_gate={})
    _rendered = []
    monkeypatch.setattr(
        _act0,
        "show_quest_readout",
        lambda _ctx, _npc, _body: _rendered.append((_npc.name, _body)),
    )

    assert _objectives.show_step_readout(_ctx, _step)
    assert _rendered
    _name, _body = _rendered[0]
    assert _name == "Research Officer"
    assert _step.completion_flavor in _body


def test_bump_q1_does_not_fire_accept_offer(monkeypatch):
    """The lab q1 is a door-bump, not a talk step - no accept offer fires."""
    _ctx = SimpleNamespace(
        main_quest_chain="lab",
        main_quest_progress={
            "prologue_seek_help": "completed",
            "lab_q1_sample": "available",
        },
        main_quest_gate={},
    )
    _offers = []
    monkeypatch.setattr(
        _act0,
        "show_help_offer",
        lambda _ctx, _npc, _step: _offers.append((_npc, _step))
        or _act0.OfferOutcome.DECLINE,
    )

    _act0.maybe_continue_chain(_ctx, "research_officer", "prologue_seek_help")

    assert _offers == []


def test_talk_q1_still_fires_accept_offer(monkeypatch):
    """Talk-commitment q1 steps (militia, etc.) keep their accept offer."""
    _ctx = SimpleNamespace(
        main_quest_chain="militia",
        main_quest_progress={
            "prologue_seek_help": "completed",
            "mil_q1_report": "available",
        },
        main_quest_gate={},
    )
    _offers = []
    monkeypatch.setattr(
        _act0,
        "show_help_offer",
        lambda _ctx, _npc, _step: _offers.append((_npc, _step))
        or _act0.OfferOutcome.DECLINE,
    )

    _act0.maybe_continue_chain(_ctx, "militia_captain", "prologue_seek_help")

    assert _offers == [("militia_captain", "mil_q1_report")]


def test_story_crate_loads_even_when_mission_log_full():
    """Main-quest crates bypass MAX_ACTIVE_MISSIONS (6/5 is allowed)."""
    _step = find_main_quest_step("lab_q2_delivery")
    _ship = SimpleNamespace(mission_reserved=0)
    _ctx = SimpleNamespace(
        main_quest_progress={"lab_q2_delivery": "available"},
        player_owned_ship=_ship,
        player_active_missions=[
            ActiveMission(mission_id=f"dummy:{_i}") for _i in range(5)
        ],
        log=SimpleNamespace(add_colored=lambda *_args, **_kwargs: None),
    )

    assert _core._trigger_smuggle_crate(_ctx, _step)

    assert len(_ctx.player_active_missions) == 6
    assert _ctx.main_quest_progress["lab_q2_delivery"] == "active"
    assert _ship.mission_reserved == 1


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
