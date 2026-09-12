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

from . import engine, rumor, world
from .data.digs import (
    DEFAULT_PREFIXES,
    DEFAULT_SUFFIXES,
    LANDMARK_CHANCE,
    LANDMARK_VARIANTS,
    TIER_POOLS,
)
from .data.planets import PlanetSpec, find_planet_spec, list_planet_specs
from .dungeon_params import DungeonParams
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
    "dig.stairs_down_log",
    "dig.stairs_up_log",
    "dig.enter_log",
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


# --- generation (SETTLED 26/38): the spec feeds the generator -------------


def derive_dig_params(spec: PlanetSpec) -> DungeonParams:
    """One config per planet, derived from theme + mission tier
    (SETTLED 26); ``spec.dig_params`` overrides wholesale. Future
    planets derive automatically — nothing per-site, nothing
    hardcoded."""
    if spec.dig_params is not None:
        return spec.dig_params
    pool, density = TIER_POOLS[max(1, min(3, spec.mission_tier))]
    tile_wall, tile_floor = _dig_tiles(spec.theme)
    return DungeonParams(
        width=64,
        height=48,
        min_room_size=4,
        max_room_size=12,
        room_fill_pct=0.6,
        tile_wall=tile_wall,
        tile_floor=tile_floor,
        monster_pool=pool,
        monster_density=density,
    )


def _dig_tiles(theme) -> tuple[world.Tile, world.Tile]:
    """The planet's palette, re-kinded for the dig: its ground as the
    floor, its solid terrain as the bedrock. No theme → the default
    dungeon tiles."""
    if theme is None:
        return world.DUNGEON_WALL, world.DUNGEON_FLOOR
    wall_src, floor_src = theme.tree, theme.floor
    tile_wall = world.Tile(
        kind="dungeon_wall", char="#", walkable=False,
        fg=wall_src.fg, bg=_dim(wall_src.bg, 0.55),
    )
    tile_floor = world.Tile(
        kind="dungeon_floor", char=".", walkable=True,
        fg=floor_src.fg, bg=_dim(floor_src.bg, 0.8),
    )
    return tile_wall, tile_floor


