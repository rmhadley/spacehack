"""Regression tests for authored Earth city interiors."""

from __future__ import annotations

import glob
from types import SimpleNamespace

from src.spacehack import city_interiors, city_landmarks, world
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


def test_no_city_interior_has_void_perimeter_walls():
    """Every authored city interior must be a clean rectangle: no ragged
    layout rows may leave a ``void`` gap in the perimeter wall ring."""
    import os

    interior_files = sorted(
        glob.glob(os.path.join(os.path.dirname(city_landmarks.__file__),
                               "data", "landmarks", "*_interior.layout"))
    )
    assert interior_files, "expected interior layout files"
    for path in interior_files:
        layout_id = os.path.basename(path).replace(".layout", "")
        asset = city_landmarks.load_city_interior(layout_id)
        game_map = asset.game_map
        height, width = game_map.height, game_map.width
        for y, row in enumerate(game_map.tiles):
            for x, tile in enumerate(row):
                if tile.kind != "void":
                    continue
                on_ring = y in (0, height - 1) or x in (0, width - 1)
                assert not on_ring, (
                    f"{layout_id} has a void ({x},{y}) in its perimeter wall"
                )


def test_ac_ring_archive_and_lab_preserve_research_officers():
    """The ring's archive override and lab catalog NPC remain interactable."""
    game_map = load_planet("ac_station")
    ctx = SimpleNamespace(
        interiors={}, game_map=game_map, player=None,
        log=SimpleNamespace(add=lambda _message: None),
    )
    for label, expected_npc in (("archive", "research_officer"), ("lab", "research_officer")):
        record = game_map.city_buildings[label]
        player = world.Entity(
            "@", (255, 255, 255), world.Position(*record["entrance"]), name="Player",
        )
        game_map.entities.append(player)
        ctx.player = player
        state = _state(game_map, player, ctx)
        assert city_interiors.enter_city_interior(state) == "ENTERED"
        assert any(entity.npc_id == expected_npc for entity in state.game_map.entities)
        assert city_interiors.exit_city_interior(state) == "HANDLED"


def test_eri_b_service_npcs_survive_authored_interior_entry():
    """Epsilon's settler and trader overrides remain in their interiors."""
    game_map = load_planet("eri_b")
    ctx = SimpleNamespace(
        interiors={}, game_map=game_map, player=None,
        log=SimpleNamespace(add=lambda _message: None),
    )
    for label, expected_name in (("bar", "Settler"), ("merchants", "Settlement Trader")):
        record = game_map.city_buildings[label]
        player = world.Entity(
            "@", (255, 255, 255), world.Position(*record["entrance"]), name="Player",
        )
        game_map.entities.append(player)
        ctx.player = player
        state = _state(game_map, player, ctx)
        assert city_interiors.enter_city_interior(state) == "ENTERED"
        assert any(entity.name == expected_name for entity in state.game_map.entities)
        assert city_interiors.exit_city_interior(state) == "HANDLED"


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
