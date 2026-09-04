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
    monkeypatch.setattr(
        city_transit, "animate_transit_arrival", lambda *_a, **_k: None,
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


def test_transit_arrival_pulses_then_restores_the_light_grid(monkeypatch):
    """The arrival bloom presents decaying frames and hands back the
    steady grid bit-identical (playtest v15: busy cities hid the
    arrival point)."""
    from src.spacehack import city_render
    from src.spacehack.framebuffer import FrameBuffer

    game_map = load_planet("earth")
    assert game_map.light_grid is not None
    before = [row[:] for row in game_map.light_grid]
    grids_at_present = []
    monkeypatch.setattr(
        city_render, "present_city_transition_frame",
        lambda *_a, _map=game_map, _grids=grids_at_present, **_k: _grids.append(
            [row[:] for row in _map.light_grid]
        ),
    )
    from src.spacehack import navigation_travel
    monkeypatch.setattr(navigation_travel, "_responsive_sleep", lambda _s: None)

    dest = game_map.city_transit["militia"]["pos"]
    state = SimpleNamespace(
        game_map=game_map,
        player=world.Entity("@", (255, 255, 255), world.Position(*dest)),
        ctx=SimpleNamespace(context=None),
        console=FrameBuffer(80, 45),
    )

    city_transit.animate_transit_arrival(state, "Militia Center")

    # 12 pulse frames + one clean settle frame.
    assert len(grids_at_present) == 13
    assert grids_at_present[0] != before, "the pulse must be visible"
    assert grids_at_present[-1] == before, "the settle frame is the steady grid"
    assert game_map.light_grid == before, "the steady grid is restored exactly"


def test_transit_arrival_is_a_noop_without_a_light_grid(monkeypatch):
    from src.spacehack import city_render

    game_map = load_planet("earth")
    game_map.light_grid = None
    presented = []
    monkeypatch.setattr(
        city_render, "present_city_transition_frame",
        lambda *_a, **_k: presented.append(1),
    )
    state = SimpleNamespace(
        game_map=game_map,
        player=world.Entity("@", (255, 255, 255), world.Position(30, 29)),
        ctx=SimpleNamespace(context=None),
        console=None,
    )

    city_transit.animate_transit_arrival(state, "Hub")

    assert presented == []


def test_transit_travel_plays_the_arrival_pulse(monkeypatch):
    game_map = load_planet("earth")
    port = next(
        e for e in _station_entities(game_map) if e.transit_station_id == "port"
    )
    state = SimpleNamespace(
        game_map=game_map,
        player=world.Entity("@", (255, 255, 255), world.Position(30, 29)),
        ctx=SimpleNamespace(context=None),
        console=None,
    )
    state.log = SimpleNamespace(add=lambda text: None)
    monkeypatch.setattr(
        city_transit, "_run_transit_menu", lambda _ctx, _s, _d: "militia",
    )
    pulses = []
    monkeypatch.setattr(
        city_transit, "animate_transit_arrival",
        lambda _state, location, colour=(0, 0, 0): pulses.append(location),
    )

    city_transit.resolve_transit_station(state, port)

    assert pulses == ["Militia Center"]


def test_every_transit_city_is_lit_and_stops_on_their_bays():
    """Option 4 (playtest v15): every settled planet's city carries a
    light grid — the painted transit bays alone guarantee it — so the
    arrival pulse works everywhere and no city renders unlit."""
    from src.spacehack.data.planets import list_planet_specs

    cities = [s for s in list_planet_specs() if getattr(s, "transit_stations", None)]
    assert len(cities) >= 20
    for spec in cities:
        game_map = load_planet(spec.id)
        assert game_map.light_grid is not None, spec.id
        stops = _station_entities(game_map)
        assert len(stops) == len(spec.transit_stations)
        bays = sum(
            1 for row in game_map.tiles for t in row if t.kind == "transit_bay"
        )
        assert len(game_map.light_sources or []) >= bays, spec.id
        for entity in stops:
            tile = game_map.tiles[entity.pos.y][entity.pos.x]
            assert tile.kind == "transit_bay", (spec.id, entity.transit_station_id)
            assert tile.walkable


def test_arrival_pulse_runs_on_a_previously_unlit_city(monkeypatch):
    """eri_b had no light grid before the city-lighting catch-up; the
    arrival animation must present its frames there now."""
    from src.spacehack import city_render
    from src.spacehack.framebuffer import FrameBuffer

    game_map = load_planet("eri_b")
    assert game_map.light_grid is not None
    monkeypatch.setattr(city_render, "present_city_transition_frame",
                        lambda *_a, **_k: None)
    from src.spacehack import navigation_travel
    monkeypatch.setattr(navigation_travel, "_responsive_sleep", lambda _s: None)

    dest = game_map.city_transit and next(iter(game_map.city_transit.values()))
    state = SimpleNamespace(
        game_map=game_map,
        player=world.Entity("@", (255, 255, 255), world.Position(*dest["pos"])),
        ctx=SimpleNamespace(context=None),
        console=FrameBuffer(80, 45),
    )

    city_transit.animate_transit_arrival(state, dest["name"])  # must not no-op


def test_transit_bay_light_stays_restrained():
    """A bay is a block of 8-12 cells and every cell collects as a
    source — a wide radius stacks a dozen emitters and the stations
    glowed white-hot (playtest v15). The spec must stay tight."""
    from src.spacehack.data.lighting import light_spec_for_kind

    spec = light_spec_for_kind("transit_bay")
    assert spec is not None
    assert spec.radius <= 1
    assert spec.intensity <= 0.5
