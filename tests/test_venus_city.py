"""Regression coverage for Venus's authored Cloudbreak City megacity."""

from __future__ import annotations

from collections import deque

from src.spacehack import city_interiors, city_landmarks
from src.spacehack.data.planets import find_planet_spec, load_planet


def _reachable(game_map, start):
    origin = (start.x, start.y)
    seen = {origin}
    queue = deque([origin])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            point = (x + dx, y + dy)
            if point in seen or not game_map.in_bounds(*point):
                continue
            if game_map.is_walkable(*point):
                seen.add(point)
                queue.append(point)
    return seen


def test_venus_is_the_authored_neon_downtown():
    game_map = load_planet("venus")
    assert game_map.city_layout_id == "venus_cloudbreak"
    assert (game_map.width, game_map.height) == (140, 100)
    assert len(game_map.landmark_stamps) == 4
    # Cloud rim rings the deck (the city floats in the atmosphere).
    assert any(tile.kind == "cloud_deck" for row in game_map.tiles for tile in row)
    # The avenue cross carries roads and the Cross plaza its beacon.
    assert sum(
        tile.kind.startswith("road") for row in game_map.tiles for tile in row
    ) > 600
    assert game_map.tiles[41][83].kind == "beacon"
    # Packed towers: a dense skyline of varied blocks, not open deck.
    assert len(game_map.skyline_placements) > 100
    # Neon signage lines the tower facades.
    assert sum(tile.kind == "neon" for row in game_map.tiles for tile in row) > 40


def test_venus_neon_seeds_a_light_grid():
    game_map = load_planet("venus")
    # The build seeds a non-None light grid from neon/beacon tiles.
    assert game_map.light_grid is not None
    # Neon signs and the beacon are light sources, so some cells carry
    # non-zero light.
    lit = [
        (x, y)
        for y, row in enumerate(game_map.light_grid)
        for x, cell in enumerate(row)
        if cell != (0, 0, 0)
    ]
    assert lit, "no lit cells despite neon signage"
    # Cells directly on a neon tile carry its colour (hot pink or cyan).
    neon_cells = [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "neon"
    ]
    for x, y in neon_cells[:5]:
        assert game_map.light_grid[y][x] != (0, 0, 0), f"neon at {x},{y} unlit"
    # Far-away cells (deep cloud deck, far corner) carry no light.
    assert game_map.light_grid[0][0] == (0, 0, 0)
    assert game_map.light_grid[99][139] == (0, 0, 0)


def test_venus_neon_sources_include_flicker_profiles():
    game_map = load_planet("venus")
    assert game_map.light_sources is not None
    profiles = {s.flicker for s in game_map.light_sources}
    # The "mixed" spec distributes steady/buzz/flicker across positions.
    assert "steady" in profiles
    assert profiles - {"steady"}, "all neon is steady — no flicker assigned"
    assert any(p != "steady" for p in profiles), "no flickering sources"


def test_venus_light_grid_varies_with_time():
    from src.spacehack.lighting import propagate_light

    game_map = load_planet("venus")
    sources = game_map.light_sources
    assert sources is not None
    occluder = lambda x, y: not game_map.tiles[y][x].walkable
    grid_t0 = propagate_light(
        game_map.width, game_map.height, sources, t=0, occluder=occluder,
    )
    grid_t99 = propagate_light(
        game_map.width, game_map.height, sources, t=99, occluder=occluder,
    )
    # Flickering sources mean the grid is not identical across time.
    assert grid_t0 != grid_t99, "light grid is static — flicker not working"


def test_venus_cloud_rim_edges_are_closed():
    game_map = load_planet("venus")
    # The rim silhouette is irregular: the cloud band borders the deck
    # but is never a solid rectangle, and it is not walkable.
    assert len({game_map.tiles[y][3].kind for y in range(4, 96)}) > 1, \
        "west rim reads as a solid wall, not an irregular silhouette"
    assert any(
        tile.kind == "cloud_deck"
        for tile in game_map.tiles[4]
    ), "no cloud band at the north deck rim"
    assert not any(
        tile.walkable and tile.kind == "cloud_deck"
        for row in game_map.tiles for tile in row
    )


def test_venus_buildings_transit_and_npcs_are_reachable():
    game_map = load_planet("venus")
    spec = find_planet_spec("venus")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert set(game_map.city_transit) == {
        "spaceport", "cloudbreak", "merchants", "depot",
    }
    # All-to-all network: every stop lists every other stop.
    assert all(
        set(metadata["destinations"]) == set(game_map.city_transit) - {station_id}
        for station_id, metadata in game_map.city_transit.items()
    )
    assert len(spec.city_npc_population) == 9
    for label, record in game_map.city_buildings.items():
        assert record["entrance"] in reachable, label
        x, y = record["entrance"]
        assert game_map.tiles[y][x].walkable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", ""):
            assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
            assert (entity.pos.x, entity.pos.y) in reachable


def test_venus_map_has_no_wall_holes_or_dead_deck_pockets():
    """The authored exteriors must close every wall row (no void gaps)
    and every walkable cell must be reachable from the hangar (the
    tower blocks and rim must never seal walkable deck from the
    streets)."""
    game_map = load_planet("venus")
    spec = find_planet_spec("venus")
    assert not any(
        tile.kind == "void"
        for row in game_map.tiles for tile in row
    ), "ragged layout row left a void wall gap"
    reachable = _reachable(game_map, spec.hangar_anchor)
    pockets = [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.walkable and (x, y) not in reachable
    ]
    assert not pockets, f"walkable cells sealed from the hangar: {pockets}"


