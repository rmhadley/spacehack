"""Ground enemy band resolver (doc 48 phase 4, SETTLED 35).

One vocabulary — a ground site's BAND (1-4) — sizes every
``NpcCharSpec`` spawn along the three axes: stats (band →
effective-level budget split by the spec's archetype weights), gear
(weapon FAMILIES rolled inside the band's tier window), and quality
(equip- and drop-time ladders step with band). Pure functions only:
callers pass ``rng``; nothing here mutates or draws.

Band 0 is "no band": base-10 stats, band-1 quality — exactly today's
numbers. Bystanders author all-zero weights so any stamp leaves them
scale-invariant (the SETTLED 14 exemption, as data); un-stamped
legacy saves derive their band from the site via :func:`entity_band`.
"""

from __future__ import annotations

from dataclasses import dataclass

# The player system the bands mirror (SETTLED 15): base 10, five
# points per level, stats cap at 100.
STAT_BASE: int = 10
STAT_CAP: int = 100

# Band → effective player level (SETTLED 35): budgets read
# +10 / +45 / +85 / +145 points over base 10 across the six stats.
BAND_LEVELS: tuple[int, ...] = (3, 10, 18, 30)

# Top-two tier windows, weighted up (SETTLED 35 verbatim): band 2
# rolls t1 70% / t2 30%; bands 3-4 roll 30% low / 70% high.
BAND_WINDOWS: tuple[tuple[tuple[int, float], ...], ...] = (
    ((1, 1.0),),
    ((1, 0.7), (2, 0.3)),
    ((2, 0.3), (3, 0.7)),
    ((3, 0.3), (4, 0.7)),
)

# Equip-time and drop-time quality ladders by band (SETTLED 35).
# Band 1 equals KILL_QUALITY_RATES — un-stamped spawns roll today's
# odds exactly.
BAND_QUALITY_RATES: tuple[tuple[int, int, int], ...] = (
    (5, 11, 25), (7, 14, 30), (8, 17, 35), (10, 20, 40),
)

# stat_weights positional order — reflexes, strength, stamina, then
# the three space skills (SETTLED 19: every NPC carries all six) —
# IS GroundBandStats's field order.


@dataclass(frozen=True)
class GroundBandStats:
    """One enemy's derived six-block at a band."""

    reflexes: int = STAT_BASE
    strength: int = STAT_BASE
    stamina: int = STAT_BASE
    gunnery: int = STAT_BASE
    piloting: int = STAT_BASE
    engineering: int = STAT_BASE


def clamp_band(band: int) -> int:
    """Clamp into ``[0, 4]`` — 0 stays (no band)."""
    return max(0, min(4, int(band)))


def band_budget(band: int) -> int:
    """Total stat points the band's effective level grants: 5×(L−1)."""
    band = clamp_band(band)
    return 0 if band == 0 else 5 * (BAND_LEVELS[band - 1] - 1)


def derive_stats(spec, band: int) -> GroundBandStats:
    """Base-10 six-block plus the band budget split by the spec's
    ``stat_weights``.

    Largest-remainder allocation (fractional ties to the earlier
    stat) over the WEIGHTED stats only, so the whole budget lands;
    zero-weight stats never receive remainder points. An all-zero row
    (the band-exempt bystander) reads flat base at every band. Each
    stat caps at 100.
    """
    budget = band_budget(band)
    if not any(spec.stat_weights):
        return GroundBandStats()
    raw = [budget * weight for weight in spec.stat_weights]
    floors = [int(value) for value in raw]
    candidates = sorted(
        (i for i, weight in enumerate(spec.stat_weights) if weight > 0),
        key=lambda i: (-(raw[i] - floors[i]), i),
    )
    for i in range(min(budget - sum(floors), len(candidates))):
        floors[candidates[i]] += 1
    return GroundBandStats(*(
        min(STAT_CAP, STAT_BASE + floors[i]) for i in range(len(floors))
    ))


def planet_band(mission_tier: int) -> int:
    """A planet's mission tier as a band, clamped into [1, 4]."""
    return max(1, min(4, int(mission_tier)))


def quality_rates(band: int) -> tuple[int, int, int]:
    """The band's equip/drop quality ladder (band 0 reads band 1)."""
    return BAND_QUALITY_RATES[max(1, clamp_band(band)) - 1]


def _window_tier(window, rng) -> int:
    """Roll one tier from a weighted window; the tail catches drift."""
    roll = rng.random()
    for tier, weight in window:
        roll -= weight
        if roll < 0:
            return tier
    return window[-1][0]


def _snap_tier(tiers, tier: int) -> int:
    """Nearest populated family tier, preferring at-or-above (toward
    the window's top) — explosives ladder t3-t4, so a band-3 t2 roll
    lands the grenade launcher, never an empty tier."""
    populated = set(tiers)
    for candidate in (*range(tier, 5), *range(tier - 1, 0, -1)):
        if candidate in populated:
            return candidate
    return tier


def roll_weapon(spec, band: int, rng) -> str:
    """One weapon id from the spec's families at the band's window.

    Family first (uniform over ``weapon_families``), then the tier
    window. ``pin_window_top`` (the sniper) takes the window's ceiling
    tier outright — the railgun at band 4 is the precision payoff.
    Rows without families keep their fixed ``weapons`` and never call
    this; an unpopulated family is a data error and raises.
    """
    from .data.ground_weapons import family_tiers

    if not spec.weapon_families:
        return ""
    family = rng.choice(spec.weapon_families)
    window = BAND_WINDOWS[max(1, clamp_band(band)) - 1]
    if spec.pin_window_top:
        tier = window[-1][0]
    else:
        tier = _window_tier(window, rng)
    tiers = family_tiers(family)
    return rng.choice(tiers[_snap_tier(tiers, tier)])


def context_band(game_map) -> int:
    """Derive the site's band from the map (un-stamped legacy saves).

    Dig floors re-derive their climbed band from the cache key through
    the dig module's own formula (single-sourced); every other map
    reads band 1 — today's numbers. New spawns always arrive stamped,
    so this only bridges one save transition.
    """
    key = getattr(game_map, "interior_cache_key", "") or ""
    if not key.startswith("dig:"):
        return 1
    from .digs import _dig_tier, parse_cache_key

    parsed = parse_cache_key(key)
    if parsed is None:
        return 1
    planet_id, _site_id, floor = parsed
    from .data.planets import find_planet_spec

    try:
        return _dig_tier(find_planet_spec(planet_id), floor)
    except KeyError:
        return 1


def entity_band(entity, game_map=None) -> int:
    """The entity's stamped band; a 0 stamp derives from the site."""
    return clamp_band(getattr(entity, "spawn_band", 0)) or context_band(
        game_map,
    )
