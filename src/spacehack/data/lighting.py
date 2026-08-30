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
    can't encode.
    """

    radius: int
    intensity: float = 1.0


# Maps a tile ``kind`` to its light emission spec. To make a new tile
# kind emit light, add a row here — no code changes elsewhere.
STATIC_LIGHT_TABLE: dict[str, LightSourceSpec] = {
    "neon": LightSourceSpec(radius=4, intensity=0.9),
    "beacon": LightSourceSpec(radius=6, intensity=1.0),
}


def light_spec_for_kind(kind: str) -> LightSourceSpec | None:
    """Return the light spec for ``kind``, or ``None`` if it doesn't emit."""
    return STATIC_LIGHT_TABLE.get(kind)


__all__ = ["LightSourceSpec", "STATIC_LIGHT_TABLE", "light_spec_for_kind"]
