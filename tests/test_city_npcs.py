"""Tests for ambient city NPCs: placement, deterministic movement, and
direct-contact hostile dispatch (Phase 3 of the planet-city expansion)."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import city_npcs, world
from src.spacehack.data.city_npcs import CityNpc, EARTH_POPULATION
from src.spacehack.data.planets import load_planet


def _walkable_map(*entities: world.Entity, w: int = 16, h: int = 12) -> world.GameMap:
    # Plaza tiles are walkable and count as city landmarks, so the
    # destination picker has something to walk toward on the open map.
    tiles = [
        [world.Tile("city_plaza", ".", True, (0, 120, 0), (0, 0, 0)) for _ in range(w)]
        for _ in range(h)
    ]
    return world.GameMap(w, h, tiles, list(entities))


def test_earth_population_uses_real_char_specs_and_valid_spawns():
    """Every catalog entry resolves to a real NpcCharSpec and lands on a
    walkable, unblocked cell on the rebuilt Earth city."""
    game_map = load_planet("earth")
    placed = {
        e.city_npc_id: e
        for e in game_map.entities
        if getattr(e, "city_npc_id", "")
    }
    assert set(placed) == {t.id for t in EARTH_POPULATION}
    for template in EARTH_POPULATION:
        entity = placed[template.id]
        tile = game_map.tiles[entity.pos.y][entity.pos.x]
        assert tile.walkable, f"{template.id} spawned on unwalkable cell"
        assert (
            game_map.blocking_entity_at(entity.pos.x, entity.pos.y, exclude=entity)
            is None
        ), f"{template.id} spawned on a blocked cell"


def test_ambient_npcs_anchor_within_wander_radius():
    """NPCs placed at their authored anchor carry anchor metadata."""
    game_map = load_planet("earth")
    for template in EARTH_POPULATION:
        entity = next(
            e for e in game_map.entities if e.city_npc_id == template.id
        )
        assert (entity.pos.x, entity.pos.y) == template.spawn
        assert entity.city_wander_radius == template.wander_radius


def test_move_city_npcs_traverses_to_destination(monkeypatch):
    """Citizens walk a destination path (space-traffic style), not a box."""
    anchor = (4, 4)
    npc = world.Entity(
        "p", (255, 100, 100), world.Position(4, 4),
        city_npc_id="npc", npc_char_id="civillian_bystander",
    )
    npc.city_spawn = world.Position(*anchor)
    npc.city_wander_radius = 10
    npc.city_move_chance = 1.0
    # Fake rng: always steps, and picks a fixed far destination.
    class _FakeRng:
        def random(self):
            return 0.0  # below 1.0 -> always move
        def choice(self, seq):
            return seq[-1]  # farthest cell in the pool
    npc.city_rng = _FakeRng()
    game_map = _walkable_map(npc, w=20, h=20)

    before = (npc.pos.x, npc.pos.y)
    city_npcs.move_city_npcs(SimpleNamespace(), game_map)
    # Exactly one cell per tick (Chebyshev — A* may step diagonally).
    assert max(abs(npc.pos.x - before[0]), abs(npc.pos.y - before[1])) == 1
    assert npc.city_dest is not None
    # The destination is a distinct, reachable pavement cell.
    dest = npc.city_dest
    assert (dest[0], dest[1]) != before
    assert game_map.tiles[dest[1]][dest[0]].walkable
    # Walking further across ticks keeps moving toward the destination.
    first = (npc.pos.x, npc.pos.y)
    for _ in range(6):
        city_npcs.move_city_npcs(SimpleNamespace(), game_map)
    assert (npc.pos.x, npc.pos.y) != first


def test_move_city_npcs_skips_combat_locked(monkeypatch):
    """Combat-locked citizens are frozen (combat AI owns their position)."""
    moving = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        city_npc_id="moving", npc_char_id="civillian_bystander",
    )
    moving.city_spawn = world.Position(2, 2)
    moving.city_move_chance = 1.0
    class _FakeRng:
        def random(self):
            return 0.0
        def choice(self, seq):
            return seq[-1]
    moving.city_rng = _FakeRng()

    locked = world.Entity(
        "g", (200, 200, 200), world.Position(5, 5),
        city_npc_id="locked", npc_char_id="civillian_bystander",
    )
    locked.combat_locked = True
    locked.city_spawn = world.Position(5, 5)
    locked.city_move_chance = 1.0
    locked.city_rng = _FakeRng()

    game_map = _walkable_map(moving, locked)
    city_npcs.move_city_npcs(SimpleNamespace(), game_map)

    # Locked citizen is frozen; the moving one steps one cell.
    assert (locked.pos.x, locked.pos.y) == (5, 5)
    assert max(abs(moving.pos.x - 2), abs(moving.pos.y - 2)) == 1


def test_every_population_has_dense_landmark_pool():
    """No citizen's district collapses to a one-landmark pool (regression:
    militia patrols circled a single door because special tiles were the
    only landmarks; streets are traffic lanes and must count too)."""
    game_map = load_planet("earth")
    cells = city_npcs._city_landmarks(game_map)
    for template in EARTH_POPULATION:
        spawn = template.spawn
        pool = [
            (x, y) for x, y in cells
            if abs(x - spawn[0]) + abs(y - spawn[1]) <= template.wander_radius
        ]
        assert len(pool) >= 8, (
            f"{template.id} has only {len(pool)} landmarks in radius "
            f"{template.wander_radius} — it will circle a single cell"
        )


def test_unreachable_destination_repicks_without_crashing():
    """A destination A* can't reach is dropped and repicked, never indexed
    as None (regression: ``_step_along_path`` clears city_dest then the
    arrival check subscripted it)."""
    game_map = load_planet("earth")
    npc = next(
        e for e in game_map.entities if e.city_npc_id == "earth_hub_guard"
    )
    # Point at water/wall tiles A* can never reach.
    npc.city_dest = (0, 0)
    npc.city_path = None
    ctx = SimpleNamespace(player=None, faction_reputation={})
    for _ in range(50):
        city_npcs.move_city_npcs(ctx, game_map)
    assert game_map.tiles[npc.pos.y][npc.pos.x].walkable


def test_place_city_npcs_skips_unknown_char(monkeypatch):
    """A template whose npc_char_id doesn't resolve is skipped, not crashed."""
    tmpl = CityNpc("ghost_npc", "does_not_exist_spec", (3, 3))
    game_map = _walkable_map()
    city_npcs.place_city_npcs(game_map, [tmpl])
    assert not any(getattr(e, "city_npc_id", "") for e in game_map.entities)


