"""Regression tests for live-session city bookkeeping in the gameplay loop.

The main-quest dialogue layer gates planet-restricted NPC talk on
``ctx.current_city_id`` (see ``main_quest/_dialogue.py``), so landing on a
planet must keep that field in sync with the loop's ``state.current_city_id``.

The bug: landing updated only ``state.current_city_id``, so a planet-gated
delivery dialogue (e.g. the lab sample handover) never resolved until a
save/continue restored ``ctx.current_city_id`` from the save file.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import game_loop


def _state():
    ctx = SimpleNamespace(current_city_id="earth")
    return game_loop.GameLoopState(
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


def test_movement_interaction_syncs_ctx_current_city_id(monkeypatch):
    """A landing that changes state.current_city_id must sync ctx too."""
    state = _state()

    def _fake_resolve(s, code, blocker, dx, dy):
        # Simulate _resolve_planet_wall's LAND branch updating the city.
        s.current_city_id = "mercury"
        return None

    monkeypatch.setattr(game_loop, "resolve_blocker", _fake_resolve)

    game_loop._apply_movement_interaction(state, "wall", object(), 0, 1)

    assert state.current_city_id == "mercury"
    assert state.ctx.current_city_id == "mercury"
