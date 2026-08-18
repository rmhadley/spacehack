"""Tests for the main-quest objective handler registry (Phase 1).

The registry replaces the scattered if/elif objective dispatch: every
cataloged objective type must resolve to a handler, unknown types must not,
and the type-specific hooks (smuggle gating, smuggle trigger) keep their
documented behaviour.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack.data.main_quest import list_main_quest_steps
from src.spacehack.main_quest.handlers import (
    _smuggle_option_gating,
    _smuggle_trigger,
    handler_for,
    registered_objective_types,
)


def test_every_cataloged_objective_type_has_a_handler():
    """Every objective type used by the step catalog resolves to a handler."""
    _used = {step.objective_type for step in list_main_quest_steps()}
    assert _used  # sanity: the catalog is not empty
    for _objective_type in sorted(_used):
        assert handler_for(_objective_type) is not None, (
            f"objective_type {_objective_type!r} has no registered handler"
        )


def test_unknown_objective_type_has_no_handler():
    """An unregistered objective type resolves to None, never a crash."""
    assert handler_for("not_a_real_objective") is None


def test_registered_types_cover_the_core_objectives():
    _registered = set(registered_objective_types())
    assert {
        "talk",
        "goods",
        "smuggle",
        "salvage",
        "visit",
        "bump",
        "delve",
        "bounty",
        "prison",
    } <= _registered


def test_talk_handler_has_no_trigger_hook():
    """talk steps fall through to complete_step (the default trigger)."""
    _handler = handler_for("talk")
    assert _handler is not None
    assert _handler.on_trigger is None


def test_delve_and_salvage_secure_quest_loot():
    """Only loot-bearing types expose secure_quest_loot to secure_quest_loot."""
    assert handler_for("delve").secures_quest_loot
    assert handler_for("salvage").secures_quest_loot
    assert not handler_for("talk").secures_quest_loot
    assert not handler_for("smuggle").secures_quest_loot


def test_bounty_and_salvage_expose_spawn_creation():
    """Only space-spawn types expose an ensure_spawns hook."""
    assert handler_for("bounty").ensure_spawns is not None
    assert handler_for("salvage").ensure_spawns is not None
    assert handler_for("delve").ensure_spawns is None


def test_smuggle_option_gating_giver_receiver():
    """Smuggle gating: giver offers while the crate is NOT held, receiver
    only while it IS held (mirrors the pre-refactor quest_option_for)."""
    _step = SimpleNamespace(id="bar_q4_blackmarket", requires_npc_id="wolf_barkeep")
    _ctx = SimpleNamespace(
        player_active_missions=[
            SimpleNamespace(main_quest_step_id="bar_q4_blackmarket"),
        ],
    )
    # Crate held: receiver sees the option, giver does not.
    assert _smuggle_option_gating(_ctx, _step, "wolf_barkeep")
    assert not _smuggle_option_gating(_ctx, _step, "old_smuggler")
    # Crate not held: giver sees the option, receiver does not.
    _ctx.player_active_missions = []
    assert _smuggle_option_gating(_ctx, _step, "old_smuggler")
    assert not _smuggle_option_gating(_ctx, _step, "wolf_barkeep")


def test_smuggle_trigger_loads_when_available_hands_over_when_active(monkeypatch):
    """The smuggle on_trigger hook loads the crate when available and hands
    it over when active (mirrors the pre-refactor trigger_dialogue branch)."""
    from src.spacehack.main_quest import _core

    _step = SimpleNamespace(id="lab_q2_delivery")
    _ctx = SimpleNamespace(main_quest_progress={"lab_q2_delivery": "available"})
    _calls: list[str] = []
    monkeypatch.setattr(
        _core,
        "_trigger_smuggle_crate",
        lambda _ctx, _step: _calls.append("load") or True,
    )
    monkeypatch.setattr(
        _core,
        "_complete_smuggle_handover",
        lambda _ctx, _step: _calls.append("handover") or True,
    )

    assert _smuggle_trigger(_ctx, _step)
    assert _calls == ["load"]

    _ctx.main_quest_progress["lab_q2_delivery"] = "active"
    assert _smuggle_trigger(_ctx, _step)
    assert _calls == ["load", "handover"]
