"""Shared procedural mission lookup and tier infrastructure."""
from __future__ import annotations

import random

_PLANET_SYSTEM_CACHE: dict[str, str] | None = None


def _planet_to_system() -> dict[str, str]:
    """Return ``{planet_id: system_id}`` for every planet (and station
    city_planet_id) across all registered solar systems.

    Lazy-built and cached so procedural generation doesn't re-scan the
    system registry on every call.
    """
    global _PLANET_SYSTEM_CACHE
    if _PLANET_SYSTEM_CACHE is not None:
        return _PLANET_SYSTEM_CACHE

    from ..data import solar_systems as _sys_mod
    mapping: dict[str, str] = {}
    for _sys in _sys_mod.list_solar_systems():
        for _p in _sys.planets:
            if not getattr(_p, 'sun', False):
                mapping[_p.id] = _sys.id
        # Stations with city_planet_id share the same system.
        for _st in getattr(_sys, 'stations', ()) or ():
            if _st.city_planet_id:
                mapping[_st.city_planet_id] = _sys.id
    _PLANET_SYSTEM_CACHE = mapping
    return mapping


def _roll_tier(max_tier: int, rng: random.Random) -> int:
    """Weighted tier roll: min-of-two gives a natural rarity curve.

    Shared by both delivery and bounty procedural generators.
    Returns 1..max_tier with lower tiers more common.
    """
    _max = max(1, max_tier)
    return min(rng.randint(1, _max), rng.randint(1, _max))


def _planet_npc_ids(planet_id: str) -> list[str]:
    """Return the NPC IDs present on ``planet_id`` (non-empty npc_ids
    from the planet's building specs).

    Used to pick a delivery target NPC for procedural missions.
    Returns empty list if the planet is unknown or has no NPC buildings.
    """
    try:
        from ..data.planets import find_planet_spec as _fps
        spec = _fps(planet_id)
    except KeyError:
        return []
    return [b.npc_id for b in spec.buildings if b.npc_id]


def _dest_candidates_in_system(
    system_id: str,
    origin_planet_id: str,
    hops: int,
) -> list[tuple[str, str, int]]:
    """Return ``[(planet_id, system_id, hops), ...]`` for every
    landable planet (or station city_planet_id) in ``system_id``
    that is not ``origin_planet_id`` and has at least one NPC.

    Handles both same-system and remote-system destination lookup
    with a single code path.
    """
    from ..data.planets import has_landable_port
    from ..data import solar_systems as _sys_mod

    try:
        _sys = _sys_mod.find_solar_system(system_id)
    except KeyError:
        return []

    result: list[tuple[str, str, int]] = []
    # Track planet ids already added so a station's city_planet_id that
    # is ALSO listed as a planet body (or shared by multiple stations,
    # e.g. the two Luyten blockade stations) is only counted once.
    # Without this, such landmarks get double weight in the rng.choice
    # pool and show up ~2x more often than any other destination.
    _seen: set[str] = set()
    # Planets.
    for _p in _sys.planets:
        if getattr(_p, 'sun', False):
            continue
        if _p.id == origin_planet_id:
            continue
        if not has_landable_port(_p.id):
            continue
        if not _planet_npc_ids(_p.id):
            continue
        _seen.add(_p.id)
        result.append((_p.id, system_id, hops))
    # Stations (city_planet_id points to the planet spec).
    for _st in getattr(_sys, 'stations', ()) or ():
        if _st.city_planet_id == origin_planet_id:
            continue
        if not _st.city_planet_id:
            continue
        if _st.city_planet_id in _seen:
            continue
        if not has_landable_port(_st.city_planet_id):
            continue
        if not _planet_npc_ids(_st.city_planet_id):
            continue
        _seen.add(_st.city_planet_id)
        result.append((_st.city_planet_id, system_id, hops))
    return result

