"""Time-varying per-cell coloured lighting primitive.

This module owns the pure, testable core of the dynamic lighting system
(documented in ``docs/design/in_progress/27_DESIGN_DYNAMIC_LIGHTING.md``).
A light grid is a 2-D array of additive ``(r, g, b)`` colours — the same
shape as a ``GameMap.tiles`` grid — produced by propagating one or more
:class:`LightSource` values with Chebyshev-distance falloff. Each source
may carry a flicker profile (a pure function of the source and the
current frame clock ``t``) so the grid varies over time; a steady source
(the common case) is the special case where the profile is constant.

The grid is **derived presentation state**: it is never serialised, it
is recomputed from the map's tiles/entities + the clock on load, and it
only changes the ``(fg, bg)`` colours that
:func:`spacehack.world_render._tile_render_colors` returns. It never
affects game logic. The only gameplay-facing interaction (dungeons:
light extending the player's sight) lives in :mod:`spacehack.dungeon_fov`
and is a separate, explicit behaviour, not a side effect of the tint.

The blend model is additive: light is *added* to a tile's base colours
(per channel, clamped to 255). This is physically correct — a red sign
lighting a blue wall produces a magenta wall, and two overlapping signs
of different hues blend their colours in the overlap (clamping to white
only at extreme overexposure; a tone-mapping pass can be added later if
the playtest reveals flat-white overlap zones).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class LightSource:
    """One coloured light emitter at a cell position.

    ``flicker`` names a profile in :data:`FLICKER_PROFILES`; ``"steady"``
    (the default) means the source never varies with time. The colour is
    the source's full-intensity emission; propagation scales it by the
    flicker profile's intensity multiplier and by distance falloff.
    """

    x: int
    y: int
    colour: RGB
    radius: int
    intensity: float = 1.0
    flicker: str = "steady"


# A flicker profile is a pure ``(source, t) -> multiplier`` function.
# ``t`` is the monotonic frame clock; the multiplier scales the source's
# base intensity at that instant. Profiles are deterministic given ``t``
# so the flicker is reproducible (important for tests and for visual
# continuity across a save/load — the clock resets, but the *grid* is
# recomputed from tiles + the new clock, so the visual resumes).
FlickerProfile = Callable[[LightSource, int], float]


def _steady(_source: LightSource, _t: int) -> float:
    return 1.0


def _buzz(source: LightSource, t: int) -> float:
    """A rapid, irregular on/off buzz — faulty ballast or old neon.

    Holds ~85% baseline with short dropouts every few frames; keyed by
    the source's x so adjacent signs buzz independently.
    """
    return 0.85 + 0.15 * (1.0 if (hash((source.x, t // 4)) & 1) else 0.0)


def _flicker(source: LightSource, t: int) -> float:
    """A slower, uneven flicker — a dying or poorly-wired sign.

    Steps between three brightness levels on a ~7-frame cadence, keyed
    by the source's full position so each sign flickers out of phase.
    """
    step = hash((source.x, source.y, t // 7)) % 3
    return (0.7, 0.85, 1.0)[step]


def _pulse(source: LightSource, t: int) -> float:
    """A smooth sinusoidal pulse — a beacon or synced display."""
    return 0.8 + 0.2 * math.sin(t * 0.3 + source.x * 0.5)


def _alarm(source: LightSource, t: int) -> float:
    """A hard strobe — full-on flashing lockdown light.

    Swings sharply between a dim baseline and full brightness on a
    ~4-frame cadence, keyed by position so adjacent panels blink out
    of phase (the prison's "flashing reds, blinking" state).
    """
    return 0.35 + 0.65 * (1.0 if hash((source.x, source.y, t // 4)) & 1 else 0.0)


FLICKER_PROFILES: dict[str, FlickerProfile] = {
    "steady": _steady,
    "buzz": _buzz,
    "flicker": _flicker,
    "pulse": _pulse,
    "alarm": _alarm,
}


def _flicker_multiplier(source: LightSource, t: int) -> float:
    """Return the intensity multiplier for ``source`` at time ``t``.

    Falls back to the steady profile (1.0) if the named profile is
    unknown, so a typo in data never silently darkens a source.
    """
    profile = FLICKER_PROFILES.get(source.flicker, _steady)
    return profile(source, t)


def _line_is_clear(
    x0: int, y0: int, x1: int, y1: int,
    occluder,
) -> bool:
    """Whether the line ``(x0,y0)`` → ``(x1,y1)`` is unobstructed.

    Uses Bresenham; returns ``False`` if any cell strictly between the
    endpoints (exclusive of the source cell, inclusive of the target)
    satisfies ``occluder(x, y)``. Pure: no I/O, no mutation.
    """
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    cx, cy = x0, y0
    while True:
        if (cx, cy) != (x0, y0) and occluder(cx, cy):
            return False
        if cx == x1 and cy == y1:
            return True
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy


def _propagate_one_source(
    grid: list[list[RGB]],
    source: LightSource,
    width: int,
    height: int,
    falloff: float,
    t: int,
    occluder,
) -> None:
    """Add ``source``'s light contribution into ``grid`` in place."""
    multiplier = _flicker_multiplier(source, t)
    if multiplier <= 0.0:
        return
    r, g, b = source.colour
    for dy in range(-source.radius, source.radius + 1):
        sy = source.y + dy
        if sy < 0 or sy >= height:
            continue
        row = grid[sy]
        for dx in range(-source.radius, source.radius + 1):
            dist = max(abs(dx), abs(dy))
            if dist > source.radius:
                continue
            sx = source.x + dx
            if sx < 0 or sx >= width:
                continue
            if occluder is not None and not _line_is_clear(
                source.x, source.y, sx, sy, occluder,
            ):
                continue
            intensity = source.intensity * multiplier * (falloff ** dist)
            if intensity <= 0.0:
                continue
            cell = row[sx]
            row[sx] = (
                min(255, cell[0] + int(r * intensity)),
                min(255, cell[1] + int(g * intensity)),
                min(255, cell[2] + int(b * intensity)),
            )


def propagate_light(
    width: int,
    height: int,
    sources: Iterable[LightSource],
    *,
    falloff: float = 0.5,
    t: int = 0,
    occluder: Callable[[int, int], bool] | None = None,
) -> list[list[RGB]]:
    """Return an additive colour grid from ``sources`` at time ``t``.

    Each source colours cells within its Chebyshev ``radius``; intensity
    falls off by ``falloff`` per cell of distance from the source (a
    source of intensity 1.0 at distance 2 with ``falloff=0.5``
    contributes 0.25). Colours from overlapping sources add per channel;
    the finished grid is luma-capped (see :data:`_LIGHT_LUMA_CAP`) so
    any number of overlapping sources stays bright-but-never-white.
    The grid is all-black ``(0, 0, 0)`` when ``sources`` is empty.

    When ``occluder`` is provided, light is blocked by cells for which
    ``occluder(x, y)`` returns ``True`` — a Bresenham line-of-sight
    check stops light from passing through walls. ``None`` (the default)
    means no occlusion (light propagates freely), matching the pre-occlusion
    behaviour. Pure: no I/O, no mutation, deterministic given ``t``.
    """
    grid: list[list[RGB]] = [[(0, 0, 0)] * width for _ in range(height)]
    source_list = list(sources)
    if not source_list or width <= 0 or height <= 0:
        return grid
    for source in source_list:
        if source.radius < 0 or source.intensity <= 0.0:
            continue
        _propagate_one_source(
            grid, source, width, height, falloff, t, occluder,
        )
    _cap_luma(grid)
    return grid


# Perceptual brightness ceiling for a lit cell. Per-channel 255
# clamping alone lets many overlapping sources stack to pure white —
# the washed-out landing (playtest v9). A luma cap with PROPORTIONAL
# scaling keeps overlit cells bright, hue-correct, and never white.
_LIGHT_LUMA_CAP = 200.0


def _luma(rgb: RGB) -> float:
    """Perceptual luma (Rec. 601 weights)."""
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _cap_luma(grid: list[list[RGB]]) -> None:
    """Scale any over-cap cell's channels proportionally to the cap."""
    for row in grid:
        for x, rgb in enumerate(row):
            brightness = _luma(rgb)
            if brightness <= _LIGHT_LUMA_CAP:
                continue
            scale = _LIGHT_LUMA_CAP / brightness
            row[x] = tuple(min(255, int(channel * scale)) for channel in rgb)


def _blend_channel(base: int, light: int) -> int:
    """Add ``light`` to ``base`` and clamp to the 0–255 channel range."""
    return max(0, min(255, base + light))


# Ceiling for a BLENDED tile: even with the light grid luma-capped,
# adding light to an already-bright floor tile clamps channels to 255
# and washes out (playtest v11: a 2x2 square of normal panels still
# read too bright). The output cap scales the blended result back,
# hue-correct. Sits above ordinary bright tile bases so unlit tiles
# are untouched.
_BLEND_LUMA_CAP = 190.0


def _cap_cell(rgb: RGB, cap: float) -> RGB:
    """Proportionally scale ``rgb`` down to ``cap`` luma if above."""
    brightness = _luma(rgb)
    if brightness <= cap:
        return rgb
    scale = cap / brightness
    return tuple(min(255, int(channel * scale)) for channel in rgb)


def blend_toward_light(
    base_fg: RGB, base_bg: RGB, light: RGB,
) -> tuple[RGB, RGB]:
    """Additively blend a tile's colours toward ``light``.

    Each channel of the base ``fg``/``bg`` has the corresponding light
    channel added, clamped, then luma-capped (see
    :data:`_BLEND_LUMA_CAP`) so no amount of light washes a tile to
    white. ``(0, 0, 0)`` light leaves the colours unchanged, so callers
    can safely pass a cell's grid value without a zero-check. Pure: no
    mutation, deterministic.
    """
    if light == (0, 0, 0):
        return base_fg, base_bg
    blended_fg = _cap_cell((
        _blend_channel(base_fg[0], light[0]),
        _blend_channel(base_fg[1], light[1]),
        _blend_channel(base_fg[2], light[2]),
    ), _BLEND_LUMA_CAP)
    blended_bg = _cap_cell((
        _blend_channel(base_bg[0], light[0]),
        _blend_channel(base_bg[1], light[1]),
        _blend_channel(base_bg[2], light[2]),
    ), _BLEND_LUMA_CAP)
    return blended_fg, blended_bg


def collect_light_sources(game_map) -> list[LightSource]:
    """Return static ``LightSource`` values for every lit tile on ``game_map``.

    Scans the map's tiles in one pass; a tile emits light when its
    ``kind`` appears in :data:`STATIC_LIGHT_TABLE
    <spacehack.data.lighting.STATIC_LIGHT_TABLE>`. The light colour is
    the tile's own ``fg``, so a pink neon tile emits pink and a cyan
    neon tile emits cyan from the same scan. Pure: no mutation, no I/O.
    """
    from .data.lighting import flicker_for, light_spec_for_kind

    sources: list[LightSource] = []
    for y, row in enumerate(game_map.tiles):
        for x, tile in enumerate(row):
            spec = light_spec_for_kind(tile.kind)
            if spec is None:
                continue
            sources.append(LightSource(
                x=x, y=y,
                colour=tuple(tile.fg),
                radius=spec.radius,
                intensity=spec.intensity,
                flicker=flicker_for(spec.flicker, x, y),
            ))
    return sources


def has_flickering_sources(sources: Iterable[LightSource]) -> bool:
    """Whether any source in ``sources`` uses a non-steady flicker profile.

    Lets the render path skip the per-frame grid recompute when every
    source is steady (the grid was seeded once at build and never
    changes). Pure: no I/O, no mutation.
    """
    return any(s.flicker != "steady" for s in sources)


def mask_grid_to_visible(game_map, grid) -> None:
    """Zero every fogged cell of ``grid`` in place (dungeon fog gate).

    Light never reveals cells through the fog: sources outside the
    visible area contribute nothing. Maps without a visibility grid
    (cities) are left untouched.
    """
    if game_map.visible is None:
        return
    for y in range(game_map.height):
        row = game_map.visible[y]
        grid_row = grid[y]
        for x in range(game_map.width):
            if not row[x]:
                grid_row[x] = (0, 0, 0)


def recompute_light_grid(
    game_map,
    sources: list[LightSource],
    *,
    t: int,
    occluder: Callable[[int, int], bool] | None = None,
) -> None:
    """Recompute ``game_map.light_grid`` for time ``t`` in place.

    Skips the recompute when ``sources`` is empty or every source is
    steady (the grid from the build pass is already correct). Mutates
    ``game_map.light_grid`` directly; the caller caches ``sources`` so
    the tile scan runs once, not every frame.

    Fog-aware: when the map carries a visibility grid (dungeon fog),
    the recomputed grid is masked to currently-visible cells — animated
    light must never reveal cells through the fog, matching the seeded
    dungeon grid's contract.
    """
    if not sources or not has_flickering_sources(sources):
        return
    game_map.light_grid = propagate_light(
        game_map.width, game_map.height, sources,
        occluder=occluder, t=t,
    )
    mask_grid_to_visible(game_map, game_map.light_grid)


def recompute_frame_light(ctx, game_map) -> None:
    """Advance animated lighting to the current frame clock.

    Shared by the explore renderer and the ground-combat renderer so
    ambient animations (flicker, pulse, alarm strobes) never freeze
    during a fight. Skips maps without cached flickering sources (the
    build-time grid is still correct for steady-only maps).
    """
    sources = getattr(game_map, "light_sources", None)
    if not sources or not has_flickering_sources(sources):
        return
    clock = getattr(getattr(ctx, "context", None), "frame_clock", 0)
    recompute_light_grid(
        game_map, sources, t=clock,
        occluder=lambda x, y: not game_map.tiles[y][x].walkable,
    )


__all__ = [
    "LightSource",
    "FlickerProfile",
    "FLICKER_PROFILES",
    "propagate_light",
    "blend_toward_light",
    "collect_light_sources",
    "has_flickering_sources",
    "recompute_light_grid",
]