def _dim(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(int(c * factor) for c in color)


def generate_dig(ctx, site: dict, floor: int) -> tuple[world.GameMap, world.Position]:
    """One floor of a dig site: the BSP pass + the floor's connections
    + the landmark sprinkle. Floor 1 keeps the generator's EXIT (the
    way out); deeper floors swap it for STAIRS_UP; every non-bottom
    floor gains a farthest STAIRS_DOWN. The caller caches the result
    under ``dig:<planet>:<id>:<floor>`` — generation happens once per
    save (SETTLED 29)."""
    from .dungeon import generate_dungeon, populate_dungeon

    spec = find_planet_spec(site["planet"])
    params = derive_dig_params(spec)
    game_map, spawn = generate_dungeon(params)
    game_map.interior_cache_key = cache_key(site["planet"], site["id"], floor)
    game_map.location_name = site["name"]
    game_map.entry_spawn = spawn
    if floor > 1:
        # The generic generator's EXIT becomes the up-connection (the
        # extension idiom).
        game_map.tiles[spawn.y][spawn.x] = world.STAIRS_UP
    _maybe_stamp_landmark(game_map, site, floor, spawn)
    populate_dungeon(game_map, params, spawn, tier=_dig_tier(spec, floor))
    _scatter_dig_loot(game_map, spec, floor)
    depth = site_depth(spec, site["id"])
    if floor < depth:
        _place_stairs_down(game_map, spawn)
    return game_map, spawn


def _dig_tier(spec: PlanetSpec, floor: int) -> int:
    """Difficulty climbs with depth (SETTLED 38): tier + floor - 1,
    inside populate's 1-3 band."""
    return max(1, min(3, spec.mission_tier + floor - 1))


def _place_stairs_down(game_map: world.GameMap, spawn: world.Position) -> None:
    """The deeper connection at the farthest free cell (the extension
    idiom), stamped after population so no enemy stands on it."""
    from .dungeon_extensions import _farthest_free_cell

    down = _farthest_free_cell(game_map, spawn)
    if down is not None:
        game_map.tiles[down.y][down.x] = world.STAIRS_DOWN


def _maybe_stamp_landmark(
    game_map: world.GameMap, site: dict, floor: int, spawn: world.Position,
) -> None:
    """The authored-room sprinkle (SETTLED 25/32): seeded per
    site+floor, a minority of floors; a layout that does not fit or
    route here is skipped, leaving the plain dig."""
    from . import landmark as landmark_module

    roll = engine.seeded_rng(engine.INIT_SEED, "dig_landmark", site["id"], floor)
    if roll.random() >= LANDMARK_CHANCE:
        return
    layout_id = landmark_module.choose_weighted_variant(
        LANDMARK_VARIANTS, roll.random(),
    )
    try:
        asset = landmark_module.load_landmark(layout_id)
        stamp = landmark_module.stamp_landmark(game_map, asset, spawn)
    except ValueError:
        return
    landmark_module.union_footprint(game_map, stamp.footprint)


def find_site(ctx, planet_id: str, site_id: str) -> dict:
    """The site record for a cache key; ValueError when unknown."""
    for site in ctx.discovered_sites:
        if site["id"] == site_id and site["planet"] == planet_id:
            return site
    raise ValueError(f"unknown dig site {planet_id}:{site_id}")


def get_or_generate_floor(ctx, site: dict, floor: int) -> tuple[world.GameMap, world.Position]:
    """Cached-or-fresh: every floor persists under its key (SETTLED
    29) — cleared stays cleared, looted stays looted. A cache hit
    scrubs the stale player entity (the shared re-entry idiom)."""
    key = cache_key(site["planet"], site["id"], floor)
    cached = ctx.interiors.get(key)
    if cached is not None:
        from .game_flow import _prep_cached_dungeon

        return cached, _prep_cached_dungeon(cached)
    game_map, spawn = generate_dig(ctx, site, floor)
    ctx.interiors[key] = game_map
    return game_map, spawn


def is_dig_floor(game_map: world.GameMap) -> bool:
    """Whether this map is a dig-site floor (its persisted cache key
    carries the dig: prefix — the single identity source)."""
    return parse_cache_key(getattr(game_map, "interior_cache_key", "")) is not None


def transition(state, direction: int) -> tuple[world.GameMap, world.Entity]:
    """One floor up/down (the extension idiom: arrive at the opposite
    stair). Returns (map, player) for the caller to install; ValueError
    when there is no floor that way or this is not a dig floor."""
    parsed = parse_cache_key(getattr(state.game_map, "interior_cache_key", ""))
    if parsed is None:
        raise ValueError("not a dig floor")
    planet_id, site_id, floor = parsed
    target = floor + direction
    if target < 1:
        raise ValueError("the dig entrance is the top floor")
    site = find_site(state.ctx, planet_id, site_id)
    spec = find_planet_spec(planet_id)
    if target > site_depth(spec, site_id):
        raise ValueError("no floor below")
    game_map, _ = get_or_generate_floor(state.ctx, site, target)
    arrival = _arrival_position(game_map, direction)
    if arrival is None:
        raise ValueError("dig floor connection is unavailable")
    _install_arrival(state, game_map, arrival)
    return game_map, state.ctx.player


def _arrival_position(game_map: world.GameMap, direction: int) -> world.Position | None:
    """The opposite stair of the move: down-moves arrive at the deeper
    floor's STAIRS_UP, up-moves at the floor's STAIRS_DOWN."""
    from .dungeon_extensions import _find_stair_position

    kind = "stairs_up" if direction > 0 else "stairs_down"
    return _find_stair_position(game_map, kind)


def stairs_log_line(direction: int) -> str:
    """The stair-move log line (data/text single-source)."""
    key = "dig.stairs_down_log" if direction > 0 else "dig.stairs_up_log"
    return _text_get(key, "")


def site_loot_rows(spec: PlanetSpec, floor: int, count: int, rng) -> list[tuple[str, int]]:
    """One ``(good_id, quantity)`` row per cache: the planet's
    produces goods, tier+floor-scaled through the pluggable loot spec
    (SETTLED 26/35). Pure given its inputs."""
    from .data.digs import DIG_LOOT_SPEC

    tier = max(1, min(3, spec.mission_tier))
    quantity = (
        DIG_LOOT_SPEC.base_qty
        + DIG_LOOT_SPEC.qty_per_tier * (tier - 1)
        + DIG_LOOT_SPEC.qty_per_floor * (floor - 1)
    )
    return [(rng.choice(spec.produces)[0], quantity) for _ in range(count)]


def _scatter_dig_loot(game_map: world.GameMap, spec: PlanetSpec, floor: int) -> None:
    """The placeholder cache scatter (SETTLED 30/35) — the loot rows
    placed at free cells after population."""
    from .data.digs import DIG_LOOT_SPEC

    if not spec.produces:
        return
    count = engine.RNG.randint(*DIG_LOOT_SPEC.cache_count)
    for good_id, quantity in site_loot_rows(spec, floor, count, engine.RNG):
        pos = _free_floor_cell(
            game_map, avoid_kinds=("exit", "stairs_up", "stairs_down"),
        )
        if pos is None:
            return
        game_map.entities.append(world.Entity(
            char="%", fg=(180, 220, 140), pos=pos, name="Cache",
            width=1, height=1,
            loot_data={"good_id": good_id, "quantity": quantity},
        ))


def enter_dig_site(state, planet_obj, site_id: str) -> str:
    """Enter floor 1 of a discovered site from its planet-menu row —
    the surface-entry idiom: return pair, dungeon mode, full ground
    hp; the site's name is the location. Cached floors keep every
    previous visit's state (SETTLED 29)."""
    site = find_site(state.ctx, planet_obj.id, site_id)
    game_map, spawn = get_or_generate_floor(state.ctx, site, 1)
    from .game_interactions import _adopt_dungeon_entry, _install_dungeon_player

    player = _install_dungeon_player(game_map, spawn)
    _adopt_dungeon_entry(state, game_map, player)
    state.log.add(_text_get("dig.enter_log", "").format(name=site["name"]))
    return "CONTINUE"


# --- the discovery doors (SETTLED 27/36): three RNG-rare rolls -----------


def _door_hit(key: str) -> bool:
    """The SETTLED 36 flat roll: a 1-in-N draw from the rates table."""
    from .data.digs import DOOR_RATES

    return engine.RNG.randint(1, DOOR_RATES[key]) == 1


def maybe_spawn_ground_pad(ctx, game_map, pos, enemy_id: str) -> bool:
    """Door 1 — the humanoid pad: a 1-in-N roll on combatant ground
    kills drops a site pad beside the loot. Never guaranteed."""
    from .data.digs import HUMANOID_PAD_DROPPERS
    from .loot import spawn_pad_entity

    # ctx is unread but pinned for signature symmetry with
    # loot.maybe_spawn_pad — the audit's one pad shape.
    if enemy_id not in HUMANOID_PAD_DROPPERS:
        return False
    if not _door_hit("humanoid_pad"):
        return False
    return spawn_pad_entity(game_map, pos, {"reveals_site": True})


def maybe_spawn_wreck_pad(game_map) -> bool:
    """Door 2 — the derelict pad: a 1-in-N roll when a generic wreck
    interior generates; the wreck despawns after boarding, so the
    interior is one-shot."""
    from .loot import spawn_pad_entity

    if not _door_hit("derelict_pad"):
        return False
    pos = _free_floor_cell(game_map)
    if pos is None:
        return False
    return spawn_pad_entity(game_map, pos, {"reveals_site": True})


def maybe_reveal_from_terminal(ctx) -> bool:
    """Door 3 — the boarded ship's computer: a 1-in-N roll on the
    first power-restore; a hit plays the full reveal."""
    if not _door_hit("terminal"):
        return False
    reveal_site(ctx)
    return True


def _free_floor_cell(
    game_map: world.GameMap,
    avoid_kinds: tuple[str, ...] = (),
) -> world.Position | None:
    """A random walkable, unoccupied cell — a scattered pad's landing
    spot; None when the map has nowhere to put one. ``avoid_kinds``
    reserves transition tiles (a cache glyph would hide the stair)."""
    occupied = {(e.pos.x, e.pos.y) for e in game_map.entities}
    candidates = [
        (x, y)
        for y in range(game_map.height)
        for x in range(game_map.width)
        if game_map.tiles[y][x].walkable
        and (x, y) not in occupied
        and game_map.tiles[y][x].kind not in avoid_kinds
    ]
    if not candidates:
        return None
    return world.Position(*engine.RNG.choice(candidates))


def _install_arrival(state, game_map: world.GameMap, spawn: world.Position) -> None:
    """Scrub stale players off both maps, then the shared entry
    invariants — fog, a fresh transient player, the arrival reveal."""
    from .dungeon_extensions import _remove_player
    from .game_interactions import _install_dungeon_player

    _remove_player(state.game_map)
    _remove_player(game_map)
    _player = _install_dungeon_player(game_map, spawn)
    state.ctx.game_map = game_map
    state.ctx.player = _player
