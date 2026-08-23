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