def test_city_npc_positions_round_trip_via_rebuild():
    """Saved city NPC positions are reapplied onto the rebuilt city map."""
    from src.spacehack import saveload_maps as _sm

    game_map = load_planet("earth")
    # Simulate the NPCs having wandered: move each to a nearby walkable cell
    # and give it an in-progress destination (the save payload shape).
    saved = {}
    for e in game_map.entities:
        if not getattr(e, "city_npc_id", ""):
            continue
        # nudge one cell west if walkable, else keep anchor
        nx = e.pos.x - 1
        ny = e.pos.y
        if (nx, ny) != (e.pos.x, e.pos.y) and game_map.tiles[ny][nx].walkable \
                and game_map.blocking_entity_at(nx, ny, exclude=e) is None:
            saved[e.city_npc_id] = {"pos": [nx, ny], "dest": [nx, ny]}
        else:
            saved[e.city_npc_id] = {"pos": [e.pos.x, e.pos.y], "dest": None}

    # Rebuild a fresh Earth map and reapply.
    fresh = load_planet("earth")
    _sm._restore_city_npc_positions(fresh, saved)

    for e in fresh.entities:
        if not getattr(e, "city_npc_id", ""):
            continue
        saved_pos = saved[e.city_npc_id]["pos"]
        assert (e.pos.x, e.pos.y) == tuple(saved_pos), e.city_npc_id
        saved_dest = saved[e.city_npc_id]["dest"]
        if saved_dest is not None:
            assert (e.city_dest[0], e.city_dest[1]) == tuple(saved_dest), e.city_npc_id
