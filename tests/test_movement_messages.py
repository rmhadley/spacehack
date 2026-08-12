"""Regression tests for exploration movement feedback."""

from src.spacehack import saveload, world


def test_blocked_tiles_own_their_movement_messages():
    sun = world.Tile(
        kind="sun",
        char="O",
        walkable=False,
        fg=(255, 230, 120),
        bg=(140, 90, 30),
        blocked_message="The sun blocks your path.",
    )
    assert world.blocked_message_for(sun) == "The sun blocks your path."


def test_try_move_returns_the_blocking_tile():
    player = world.Entity("@", (255, 255, 255), world.Position(0, 0))
    wall = world.Tile(
        kind="space_obstacle",
        char="#",
        walkable=False,
        fg=(1, 2, 3),
        bg=(4, 5, 6),
        blocked_message="A force field blocks your path.",
    )
    game_map = world.GameMap(2, 1, [[world.FLOOR, wall]], [player])

    code, blocker = world.try_move(player, game_map, 1, 0)

    assert code == "wall"
    assert blocker is wall
    assert world.blocked_message_for(blocker) == "A force field blocks your path."


def test_blocked_entities_own_their_movement_messages():
    blocker = world.Entity(
        "#", (255, 255, 255), world.Position(1, 0),
        name="Bulkhead",
        blocked_message="The {name} blocks your path.",
    )

    assert world.blocked_message_for(blocker) == "The Bulkhead blocks your path."


def test_out_of_bounds_has_no_blocking_object_and_keeps_wall_fallback():
    player = world.Entity("@", (255, 255, 255), world.Position(0, 0))
    game_map = world.GameMap(1, 1, [[world.FLOOR]], [player])

    code, blocker = world.try_move(player, game_map, -1, 0)

    assert code == "wall"
    assert blocker is None
    assert world.blocked_message_for(blocker) == "A wall blocks your path."


def test_custom_blocked_messages_survive_dungeon_save_round_trip():
    custom_tile = world.Tile(
        kind="alien_barrier",
        char="=",
        walkable=False,
        fg=(1, 2, 3),
        bg=(4, 5, 6),
        blocked_message="The alien barrier rejects you.",
    )
    custom_entity = world.Entity(
        "#", (7, 8, 9), world.Position(1, 0),
        name="Sealed Bulkhead",
        blocked_message="The {name} is sealed shut.",
    )
    game_map = world.GameMap(
        2,
        1,
        [[custom_tile, world.FLOOR]],
        [custom_entity],
    )

    restored, _space_position = saveload._dungeon_from_dict(
        saveload._dungeon_to_dict(game_map, None),
    )

    assert restored.tiles[0][0].blocked_message == "The alien barrier rejects you."
    assert restored.entities[0].blocked_message == "The {name} is sealed shut."
    assert world.blocked_message_for(restored.entities[0]) == (
        "The Sealed Bulkhead is sealed shut."
    )
