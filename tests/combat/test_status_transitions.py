"""The status transition seams (doc 103 Build C).

Landing removes every debuff beside the rest's full heal (the
catalog-side default — buffs pause through the flight and resume);
boarding fires the transition at BOTH seams — the launch success
path and the dungeon-exit-to-space flip — removing nothing in v1
(no row declares board until the future fire debuff). Every seam
is ONE call to the engine helper; removal is silent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.combat import _statuses
from src.spacehack.data.statuses import (
    REGEN_ID, STAGGERED_ID, STIM_ID,
)
from tests.support.asyncutil import run


def _carried_statuses():
    """A carried container: two buffs and a debuff."""
    container: dict = {}
    _statuses.apply(container, REGEN_ID, theater="ground")
    _statuses.apply(container, STIM_ID, theater="ground")
    _statuses.apply(container, STAGGERED_ID, theater="ground")
    return container


def test_landing_removes_debuffs_keeps_buffs_and_heals(monkeypatch):
    """The land seam (doc 103 Build C), through the production
    landing path: the rest's full heal stands, every debuff dies at
    the rest line (the catalog-side default), the buffs survive to
    resume on the ground."""
    from src.spacehack import game_interactions
    from src.spacehack import solar_system as solar_module
    from tests.support.landing import landing_state

    monkeypatch.setattr(
        solar_module, "current_solar_system_id",
        solar_module.current_solar_system_id,
    )
    _container = _carried_statuses()
    state = landing_state(active_statuses=_container)
    # Below max so the rest's heal actually fires (the harness
    # defaults to full HP, which would make the heal pin vacuous).
    state.ctx.ground_hp = 10
    monkeypatch.setattr(
        game_interactions, "_run_cargo_scan",
        _async_noop(),
    )
    monkeypatch.setattr(
        game_interactions, "_animate_ship_to_y",
        _async_noop(),
    )

    assert run(game_interactions.land_at_city(state, "tc_b")) == "CONTINUE"

    assert state.ctx.ground_hp == state.ctx.ground_max_hp  # the rest
    assert set(_container) == {REGEN_ID, STIM_ID}  # staggered died at it


def test_launch_board_seam_removes_nothing_in_v1(monkeypatch):
    """The board seam's launch site (doc 103 Build C): firing with
    zero removals — nothing declares board until the future fire
    debuff — while the mode flips to space (the paused rows then
    freeze at the space walk)."""
    from src.spacehack import game_interactions
    from src.spacehack.menus import ShipMenuAction

    _container = _carried_statuses()
    _ctx = SimpleNamespace(
        active_statuses=_container, game_map=None, player=None,
    )
    _map, _player = object(), object()
    monkeypatch.setattr(
        game_interactions, "_run_ship_menu",
        _async_value(ShipMenuAction.LAUNCH),
    )
    monkeypatch.setattr(
        game_interactions, "_launch_owned_ship",
        _async_value((_map, _player)),
    )
    state = SimpleNamespace(
        ctx=_ctx, console=None, current_mode="city", current_city_id="earth",
        player_owned_ship=None, city_game_map=None, city_player=None,
        game_map=None, player=None,
    )
    blocker = SimpleNamespace(owned=True, ship_id="cruiser")

    assert run(game_interactions._resolve_ship_blocker(
        state, blocker,
    )) == "CONTINUE"

    assert state.current_mode == "space"
    assert set(_container) == {REGEN_ID, STIM_ID, STAGGERED_ID}  # v1: none


def test_dungeon_exit_board_seam_removes_nothing_in_v1(monkeypatch):
    """The board seam's second site (doc 103 Build C): exiting a
    derelict/salvage interior re-enters the ship — the exact
    scenario the fire vocabulary exists for — and fires the SAME
    zero-removal call in v1."""
    from src.spacehack import game_flow

    _container = _carried_statuses()
    _ctx = SimpleNamespace(active_statuses=_container, game_map=None, player=None)
    _space_map, _space_player = object(), object()
    monkeypatch.setattr(
        game_flow, "_leave_dungeon_to_space",
        _async_value((_space_map, _space_player)),
    )
    _tiles = [[world.DUNGEON_FLOOR for _ in range(10)] for _ in range(6)]
    _dungeon = world.GameMap(10, 6, _tiles, [])

    _result = run(game_flow._handle_dungeon_exit(
        _ctx, _dungeon, None, None, None, [], SimpleNamespace(add=lambda *_a, **_k: None),
    ))

    assert _result[2] == "space"
    assert _ctx.game_map is _space_map
    assert set(_container) == {REGEN_ID, STIM_ID, STAGGERED_ID}  # v1: none


def _async_value(value):
    async def _fake(*_args, **_kwargs):
        return value
    return _fake


def _async_noop():
    async def _fake(*_args, **_kwargs):
        return None
    return _fake
