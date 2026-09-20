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

import pytest

from src.spacehack import dungeon_layout
from src.spacehack.dungeon_layout import load_layout
from src.spacehack.ship import StoredEquipment


@pytest.fixture(autouse=True)
def _no_room_module_pool(monkeypatch):
    """Strip tests isolate the capture path from the wreck room pool
    (pool tests override the rate or script the RNG themselves)."""
    monkeypatch.setattr(dungeon_layout, "WRECK_MODULE_RATE", 10**9)

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


# ---------------------------------------------------------------------------
# Wreck room pools (doc 47.3 SETTLED 15)
# ---------------------------------------------------------------------------

_BOTH_ROOMS_LAYOUT = """\
MAP
#############
#P..#3...#4.#
#...#....#..#
#############
ENDMAP
TILE: . = DUNGEON_FLOOR
LOOT: 3 = engine_room
LOOT: 4 = cargo_bay
"""


class _LowRng:
    """Every randint returns its low bound: every presence roll hits,
    first cell, first pool entry, tier-3 quality."""

    def randint(self, low, high):
        return low

    def choice(self, seq):
        return seq[0]

    def random(self):
        return 0.0

    def shuffle(self, seq):
        pass


class _HighRng:
    """Every randint returns its high bound: every presence roll
    misses."""

    def randint(self, low, high):
        return high

    def choice(self, seq):
        return seq[0]

    def random(self):
        return 1.0

    def shuffle(self, seq):
        pass


def test_room_module_pools_feed_engine_and_cargo_rooms(tmp_path, monkeypatch):
    monkeypatch.setattr("src.spacehack.engine.RNG", _LowRng())
    game_map, _spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, _BOTH_ROOMS_LAYOUT),
    )
    # Engine rooms host engine-slot reactors; cargo bays host the
    # system-slot spare-parts pool (SETTLED 15).
    assert {
        (payload["item_id"], payload.get("quality", 0))
        for payload in _module_payloads(game_map)
    } == {("compact_reactor", 3), ("shield_mk1", 3)}


def test_room_module_presence_misses_leave_no_modules(tmp_path, monkeypatch):
    monkeypatch.setattr("src.spacehack.engine.RNG", _HighRng())
    game_map, _spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, _BOTH_ROOMS_LAYOUT),
    )
    assert _module_payloads(game_map) == []


def test_wreck_module_rate_wiring_is_one_in_n(tmp_path, monkeypatch):
    """The authored rate threads through: a 1-in-1 rate always hits."""
    from src.spacehack import dungeon_layout

    monkeypatch.setattr(dungeon_layout, "WRECK_MODULE_RATE", 1)
    game_map, _spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, _ENGINE_ROOM_LAYOUT),
    )
    assert len(_module_payloads(game_map)) == 1


# ---------------------------------------------------------------------------
# Randart instance travel (doc 47 phase 4): pickup → storage → install →
# store keeps the seed at every construction site.
# ---------------------------------------------------------------------------


class _RecordingLog:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, message: str) -> None:
        self.lines.append(message)


def test_randart_pickup_carries_the_seed_into_storage(monkeypatch):
    from types import SimpleNamespace

    from tests.support.asyncutil import as_async, run
    from src.spacehack import loot as loot_mod
    from src.spacehack.loot import _apply_module_loot
    from src.spacehack.data.randarts import roll_randart

    presented = []
    monkeypatch.setattr(
        loot_mod, "_present_randart_find",
        as_async(lambda ctx, mid, seed: presented.append((mid, seed))),
    )

    entity = SimpleNamespace(
        loot_data={
            "item_type": "module", "item_id": "shield_mk1",
            "quality": 4, "randart_seed": 4242,
        },
        pos=SimpleNamespace(x=1, y=1),
    )
    ctx = SimpleNamespace(
        log=_RecordingLog(), ship_storage=[],
        game_map=SimpleNamespace(entities=[entity]),
    )

    run(_apply_module_loot(ctx, entity))

    (entry,) = ctx.ship_storage
    assert entry.item_id == "shield_mk1"
    assert entry.quality == 4
    assert entry.randart_seed == 4242
    assert ctx.log.lines == [
        f"Stored ship module: {roll_randart('shield_mk1', 4242).name}.",
    ]
    assert presented == [("shield_mk1", 4242)]


