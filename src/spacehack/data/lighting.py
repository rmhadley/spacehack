"""Static light-source data for the dynamic lighting system.

Light sources are discovered from existing tile ``kind`` values; this
module holds the table that maps a kind to its light radius and default
intensity. The light *colour* comes from the tile's own ``fg`` (so a
pink neon tile emits pink light, a cyan neon tile emits cyan) — no new
fields on :class:`~spacehack.world.Tile`.

This is a data-first catalog (frozen dataclass + lookup table), matching
the project's content convention: extend the table here, not in render
or builder modules.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LightSourceSpec:
    """Light emission parameters for a tile ``kind``.

    The colour is read from the tile's ``fg`` at collect time; this spec
    only carries the geometric/intensity parameters that the kind alone
    can't encode. ``flicker`` names a profile in
    :data:`spacehack.lighting.FLICKER_PROFILES`; a spec whose flicker is
    ``"mixed"`` gets a position-based profile assignment so adjacent
    signs flicker out of phase without per-instance data.
    """

    radius: int
    intensity: float = 1.0
    flicker: str = "steady"


# Maps a tile ``kind`` to its light emission spec. To make a new tile
# kind emit light, add a row here — no code changes elsewhere.
STATIC_LIGHT_TABLE: dict[str, LightSourceSpec] = {
    "neon": LightSourceSpec(radius=4, intensity=0.9, flicker="mixed"),
    "beacon": LightSourceSpec(radius=6, intensity=1.0),
    "glow_fungus": LightSourceSpec(radius=3, intensity=0.7, flicker="pulse"),
    "city_water": LightSourceSpec(radius=2, intensity=0.4, flicker="pulse"),
}


# Position-based flicker assignment for the "mixed" profile key.
# A third of signs are steady, a third buzz, a third flicker — so the
# neon canyon reads as a mix of solid and faulty lights. Deterministic
# by position so it survives save/load (no per-instance state needed).
_MIXED_PROFILES = ("steady", "buzz", "flicker")


def flicker_for(spec_flicker: str, x: int, y: int) -> str:
    """Resolve a spec's flicker key to a concrete profile for ``(x, y)``.

    ``"mixed"`` is distributed across positions so adjacent signs get
    different profiles; any other key (``"steady"``, ``"buzz"``, …) is
    returned as-is so a spec can pin a single profile if desired.
    """
    if spec_flicker != "mixed":
        return spec_flicker
    return _MIXED_PROFILES[hash((x, y)) % len(_MIXED_PROFILES)]


def light_spec_for_kind(kind: str) -> LightSourceSpec | None:
    """Return the light spec for ``kind``, or ``None`` if it doesn't emit."""
    return STATIC_LIGHT_TABLE.get(kind)


__all__ = [
    "LightSourceSpec",
    "STATIC_LIGHT_TABLE",
    "light_spec_for_kind",
    "flicker_for",
]
