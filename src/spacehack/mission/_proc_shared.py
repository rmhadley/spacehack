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
    """Return the real NPC spec IDs present on ``planet_id``.

    Building ``npc_id`` slots are resolved through the planet's
    ``npc_overrides`` and the global catalog (mirroring
    ``_resolve_npc_entity``), so the returned ids are always ids a
    live NPC entity carries — a slot key like
    ``"archive_research_officer"`` maps to the actual spec id
    ``"research_officer"``. Used to pick delivery/smuggle target
    NPCs for procedural missions; unresolvable slots are skipped.
    Returns empty list if the planet is unknown or has no NPC buildings.
    """
    try:
        from ..data.planets import (
            find_planet_spec as _fps,
            _resolve_npc_entity as _rne,
        )
        spec = _fps(planet_id)
    except KeyError:
        return []
    _ids: list[str] = []
    for _b in spec.buildings:
        if not _b.npc_id:
            continue
        _ent = _rne(_b.npc_id, spec)
        if _ent is not None and _ent.npc_id not in _ids:
            _ids.append(_ent.npc_id)
    return _ids


def _planet_dest_candidates(
    _sys, origin_planet_id: str, hops: int, _seen: set[str],
) -> list[tuple[str, str, int]]:
    """Planet bodies in ``_sys`` usable as delivery destinations."""
    from ..data.planets import has_landable_port

    result: list[tuple[str, str, int]] = []
    for _p in _sys.planets:
        if getattr(_p, 'sun', False) or _p.id == origin_planet_id:
            continue
        if not has_landable_port(_p.id) or not _planet_npc_ids(_p.id):
            continue
        _seen.add(_p.id)
        result.append((_p.id, _sys.id, hops))
    return result


def _station_dest_candidates(
    _sys, origin_planet_id: str, hops: int, _seen: set[int],
) -> list[tuple[str, str, int]]:
    """Station city_planet_ids in ``_sys`` usable as destinations.

    ``_seen`` holds planet ids already collected, so a station whose
    city_planet_id is ALSO a planet body (or is shared by multiple
    stations, e.g. the two Luyten blockade stations) is only counted
    once in the rng.choice pool.
    """
    from ..data.planets import has_landable_port

    result: list[tuple[str, str, int]] = []
    for _st in getattr(_sys, 'stations', ()) or ():
        _cid = _st.city_planet_id
        if not _cid or _cid == origin_planet_id or _cid in _seen:
            continue
        if not has_landable_port(_cid) or not _planet_npc_ids(_cid):
            continue
        _seen.add(_cid)
        result.append((_cid, _sys.id, hops))
    return result


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
    from ..data import solar_systems as _sys_mod

    try:
        _sys = _sys_mod.find_solar_system(system_id)
    except KeyError:
        return []
    _seen: set[int] = set()
    return (
        _planet_dest_candidates(_sys, origin_planet_id, hops, _seen)
        + _station_dest_candidates(_sys, origin_planet_id, hops, _seen)
    )


def hop_candidates(
    origin_planet_id: str,
    tier: int,
    *,
    hop_ranges: dict,
    default_range: tuple[int, int] = (1, 10),
) -> list[tuple[str, int]] | None:
    """(system_id, hops) candidates within the tier's hop range.

    ``None`` = unknown origin planet. The origin system is excluded
    (system-level work always means leaving home).
    """
    from ..data.solar_systems import reachable_system_ids
    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None
    reachable = reachable_system_ids(origin_system_id, max_hops=10)
    min_hops, max_hops = hop_ranges.get(tier, default_range)
    return [
        (sid, hops) for sid, hops in reachable.items()
        if min_hops <= hops <= max_hops and sid != origin_system_id
    ]


def planet_destinations(
    origin_planet_id: str,
    tier: int,
    *,
    hop_ranges: dict,
    default_range: tuple[int, int] = (0, 10),
) -> list[tuple[str, str, int]] | None:
    """(planet_id, system_id, hops) candidates for delivery-style work.

    ``None`` = unknown origin. Same-system candidates are included
    when the tier's range reaches hop 0 (order preserved: origin
    system first, then reachable systems — callers rng.choice over
    the list, so order is behavior).
    """
    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None
    from ..data.solar_systems import reachable_system_ids
    reachable = reachable_system_ids(origin_system_id, max_hops=10)
    min_hops, max_hops = hop_ranges.get(tier, default_range)
    out: list[tuple[str, str, int]] = []
    if min_hops == 0:
        out.extend(
            _dest_candidates_in_system(origin_system_id, origin_planet_id, 0)
        )
    for sys_id, hops in reachable.items():
        if min_hops <= hops <= max_hops:
            out.extend(
                _dest_candidates_in_system(sys_id, origin_planet_id, hops)
            )
    return out


def display_name_of(lookup, key: str) -> str:
    """A catalog display name with the raw key as fallback."""
    try:
        return lookup(key).name
    except KeyError:
        return key
