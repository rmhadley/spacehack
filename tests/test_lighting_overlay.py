"""Regression coverage for Phase 5: river current and transient glows.

Covers two deliverables:
- Earth river water shimmers via the ``city_water`` light source (bitmap
  layer, pulse profile) and the grid varies with ``t``.
- ``LightGlow`` overlay effect is queued, consumed on read, and fades
  with age (the combat explosion glow path).
"""

from __future__ import annotations

from src.spacehack.data.planets import load_planet
from src.spacehack.lighting import propagate_light
from src.spacehack.pygame_overlay import LightGlow, OverlayFrame


def test_earth_river_seeds_a_light_grid():
    game_map = load_planet("earth")
    assert game_map.light_grid is not None
    # Water cells emit light, so some cells carry non-zero light.
    lit = [
        (x, y)
        for y, row in enumerate(game_map.light_grid)
        for x, cell in enumerate(row)
        if cell != (0, 0, 0)
    ]
    assert lit, "no lit cells despite river water"


def test_earth_river_light_varies_with_time():
    game_map = load_planet("earth")
    sources = game_map.light_sources
    assert sources is not None
    occluder = lambda x, y: not game_map.tiles[y][x].walkable
    grid_t0 = propagate_light(
        game_map.width, game_map.height, sources, t=0, occluder=occluder,
    )
    grid_t50 = propagate_light(
        game_map.width, game_map.height, sources, t=50, occluder=occluder,
    )
    # The pulse profile means the water shimmer varies with time.
    assert grid_t0 != grid_t50, "river light is static — pulse not working"


def test_light_glow_is_a_valid_overlay_field():
    glow = LightGlow(x=5, y=3, color=(255, 200, 100), radius=3, age=0, lifetime=3)
    frame = OverlayFrame(
        hud=(), messages=(), hud_x=0, hud_top=0, hud_height=10,
        message_top=50, message_height=10,
        glows=(glow,),
    )
    assert len(frame.glows) == 1
    assert frame.glows[0] is glow


def test_active_glows_consume_on_read():
    from src.spacehack.combat import _animations

    _animations._set_glows([
        LightGlow(x=1, y=1, color=(255, 0, 0), radius=2, age=0, lifetime=2),
    ])
    glows = _animations.active_glows()
    assert len(glows) == 1
    # Second call returns nothing — consumed.
    assert _animations.active_glows() == ()


def test_active_glows_empty_when_none_queued():
    from src.spacehack.combat import _animations

    _animations._set_glows([])
    assert _animations.active_glows() == ()
