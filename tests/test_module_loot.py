"""Module-loot floor tests (doc 47 phase 3): the capture strip.

The strip seeds an intact capture's interior with the flown module
instances at the quality they flew (SETTLED 14/16); dead-ship
interiors never strip. Layouts are authored into tmp dirs so the
tests control the room markers exactly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.dungeon_layout import load_layout
from src.spacehack.ship import StoredEquipment

_ENGINE_ROOM_LAYOUT = """\
MAP
#########
#P..#3..#
#...#...#
#########
ENDMAP
TILE: . = DUNGEON_FLOOR
LOOT: 3 = engine_room
"""

_NO_ENGINE_ROOM_LAYOUT = """\
MAP
#########
#P..4...#
#.......#
ENDMAP
TILE: . = DUNGEON_FLOOR
LOOT: 4 = cargo_bay
"""


def _layout_dir(tmp_path, text: str) -> Path:
    (tmp_path / "strip_probe.layout").write_text(text, encoding="utf-8")
    return tmp_path


def _module_payloads(game_map) -> list[dict]:
    return [
        entity.loot_data
        for entity in game_map.entities
        if (getattr(entity, "loot_data", None) or {}).get("item_type") == "module"
    ]


def test_capture_strip_drops_the_flown_instances(tmp_path):
    game_map, _spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, _ENGINE_ROOM_LAYOUT),
        capture_modules=(
            StoredEquipment("module", "compact_reactor", quality=2),
            StoredEquipment("module", "shield_mk1"),
        ),
    )
    # The exact (id, quality) pairs that flew — no re-roll, no loss.
    assert {
        (payload["item_id"], payload.get("quality", 0))
        for payload in _module_payloads(game_map)
    } == {("compact_reactor", 2), ("shield_mk1", 0)}


def test_capture_strip_places_inside_the_engine_room(tmp_path):
    game_map, spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, _ENGINE_ROOM_LAYOUT),
        capture_modules=(StoredEquipment("module", "reactor_mk2", quality=3),),
    )
    entities = [
        entity for entity in game_map.entities
        if (getattr(entity, "loot_data", None) or {}).get("item_type") == "module"
    ]
    assert len(entities) == 1
    pos = entities[0].pos
    # The dividing wall pins the engine room to x >= 5 — the strip
    # lands in the pulled-hardware room, never the spawn corridor.
    assert pos.x >= 5
    assert (pos.x, pos.y) != (spawn.x, spawn.y)


def test_capture_strip_falls_back_spawn_adjacent_without_engine_markers(tmp_path):
    game_map, spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, _NO_ENGINE_ROOM_LAYOUT),
        capture_modules=(
            StoredEquipment("module", "shield_mk1"),
            StoredEquipment("module", "shield_mk2", quality=1),
        ),
    )
    entities = [
        entity for entity in game_map.entities
        if (getattr(entity, "loot_data", None) or {}).get("item_type") == "module"
    ]
    assert len(entities) == 2
    assert all(
        max(abs(entity.pos.x - spawn.x), abs(entity.pos.y - spawn.y)) <= 1
        for entity in entities
    )


def test_dead_interiors_never_strip(tmp_path):
    """No capture_modules argument (every dead-ship path) seeds
    nothing from an installed list."""
    game_map, _spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, _ENGINE_ROOM_LAYOUT),
    )
    assert _module_payloads(game_map) == []


def test_capture_strip_survives_a_spawnless_layout(tmp_path):
    """require_spawn=False tolerates no-P layouts: the engine room
    still seeds, and nothing crashes without a spawn fallback."""
    text = _ENGINE_ROOM_LAYOUT.replace("#P..#3..#", "#...#3..#")
    game_map, spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, text),
        capture_modules=(StoredEquipment("module", "shield_mk1"),),
        require_spawn=False,
    )
    assert spawn is None
    assert [
        (payload["item_id"], payload.get("quality", 0))
        for payload in _module_payloads(game_map)
    ] == [("shield_mk1", 0)]
