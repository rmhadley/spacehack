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


FLICKER_PROFILES: dict[str, FlickerProfile] = {
    "steady": _steady,
    "buzz": _buzz,
    "flicker": _flicker,
    "pulse": _pulse,
}


def _flicker_multiplier(source: LightSource, t: int) -> float:
    """Return the intensity multiplier for ``source`` at time ``t``.

    Falls back to the steady profile (1.0) if the named profile is
    unknown, so a typo in data never silently darkens a source.
    """
    profile = FLICKER_PROFILES.get(source.flicker, _steady)
    return profile(source, t)


def _propagate_one_source(
    grid: list[list[RGB]],
    source: LightSource,
    width: int,
    height: int,
    falloff: float,
    t: int,
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
) -> list[list[RGB]]:
    """Return an additive colour grid from ``sources`` at time ``t``.

    Each source colours cells within its Chebyshev ``radius``; intensity
    falls off by ``falloff`` per cell of distance from the source (a
    source of intensity 1.0 at distance 2 with ``falloff=0.5``
    contributes 0.25). Colours from overlapping sources add per channel,
    clamped to 255. The grid is all-black ``(0, 0, 0)`` when ``sources``
    is empty.

    Pure: no I/O, no mutation of arguments, deterministic given ``t``.
    """
    grid: list[list[RGB]] = [[(0, 0, 0)] * width for _ in range(height)]
    source_list = list(sources)
    if not source_list or width <= 0 or height <= 0:
        return grid
    for source in source_list:
        if source.radius < 0 or source.intensity <= 0.0:
            continue
        _propagate_one_source(grid, source, width, height, falloff, t)
    return grid


def _blend_channel(base: int, light: int) -> int:
    """Add ``light`` to ``base`` and clamp to the 0–255 channel range."""
    return max(0, min(255, base + light))


def blend_toward_light(
    base_fg: RGB, base_bg: RGB, light: RGB,
) -> tuple[RGB, RGB]:
    """Additively blend a tile's colours toward ``light``.

    Each channel of the base ``fg``/``bg`` has the corresponding light
    channel added and clamped. ``(0, 0, 0)`` light leaves the colours
    unchanged, so callers can safely pass a cell's grid value without a
    zero-check. Pure: no mutation, deterministic.
    """
    if light == (0, 0, 0):
        return base_fg, base_bg
    return (
        (
            _blend_channel(base_fg[0], light[0]),
            _blend_channel(base_fg[1], light[1]),
            _blend_channel(base_fg[2], light[2]),
        ),
        (
            _blend_channel(base_bg[0], light[0]),
            _blend_channel(base_bg[1], light[1]),
            _blend_channel(base_bg[2], light[2]),
        ),
    )


def collect_light_sources(game_map) -> list[LightSource]:
    """Return static ``LightSource`` values for every lit tile on ``game_map``.

    Scans the map's tiles in one pass; a tile emits light when its
    ``kind`` appears in :data:`STATIC_LIGHT_TABLE
    <spacehack.data.lighting.STATIC_LIGHT_TABLE>`. The light colour is
    the tile's own ``fg``, so a pink neon tile emits pink and a cyan
    neon tile emits cyan from the same scan. Pure: no mutation, no I/O.
    """
    from .data.lighting import light_spec_for_kind

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
            ))
    return sources


__all__ = [
    "LightSource",
    "FlickerProfile",
    "FLICKER_PROFILES",
    "propagate_light",
    "blend_toward_light",
    "collect_light_sources",
]
