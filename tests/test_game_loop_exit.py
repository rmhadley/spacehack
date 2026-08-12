"""Regression tests for gameplay-loop exit initialization."""

from types import SimpleNamespace

from src.spacehack import __main__ as game_main


def test_save_and_exit_accepts_fresh_city_without_space_player(monkeypatch):
    calls = []
    monkeypatch.setattr(game_main, "_save_game", lambda *args, **kwargs: calls.append(kwargs))

    ctx = SimpleNamespace()
    game_main._save_and_exit(ctx, "city", "earth", None)

    assert calls == [{
        "mode": "city",
        "city_id": "earth",
        "system_id": game_main.solar_system_module.current_solar_system_id,
    }]


def test_save_and_exit_preserves_dungeon_space_player_position(monkeypatch):
    calls = []
    monkeypatch.setattr(game_main, "_save_game", lambda *args, **kwargs: calls.append(kwargs))

    ctx = SimpleNamespace()
    space_player = SimpleNamespace(pos=SimpleNamespace(x=17, y=23))
    game_main._save_and_exit(ctx, "dungeon", "mars", space_player)

    assert calls == [{
        "mode": "dungeon",
        "city_id": "mars",
        "system_id": game_main.solar_system_module.current_solar_system_id,
        "space_player_pos": (17, 23),
    }]
