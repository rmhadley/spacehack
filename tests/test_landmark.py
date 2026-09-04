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


def test_weighted_landmark_variants_skip_zero_weight_and_clamp_roll():
    """Weighted variant choice is deterministic at both roll boundaries."""
    from src.spacehack.data.dungeon_extensions import LandmarkVariant

    _variants = (
        LandmarkVariant("common", 3.0),
        LandmarkVariant("rare", 1.0),
        LandmarkVariant("disabled", 0.0),
    )

    assert landmark.choose_weighted_variant(_variants, -1.0) == "common"
    assert landmark.choose_weighted_variant(_variants, 0.75) == "rare"
    assert landmark.choose_weighted_variant(_variants, 1.0) == "rare"


def test_weighted_landmark_variants_reject_empty_weights():
    """A content pack cannot silently choose from an empty weighted pool."""
    from src.spacehack.data.dungeon_extensions import LandmarkVariant

    try:
        landmark.choose_weighted_variant((LandmarkVariant("none", 0.0),), 0.5)
    except ValueError as _error:
        assert "positive weight" in str(_error)
    else:
        raise AssertionError("empty landmark pool unexpectedly accepted")


def test_deep_cell_landmark_parses_torn_entrance_and_claw_scars():
    """The F5 asset has a walkable torn entrance and authored claw marks."""
    _asset = landmark.load_landmark("alien_prison_deep_cell")
    _entrances = [
        (x, y) for y, row in enumerate(_asset.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "landmark_entrance"
    ]
    _scars = [
        tile for row in _asset.tiles for tile in row
        if tile.kind == "claw_scar"
    ]

    assert _asset.width == 35
    assert _asset.height == 30
    assert _entrances == [(17, 15)]
    assert len(_scars) >= 20
    assert sum(
        tile.kind == "void"
        for row in _asset.tiles for tile in row
    ) >= 1
    assert landmark._landmark_markers(_asset) == (
        world.Position(17, 15), world.Position(17, 1), None, None,
    )


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


def test_deep_cell_landmark_serializes_authored_tiles():
    """The F5 landmark's torn entrance and claw scars survive save/load."""
    _asset = landmark.load_landmark("alien_prison_deep_cell")
    _restored, _space_pos = _dungeon_from_dict(_dungeon_to_dict(_asset, None))

    assert _restored.tiles[15][17].kind == "landmark_entrance"
    assert sum(
        tile.kind == "claw_scar"
        for row in _restored.tiles for tile in row
    ) >= 20


def test_landmark_inherits_destination_wall_and_floor_theme():
    """Generic landmark tiles use the generated dungeon's themed tiles."""
    seed_rng(11)
    _params = find_planet_spec("mars").dungeon_params
    _game_map, _spawn = dungeon.generate_dungeon(_params)
    _asset = copy.deepcopy(landmark.load_landmark("mars_signal_door"))
    _wall_pos = next(
        (x, y)
        for y, row in enumerate(_asset.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "dungeon_wall"
        and _asset.tiles[y][x].fg == world.DUNGEON_WALL.fg
    )
    _floor_pos = (17, 2)
    _asset.tiles[_floor_pos[1]][_floor_pos[0]] = world.DUNGEON_FLOOR

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
    assert _stamped_wall.bg == (18, 28, 48)
    assert _stamped_floor.fg == (200, 200, 210)
    assert _stamped_floor.bg == (42, 58, 88)


def test_layout_colour_override_is_parsed_for_generic_tiles(tmp_path):
    """COLOUR directives in a layout create explicit generic-tile overrides."""
    (_layout := tmp_path / "override.layout").write_text(
        "MAP\n###\n#.#\n###\nENDMAP\n"
        "TILE: # = DUNGEON_WALL\n"
        "TILE: . = DUNGEON_FLOOR\n"
        "COLOUR: # = (1, 2, 3) / (7, 8, 9)\n"
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
    assert _loaded.tiles[0][0].bg == (7, 8, 9)
    assert _loaded.tiles[0][0].bg_override
    assert _loaded.tiles[1][1] is not world.DUNGEON_FLOOR
    assert _loaded.tiles[1][1].fg == (4, 5, 6)
    assert _loaded.tiles[1][1].bg == world.DUNGEON_FLOOR.bg
    assert not _loaded.tiles[1][1].bg_override


def test_landmark_colour_override_keeps_theme_shape_and_background():
    """A foreground-only layout color keeps the destination background."""
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
    assert not _tile.bg_override
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


def test_mars_surface_rejects_landmark_without_required_markers(monkeypatch):
    """Act 0 validates its required console/stairs contract explicitly."""
    _ctx = _quest_ctx({"prologue_mars_entrance": "available"})
    _game_map = world.GameMap(
        10, 10,
        [[world.DUNGEON_FLOOR for _ in range(10)] for _ in range(10)],
        [],
    )
    monkeypatch.setattr(
        act0.landmark,
        "load_landmark",
        lambda _layout_id: world.GameMap(
            1, 1, [[world.DUNGEON_FLOOR]], [],
        ),
    )
    monkeypatch.setattr(
        act0.landmark,
        "stamp_landmark",
        lambda *_args: landmark.LandmarkStamp(
            origin=world.Position(0, 0),
            entrance=world.Position(0, 0),
            console=None,
            stairs=None,
            footprint=frozenset(),
        ),
    )

    try:
        act0.prepare_mars_surface(
            _ctx, _game_map, world.Position(1, 1),
        )
    except ValueError as _error:
        assert "console and stairs" in str(_error)
    else:
        raise AssertionError("invalid Mars landmark unexpectedly accepted")


def test_mars_console_bump_runs_discovery_interaction(monkeypatch):
    """The landmark console routes the first bump to the Act 0 handler."""
    _ctx = _quest_ctx({"prologue_mars_entrance": "available"})
    _beats = []
    monkeypatch.setattr(act0, "show_sealed_door_overlay", lambda ctx, beat: _beats.append(beat))

    bump_mars_door(_ctx)

    assert _ctx.main_quest_progress["prologue_mars_entrance"] == "completed"
    assert _beats == ["discover"]


def test_mars_console_bump_opens_with_prologue_tool(monkeypatch):
    """The console opens access without claiming the prison data was recovered."""
    _ctx = _quest_ctx({"prologue_open": "active"})
    _beats = []
    _animations = []
    monkeypatch.setattr(act0, "show_sealed_door_overlay", lambda ctx, beat: _beats.append(beat))
    monkeypatch.setattr(act0, "animate_signal_door_opening", lambda *args: _animations.append(args))

    bump_mars_door(_ctx)

    assert _ctx.main_quest_progress["prologue_open"] == "completed"
    assert "prison_data" not in _ctx.main_quest_unlocked_items
    assert _beats == ["open"]
    assert any(
        call.args == (
            "The seal gives way. Inside: an empty cell built for something enormous - "
            "and a dark terminal interface waiting to be accessed.",
            act0.message_log.COLOR_IMPORTANT_EVENT,
        )
        for call in _ctx.log.add_colored.call_args_list
    )
    assert any(
        call.args == (
            "The entrance is open. Beyond it, the facility descends into darkness.",
        )
        for call in _ctx.log.add.call_args_list
    )
    assert len(_animations) == 1
    _door_log = " ".join(
        str(call.args[0])
        for call in (
            *_ctx.log.add_colored.call_args_list,
            *_ctx.log.add.call_args_list,
        )
        if call.args
    ).lower()
    from src.spacehack.text import RUNTIME as _RUNTIME
    _open_overlay = " ".join(
        str(_RUNTIME.get(f"runtime.door_open_{key}", ""))
        for key in ("meta", "body", "highlight")
    ).lower()
    assert "data is recovered" not in _door_log
    assert "data: recovered" not in _open_overlay
    assert "data is recovered" not in _open_overlay


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
    assert all(
        _game_map.tiles[pos.y][pos.x].fg == (200, 200, 210)
        and _game_map.tiles[pos.y][pos.x].bg == (42, 58, 88)
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
    assert all(
        _game_map.tiles[pos.y][pos.x].fg == (200, 200, 210)
        and _game_map.tiles[pos.y][pos.x].bg == (42, 58, 88)
        for pos in _barrier_positions
    )


def test_deep_cell_landmark_stamps_reachable_footprint():
    """The authored cell stamps into F5-sized procedural maps and is reachable."""
    seed_rng(401)
    _params = find_planet_spec("mars").dungeon_params
    _params = type(_params)(
        width=58, height=46, min_room_size=8, max_room_size=18,
        room_fill_pct=0.60, sight_radius=11,
    )
    _game_map, _spawn = dungeon.generate_dungeon(_params)
    _asset = landmark.load_landmark("alien_prison_deep_cell")

    _stamp = landmark.stamp_landmark(_game_map, _asset, _spawn)
    _approach = type(_spawn)(_stamp.entrance.x, _stamp.entrance.y + 1)

    assert _reachable(_game_map, _spawn, _approach)
    assert len(_stamp.footprint) == _asset.width * _asset.height
    assert _stamp.arrival is not None
    assert _stamp.console is None
    assert _stamp.stairs is None


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


def test_entrance_marker_frees_interior_doors():
    """The explicit LANDMARK_ENTRANCE marker is the single link point
    to the proc-gen'd dungeon; dungeon doors are free for interior
    use. Without the marker, the old rule holds - exactly one door
    serves as the entrance (user ruling: the link tile doesn't have
    to be a door)."""
    from src.spacehack import landmark as landmark_module
    from src.spacehack import world as world_module

    def _asset(rows):
        mapping = {
            "#": world_module.DUNGEON_WALL,
            ".": world_module.DUNGEON_FLOOR,
            "d": world_module.DUNGEON_DOOR,
            "P": world_module.LANDMARK_ENTRANCE,
        }
        tiles = [[mapping[ch] for ch in row] for row in rows]
        return world_module.GameMap(
            width=len(rows[0]), height=len(rows), tiles=tiles,
            entities=[],
        )

    # Marker + two interior doors: parses, the marker is the entrance.
    stamped = landmark_module._landmark_markers(_asset([
        "#####d#####",
        "#..d......#",
        "#####P#####",
    ]))
    assert stamped == (world_module.Position(5, 2), None, None, None)

    # One door, no marker: back-compat, the door is the entrance.
    stamped = landmark_module._landmark_markers(_asset([
        "###########",
        "#.........#",
        "#####d#####",
    ]))
    assert stamped == (world_module.Position(5, 2), None, None, None)

    # Two doors, no marker: rejected.
    try:
        landmark_module._landmark_markers(_asset([
            "#####d#####",
            "#..d......#",
            "###########",
        ]))
    except ValueError as error:
        assert "entrance marker or exactly one door" in str(error)
    else:
        raise AssertionError("two doors without a marker were accepted")

    # Two markers: rejected.
    try:
        landmark_module._landmark_markers(_asset([
            "#####P#####",
            "#.........#",
            "#####P#####",
        ]))
    except ValueError as error:
        assert "at most one entrance marker" in str(error)
    else:
        raise AssertionError("two entrance markers were accepted")
