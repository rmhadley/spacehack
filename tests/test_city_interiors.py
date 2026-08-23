"""Regression tests for authored Earth city interiors."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import city_interiors, world
from src.spacehack.data.planets import load_planet


def _state(game_map, player, ctx):
    """Build the minimal transition state used by city interior helpers."""
    return SimpleNamespace(
        ctx=ctx,
        game_map=game_map,
        player=player,
        city_game_map=game_map,
        city_player=player,
        current_mode="city",
        log=ctx.log,
    )


def test_every_earth_functional_building_enters_a_distinct_authored_room():
    game_map = load_planet("earth")
    ctx = SimpleNamespace(interiors={}, game_map=game_map, player=None, log=SimpleNamespace(add=lambda _message: None))

    for label, record in game_map.city_buildings.items():
        player = world.Entity(
            "@", (255, 255, 255), world.Position(*record["entrance"]), name="Player",
        )
        game_map.entities.append(player)
        ctx.player = player
        state = _state(game_map, player, ctx)

        assert city_interiors.enter_city_interior(state) == "ENTERED"
        interior = state.game_map
        assert interior.city_interior_id == record["cache_key"]
        assert interior.width >= 18
        assert any(tile.kind == "exit" for row in interior.tiles for tile in row)
        assert state.current_mode == "dungeon"
        if record["npc_id"]:
            assert any(entity.npc_id == record["npc_id"] for entity in interior.entities)

        assert city_interiors.exit_city_interior(state) == "HANDLED"
        assert state.game_map is game_map
        assert state.player.pos == world.Position(*record["entrance"])
        assert state.current_mode == "city"


def test_city_interior_is_cached_and_reuses_the_same_room_map():
    game_map = load_planet("earth")
    record = game_map.city_buildings["bar"]
    player = world.Entity("@", (255, 255, 255), world.Position(*record["entrance"]), name="Player")
    game_map.entities.append(player)
    ctx = SimpleNamespace(interiors={}, game_map=game_map, player=player, log=SimpleNamespace(add=lambda _message: None))
    state = _state(game_map, player, ctx)

    assert city_interiors.enter_city_interior(state) == "ENTERED"
    first_room = state.game_map
    assert city_interiors.exit_city_interior(state) == "HANDLED"
    assert city_interiors.enter_city_interior(state) == "ENTERED"

    assert state.game_map is first_room
    assert sum(entity.char == "@" for entity in state.game_map.entities) == 1
    assert sum(entity.npc_id == "barkeep" for entity in state.game_map.entities) == 1
