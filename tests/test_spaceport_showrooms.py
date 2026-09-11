"""Corpus and helper audits for indoor showrooms (doc 45 phase 1).

Pins the end state over the whole corpus: every interior passes the
P/exit placement rule, every city's manifest matches its interior's
berth markers and every berth is bump-reachable from the spawn, no
built city places showroom ships outdoors (authored AND grid paths),
and the shared seating helper's contract holds.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.spacehack import city_tiles, world
from src.spacehack.city_builder import build_city
from src.spacehack.city_kit import seat_showroom_ships
from src.spacehack.city_landmarks import load_city_interior
from src.spacehack.data.planets import PlanetSpec, list_planet_specs, load_planet
from src.spacehack.dungeon_layout import load_layout

_LANDMARKS = (
    Path(__file__).resolve().parent.parent / "src" / "spacehack" / "data" / "landmarks"
)
_INTERIORS = sorted(_LANDMARKS.glob("*_interior.layout"))


def _berth_cells(game_map):
    return [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "showroom_berth"
    ]


def _reachable_walkable(game_map, start):
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            neighbor = (x + dx, y + dy)
            if neighbor in seen:
                continue
            nx, ny = neighbor
            if not (0 <= nx < game_map.width and 0 <= ny < game_map.height):
                continue
            if not game_map.tiles[ny][nx].walkable:
                continue
            seen.add(neighbor)
            queue.append(neighbor)
    return seen


@pytest.mark.parametrize("layout", _INTERIORS, ids=lambda path: path.stem)
def test_every_interior_layout_passes_the_door_placement_rule(layout):
    # Exercises the production load-time gate end to end.
    load_city_interior(layout.stem)


@pytest.mark.parametrize("spec", list_planet_specs(), ids=lambda spec: spec.id)
def test_spaceport_manifest_matches_berths_and_berths_are_reachable(spec):
    layout_id = dict(spec.interior_layouts)["spaceport"]
    game_map, spawn = load_layout(
        layout_id, layout_dir=_LANDMARKS, require_spawn=True,
    )

    berths = _berth_cells(game_map)
    assert len(berths) == len(spec.showroom_ships)
    reachable = _reachable_walkable(game_map, (spawn.x, spawn.y))
    berth_set = set(berths)
    for x, y in berths:
        assert game_map.tiles[y][x].walkable
        # A seated display blocks its own cell; the player must be able
        # to stand beside it to bump it — and never on another berth,
        # whose display blocks it too.
        neighbours = (
            (x + dx, y + dy) for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        )
        assert any(
            cell in reachable and cell not in berth_set
            for cell in neighbours
        ), (x, y)


@pytest.mark.parametrize("spec", list_planet_specs(), ids=lambda spec: spec.id)
def test_no_authored_city_places_showroom_ships_outdoors(spec):
    game_map = load_planet(spec.id)

    assert not [
        entity for entity in game_map.entities
        if entity.ship_id and not entity.owned
    ]


def test_grid_path_places_no_showroom_ships():
    spec = PlanetSpec(
        id="grid_probe", name="Grid Probe", char="g", fg=(200, 200, 200),
        description="synthetic grid city",
        width=40, height=30,
        hangar_anchor=world.Position(20, 15),
        buildings=(
            world.CityBuilding(
                label="spaceport", x_lo=14, x_hi=26, y_lo=8, y_hi=12,
                door_x=20, npc_id="",
            ),
        ),
        showroom_ships=("scout", "hauler"),
    )

    game_map = build_city(spec, lambda npc_id: None)

    assert not [
        entity for entity in game_map.entities
        if entity.ship_id and not entity.owned
    ]
    # The terminal trio survives the retirement on the grid path.
    assert sum(entity.trade_terminal for entity in game_map.entities) == 1
    assert sum(entity.mech_terminal for entity in game_map.entities) == 1
    assert sum(entity.armory_terminal for entity in game_map.entities) == 1


# ----- the shared seating helper's contract -----


def _berth_map(berths, width=10, height=6):
    tiles = [
        [city_tiles.CITY_BUILDING_FLOOR for _ in range(width)]
        for _ in range(height)
    ]
    for x, y in berths:
        tiles[y][x] = world.SHOWROOM_BERTH
    return world.GameMap(width=width, height=height, tiles=tiles, entities=[])


def _displays(game_map):
    return [e for e in game_map.entities if e.ship_id and not e.owned]


def test_seat_showroom_ships_seats_manifest_in_reading_order():
    game_map = _berth_map([(8, 1), (2, 3)])
    spec = SimpleNamespace(id="probe", showroom_ships=("scout", "hauler"))

    seat_showroom_ships(game_map, spec, None)

    seated = _displays(game_map)
    assert [(e.ship_id, (e.pos.x, e.pos.y)) for e in seated] == [
        ("scout", (8, 1)),  # row 1 berths seat earlier manifest entries
        ("hauler", (2, 3)),
    ]
    assert [e.name for e in seated] == ["Ship: Scout", "Ship: Hauler"]
    assert all(not e.owned for e in seated)


def test_seat_showroom_ships_skips_the_owned_models_berth():
    game_map = _berth_map([(1, 1), (5, 1), (9, 1)])
    spec = SimpleNamespace(id="probe", showroom_ships=("scout", "hauler", "cruiser"))

    seat_showroom_ships(game_map, spec, "hauler")

    assert [(e.ship_id, e.pos.x) for e in _displays(game_map)] == [
        ("scout", 1), ("cruiser", 9),  # hauler's berth at x=5 seats nothing
    ]


def test_seat_showroom_ships_is_idempotent_and_strips_stale_displays():
    game_map = _berth_map([(1, 1), (5, 1)])
    spec = SimpleNamespace(id="probe", showroom_ships=("scout", "hauler"))
    stale = world.Entity(
        char="C", fg=(255, 255, 255), pos=world.Position(1, 1),
        name="Ship: Cruiser", ship_id="cruiser",
    )
    game_map.entities.append(stale)

    seat_showroom_ships(game_map, spec, None)
    first = [(e.ship_id, e.pos.x) for e in _displays(game_map)]
    seat_showroom_ships(game_map, spec, None)
    again = [(e.ship_id, e.pos.x) for e in _displays(game_map)]

    assert first == [("scout", 1), ("hauler", 5)] == again  # stale cruiser gone


def test_seat_showroom_ships_without_berths_is_a_no_op():
    game_map = _berth_map([])
    spec = SimpleNamespace(id="probe", showroom_ships=("scout",))

    seat_showroom_ships(game_map, spec, None)  # must not raise

    assert not _displays(game_map)


def test_seat_showroom_ships_raises_on_manifest_berth_count_mismatch():
    game_map = _berth_map([(1, 1)])
    spec = SimpleNamespace(id="probe", showroom_ships=("scout", "hauler"))

    with pytest.raises(ValueError, match="probe showroom manifest"):
        seat_showroom_ships(game_map, spec, None)