def test_randart_seed_survives_install_and_store():
    from src.spacehack.data.ships import find_ship
    from src.spacehack.ship import (
        OwnedShip, StoredEquipment, install_stored_equipment, store_module,
    )

    owned = OwnedShip(ship_id="starter")
    ship_spec = find_ship("starter")
    storage = [StoredEquipment("module", "reactor_mk2", quality=4, randart_seed=99)]

    assert install_stored_equipment(owned, storage, 0, ship_spec)
    assert owned.modules[0].randart_seed == 99
    assert store_module(owned, storage, 0)
    assert storage[0].randart_seed == 99

    assert install_stored_equipment(owned, storage, 0, ship_spec)
    assert owned.modules[0].randart_seed == 99
    assert store_module(owned, storage, 0)
    assert storage[0].randart_seed == 99


# --- the wreck credit-chip pass (doc 47 phase 4, SETTLED 6/22) ---------------


def test_wreck_chip_pass_scatters_two_to_four_chips(tmp_path):
    game_map, _spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, _ENGINE_ROOM_LAYOUT),
        credit_chips=True,
    )
    chips = [
        e for e in game_map.entities
        if (e.loot_data or {}).get("credits_kind") == "chip"
    ]
    assert 2 <= len(chips) <= 4
    for chip in chips:
        assert 40 <= chip.loot_data["credits"] <= 120


def test_wreck_chip_pass_stays_gated_off_by_default(tmp_path):
    game_map, _spawn = load_layout(
        "strip_probe", layout_dir=_layout_dir(tmp_path, _ENGINE_ROOM_LAYOUT),
    )
    assert not [
        e for e in game_map.entities
        if (e.loot_data or {}).get("credits")
    ]


# --- the legendary pickup modal (doc 47 phase 4, SETTLED 24) ------------------


def test_randart_frame_is_the_stat_sheet():
    from src.spacehack.loot import _randart_frame
    from src.spacehack.data.randarts import roll_randart

    seed = 88
    frame = _randart_frame("shield_mk1", seed)
    manifest = roll_randart("shield_mk1", seed)
    assert frame.title == "LEGENDARY FIND"
    assert frame.body[0] == manifest.name
    assert frame.body[1] == "A Shield Mk. 1, modified far beyond factory spec:"
    from src.spacehack.data.randarts import axis_line
    assert list(frame.body[2:]) == [
        axis_line(field, delta) for field, delta in manifest.axes
    ]
    assert frame.rows[0].text == "Continue"
    # The name line is the only accented run.
    assert frame.body_runs[0] is not None
    assert all(run is None for run in frame.body_runs[1:])


def test_unseeded_module_pickups_never_fire_the_modal(monkeypatch):
    from types import SimpleNamespace

    from tests.support.asyncutil import as_async, run
    from src.spacehack import loot as loot_mod
    from src.spacehack.loot import _apply_module_loot

    presented = []
    monkeypatch.setattr(
        loot_mod, "_present_randart_find",
        as_async(lambda ctx, mid, seed: presented.append((mid, seed))),
    )
    entity = SimpleNamespace(
        loot_data={"item_type": "module", "item_id": "shield_mk2", "quality": 3},
        pos=SimpleNamespace(x=1, y=1),
    )
    ctx = SimpleNamespace(
        log=_RecordingLog(), ship_storage=[],
        game_map=SimpleNamespace(entities=[entity]),
    )

    run(_apply_module_loot(ctx, entity))

    assert presented == []  # t1-t3 stay log lines (SETTLED 12/24)
