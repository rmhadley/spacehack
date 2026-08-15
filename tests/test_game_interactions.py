"""Regression tests for live-session city bookkeeping in planet landing.

The main-quest dialogue layer gates planet-restricted NPC talk on
``ctx.current_city_id`` (see ``main_quest/_dialogue.py``), so landing on a
planet must update both the loop's ``state.current_city_id`` and
``ctx.current_city_id``. The bug: landing updated only ``state``, so a
planet-gated delivery dialogue (e.g. the lab sample handover) never resolved
until a save/continue restored ``ctx.current_city_id`` from the save file.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import game_interactions


def _state():
    ctx = SimpleNamespace(
        current_city_id="earth",
        game_map=None,
        player=object(),
        militia_scanned=[],
        ground_hp=23,
        ground_max_hp=23,
    )
    state = game_interactions.GameLoopState(
        ctx=ctx,
        console=object(),
        map_w=40,
        map_h=24,
        log=SimpleNamespace(add=lambda _msg: None),
        stats=object(),
        game_map=object(),
        player=object(),
        current_mode="space",
        current_city_id="earth",
        player_owned_ship=None,
        player_active_missions=[],
    )
    return state


def test_landing_syncs_ctx_current_city_id(monkeypatch):
    """Landing on Mercury must update ctx.current_city_id, not just state."""
    state = _state()
    ctx = state.ctx

    monkeypatch.setattr(
        game_interactions,
        "_run_planet_menu",
        lambda _ctx, _planet: game_interactions.PlanetMenuOutcome.LAND,
    )
    monkeypatch.setattr(game_interactions, "_run_cargo_scan", lambda _ctx, _pid: None)
    monkeypatch.setattr(
        game_interactions.main_quest_module,
        "spawn_quest_npcs",
        lambda _ctx, _map, _pid, **_kw: None,
    )

    game_interactions._resolve_planet_wall(state, "mercury")

    assert state.current_city_id == "mercury"
    assert ctx.current_city_id == "mercury"
    assert state.current_mode == "city"
