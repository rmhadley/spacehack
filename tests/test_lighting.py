"""Regression coverage for the time-varying lighting primitive.

Covers :mod:`spacehack.lighting` — the pure, testable core of the
dynamic lighting system (see
``docs/design/in_progress/27_DESIGN_DYNAMIC_LIGHTING.md``). The grid
propagation, flicker profiles, and additive blend are all pure
functions, so these tests construct inputs and assert exact outputs
without touching the renderer or game state.
"""

from __future__ import annotations

from src.spacehack.lighting import LightSource, blend_toward_light, propagate_light


# ---------------------------------------------------------------------
# propagate_light — grid propagation
# ---------------------------------------------------------------------


def test_empty_sources_produce_all_black_grid():
    grid = propagate_light(4, 3, [])
    assert len(grid) == 3
    assert all(cell == (0, 0, 0) for row in grid for cell in row)


def test_single_source_lights_only_within_radius():
    source = LightSource(x=2, y=2, colour=(255, 0, 0), radius=1)
    grid = propagate_light(5, 5, [source])
    # The source cell and its 8 neighbours (radius 1) carry red; the
    # corners of the 5x5 grid stay black.
    assert grid[2][2] == (255, 0, 0)
    assert grid[1][2] != (0, 0, 0)
    assert grid[2][1] != (0, 0, 0)
    assert grid[0][0] == (0, 0, 0)
    assert grid[4][4] == (0, 0, 0)


def test_radius_zero_lights_only_source_cell():
    source = LightSource(x=1, y=1, colour=(100, 200, 50), radius=0)
    grid = propagate_light(3, 3, [source])
    assert grid[1][1] == (100, 200, 50)
    # All neighbours stay black.
    assert grid[0][0] == (0, 0, 0)
    assert grid[1][0] == (0, 0, 0)
    assert grid[2][2] == (0, 0, 0)


def test_falloff_reduces_intensity_with_distance():
    # falloff=0.5 → distance 1 contributes 0.5x, distance 2 → 0.25x.
    source = LightSource(x=5, y=0, colour=(200, 200, 200), radius=5)
    grid = propagate_light(11, 1, [source], falloff=0.5)
    # Source cell: 200 (full intensity, falloff^0 = 1).
    assert grid[0][5] == (200, 200, 200)
    # Distance 1: 200 * 0.5 = 100.
    assert grid[0][4] == (100, 100, 100)
    # Distance 2: 200 * 0.25 = 50.
    assert grid[0][3] == (50, 50, 50)


def test_overlapping_sources_add_and_clamp():
    red = LightSource(x=0, y=0, colour=(255, 0, 0), radius=2)
    blue = LightSource(x=0, y=0, colour=(0, 0, 255), radius=2)
    grid = propagate_light(1, 1, [red, blue])
    # Both sources land on the same cell → additive: (255, 0, 255).
    assert grid[0][0] == (255, 0, 255)


def test_additive_clamps_to_255_per_channel():
    bright = LightSource(
        x=0, y=0, colour=(255, 255, 255), radius=0, intensity=2.0,
    )
    grid = propagate_light(1, 1, [bright])
    # 255 * 2.0 = 510 → clamped to 255.
    assert grid[0][0] == (255, 255, 255)


def test_occluder_blocks_light_through_walls():
    # A wall between the source and a cell stops the light.
    # Grid: 5x1. Source at (0,0). Wall at (2,0). Cell at (4,0).
    source = LightSource(x=0, y=0, colour=(255, 0, 0), radius=5)
    walls = {(2, 0)}
    grid = propagate_light(
        5, 1, [source],
        occluder=lambda x, y: (x, y) in walls,
    )
    # Source cell is lit.
    assert grid[0][0] != (0, 0, 0)
    # Cell before the wall is lit.
    assert grid[0][1] != (0, 0, 0)
    # The wall cell itself is not lit (occluded).
    assert grid[0][2] == (0, 0, 0)
    # Cells beyond the wall are not lit.
    assert grid[0][3] == (0, 0, 0)
    assert grid[0][4] == (0, 0, 0)


def test_no_occluder_means_light_passes_through():
    # Same layout, no occluder → light reaches the far cell.
    source = LightSource(x=0, y=0, colour=(255, 0, 0), radius=5)
    grid = propagate_light(5, 1, [source])
    assert grid[0][4] != (0, 0, 0)


