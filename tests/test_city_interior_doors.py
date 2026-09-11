"""P/exit placement-rule tests for city interiors (doc 45 phase 1).

One shared predicate (``city_landmarks.door_placement_error``) backs the
load-time gate, the layout-editor mirror, and the corpus audit sweep —
these tests pin the predicate itself and both enforcement paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.spacehack import landmark
from src.spacehack.city_landmarks import door_placement_error, load_city_interior
from tools.layout_editor.model import load_document
from tools.layout_editor.validation import validate_document

_DATA = Path(__file__).resolve().parent.parent / "src" / "spacehack" / "data"

_GOOD_INTERIOR = """\
MAP
##########
#........#
#...P....#
#...>....#
##########
ENDMAP

TILE: # = CITY_BUILDING_WALL
TILE: . = CITY_BUILDING_FLOOR
TILE: P = LANDMARK_ENTRANCE
TILE: > = EXIT
"""

_MID_ROOM_EXIT_INTERIOR = """\
MAP
##########
#........#
#...>....#
#...P....#
#........#
##########
ENDMAP

TILE: # = CITY_BUILDING_WALL
TILE: . = CITY_BUILDING_FLOOR
TILE: P = LANDMARK_ENTRANCE
TILE: > = EXIT
"""

_TWO_SPAWNS_INTERIOR = """\
MAP
##########
#..P.....#
#..P..>..#
#........#
##########
ENDMAP

TILE: # = CITY_BUILDING_WALL
TILE: . = CITY_BUILDING_FLOOR
TILE: P = LANDMARK_ENTRANCE
TILE: > = EXIT
"""


def _write_layout(tmp_path, stem, text):
    # infer_mode keys on the parent directory name; city documents
    # must live under "landmarks" to validate as CITY assets.
    landmarks = tmp_path / "landmarks"
    landmarks.mkdir(exist_ok=True)
    path = landmarks / f"{stem}.layout"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("exits", "spawn", "height"),
    [
        ([(4, 3)], (4, 2), 5),   # walkable-row exit, P directly above
        ([(4, 3)], (3, 3), 5),   # walkable-row exit, P beside on the row
        ([(4, 4)], (4, 3), 5),   # in-wall doorway, P just inside
    ],
)
def test_placement_rule_accepts_south_door_patterns(exits, spawn, height):
    assert door_placement_error(exits, spawn, height) is None


@pytest.mark.parametrize(
    ("exits", "spawn", "height", "fragment"),
    [
        ([], (4, 3), 5, "0 exits"),
        ([(1, 3), (8, 3)], (1, 2), 5, "2 exits"),
        ([(4, 2)], (4, 1), 5, "not on the south perimeter"),
        ([(4, 3)], (1, 1), 5, "not orthogonally adjacent"),
        ([(4, 3)], None, 5, "no P spawn"),
        # adjacent but ON the wall row: never a legal spawn position
        ([(4, 4)], (3, 4), 5, "south wall row"),
        ([(4, 3)], (4, 4), 5, "south wall row"),
    ],
)
def test_placement_rule_rejects_violations(exits, spawn, height, fragment):
    assert fragment in door_placement_error(exits, spawn, height)


def test_load_city_interior_accepts_compliant_layout(tmp_path, monkeypatch):
    _write_layout(tmp_path, "good_interior", _GOOD_INTERIOR)
    monkeypatch.setattr(landmark, "_LANDMARK_DIR", tmp_path / "landmarks")

    asset = load_city_interior("good_interior")

    assert (asset.spawn.x, asset.spawn.y) == (4, 2)


def test_load_city_interior_rejects_mid_room_exit(tmp_path, monkeypatch):
    _write_layout(tmp_path, "mid_room_exit", _MID_ROOM_EXIT_INTERIOR)
    monkeypatch.setattr(landmark, "_LANDMARK_DIR", tmp_path / "landmarks")

    with pytest.raises(ValueError, match="not on the south perimeter"):
        load_city_interior("mid_room_exit")


def test_editor_mirror_flags_door_violations(tmp_path):
    document = load_document(_write_layout(tmp_path, "mid_room_exit", _MID_ROOM_EXIT_INTERIOR))

    messages = {issue.message for issue in validate_document(document)}

    assert "Interior door placement: exit at row 2 of 6 is not on the south perimeter" in messages


def test_editor_mirror_requires_single_spawn(tmp_path):
    document = load_document(_write_layout(tmp_path, "two_spawns", _TWO_SPAWNS_INTERIOR))

    messages = {issue.message for issue in validate_document(document)}

    assert "Interior door placement: interiors allow exactly one P marker" in messages


def test_editor_mirror_exempts_exterior_stamps():
    document = load_document(_DATA / "landmarks" / "mars_militia.layout")

    assert not any(
        issue.message.startswith("Interior door placement")
        for issue in validate_document(document)
    )
