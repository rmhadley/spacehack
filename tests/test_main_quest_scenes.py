"""Tests for the scene registry + auto-load-next-smuggle flag (Phase 3).

Steps declare which cutscene plays at their beat via ``MainQuestStep.scene``;
``main_quest/_scenes.py`` maps each id to its implementation and
``play_scene`` dispatches it. The ``auto_load_next_smuggle`` flag controls
whether a smuggle step's crate auto-loads the moment it becomes available.
These tests pin the registry contents, the dispatch/no-op/raise semantics,
and the auto-load flag.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack.data.main_quest import MainQuestStep, list_main_quest_steps
from src.spacehack.main_quest import _act0, _act1, _core, _scenes

_CTX = SimpleNamespace()


# ---------------------------------------------------------------------------
# Registry contents + data integrity
# ---------------------------------------------------------------------------


def test_scene_registry_maps_every_declared_scene():
    assert set(_scenes.registered_scene_ids()) == {
        "prologue_transmission",
        "sealed_door_discover",
        "sealed_door_open",
        "orbit_disclosure",
    }
    assert _scenes._SCENES["prologue_transmission"] is _act0.show_prologue_transmission
    assert _scenes._SCENES["sealed_door_open"] is _act0._play_sealed_door_open
    assert _scenes._SCENES["orbit_disclosure"] is _act1.maybe_show_post_prison_orbit


def test_every_declared_scene_id_resolves():
    _ids = set(_scenes.registered_scene_ids())
    for _step in list_main_quest_steps():
        if _step.scene:
            assert _step.scene in _ids, f"{_step.id} -> {_step.scene}"


def test_scene_ids_are_declared_on_the_expected_steps():
    from src.spacehack.data.main_quest import find_main_quest_step as _fms
    assert _fms("prologue_signal").scene == "prologue_transmission"
    assert _fms("prologue_mars_entrance").scene == "sealed_door_discover"
    assert _fms("prologue_open").scene == "sealed_door_open"
    assert _fms("act1_prison").scene == "orbit_disclosure"
    # Generic beats carry no scene (no cutscene at their step).
    assert _fms("prologue_seek_help").scene == ""
    assert _fms("bar_q2_proof").scene == ""


# ---------------------------------------------------------------------------
# play_scene dispatch / no-op / raise
# ---------------------------------------------------------------------------


def test_play_scene_dispatches_to_the_registered_impl(monkeypatch):
    _calls = []
    _scenes._build()
    monkeypatch.setitem(
        _scenes._SCENES, "prologue_transmission",
        lambda ctx, **kw: _calls.append(ctx),
    )
    _scenes.play_scene(_CTX, "prologue_signal")
    assert _calls == [_CTX]


def test_sealed_door_discover_scene_plays_the_discover_overlay(monkeypatch):
    _beats = []
    monkeypatch.setattr(
        _act0, "show_sealed_door_overlay", lambda ctx, beat: _beats.append(beat),
    )
    _scenes.play_scene(_CTX, "prologue_mars_entrance")
    assert _beats == ["discover"]


def test_sealed_door_open_impl_animates_then_overlays(monkeypatch):
    # The registry maps "sealed_door_open" -> _play_sealed_door_open
    # (see test_scene_registry_maps_every_declared_scene); this pins
    # that impl's presentation order.
    _order = []
    monkeypatch.setattr(
        _act0, "animate_signal_door_opening", lambda *a, **k: _order.append("animate"),
    )
    monkeypatch.setattr(
        _act0, "show_sealed_door_overlay", lambda ctx, beat: _order.append(beat),
    )
    _ctx = SimpleNamespace(game_map=None, player=SimpleNamespace(pos=None))
    _act0._play_sealed_door_open(_ctx)
    assert _order == ["animate", "open"]


def test_orbit_disclosure_scene_forwards_kwargs(monkeypatch):
    _seen = []
    _scenes._build()
    monkeypatch.setitem(
        _scenes._SCENES, "orbit_disclosure",
        lambda ctx, **kw: _seen.append(kw) or True,
    )
    assert _scenes.play_scene(_CTX, "act1_prison", from_mars_prison=True) is True
    assert _seen == [{"from_mars_prison": True}]


def test_play_scene_noops_for_steps_without_a_scene():
    assert _scenes.play_scene(_CTX, "prologue_seek_help") is None


def test_play_scene_noops_for_unknown_step():
    assert _scenes.play_scene(_CTX, "not_a_real_step") is None


def test_play_scene_raises_on_unregistered_scene(monkeypatch):
    _fake = MainQuestStep(id="fake", scene="bogus_scene")
    monkeypatch.setattr(_scenes, "find_main_quest_step", lambda _id: _fake)
    try:
        _scenes.play_scene(_CTX, "fake")
    except ValueError as _error:
        assert "bogus_scene" in str(_error)
    else:
        raise AssertionError("expected ValueError for unregistered scene")


# ---------------------------------------------------------------------------
# auto_load_next_smuggle
# ---------------------------------------------------------------------------


def _smuggle_ctx(progress: dict, ship=None):
    return SimpleNamespace(
        main_quest_chain="bar",
        main_quest_progress=progress,
        player_owned_ship=ship or SimpleNamespace(mission_reserved=0, inventory={}),
        player_active_missions=[],
        log=SimpleNamespace(add=lambda *a, **k: None, add_colored=lambda *a, **k: None),
    )


def test_auto_load_default_true_loads_next_smuggle_crate():
    """Real chain: bar_q3 (delve) -> bar_q4 (smuggle) auto-loads the cell."""
    _ship = SimpleNamespace(mission_reserved=0, inventory={})
    _ctx = _smuggle_ctx({
        "bar_q3_rigparts": "completed",
        "bar_q4_blackmarket": "available",
    }, ship=_ship)
    _core._maybe_auto_trigger_next_smuggle(_ctx, "bar_q3_rigparts")
    assert _ship.mission_reserved == 1  # the cell, singular (doc 36)
    assert len(_ctx.player_active_missions) == 1
    assert _ctx.player_active_missions[0].main_quest_step_id == "bar_q4_blackmarket"
    assert _ctx.main_quest_progress["bar_q4_blackmarket"] == "active"


def test_auto_load_respects_opt_out(monkeypatch):
    """A smuggle step with auto_load_next_smuggle=False is not auto-loaded."""
    _next = MainQuestStep(
        id="fake_smuggle",
        objective_type="smuggle",
        smuggle_good_id="x",
        smuggle_cargo_size=2,
        auto_load_next_smuggle=False,
    )
    monkeypatch.setattr(_core, "main_quest_step_after", lambda *a, **k: _next)
    _ctx = _smuggle_ctx({"bar_q3_rigparts": "completed", "fake_smuggle": "available"})
    _core._maybe_auto_trigger_next_smuggle(_ctx, "bar_q3_rigparts")
    assert _ctx.player_active_missions == []
    assert _ctx.player_owned_ship.mission_reserved == 0
    assert _ctx.main_quest_progress["fake_smuggle"] == "available"
