"""Dormant prison security — the powered_down entity contract (doc 30).

A dormant unit is grey, inert, and bump-reported: it never enters an
encounter, never patrols, and survives save/load in its exact state.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import ground_npcs, saveload_maps, world


def _dormant_drone(x=5, y=5):
    return world.Entity(
        char="d", fg=(110, 110, 110),
        pos=world.Position(x, y), name="", width=1, height=1,
        npc_char_id="sentry_drone", squad_id="prison_x_security",
        powered_down=True,
    )


def _active_drone(x=7, y=5):
    return world.Entity(
        char="d", fg=(150, 185, 255),
        pos=world.Position(x, y), name="", width=1, height=1,
        npc_char_id="sentry_drone", squad_id="prison_y_security",
    )


def _map_with(entities):
    width, height = 15, 9
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            tiles[y][x] = world.DUNGEON_FLOOR
    return world.GameMap(width=width, height=height, tiles=tiles,
                         entities=list(entities))


def test_powered_down_round_trips_through_dungeon_save():
    game_map = _map_with([_dormant_drone(), _active_drone()])
    data = saveload_maps._dungeon_to_dict(game_map, None)
    restored = saveload_maps._dungeon_from_dict(data)[0]
    states = {
        e.squad_id: e.powered_down for e in restored.entities
    }
    assert states == {"prison_x_security": True, "prison_y_security": False}


def test_dormant_units_never_enter_visible_hostiles():
    from src.spacehack.combat._encounter import _visible_hostile_entities

    game_map = _map_with([_dormant_drone(3, 4), _active_drone(11, 4)])
    ctx = SimpleNamespace(player=SimpleNamespace(pos=world.Position(7, 4)))
    seen = _visible_hostile_entities(ctx, game_map, ctx.player.pos, radius=8)
    assert [e.squad_id for e in seen] == ["prison_y_security"]


def test_dormant_units_do_not_move_on_the_ground_tick():
    game_map = _map_with([_dormant_drone(3, 4)])
    ctx = SimpleNamespace(player=SimpleNamespace(pos=world.Position(7, 4)))
    ground_npcs.move_ground_npcs(ctx, game_map)
    drone = game_map.entities[0]
    assert (drone.pos.x, drone.pos.y) == (3, 4)


def test_bumping_a_dormant_unit_reports_and_never_fights():
    from src.spacehack.game_interactions import resolve_blocker

    messages = []
    state = SimpleNamespace(
        ctx=SimpleNamespace(),
        log=SimpleNamespace(add=messages.append),
        current_mode="dungeon",
    )
    drone = _dormant_drone(8, 4)
    assert resolve_blocker(state, "occupied", drone, 1, 0) is None
    assert any("powered down Sentry Drone" in m for m in messages)
