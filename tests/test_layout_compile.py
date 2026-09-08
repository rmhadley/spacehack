"""Tests for the JSON→.layout compiler/validator (doc 40 phase 6c).

The compiler must refuse to emit an invalid ship — dead doors,
disconnected floors, hull leaks, asymmetric twins — and its happy
path must produce a layout the real parser accepts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

from layout_compile import LayoutSpecError, check_layout, compile_spec  # noqa: E402


def _base_spec() -> dict:
    return {
        "layout_id": "test_deck",
        "reference": "test",
        "size": {"w": 20, "h": 7},
        "hull": {"spans": [[y, 0, 19] for y in range(7)]},
        "rooms": [
            {"name": "aft", "rect": [2, 1, 5, 5], "role": "entry"},
            {"name": "bow", "rect": [7, 1, 12, 5], "role": "command"},
        ],
        "doors": [{"between": ["aft", "bow"], "at": [6, 3]}],
        "entry": {"breach": [1, 1], "spawn": [1, 2], "exit": [1, 3]},
        "console": {"pos": [12, 3]},
        "content": {"crew": [{"spec": "pirate_raider", "room": "bow",
                              "count": "1-2"}],
                    "loot": [{"room": "aft", "table": "personal_storage"}]},
    }


def test_happy_path_emits_a_parseable_layout(tmp_path):
    text = compile_spec(_base_spec())
    assert "MAP" in text and "ENDMAP" in text
    assert "ENEMY: r = pirate_raider@1.0#1-2" in text
    assert "LOOT: 1 = personal_storage" in text

    out = tmp_path / "test_deck.layout"
    out.write_text(text)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from src.spacehack.dungeon_layout import load_layout

    game_map, spawn = load_layout("test_deck", layout_dir=tmp_path)
    assert spawn is not None
    assert (game_map.width, game_map.height) == (20, 7)


def test_dead_door_refuses_to_emit():
    spec = _base_spec()
    spec["doors"].append({"between": ["aft", "void"], "at": [3, 0]})
    # (3,0) sits in the wall row: no walkable ends
    with pytest.raises(LayoutSpecError) as exc:
        compile_spec(spec)
    assert any("door to nowhere" in r for r in exc.value.reasons)


def test_unreachable_floor_refuses_to_emit():
    spec = _base_spec()
    spec["rooms"][1]["rect"] = [8, 1, 12, 5]
    spec["doors"] = []  # bow unreachable from aft
    with pytest.raises(LayoutSpecError) as exc:
        compile_spec(spec)
    assert any("unreachable floor" in r for r in exc.value.reasons)


def test_hull_leak_refuses_to_emit():
    spec = _base_spec()
    spec["hull"]["spans"][0] = [0, 4, 19]  # row 0 void; aft floor at y1
    spec["hull"]["spans"][1] = [0, 4, 19]
    with pytest.raises(LayoutSpecError) as exc:
        compile_spec(spec)
    assert any("hull leak" in r for r in exc.value.reasons)


def test_twin_asymmetry_refuses_to_emit():
    spec = _base_spec()
    spec["rooms"] += [
        {"name": "q_up", "rect": [14, 1, 16, 2], "twin": "q_dn"},
        {"name": "q_dn", "rect": [14, 4, 17, 5], "twin": "q_up"},
    ]
    with pytest.raises(LayoutSpecError) as exc:
        compile_spec(spec)
    assert any("twin asymmetry" in r for r in exc.value.reasons)


def test_check_mode_passes_the_compiled_artifact(tmp_path):
    text = compile_spec(_base_spec())
    out = tmp_path / "test_deck.layout"
    out.write_text(text)
    assert check_layout(out) == []


def test_check_walks_what_the_parse_calls_walkable(tmp_path):
    """An authored airlock chamber (scout_a pattern) must not report
    its cells unreachable: --check reads tile walkability, not a
    hardcoded kind list."""
    layout = tmp_path / "airlock_deck.layout"
    layout.write_text(
        "# airlock: exterior hatch, chamber, deck-side hatch\n"
        "MAP\n"
        "############\n"
        "#P.........#\n"
        "#..........#\n"
        "#######....#\n"
        "   a....a..#\n"
        "############\n"
        "ENDMAP\n"
        "TILE: # = DUNGEON_WALL\n"
        "TILE: . = DUNGEON_FLOOR\n"
        "TILE: a = AIRLOCK\n"
    )
    assert check_layout(layout) == []


def test_check_skips_padding_invented_floor(tmp_path):
    """In-span spaces the author left empty are authored void (hull
    notches beside enclosed stubs) — the padding rule invents floor
    there, and a sealed pocket of it is not an authoring error."""
    layout = tmp_path / "notch_deck.layout"
    layout.write_text(
        "MAP\n"
        "############\n"
        "#P.........#\n"
        "#..........#\n"
        "#####  #####\n"
        "############\n"
        "ENDMAP\n"
        "TILE: # = DUNGEON_WALL\n"
        "TILE: . = DUNGEON_FLOOR\n"
    )
    assert check_layout(layout) == []


def test_check_still_flags_authored_sealed_floor(tmp_path):
    """The same pocket AUTHORED as floor ('.') stays a defect: sealed
    rooms the author meant to be reachable must still be reported."""
    layout = tmp_path / "sealed_deck.layout"
    layout.write_text(
        "MAP\n"
        "############\n"
        "#P.........#\n"
        "#..........#\n"
        "############\n"
        "#####..#####\n"
        "############\n"
        "ENDMAP\n"
        "TILE: # = DUNGEON_WALL\n"
        "TILE: . = DUNGEON_FLOOR\n"
    )
    reasons = check_layout(layout)
    assert reasons and all(r.startswith("unreachable floor") for r in reasons)
