"""Tests for authored landmarks stamped into procedural dungeons."""

from __future__ import annotations

from collections import deque
import copy
from unittest.mock import MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import dungeon, landmark
from src.spacehack.data.planets import find_planet_spec
from src.spacehack.engine import seed_rng
from src.spacehack.saveload import _dungeon_from_dict, _dungeon_to_dict
from src.spacehack import world
from src.spacehack.main_quest import bump_mars_door
import src.spacehack.main_quest._act0 as act0


def _reachable(game_map, start, goal) -> bool:
    """Return whether four-way movement can reach ``goal`` from ``start``."""
    _start = (start.x, start.y)
    _goal = (goal.x, goal.y)
    _queue = deque([_start])
    _seen = {_start}
    while _queue:
        _x, _y = _queue.popleft()
        if (_x, _y) == _goal:
            return True
        for _dx, _dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            _next = (_x + _dx, _y + _dy)
            if _next in _seen or not game_map.in_bounds(*_next):
                continue
            if not game_map.tiles[_next[1]][_next[0]].walkable:
                continue
            _seen.add(_next)
            _queue.append(_next)
    return False


def test_mars_landmark_layout_parses_console_and_bottom_door():
    """The authored asset exposes one quest console and one entrance tile."""
    _asset = landmark.load_landmark("mars_signal_door")

    _consoles = [entity for entity in _asset.entities if entity.main_quest_console]
    _doors = [
        (x, y)
        for y, row in enumerate(_asset.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "dungeon_door"
    ]

    assert len(_consoles) == 1
    assert _consoles[0].name == "Alien Door Console"
    _stairs = [
        (x, y)
        for y, row in enumerate(_asset.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "stairs_down"
    ]
    assert len(_doors) == 1
    assert _doors[0] == (
        _asset.width // 2,
        _asset.height - 1,
    )
    assert _stairs == [(_asset.width // 2, 3)]


def test_landmark_console_survives_dungeon_serialization():
    """The quest console and alien-door tiles survive save/load encoding."""
    _asset = landmark.load_landmark("mars_signal_door")
    _encoded = _dungeon_to_dict(_asset, None)
    _restored, _space_pos = _dungeon_from_dict(_encoded)

    _console = next(entity for entity in _restored.entities if entity.main_quest_console)
    assert _console.name == "Alien Door Console"
    assert _console.pos == next(
        entity.pos for entity in _asset.entities if entity.main_quest_console
    )
    _door = next(
        (x, y)
        for y, row in enumerate(_asset.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "dungeon_door"
    )
    assert _restored.tiles[_door[1]][_door[0]].kind == "dungeon_door"
    assert _restored.tiles[3][20].kind == "stairs_down"
    assert _restored.tiles[0][1].kind == "dungeon_wall"
    assert _restored.tiles[2][18].kind == "dungeon_floor"


def test_landmark_inherits_destination_wall_and_floor_theme():
    """Generic landmark tiles use the generated dungeon's themed tiles."""
    seed_rng(11)
    _params = find_planet_spec("mars").dungeon_params
    _game_map, _spawn = dungeon.generate_dungeon(_params)
    _asset = landmark.load_landmark("mars_signal_door")
    _wall_pos = next(
        (x, y)
        for y, row in enumerate(_asset.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "dungeon_wall"
    )
    _floor_pos = next(
        (x, y)
        for y, row in enumerate(_asset.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "dungeon_floor"
        and y > 0
        and x > 0
    )

    _stamp = landmark.stamp_landmark(_game_map, _asset, _spawn)

    _stamped_wall = _game_map.tiles[_stamp.origin.y + _wall_pos[1]][_stamp.origin.x + _wall_pos[0]]
    _stamped_floor = _game_map.tiles[_stamp.origin.y + _floor_pos[1]][_stamp.origin.x + _floor_pos[0]]
    assert _stamped_wall.kind == _params.tile_wall.kind
    assert _stamped_wall.char == _params.tile_wall.char
    assert _stamped_wall.walkable == _params.tile_wall.walkable
    assert _stamped_wall.bg == _params.tile_wall.bg
    assert _stamped_floor.kind == _params.tile_floor.kind
    assert _stamped_floor.char == _params.tile_floor.char
    assert _stamped_floor.walkable == _params.tile_floor.walkable
    assert _stamped_floor.bg == _params.tile_floor.bg


def test_mars_landmark_preserves_authored_wall_and_floor_colors():
    """Mars landmark overrides remain active when stamped into the cave theme."""
    seed_rng(29)
    _params = find_planet_spec("mars").dungeon_params
    _game_map, _spawn = dungeon.generate_dungeon(_params)
    _asset = landmark.load_landmark("mars_signal_door")
    _stamp = landmark.stamp_landmark(_game_map, _asset, _spawn)

    # Use coordinates authored as '+' and '.' in the layout. Both glyphs
    # resolve to generic dungeon kinds, so their original glyph identity is
    # not available after parsing.
    _wall_pos = (16, 1)
    _floor_pos = (17, 2)
    assert _asset.tiles[_wall_pos[1]][_wall_pos[0]].kind == "dungeon_wall"
    assert _asset.tiles[_wall_pos[1]][_wall_pos[0]].fg == (120, 130, 150)
    assert _asset.tiles[_floor_pos[1]][_floor_pos[0]].kind == "dungeon_floor"
    assert _asset.tiles[_floor_pos[1]][_floor_pos[0]].fg == (200, 200, 210)

    _stamped_wall = _game_map.tiles[_stamp.origin.y + _wall_pos[1]][_stamp.origin.x + _wall_pos[0]]
    _stamped_floor = _game_map.tiles[_stamp.origin.y + _floor_pos[1]][_stamp.origin.x + _floor_pos[0]]

    assert _stamped_wall.fg == (120, 130, 150)
    assert _stamped_floor.fg == (200, 200, 210)


def test_layout_colour_override_is_parsed_for_generic_tiles(tmp_path):
    """COLOUR directives in a layout create explicit generic-tile overrides."""
    (_layout := tmp_path / "override.layout").write_text(
        "MAP\n###\n#.#\n###\nENDMAP\n"
        "TILE: # = DUNGEON_WALL\n"
        "TILE: . = DUNGEON_FLOOR\n"
        "COLOUR: # = (1, 2, 3)\n"
        "COLOUR: . = (4, 5, 6)\n",
        encoding="utf-8",
    )

    _loaded, _spawn = dungeon.load_layout(
        "override",
        layout_dir=tmp_path,
        require_spawn=False,
    )

    assert _loaded.tiles[0][0] is not world.DUNGEON_WALL
    assert _loaded.tiles[0][0].fg == (1, 2, 3)
    assert _loaded.tiles[1][1] is not world.DUNGEON_FLOOR
    assert _loaded.tiles[1][1].fg == (4, 5, 6)


def test_landmark_colour_override_keeps_theme_shape_and_background():
    """An explicit layout color changes fg without replacing dungeon theming."""
    seed_rng(13)
    _params = find_planet_spec("mars").dungeon_params
    _game_map, _spawn = dungeon.generate_dungeon(_params)
    _asset = copy.deepcopy(landmark.load_landmark("mars_signal_door"))
    _asset.tiles[0][0] = world.Tile(
        kind="dungeon_wall", char="#", walkable=False,
        fg=(1, 2, 3), bg=(99, 98, 97),
    )

    _stamp = landmark.stamp_landmark(_game_map, _asset, _spawn)
    _tile = _game_map.tiles[_stamp.origin.y][_stamp.origin.x]

    assert _tile.kind == _params.tile_wall.kind
    assert _tile.char == _params.tile_wall.char
    assert _tile.walkable == _params.tile_wall.walkable
    assert _tile.bg == _params.tile_wall.bg
    assert _tile.fg == (1, 2, 3)


def _quest_ctx(progress):
    """Build the small mutable context needed by the Act 0 bump handler."""
    _ctx = MagicMock()
    _ctx.main_quest_progress = dict(progress)
    _ctx.main_quest_chain = ""
    _ctx.main_quest_gate = {}
    _ctx.main_quest_unlocked_items = set()
    _ctx.player_active_missions = []
    _ctx.player_owned_ship = None
    _ctx.time_day = 1
    _ctx.time_month = 1
    _ctx.time_year = 2200
    _ctx.player_xp = 0
    _ctx.player_level = 1
    _ctx.player_skill_points = 0
    _ctx.player_traits = []
    _ctx.player_counters = MagicMock()
    _ctx.log = MagicMock()
    _ctx.stats = MagicMock(credits=0)
    _ctx.game_map = MagicMock()
    _ctx.game_map.entities = []
    return _ctx


def test_mars_console_bump_runs_discovery_interaction(monkeypatch):
    """The landmark console routes the first bump to the Act 0 handler."""
    _ctx = _quest_ctx({"prologue_mars_entrance": "available"})
    _beats = []
    monkeypatch.setattr(act0, "show_sealed_door_overlay", lambda ctx, beat: _beats.append(beat))

    bump_mars_door(_ctx)

    assert _ctx.main_quest_progress["prologue_mars_entrance"] == "completed"
    assert _beats == ["discover"]


def test_mars_console_bump_opens_with_prologue_tool(monkeypatch):
    """The console's open path grants prison data and uses the open overlay."""
    _ctx = _quest_ctx({"prologue_open": "active"})
    _beats = []
    _animations = []
    monkeypatch.setattr(act0, "show_sealed_door_overlay", lambda ctx, beat: _beats.append(beat))
    monkeypatch.setattr(act0, "animate_signal_door_opening", lambda *args: _animations.append(args))

    bump_mars_door(_ctx)

    assert _ctx.main_quest_progress["prologue_open"] == "completed"
    assert "prison_data" in _ctx.main_quest_unlocked_items
    assert _beats == ["open"]
    assert len(_animations) == 1


def test_mars_door_animation_reveals_stairs_on_real_map(monkeypatch):
    """A successful real-map opening replaces the barrier and reveals stairs."""
    seed_rng(19)
    _params = find_planet_spec("mars").dungeon_params
    _game_map, _spawn = dungeon.generate_dungeon(_params)
    _asset = landmark.load_landmark("mars_signal_door")
    _stamp = landmark.stamp_landmark(_game_map, _asset, _spawn)
    _game_map.mars_stairs_pos = _stamp.stairs
    _ctx = _quest_ctx({"prologue_open": "active"})
    _ctx.game_map = _game_map
    _barrier_positions = act0._signal_door_barrier(_game_map)
    monkeypatch.setattr(act0, "_render_signal_door_frame", lambda *args: None)
    monkeypatch.setattr(act0, "show_sealed_door_overlay", lambda *args: None)
    import src.spacehack.navigation as navigation
    monkeypatch.setattr(navigation, "_responsive_sleep", lambda seconds: None)

    bump_mars_door(_ctx)

    assert _game_map.tiles[_stamp.stairs.y][_stamp.stairs.x] is world.STAIRS_DOWN
    assert all(
        _game_map.tiles[pos.y][pos.x].kind == "dungeon_floor"
        for pos in _barrier_positions
    )


def test_opened_mars_stairs_survive_dungeon_serialization():
    """The deferred Act 1 stairs state survives save/load."""
    seed_rng(23)
    _params = find_planet_spec("mars").dungeon_params
    _game_map, _spawn = dungeon.generate_dungeon(_params)
    _asset = landmark.load_landmark("mars_signal_door")
    _stamp = landmark.stamp_landmark(_game_map, _asset, _spawn)
    _game_map.mars_stairs_pos = _stamp.stairs
    _game_map.tiles[_stamp.stairs.y][_stamp.stairs.x] = world.STAIRS_DOWN

    _restored, _space_pos = _dungeon_from_dict(
        _dungeon_to_dict(_game_map, None),
    )

    assert _restored.mars_stairs_pos == _stamp.stairs
    assert _restored.tiles[_stamp.stairs.y][_stamp.stairs.x] is not world.EXIT
    assert _restored.tiles[_stamp.stairs.y][_stamp.stairs.x].kind == "stairs_down"


def test_signal_door_animation_undulates_then_splits(monkeypatch):
    """Opening frames wave first, then clear progressively from center."""
    seed_rng(17)
    _params = find_planet_spec("mars").dungeon_params
    _game_map, _spawn = dungeon.generate_dungeon(_params)
    _asset = landmark.load_landmark("mars_signal_door")
    _stamp = landmark.stamp_landmark(_game_map, _asset, _spawn)
    _game_map.mars_stairs_pos = _stamp.stairs
    _barrier_positions = act0._signal_door_barrier(_game_map)
    _frames = []
    _ctx = MagicMock()
    monkeypatch.setattr(act0, "_render_signal_door_frame", lambda *args: _frames.append(args[-1]))
    import src.spacehack.navigation as navigation
    monkeypatch.setattr(navigation, "_responsive_sleep", lambda seconds: None)

    assert act0.animate_signal_door_opening(_ctx, MagicMock(), _game_map, _spawn)

    assert tuple(_frames[:5]) == act0._SIGNAL_DOOR_WAVE_FRAMES
    assert _frames[5][3] == " "
    assert _frames[6][2:5] == "   "
    assert _frames[-1] == " " * 7
    assert _game_map.tiles[_stamp.stairs.y][_stamp.stairs.x] is world.STAIRS_DOWN
    assert all(
        _game_map.tiles[pos.y][pos.x].kind == "dungeon_floor"
        for pos in _barrier_positions
    )


def test_mars_landmark_stamp_rejects_undersized_map():
    """Stamping fails cleanly when the generated map cannot contain the asset."""
    _asset = landmark.load_landmark("mars_signal_door")
    _tiny = type(find_planet_spec("mars").dungeon_params)(width=10, height=10)
    _game_map, _spawn = dungeon.generate_dungeon(_tiny)

    try:
        landmark.stamp_landmark(_game_map, _asset, _spawn)
    except ValueError as _error:
        assert "fit" in str(_error)
    else:
        raise AssertionError("undersized map unexpectedly accepted landmark")


def test_mars_landmark_stamp_carves_reachable_approach():
    """Stamping preserves the landmark and connects its lower door to spawn."""
    seed_rng(7)
    _params = find_planet_spec("mars").dungeon_params
    _game_map, _spawn = dungeon.generate_dungeon(_params)
    _asset = landmark.load_landmark("mars_signal_door")

    _stamp = landmark.stamp_landmark(_game_map, _asset, _spawn)
    _approach = type(_spawn)(_stamp.entrance.x, _stamp.entrance.y + 1)

    assert _reachable(_game_map, _spawn, _approach)
    assert _game_map.tiles[_stamp.entrance.y][_stamp.entrance.x].kind == "dungeon_door"
    assert any(
        entity.main_quest_console and entity.pos == _stamp.console
        for entity in _game_map.entities
    )
    assert _game_map.tiles[_stamp.console.y][_stamp.console.x].kind == "dungeon_floor"
