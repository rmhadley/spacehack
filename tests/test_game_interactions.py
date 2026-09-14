"""Regression tests for live-session city bookkeeping in planet landing.

The main-quest dialogue layer gates planet-restricted NPC talk on
``ctx.current_city_id`` (see ``main_quest/_dialogue.py``), so landing on a
planet must update both the loop's ``state.current_city_id`` and
``ctx.current_city_id``. The bug: landing updated only ``state``, so a
planet-gated delivery dialogue (e.g. the lab sample handover) never resolved
until a save/continue restored ``ctx.current_city_id`` from the save file.
"""

from __future__ import annotations
from tests.support.asyncutil import run, as_async

from types import SimpleNamespace

import pytest

from src.spacehack import game_interactions
from src.spacehack.npc import TalkOutcome


def _state(city_id: str = "earth"):
    ctx = SimpleNamespace(
        current_city_id=city_id,
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
        current_city_id=city_id,
        player_owned_ship=None,
        player_active_missions=[],
    )
    return state


def test_bump_talk_resolves_planet_override_npcs(monkeypatch):
    """Procyon C's Campus Cook is a spec npc_override, not a catalog id.

    Bump-talk resolved npc_id through the global catalog only, so
    bumping the mess-hall cook crashed with KeyError: unknown npc id
    'cook'. Resolution must go through the planet (find_planet_npc).
    """
    state = _state(city_id="proc_planet_2")
    blocker = SimpleNamespace(npc_id="cook")
    seen = {}

    async def fake_talk(_ctx, npc_obj, deliver_missions=None):
        seen["npc"] = npc_obj
        return TalkOutcome.QUIT, None

    monkeypatch.setattr(game_interactions, "_run_npc_talk", fake_talk)

    result = run(game_interactions._resolve_npc_blocker(state, blocker))

    assert result == "QUIT"
    assert seen["npc"].name == "Campus Cook"


def test_bump_talk_unknown_npc_still_raises_keyerror():
    state = _state(city_id="earth")

    with pytest.raises(KeyError):
        run(game_interactions._resolve_npc_blocker(state, SimpleNamespace(npc_id="no_such_npc")))


def test_talk_dialogue_resolves_planet_override_flavor():
    """The frame that still crashed after the resolver fix: the talk
    modal's flavor fallback re-looked the override-only id up in the
    global catalog (KeyError 'cook'). The resolved speaker covers it."""
    from src.spacehack.data.planets import find_planet_npc
    from src.spacehack.main_quest import resolve_npc_dialogue

    ctx = SimpleNamespace(
        main_quest_progress={},
        main_quest_chain=None,
        current_city_id="proc_planet_2",
    )
    cook = find_planet_npc("cook", "proc_planet_2")

    text, trigger = resolve_npc_dialogue(ctx, "cook", speaker=cook)

    assert text == cook.flavor_text
    assert trigger is None


def test_landing_syncs_ctx_current_city_id(monkeypatch):
    """Landing on Mercury must update ctx.current_city_id, not just state."""
    state = _state()
    ctx = state.ctx

    monkeypatch.setattr(
        game_interactions,
        "_run_planet_menu",
        as_async(lambda _ctx, _planet: (game_interactions.PlanetMenuOutcome.LAND, None)),
    )
    monkeypatch.setattr(game_interactions, "_run_cargo_scan", as_async(lambda _ctx, _pid: None))

    run(game_interactions._resolve_planet_wall(state, "mercury"))

    assert state.current_city_id == "mercury"
    assert ctx.current_city_id == "mercury"
    assert state.current_mode == "city"
