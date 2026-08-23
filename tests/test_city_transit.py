"""Regression tests for the city transit network.

Phase 2 of the planet-city expansion: data-defined stations, deterministic
placement on the rebuilt Earth map, and bump-to-travel between districts.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import city_transit, world
from src.spacehack.data.planets import load_planet


def _station_entities(game_map):
    return [e for e in game_map.entities if getattr(e, "transit_station_id", "")]


def test_earth_places_every_transit_station_on_walkable_cells():
    from src.spacehack.data.planets import find_planet_spec

    game_map = load_planet("earth")
    spec_ids = {s.id for s in find_planet_spec("earth").transit_stations}
    entities = _station_entities(game_map)

    assert {e.transit_station_id for e in entities} == spec_ids
    assert len(entities) == 6
    for entity in entities:
        tile = game_map.tiles[entity.pos.y][entity.pos.x]
        assert tile.walkable
        assert entity.char == "◉"
        assert entity.fg == (255, 215, 100)


def test_transit_lookup_has_every_station_and_valid_full_destination_routes():
    game_map = load_planet("earth")
    lookup = game_map.city_transit

    assert set(lookup) == {e.transit_station_id for e in _station_entities(game_map)}
    for station_id, metadata in lookup.items():
        assert metadata["name"]
        assert isinstance(metadata["pos"], tuple)
        destinations = set(metadata["destinations"])
        # Every destination is a real station, and the network is fully
        # connected: each station can reach every other station.
        assert destinations == (set(lookup) - {station_id})


def test_transit_travel_moves_player_to_chosen_destination(monkeypatch):
    game_map = load_planet("earth")
    port = next(
        e for e in _station_entities(game_map) if e.transit_station_id == "port"
    )
    state = SimpleNamespace(
        game_map=game_map,
        player=world.Entity("@", (255, 255, 255), world.Position(30, 29)),
        ctx=SimpleNamespace(context=None),
    )
    console = []
    state.log = SimpleNamespace(add=lambda text: console.append(text))

    monkeypatch.setattr(
        city_transit,
        "_run_transit_menu",
        lambda _ctx, _station, _dests: "militia",
    )

    result = city_transit.resolve_transit_station(state, port)

    assert result is None
    militia = game_map.city_transit["militia"]["pos"]
    # The player landed on or beside the Militia Center station.
    assert (
        (state.player.pos.x, state.player.pos.y)
        in {
            (militia[0] + dx, militia[1] + dy)
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0), (0, 0))
        }
    )
    assert any("transit" in text.lower() for text in console)


def test_transit_cancel_does_not_move_player(monkeypatch):
    game_map = load_planet("earth")
    hub = next(
        e for e in _station_entities(game_map) if e.transit_station_id == "hub"
    )
    state = SimpleNamespace(
        game_map=game_map,
        player=world.Entity("@", (255, 255, 255), world.Position(69, 52)),
        ctx=SimpleNamespace(context=None),
    )
    state.log = SimpleNamespace(add=lambda text: None)

    monkeypatch.setattr(city_transit, "_run_transit_menu", lambda *_a, **_k: None)

    city_transit.resolve_transit_station(state, hub)

    assert (state.player.pos.x, state.player.pos.y) == (69, 52)


def test_transit_station_without_routes_logs_and_does_not_move(monkeypatch):
    game_map = load_planet("earth")
    for e in list(_station_entities(game_map)):
        e.transit_station_id = e.transit_station_id  # no-op, keep ids
    station = _station_entities(game_map)[0]
    # Simulate a station whose lookup has no reachable destinations.
    game_map.city_transit[station.transit_station_id]["destinations"] = []
    start = world.Position(station.pos.x, station.pos.y - 1)
    state = SimpleNamespace(
        game_map=game_map,
        player=world.Entity("@", (255, 255, 255), start),
        ctx=SimpleNamespace(context=None),
        log=SimpleNamespace(add=lambda text: None),
    )

    city_transit.resolve_transit_station(state, station)

    assert (state.player.pos.x, state.player.pos.y) == (start.x, start.y)


def test_no_station_sits_in_front_of_a_building_door():
    from src.spacehack.data.planets import find_planet_spec

    spec = find_planet_spec("earth")
    door_cells = {
        (b.door_x, b.y_hi + 1) for b in spec.buildings
    }
    station_cells = {
        (s.pos.x, s.pos.y) for s in spec.transit_stations
    }
    # A station must never occupy the cell directly outside a building door
    # (that would block the doorway).
    assert station_cells.isdisjoint(door_cells)


def test_all_stations_are_walkable_and_free_of_other_blockers():
    game_map = load_planet("earth")
    for entity in _station_entities(game_map):
        tile = game_map.tiles[entity.pos.y][entity.pos.x]
        assert tile.walkable
        # The only blocker on a station cell is the station itself.
        blocker = game_map.blocking_entity_at(entity.pos.x, entity.pos.y)
        assert blocker is entity


def test_transit_arrival_never_lands_on_terminal_npc_ship_or_door(monkeypatch):
    from src.spacehack.data.planets import find_planet_spec

    game_map = load_planet("earth")
    spec = find_planet_spec("earth")

    dest_pos = {dest.id: dest.pos for dest in spec.transit_stations}
    for source in spec.transit_stations:
        for dest_id in source.destinations:
            cell = city_transit._arrival_cell(
                game_map, dest_pos[dest_id], dest_id,
            )
            tile = game_map.tiles[cell.y][cell.x]
            assert tile.walkable
            assert tile.kind != "door"
            blocker = game_map.blocking_entity_at(cell.x, cell.y)
            # No terminal, NPC, ship, or other station under the arrival cell.
            assert blocker is None


def test_spaceport_arrival_lands_on_open_landing_pad_not_a_terminal():
    game_map = load_planet("earth")
    # The reported bug: riding to the spaceport dropped the player on the
    # Mechanic Terminal. The arrival cell must be clear.
    port = next(e for e in _station_entities(game_map) if e.transit_station_id == "port")
    cell = city_transit._arrival_cell(game_map, (port.pos.x, port.pos.y), "port")
    assert game_map.blocking_entity_at(cell.x, cell.y) is None
    assert game_map.tiles[cell.y][cell.x].walkable


def test_transit_menu_dispatch_returns_destination(monkeypatch):
    from src.spacehack import pygame_menu

    # Mirror the planet-menu test seam: the shared runner decides the outcome.
    game_map = load_planet("earth")
    ctx = SimpleNamespace(context=object())
    destinations = [
        ("hub", game_map.city_transit["hub"]),
        ("bar", game_map.city_transit["bar"]),
    ]
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *_a, **_k: ("SELECT", "bar", 1),
    )

    chosen = city_transit._run_transit_menu(ctx, "Spaceport", destinations)

    assert chosen == "bar"