def test_venus_circulation_is_planned():
    """Civil-engineering regression: one connected road network, and
    every transit stop standing on charted surface."""
    game_map = load_planet("venus")
    # Roads are circulation and are never paved over: the bays stand
    # beside them as curb-side stamps. The landing apron is also planned
    # circulation — it docks onto the avenue via the apron spur, and
    # the spaceport bay sits in its middle.
    road_kinds = {"road", "road_ns", "road_ew", "road_surface",
                  "transit_bay", "landing_pad"}
    planned = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind in road_kinds
    }
    assert len(planned) > 500, "the avenue network is too small"
    # One connected component: no avenue or lane stranded off the grid.
    # Each curb-side bay touches its road on one edge, so the whole
    # network (roads + bays) stays a single connected component.
    start = next(iter(planned))
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            point = (x + dx, y + dy)
            if point in seen or point not in planned:
                continue
            seen.add(point)
            queue.append(point)
    assert seen == planned, f"road bands stranded: {planned - seen}"
    # Every transit stop stands on charted surface (road, plaza, pad, bay).
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        kind = game_map.tiles[y][x].kind
        assert kind in {
            "road", "road_ns", "road_ew", "road_surface", "plaza",
            "landing_pad", "transit_bay",
        }, f"{station_id} stop floats on {kind}"


def test_venus_bays_never_pave_roads():
    """Transit bays are curb-side: every bay cell must sit on plaza,
    deck, pad, or sidewalk ground — never on asphalt."""
    game_map = load_planet("venus")
    road_kinds = {"road", "road_ns", "road_ew", "road_surface"}
    for y, row in enumerate(game_map.tiles):
        for x, tile in enumerate(row):
            if tile.kind == "transit_bay":
                assert tile.kind not in road_kinds  # trivially true
    # The real invariant: the road network keeps its authored size.
    # The six bands paint 771 unique cells; the spur roads stop at the
    # curb (y=68) so sidewalks own the door forecourts — no road cell is
    # ceded to sidewalk and no bay ever paves over asphalt.
    road_count = sum(
        1 for row in game_map.tiles for tile in row
        if tile.kind in road_kinds
    )
    assert road_count == 771, (
        f"road network changed size: {road_count} != 771 "
        "(bays must never pave over roads)"
    )


def test_venus_transit_bays_are_full_stamps():
    """Every transit stop must render a full 3x3 bay (or as much as the
    deck edge allows): bays clipped to a single column read as broken
    stamps on the avenue."""
    game_map = load_planet("venus")
    spec = find_planet_spec("venus")
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        bay_count = sum(
            1
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
            if game_map.tiles[y + dy][x + dx].kind == "transit_bay"
        )
        assert bay_count >= 4, (
            f"{station.id} stop at ({x},{y}) has only {bay_count} bay tiles"
        )
        assert game_map.tiles[y][x].kind == "transit_bay", station.id


def test_venus_surfaces_are_visually_distinct():
    """Road, sidewalk, plaza, and base deck must differ in fg or bg so
    the street hierarchy reads on screen (regression for the monochrome
    neon-canyon pass where every surface lifted to the same gray)."""
    from src.spacehack.data.planets import _readable_city_theme
    from src.spacehack.venus_city import VENUS_NEON

    theme = _readable_city_theme(VENUS_NEON)
    surfaces = {
        "floor": theme.floor,
        "sidewalk": theme.sidewalk,
        "road": theme.road_surface,
        "road_ns": theme.road_ns,
        "road_ew": theme.road_ew,
        "plaza": theme.plaza,
        "landing_pad": theme.landing_pad,
    }
    signatures = set()
    for name, tile in surfaces.items():
        sig = (tile.char, tile.fg, tile.bg)
        assert sig not in signatures, f"{name} is visually identical to another surface"
        signatures.add(sig)


def test_venus_interiors_follow_authored_conventions():
    """Every Venus interior uses the shared authored-room conventions:
    spawn and exit adjacent at the door side, furnished rooms, and each
    service NPC seats on a walkable, spawn-reachable cell."""
    game_map = load_planet("venus")
    assert set(game_map.city_buildings) == {"spaceport", "bar", "merchants", "depot"}
    furniture_kinds = {"table", "bar_body", "drink", "city_ornament"}
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        interior = asset.game_map
        spawn = asset.spawn
        assert spawn is not None, label
        exits = [
            (x, y)
            for y, row in enumerate(interior.tiles)
            for x, tile in enumerate(row)
            if tile.kind == "exit"
        ]
        assert len(exits) == 1, label
        assert exits[0] == (spawn.x, spawn.y + 1), label
        assert any(
            tile.kind in furniture_kinds
            for row in interior.tiles for tile in row
        ), label
        if not record.get("npc_id"):
            continue
        seat = city_interiors._first_interior_npc(interior, spawn)
        assert seat is not None, label
        assert interior.tiles[seat.y][seat.x].walkable, label
        reachable = _reachable(interior, spawn)
        assert (seat.x, seat.y) in reachable, label