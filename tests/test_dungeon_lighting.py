"""Regression coverage for dungeon ambient light and sight extension.

Phase 4 of the dynamic lighting system: glow fungus in BSP-carved
rooms emits light that extends the player's sight radius, and the
light grid tints visible cells while staying fog-gated (unseen cells
carry no light).

See ``docs/design/in_progress/27_DESIGN_DYNAMIC_LIGHTING.md`` Phase 4.
"""

from __future__ import annotations

from src.spacehack import dungeon_fov, world
from src.spacehack.dungeon_bsp import generate_dungeon
from src.spacehack.dungeon_params import DungeonParams


def _make_dungeon_with_fungus():
    """Generate a dungeon that has at least one glow_fungus tile."""
    for _ in range(50):
        params = DungeonParams(width=50, height=40)
        game_map, spawn = generate_dungeon(params)
        if any(
            tile.kind == "glow_fungus"
            for row in game_map.tiles
            for tile in row
        ):
            return game_map, spawn
    return game_map, spawn


def test_dungeon_generation_places_glow_fungus():
    game_map, _ = _make_dungeon_with_fungus()
    fungus = [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "glow_fungus"
    ]
    assert fungus, "no glow_fungus placed after 50 generations"
    # Fungus is walkable.
    for x, y in fungus:
        assert game_map.tiles[y][x].walkable


def test_glow_fungus_is_in_static_light_table():
    from src.spacehack.data.lighting import light_spec_for_kind

    spec = light_spec_for_kind("glow_fungus")
    assert spec is not None
    assert spec.radius == 3


def test_reveal_around_seeds_dungeon_light_grid():
    game_map, spawn = _make_dungeon_with_fungus()
    dungeon_fov.init_fog(game_map)
    # Find a fungus tile and reveal around it so the light is in sight.
    fungus = next(
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "glow_fungus"
    )
    reveal_pos = world.Position(*fungus)
    dungeon_fov.reveal_around(game_map, reveal_pos)
    # A dungeon with fungus gets a light grid.
    assert game_map.light_grid is not None
    # Some visible cells carry non-zero light.
    lit = [
        (x, y)
        for y, row in enumerate(game_map.light_grid)
        for x, cell in enumerate(row)
        if cell != (0, 0, 0)
    ]
    assert lit, "no lit cells despite glow fungus"


def test_light_grid_is_masked_to_visible_cells():
    game_map, spawn = _make_dungeon_with_fungus()
    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, spawn)
    # Cells outside the current LOS carry no light, even if a fungus
    # is nearby (light is fog-gated).
    for y in range(game_map.height):
        for x in range(game_map.width):
            if not game_map.visible[y][x]:
                assert game_map.light_grid[y][x] == (0, 0, 0), (
                    f"unseen cell ({x},{y}) carries light"
                )


def test_lit_cells_extend_sight_beyond_base_radius():
    """A glow fungus within sight reveals cells beyond the base radius."""
    # Build a small flat dungeon: a corridor with fungus in the middle.
    width, height = 21, 3
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    for x in range(1, width - 1):
        tiles[1][x] = world.DUNGEON_FLOOR
    # Place fungus at x=5, player at x=1, sight radius 3.
    tiles[1][5] = world.GLOW_FUNGUS
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    player_pos = world.Position(1, 1)
    dungeon_fov.init_fog(game_map)
    # With sight radius 3, the player sees x=1..4. The fungus at x=5 is
    # at distance 4 — just outside the base radius. But wait: distance
    # 3 reaches x=4, not x=5. So fungus at x=5 isn't visible yet.
    # Let's place fungus at x=4 (distance 3, within sight).
    tiles[1][4] = world.GLOW_FUNGUS
    tiles[1][5] = world.DUNGEON_FLOOR
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, player_pos, radius=3)
    # Player sees x=1..4 (radius 3). Fungus at x=4 is visible.
    assert game_map.visible[1][4]
    # The fungus (radius 3) should reveal x=5..7, beyond the base radius.
    # x=7 is at distance 6 from the player (beyond radius 3) but within
    # the fungus's light radius.
    assert game_map.visible[1][7], "fungus didn't extend sight to x=7"


def test_dungeon_without_fungus_has_no_light_grid():
    """A dungeon with no light sources gets no light grid."""
    width, height = 15, 7
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    for x in range(1, width - 1):
        tiles[3][x] = world.DUNGEON_FLOOR
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    player_pos = world.Position(2, 3)
    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, player_pos, radius=5)
    assert game_map.light_grid is None
