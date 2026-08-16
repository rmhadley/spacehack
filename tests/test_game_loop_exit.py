"""Regression tests for gameplay-loop exit initialization."""

from types import SimpleNamespace

from src.spacehack import __main__ as game_main
from src.spacehack import game_loop, world


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


def test_secured_salvage_exit_removes_wreck_and_guard_squad():
    """Live space maps must match the cleaned save spawn registry."""
    _space_map = world.GameMap(12, 12, [], [])
    _wreck = world.Entity(
        "D", (190, 140, 60), world.Position(8, 5),
        name="Derelict Scout", npc_ship_id="derelict_scout",
    )
    _wreck.salvage_wreck_spawn_id = "lab_derelict_guardian_wreck"
    _leader = world.Entity(
        "P", (255, 80, 80), world.Position(3, 5),
        name="Pirate Captain", npc_ship_id="pirate_captain",
    )
    _leader.bounty_spawn_id = "lab_derelict_guardian"
    _leader.bounty_squad_id = "lab_derelict_guardian"
    _escort = world.Entity(
        "P", (255, 80, 80), world.Position(5, 5),
        name="Pirate Raider", npc_ship_id="pirate_raider",
    )
    _escort.bounty_squad_id = "lab_derelict_guardian"
    _unrelated = world.Entity(
        "P", (255, 80, 80), world.Position(10, 10),
        name="Other Pirate", npc_ship_id="pirate_scout",
    )
    _unrelated.bounty_squad_id = "other_mission"
    _space_map.entities.extend((_wreck, _leader, _escort, _unrelated))

    game_loop._remove_secured_salvage_entities(
        _space_map, "lab_derelict_guardian_wreck",
    )

    assert _space_map.entities == [_unrelated]
