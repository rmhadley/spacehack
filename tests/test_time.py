"""Tests for the game-clock helpers in time.py."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack.time import month_index


def test_month_index_combines_year_and_month():
    """A unique integer increases across month AND year rollovers."""
    assert month_index(SimpleNamespace(time_year=2200, time_month=1)) == 2200 * 12 + 1
    assert month_index(SimpleNamespace(time_year=2200, time_month=12)) == 2200 * 12 + 12
    assert month_index(SimpleNamespace(time_year=2201, time_month=1)) == 2201 * 12 + 1


def test_month_index_falls_back_to_start_date_for_light_doubles():
    """Missing clock fields resolve to the canonical 2200-01 start date."""
    assert month_index(SimpleNamespace()) == 2200 * 12 + 1


def test_space_wait_passes_a_full_day(monkeypatch):
    """User ruling 2026-09-10 (doc 41 phase-2 playtest): pressing . in
    space moves the world — so a day passes. The wait runs the
    per-step passes on the old day, THEN flips the clock (movement
    ordering). A BOARDED wait is a fight, not a wait — no day."""
    from src.spacehack import game_loop

    monkeypatch.setattr(game_loop, "_run_combat_loop", lambda *_a, **_k: None)
    ctx = SimpleNamespace(
        time_day=5, time_month=1, time_year=2200, economy_state={},
        player_active_missions=[], game_map=object(), player=object(),
        log=SimpleNamespace(add=lambda _m: None, add_colored=lambda _m, _c: None),
    )
    state = SimpleNamespace(
        ctx=ctx, console=object(), player=SimpleNamespace(pos=None),
        current_mode="space", player_owned_ship=object(),
        player_active_missions=[], game_map=object(),
    )
    period = SimpleNamespace(kind="keydown", key_name=".")

    assert game_loop._handle_wait_event(state, period) == "HANDLED"
    assert (ctx.time_day, ctx.time_month, ctx.time_year) == (6, 1, 2200)

    # A fight that boards consumes the wait: the clock stands down.
    monkeypatch.setattr(game_loop, "_run_combat_loop", lambda *_a, **_k: "BOARDED")
    ctx.time_day = 6
    assert game_loop._handle_wait_event(state, period) == "HANDLED"
    assert ctx.time_day == 6
