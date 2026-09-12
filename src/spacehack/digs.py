"""Dig sites (doc 42 phase 4): procedural dungeons on every planet.

A reveal derives the site pure from INIT_SEED + the reveal ordinal
(SETTLED 7/28): the planet among ALL planets, a two-part name from
the planet's pools, depth within the planet's bounds. Site records
are ``{id, planet, name}`` in reveal order on
``ctx.discovered_sites``; floors cache under
``dig:<planet>:<id>:<floor>`` and that cache key is the single
identity source for anything standing on a dig floor — no dig
attributes are stored on maps.
"""

from __future__ import annotations

from . import engine, rumor
from .data.digs import DEFAULT_PREFIXES, DEFAULT_SUFFIXES
from .data.planets import PlanetSpec, list_planet_specs
from .text import get as _text_get

CACHE_PREFIX = "dig:"

# The template keys this domain resolves (validation-only — the prose
# lives in data/text/09_digs.json and is a DRAFT pending the playtest
# checkpoint's prose read-through; the orphan-key test unions this set
# with the catalogs).
TEXT_KEYS: frozenset[str] = frozenset({
    "dig.reveal.title",
    "dig.reveal.text",
    "dig.pointer_line",
})


def cache_key(planet_id: str, site_id: str, floor: int) -> str:
    """The interiors key for one site floor (persists through the
    existing ``city:``-only exclusion — no save plumbing of its own)."""
    return f"{CACHE_PREFIX}{planet_id}:{site_id}:{floor}"


def parse_cache_key(key: str) -> tuple[str, str, int] | None:
    """``dig:<planet>:<site>:<floor>`` → (planet, site, floor); None
    for any other interiors key."""
    if not key.startswith(CACHE_PREFIX):
        return None
    parts = key[len(CACHE_PREFIX):].split(":")
    if len(parts) != 3:
        return None
    planet, site, floor = parts
    try:
        return planet, site, int(floor)
    except ValueError:
        return None


def site_depth(spec: PlanetSpec, site_id: str) -> int:
    """The site's floor count: seeded within the spec's bounds
    (SETTLED 38) — derived on read, never stored. A max below the min
    collapses to the min."""
    lo = max(1, spec.dig_min_floors)
    hi = max(lo, spec.dig_max_floors)
    return engine.seeded_rng(engine.INIT_SEED, "dig_depth", site_id).randint(lo, hi)


def site_name(spec: PlanetSpec, roll: int, taken: set[str] | None = None) -> str:
    """Two-part generated name from the spec's pools; the data/digs
    defaults when the spec authors none (SETTLED 33). Names in
    ``taken`` are skipped (seeded walk, keyed by roll); a fully
    exhausted pool numbers instead of looping."""
    prefixes = spec.dig_prefixes or DEFAULT_PREFIXES
    suffixes = spec.dig_suffixes or DEFAULT_SUFFIXES
    combos = [f"{p} {s}" for p in prefixes for s in suffixes]
    rng = engine.seeded_rng(engine.INIT_SEED, "dig_name", spec.id, roll)
    order = combos[:]
    rng.shuffle(order)
    taken = taken or set()
    for name in order:
        if name not in taken:
            return name
    return f"{combos[roll % len(combos)]} {len(taken) + 1}"


def reveal_site(ctx) -> dict:
    """Derive and record the next site — the reveal idiom (SETTLED
    34): the caller consumed the find; this records and reads out.
    Returns the new site record. Names never repeat within a planet
    (the menu renders one row per site)."""
    roll = len(ctx.discovered_sites) + 1
    spec = engine.seeded_rng(engine.INIT_SEED, "dig_reveal", roll).choice(
        sorted(list_planet_specs(), key=lambda s: s.id),
    )
    taken = {
        site["name"]
        for site in ctx.discovered_sites
        if site["planet"] == spec.id
    }
    site = {
        "id": f"s{roll}",
        "planet": spec.id,
        "name": site_name(spec, roll, taken),
    }
    ctx.discovered_sites.append(site)
    rumor.present_hearing(
        ctx,
        _text_get("dig.reveal.title", ""),
        _text_get("dig.reveal.text", "").format(
            name=site["name"], planet=spec.name,
        ),
    )
    return site