def test_source_cell_is_lit_even_when_it_is_an_occluder():
    # A neon sign is non-walkable (an occluder), but it still lights itself.
    source = LightSource(x=2, y=2, colour=(255, 0, 0), radius=3)
    grid = propagate_light(
        5, 5, [source],
        occluder=lambda x, y: (x, y) == (2, 2),
    )
    assert grid[2][2] != (0, 0, 0)


def test_source_outside_bounds_does_not_crash():
    # Source off the map edge but whose radius reaches into the grid.
    source = LightSource(x=-1, y=-1, colour=(255, 0, 0), radius=3)
    grid = propagate_light(4, 4, [source])
    # The (0, 0) cell is at Chebyshev distance 1 from the source.
    assert grid[0][0] != (0, 0, 0)
    # The far corner is at distance 6, outside the radius of 3.
    assert grid[3][3] == (0, 0, 0)


def test_zero_dimensions_return_empty_grid():
    grid = propagate_light(0, 0, [LightSource(0, 0, (255, 0, 0), 1)])
    assert grid == []


# ---------------------------------------------------------------------
# Flicker profiles — time-varying intensity
# ---------------------------------------------------------------------


def test_steady_profile_is_constant_across_time():
    source = LightSource(x=0, y=0, colour=(255, 0, 0), radius=0, flicker="steady")
    grids = [propagate_light(1, 1, [source], t=t) for t in range(10)]
    # Every frame produces the same full-intensity red.
    assert all(g[0][0] == (255, 0, 0) for g in grids)


def test_flicker_profile_varies_with_time():
    intensities = {
        propagate_light(1, 1, [LightSource(0, 0, (255, 0, 0), 0, flicker="buzz")], t=t)[0][0][0]
        for t in range(40)
    }
    # The buzz profile produces at least two distinct brightness levels
    # over 40 frames (it's not constant).
    assert len(intensities) >= 2


def test_flicker_is_deterministic_for_same_t():
    source = LightSource(x=2, y=2, colour=(255, 0, 0), radius=0, flicker="flicker")
    g1 = propagate_light(1, 1, [source], t=7)
    g2 = propagate_light(1, 1, [source], t=7)
    assert g1 == g2


def test_unknown_flicker_falls_back_to_steady():
    source = LightSource(
        x=0, y=0, colour=(255, 0, 0), radius=0, flicker="nonexistent",
    )
    grid = propagate_light(1, 1, [source], t=0)
    # Falls back to steady (full intensity), not zero.
    assert grid[0][0] == (255, 0, 0)


def test_adjacent_sources_flicker_independently():
    # Two buzz sources at different x should not be phase-locked.
    a = LightSource(x=1, y=0, colour=(255, 0, 0), radius=0, flicker="buzz")
    b = LightSource(x=5, y=0, colour=(255, 0, 0), radius=0, flicker="buzz")
    differs = any(
        propagate_light(6, 1, [a], t=t)[0][1]
        != propagate_light(6, 1, [b], t=t)[0][5]
        for t in range(40)
    )
    assert differs, "adjacent buzz sources flicker in lockstep"


# ---------------------------------------------------------------------
# blend_toward_light — additive tile tint
# ---------------------------------------------------------------------


def test_zero_light_leaves_colours_unchanged():
    fg, bg = blend_toward_light((100, 50, 25), (20, 10, 5), (0, 0, 0))
    assert fg == (100, 50, 25)
    assert bg == (20, 10, 5)


def test_blend_adds_light_per_channel():
    fg, bg = blend_toward_light((40, 60, 80), (10, 20, 30), (100, 50, 25))
    assert fg == (140, 110, 105)
    assert bg == (110, 70, 55)


def test_blend_clamps_to_255():
    fg, bg = blend_toward_light(
        (200, 200, 200), (200, 200, 200), (100, 100, 100),
    )
    assert fg == (255, 255, 255)
    assert bg == (255, 255, 255)


def test_red_light_on_blue_surface_gives_magenta():
    # The classic neon-canyon case: a red sign lighting a blue wall.
    fg, _bg = blend_toward_light((0, 0, 200), (0, 0, 40), (150, 0, 0))
    assert fg == (150, 0, 200)
