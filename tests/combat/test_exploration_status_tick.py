"""The exploration status tick (doc 103 Build C).

One completed dungeon/interior turn = one status tick: heal events
restore ``ctx.ground_hp`` clamped at the refreshed max, ap events
drop (no AP pool out of combat), tick/expire lines log per the
adapter contract, and the seam hook at
``game_flow._dungeon_post_move_tick``'s top drives it for every
dungeon-mode step, wait, goto, and auto-explore path (city streets
never dispatch through the seam — their steps freeze statuses BY
CONSTRUCTION; city interiors are dungeon-mode maps, so they tick).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.combat import _statuses
from src.spacehack.combat._ground_effects import advance_exploration_statuses
from src.spacehack.data.statuses import (
    REGEN_ID, STAGGERED_ID, STIM_ID,
)
from tests.support.asyncutil import run


def _log_spy():
    lines: list[str] = []

    def _add(text, *_a, **_k):
        lines.append(text)

    return SimpleNamespace(add=_add, add_colored=_add), lines


def _explore_ctx(ground_hp: int, ground_max_hp: int):
    """A minimal exploration ctx: stamina 10 keeps the refreshed max
    at 25 (20 + 10//2, no armor/traits/species)."""
    _log, _lines = _log_spy()
    _ctx = SimpleNamespace(
        log=_log,
        ground_hp=ground_hp,
        ground_max_hp=ground_max_hp,
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        equipped_ground_armor={},
        player_traits=[],
        active_statuses={},
        character_info={},
    )
    return _ctx, _lines


def test_regen_heals_per_step_clamped_at_max():
    _ctx, lines = _explore_ctx(ground_hp=20, ground_max_hp=25)
    _statuses.apply(_ctx.active_statuses, REGEN_ID, source="Med Pack", theater="ground")
    advance_exploration_statuses(_ctx)
    assert _ctx.ground_hp == 22
    assert lines == ["Med Pack regeneration: +2 HP."]
    advance_exploration_statuses(_ctx)
    assert _ctx.ground_hp == 24
    advance_exploration_statuses(_ctx)  # clamped at 25, then expire
    assert _ctx.ground_hp == 25
    assert lines[-1] == "Med Pack regeneration: +1 HP."
    assert REGEN_ID not in _ctx.active_statuses


def test_the_clamp_reads_the_refreshed_max_not_the_stale_one():
    """The ground-max staleness law: a stale stored max (23) must not
    cap the heal — the adapter refreshes before clamping (stamina 10
    refreshes the ceiling to 25; the grow kernel raises current HP by
    the max delta first, then the regen heals on top)."""
    _ctx, lines = _explore_ctx(ground_hp=20, ground_max_hp=23)
    _statuses.apply(_ctx.active_statuses, REGEN_ID, source="Med Pack", theater="ground")
    advance_exploration_statuses(_ctx)
    assert _ctx.ground_max_hp == 25
    assert _ctx.ground_hp == 24  # 20 +2 (grow) +2 (regen)
    assert lines == ["Med Pack regeneration: +2 HP."]


def test_regen_at_full_hp_decrements_silently():
    _ctx, lines = _explore_ctx(ground_hp=25, ground_max_hp=25)
    _statuses.apply(_ctx.active_statuses, REGEN_ID, theater="ground")
    advance_exploration_statuses(_ctx)
    # Tick line only on healed > 0 (the adapter contract).
    assert _ctx.ground_hp == 25
    assert lines == []
    assert _ctx.active_statuses[REGEN_ID].remaining_turns == 2


def test_stim_spends_duration_with_no_ap_effect():
    _ctx, _lines = _explore_ctx(ground_hp=20, ground_max_hp=25)
    _statuses.apply(_ctx.active_statuses, STIM_ID, theater="ground")
    advance_exploration_statuses(_ctx)
    # No AP pool exists out of combat: the duration walks down, the
    # +1 arrives never, and nothing raises.
    assert _ctx.active_statuses[STIM_ID].remaining_turns == 2
    advance_exploration_statuses(_ctx)
    advance_exploration_statuses(_ctx)
    assert STIM_ID not in _ctx.active_statuses


def test_staggered_walks_off_and_logs_its_expire_line():
    _ctx, lines = _explore_ctx(ground_hp=20, ground_max_hp=25)
    _statuses.apply(_ctx.active_statuses, STAGGERED_ID, theater="ground")
    advance_exploration_statuses(_ctx)
    assert _ctx.active_statuses[STAGGERED_ID].remaining_turns == 1
    assert lines == []  # staggered has no tick line
    advance_exploration_statuses(_ctx)
    assert STAGGERED_ID not in _ctx.active_statuses
    assert lines == ["The stagger wears off."]


def test_space_tagged_rows_stay_frozen_while_exploring():
    _ctx, _lines = _explore_ctx(ground_hp=20, ground_max_hp=25)
    _statuses.apply(_ctx.active_statuses, STIM_ID, theater="space")
    advance_exploration_statuses(_ctx)
    assert _ctx.active_statuses[STIM_ID].remaining_turns == 3


def _dungeon_map() -> world.GameMap:
    _tiles = [
        [world.DUNGEON_FLOOR for _ in range(10)] for _ in range(6)
    ]
    return world.GameMap(10, 6, _tiles, [])


def test_the_dungeon_seam_ticks_at_the_top_before_combat():
    """The hook placement (doc 103 Build C): one seam call = one
    tick, fired whether or not the step starts a fight (the combat
    check runs after — with an empty map there is no fight)."""
    from src.spacehack import game_flow

    _ctx, lines = _explore_ctx(ground_hp=20, ground_max_hp=25)
    _ctx.player = world.Entity("@", (255, 255, 255), world.Position(2, 2))
    _ctx.dungeon_extension = None
    _map = _dungeon_map()
    _statuses.apply(_ctx.active_statuses, REGEN_ID, source="Med Pack", theater="ground")
    run(game_flow._dungeon_post_move_tick(_ctx, None, _map))
    assert _ctx.ground_hp == 22
    assert lines == ["Med Pack regeneration: +2 HP."]


def test_a_fight_starting_step_ticks_before_the_combat_check(monkeypatch):
    """The ruling's specific order, behaviorally: a step that STARTS
    a fight has already ticked by the time the combat check runs —
    the fake fight captures ground_hp at entry (reviewer C4 minor:
    the empty-map pin cannot see a regressive hook move)."""
    from src.spacehack import game_flow

    _ctx, _lines = _explore_ctx(ground_hp=20, ground_max_hp=25)
    _ctx.player = world.Entity("@", (255, 255, 255), world.Position(2, 2))
    _ctx.dungeon_extension = None
    _statuses.apply(_ctx.active_statuses, REGEN_ID, theater="ground")

    _hp_at_fight_entry: list[int] = []

    async def _fake_fight(*_a, **_k):
        _hp_at_fight_entry.append(_ctx.ground_hp)
        return None  # no fight result: the caller continues

    async def _no_activation(*_a, **_k):
        return None

    monkeypatch.setattr(game_flow, "_run_ground_combat_tick", _fake_fight)
    monkeypatch.setattr(
        "src.spacehack.dungeon_extensions.tick_activation",
        _no_activation,
    )
    run(game_flow._dungeon_post_move_tick(_ctx, None, _dungeon_map()))
    assert _hp_at_fight_entry == [22]  # the heal landed FIRST


def test_the_wait_handler_ticks_in_dungeon_not_in_city(monkeypatch):
    """Routing (doc 103 Build C): a dungeon WAIT dispatches through
    the seam (one tick); a city WAIT never does (the streets freeze —
    city waits advance ambient NPCs on their own path)."""
    from src.spacehack import game_loop

    _calls: list = []

    async def _seam_recorder(ctx, console, game_map, **_k):
        _calls.append(True)
        return None

    monkeypatch.setattr(game_loop, "_dungeon_post_move_tick", _seam_recorder)

    def _state(mode: str) -> SimpleNamespace:
        _ctx, _lines = _explore_ctx(ground_hp=20, ground_max_hp=25)
        return SimpleNamespace(
            ctx=_ctx, console=None, current_mode=mode,
            game_map=_dungeon_map(),
        )

    run(game_loop._handle_wait_event(_state("dungeon"), _period_press()))
    assert _calls == [True]
    run(game_loop._handle_wait_event(_state("city"), _period_press()))
    assert _calls == [True]  # the city wait added no seam call


def test_goto_and_autoexplore_thread_the_seam(monkeypatch):
    """Routing (doc 103 Build C): the goto and auto-explore handlers
    pass the dungeon seam as their post-step tick — the fakes invoke
    the seam exactly as the real runners do per step."""
    from src.spacehack import game_loop
    from src.spacehack import autoexplore as _autoexplore

    _calls: list = []

    async def _seam_recorder(ctx, console, game_map, **_k):
        _calls.append(True)
        return None

    async def _fake_goto(ctx, console, game_map, player, *, post_step_tick, **_k):
        await post_step_tick(ctx, console, game_map)
        return "DONE"

    async def _fake_explore(ctx, console, game_map, player, *, post_step_tick, **_k):
        await post_step_tick(ctx, console, game_map)
        return "DONE"

    monkeypatch.setattr(_autoexplore, "run_dungeon_goto", _fake_goto)
    monkeypatch.setattr(_autoexplore, "run_auto_explore", _fake_explore)
    # The handlers pass game_loop's own seam binding as post_step_tick —
    # patch it there so the fake's invocation lands in the recorder.
    monkeypatch.setattr(game_loop, "_dungeon_post_move_tick", _seam_recorder)

    def _state(mode: str) -> SimpleNamespace:
        _ctx, _lines = _explore_ctx(ground_hp=20, ground_max_hp=25)
        _ctx.player = world.Entity("@", (255, 255, 255), world.Position(2, 2))
        return SimpleNamespace(
            ctx=_ctx, console=None, current_mode=mode,
            game_map=_dungeon_map(), player=_ctx.player,
            map_w=10, map_h=6,
        )

    run(game_loop._handle_dungeon_automation_event(
        _state("dungeon"), _g_press(),
    ))
    run(game_loop._handle_dungeon_automation_event(
        _state("dungeon"), _o_press(),
    ))
    assert _calls == [True, True]


def _press(key_name: str) -> SimpleNamespace:
    """A project-shaped keydown fake (kind='keydown')."""
    return SimpleNamespace(kind="keydown", key_name=key_name)


def _period_press() -> SimpleNamespace:
    return _press(".")


def _g_press() -> SimpleNamespace:
    return _press("g")


def _o_press() -> SimpleNamespace:
    return _press("o")
