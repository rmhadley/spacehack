"""Dig-site derivations (doc 42 phase 4): reveal determinism, name
pools, depth bounds, and the cache-key contract."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import digs, engine, world, landmark
from src.spacehack.data.digs import DEFAULT_PREFIXES, DEFAULT_SUFFIXES
from src.spacehack.data.planets import list_planet_specs, find_planet_spec


@pytest.fixture(autouse=True)
def _pinned_seed(monkeypatch):
    monkeypatch.setattr(engine, "INIT_SEED", 424242)


def _ctx(monkeypatch, sites=None):
    """A ctx with the readout captured instead of presented."""
    seen = []
    monkeypatch.setattr(
        digs.rumor, "present_hearing",
        lambda ctx, title, text: seen.append((title, text)),
    )
    return SimpleNamespace(discovered_sites=list(sites or [])), seen


def test_reveal_is_deterministic_per_seed_and_ordinal(monkeypatch):
    """Same INIT_SEED + same ordinal → the same planet and name; the
    ordinal keys the derivation (SETTLED 7/28)."""
    first, _ = _ctx(monkeypatch)
    second, _ = _ctx(monkeypatch)
    a = digs.reveal_site(first)
    b = digs.reveal_site(second)
    assert a == b


def test_reveal_records_and_presents(monkeypatch):
    ctx, seen = _ctx(monkeypatch)
    site = digs.reveal_site(ctx)
    assert ctx.discovered_sites == [site]
    assert set(site) == {"id", "planet", "name"}
    assert site["id"] == "s1"
    assert site["planet"] in {spec.id for spec in list_planet_specs()}
    title, text = seen[0]
    assert title
    assert site["name"] in text
    assert find_planet_spec(site["planet"]).name in text


def test_reveal_stacks_a_new_site(monkeypatch):
    """Each reveal is a new, distinct site (SETTLED 31); the ordinal
    advances, so the derivation moves on."""
    ctx, _ = _ctx(monkeypatch)
    one = digs.reveal_site(ctx)
    two = digs.reveal_site(ctx)
    assert one["id"] == "s1" and two["id"] == "s2"
    assert ctx.discovered_sites == [one, two]


def test_rerolled_seed_yields_a_different_legal_reveal(monkeypatch):
    """A reroll must move the derivation — distinct planets or names
    across seeds, every draw legal (the rumor-routing shape)."""
    planets = {spec.id for spec in list_planet_specs()}
    draws = set()
    for seed in range(40):
        monkeypatch.setattr(engine, "INIT_SEED", seed)
        ctx, _ = _ctx(monkeypatch)
        site = digs.reveal_site(ctx)
        assert site["planet"] in planets
        draws.add((site["planet"], site["name"]))
    assert len(draws) > 1


def test_same_planet_sites_never_share_a_name(monkeypatch):
    """Rows are one per site, so two reveals on one planet never
    render the same name: the seeded walk skips taken names, and a
    fully exhausted (one-combo) pool numbers instead of looping."""
    spec = find_planet_spec("mars")
    narrow = dataclasses.replace(
        spec, dig_prefixes=("Only",), dig_suffixes=("Name",),
    )
    monkeypatch.setattr(digs, "list_planet_specs", lambda: [narrow])
    ctx, _ = _ctx(monkeypatch)
    one = digs.reveal_site(ctx)
    two = digs.reveal_site(ctx)
    three = digs.reveal_site(ctx)
    assert one["name"] == "Only Name"
    assert two["name"] == "Only Name 2"
    assert three["name"] == "Only Name 3"


def test_authored_name_pools_win(monkeypatch):
    """A spec's pools are the only source when authored (SETTLED 33)."""
    spec = find_planet_spec("mars")
    authored = dataclasses.replace(
        spec, dig_prefixes=("Alpha",), dig_suffixes=("One", "Two"),
    )
    for roll in range(1, 20):
        assert digs.site_name(authored, roll) in {"Alpha One", "Alpha Two"}


def test_default_pools_fill_unauthored_specs():
    spec = find_planet_spec("mars")
    name = digs.site_name(spec, 7)
    prefix, suffix = name.split(" ")
    assert prefix in DEFAULT_PREFIXES
    assert suffix in DEFAULT_SUFFIXES


def test_depth_lands_within_spec_bounds():
    spec = find_planet_spec("mars")
    tight = dataclasses.replace(spec, dig_min_floors=3, dig_max_floors=5)
    for n in range(1, 15):
        assert 3 <= digs.site_depth(tight, f"s{n}") <= 5
        assert 1 <= digs.site_depth(spec, f"s{n}") <= 2


def test_depth_min_beats_inverted_max():
    spec = find_planet_spec("mars")
    inverted = dataclasses.replace(spec, dig_min_floors=4, dig_max_floors=2)
    assert digs.site_depth(inverted, "s1") == 4


def test_cache_key_round_trip():
    key = digs.cache_key("mars", "s3", 2)
    assert key == "dig:mars:s3:2"
    assert digs.parse_cache_key(key) == ("mars", "s3", 2)


def test_parse_cache_key_rejects_other_families():
    assert digs.parse_cache_key("city:earth:bar") is None
    assert digs.parse_cache_key("surface:mars") is None
    assert digs.parse_cache_key("extension:mars_alien_prison:floor:1") is None
    assert digs.parse_cache_key("dig:mars:s3") is None
    assert digs.parse_cache_key("dig:mars:s3:x") is None
    assert digs.parse_cache_key("plainly not a key") is None


# --- generation (doc 42 phase 4, step 2) -----------------------------------

from src.spacehack.data.digs import LANDMARK_VARIANTS
from src.spacehack.dungeon_params import DungeonParams as _DParams


def _dig_world(monkeypatch, depth=3, chance=None):
    """A one-planet dig universe with forced depth; returns (ctx, site)."""
    spec = find_planet_spec("mars")
    monkeypatch.setattr(digs, "list_planet_specs", lambda: [spec])
    monkeypatch.setattr(digs, "site_depth", lambda spec, sid: depth)
    if chance is not None:
        monkeypatch.setattr(digs, "LANDMARK_CHANCE", chance)
    ctx, _ = _ctx(monkeypatch)
    ctx.interiors = {}
    ctx.dungeon_extension = None
    site = digs.reveal_site(ctx)
    return ctx, site


def _tile_of(game_map, kind):
    for y in range(game_map.height):
        for x in range(game_map.width):
            if game_map.tiles[y][x].kind == kind:
                return x, y
    return None


def test_derive_dig_params_from_theme_and_tier():
    spec = find_planet_spec("mars")
    params = digs.derive_dig_params(spec)
    assert params.tile_wall.kind == "dungeon_wall"
    assert params.tile_floor.kind == "dungeon_floor"
    assert params.monster_pool
    low = digs.derive_dig_params(dataclasses.replace(spec, mission_tier=1))
    high = digs.derive_dig_params(dataclasses.replace(spec, mission_tier=3))
    assert low.monster_pool != high.monster_pool
    assert high.monster_density > low.monster_density


def test_dig_params_override_wins():
    custom = _DParams(width=20, height=15)
    spec = dataclasses.replace(find_planet_spec("mars"), dig_params=custom)
    assert digs.derive_dig_params(spec) is custom


def test_generate_dig_floor_connections(monkeypatch):
    ctx, site = _dig_world(monkeypatch, depth=3)
    f1, s1 = digs.get_or_generate_floor(ctx, site, 1)
    assert f1.tiles[s1.y][s1.x].kind == "exit"          # floor 1: the way out
    assert _tile_of(f1, "stairs_down") is not None
    f2, s2 = digs.get_or_generate_floor(ctx, site, 2)
    assert f2.tiles[s2.y][s2.x].kind == "stairs_up"     # deeper: swapped
    assert _tile_of(f2, "stairs_down") is not None
    f3, _s3 = digs.get_or_generate_floor(ctx, site, 3)
    assert _tile_of(f3, "stairs_up") is not None
    assert _tile_of(f3, "stairs_down") is None          # the bottom
    assert ctx.interiors[digs.cache_key(site["planet"], site["id"], 2)] is f2


def test_floors_generate_once_then_persist(monkeypatch):
    ctx, site = _dig_world(monkeypatch, depth=2)
    a, _ = digs.get_or_generate_floor(ctx, site, 2)
    b, _ = digs.get_or_generate_floor(ctx, site, 2)
    assert a is b


def test_landmark_sprinkle_is_seeded_and_optional(monkeypatch):
    ctx, site = _dig_world(monkeypatch, depth=2, chance=1.0)
    f1, _ = digs.get_or_generate_floor(ctx, site, 1)
    assert getattr(f1, "landmark_footprint", set())
    ctx2, site2 = _dig_world(monkeypatch, depth=2, chance=0.0)
    plain, _ = digs.get_or_generate_floor(ctx2, site2, 1)
    assert not getattr(plain, "landmark_footprint", set())


def test_dig_landmark_layouts_load_and_stamp(monkeypatch):
    """Every authored dig landmark parses and stamps into a fresh dig
    floor — the three pieces stay legal (entrance, no stairs)."""
    ctx, site = _dig_world(monkeypatch, depth=1)
    for variant in LANDMARK_VARIANTS:
        asset = landmark.load_landmark(variant.layout_id)
        f1, spawn = digs.generate_dig(ctx, site, 1)
        stamp = landmark.stamp_landmark(f1, asset, spawn)
        assert stamp.entrance is not None


def test_transition_moves_between_floors(monkeypatch):
    ctx, site = _dig_world(monkeypatch, depth=3)
    f1, _ = digs.get_or_generate_floor(ctx, site, 1)
    f2, _ = digs.get_or_generate_floor(ctx, site, 2)
    down_pos = world.Position(*_tile_of(f1, "stairs_down"))
    state = SimpleNamespace(
        ctx=ctx, game_map=f1,
        player=world.Entity(char="@", fg=(255, 255, 255), pos=down_pos, name="Player"),
    )
    ctx.game_map, ctx.player = f1, state.player
    m1, p1 = digs.transition(state, 1)
    assert m1 is f2
    assert (p1.pos.x, p1.pos.y) == _tile_of(f2, "stairs_up")
    state.game_map, state.player = m1, p1
    m2, p2 = digs.transition(state, -1)
    assert m2 is f1
    assert (p2.pos.x, p2.pos.y) == _tile_of(f1, "stairs_down")
    # The climbed-from floor keeps no stranded player.
    assert [e for e in f2.entities if e.char == "@"] == []


def test_transition_refuses_impossible_moves(monkeypatch):
    ctx, site = _dig_world(monkeypatch, depth=1)
    f1, _ = digs.get_or_generate_floor(ctx, site, 1)
    state = SimpleNamespace(
        ctx=ctx, game_map=f1,
        player=world.Entity(char="@", fg=(255, 255, 255), pos=f1.entry_spawn, name="P"),
    )
    with pytest.raises(ValueError):
        digs.transition(state, 1)  # depth 1 — nothing below
    with pytest.raises(ValueError):
        digs.transition(SimpleNamespace(ctx=ctx, game_map=object()), 1)


def test_stair_handlers_route_dig_floors(monkeypatch):
    """The game_loop stair handlers delegate dig floors to digs —
    the full descend/climb round trip through the live handlers."""
    from src.spacehack import game_loop
    ctx, site = _dig_world(monkeypatch, depth=2)
    f1, _ = digs.get_or_generate_floor(ctx, site, 1)
    f2, _ = digs.get_or_generate_floor(ctx, site, 2)
    state = SimpleNamespace(
        ctx=ctx, game_map=f1, log=SimpleNamespace(add=lambda *_: None),
        dungeon_extension=None,
        player=world.Entity(
            char="@", fg=(255, 255, 255),
            pos=world.Position(*_tile_of(f1, "stairs_down")), name="P",
        ),
        current_mode="dungeon",
    )
    ctx.ground_hp = ctx.ground_max_hp = 30
    assert game_loop._handle_stairs_down(state) == "HANDLED"
    assert state.game_map is f2
    assert game_loop._handle_stairs_up(state) == "HANDLED"
    assert state.game_map is f1


def test_stairs_down_never_lands_in_a_landmark(monkeypatch):
    """The reviewer-measured hole: with the sprinkle forced on, the
    deeper connection must respect the stamped footprint (next-farthest
    free cell outside it)."""
    for floor in range(1, 6):
        ctx, site = _dig_world(monkeypatch, depth=3, chance=1.0)
        game_map, _ = digs.generate_dig(ctx, site, floor)
        footprint = set(getattr(game_map, "landmark_footprint", ()) or ())
        down = _tile_of(game_map, "stairs_down")
        if down is not None:
            assert down not in footprint


def test_dig_tier_clamps_to_the_band():
    spec = find_planet_spec("mars")
    assert digs._dig_tier(dataclasses.replace(spec, mission_tier=1), 1) == 1
    assert digs._dig_tier(dataclasses.replace(spec, mission_tier=1), 5) == 3
    assert digs._dig_tier(dataclasses.replace(spec, mission_tier=3), 1) == 3
    assert digs._dig_tier(dataclasses.replace(spec, mission_tier=0), 2) == 1


def test_mid_tier_pool_sits_between_bands():
    spec = find_planet_spec("mars")
    low = digs.derive_dig_params(dataclasses.replace(spec, mission_tier=1))
    mid = digs.derive_dig_params(dataclasses.replace(spec, mission_tier=2))
    assert low.monster_density < mid.monster_density
    assert mid.monster_pool != low.monster_pool


def test_dim_takes_a_proportion():
    assert digs._dim((200, 100, 50), 0.5) == (100, 50, 25)


def test_find_site_rejects_unknown_ids(monkeypatch):
    ctx, site = _dig_world(monkeypatch, depth=1)
    assert digs.find_site(ctx, site["planet"], site["id"]) is site
    with pytest.raises(ValueError):
        digs.find_site(ctx, site["planet"], "s99")
    with pytest.raises(ValueError):
        digs.find_site(ctx, "venus", site["id"])


def test_stairs_log_lines_resolve_from_text():
    assert digs.stairs_log_line(1) == "You descend deeper into the dig site."
    assert digs.stairs_log_line(-1) == "You climb back up through the dig site."


# --- the discovery doors (doc 42 phase 4, step 3) ---------------------------

from src.spacehack import loot as loot_module
from src.spacehack.data.digs import DOOR_RATES, HUMANOID_PAD_DROPPERS


def _floor_map():
    gm = world.GameMap(width=8, height=8, tiles=[
        [world.DUNGEON_FLOOR for _ in range(8)] for _ in range(8)
    ], entities=[])
    return gm


def test_ground_pad_never_spawns_for_non_droppers(monkeypatch):
    gm = _floor_map()
    ctx = SimpleNamespace(known_rumors=[])
    monkeypatch.setattr(digs.engine.RNG, "randint", lambda a, b: 1)
    assert digs.maybe_spawn_ground_pad(ctx, gm, world.Position(2, 2), "rock_scavenger") is False
    assert digs.maybe_spawn_ground_pad(
        ctx, gm, world.Position(2, 2), "civillian_bystander",
    ) is False
    assert gm.entities == []


def test_ground_pad_roll_is_flat(monkeypatch):
    gm = _floor_map()
    ctx = SimpleNamespace(known_rumors=[])
    rolls = []
    monkeypatch.setattr(digs.engine.RNG, "randint", lambda a, b: rolls.pop(0))
    rolls.append(DOOR_RATES["humanoid_pad"])  # miss
    assert digs.maybe_spawn_ground_pad(
        ctx, gm, world.Position(2, 2), "pirate_raider",
    ) is False
    rolls.append(1)  # hit
    assert digs.maybe_spawn_ground_pad(
        ctx, gm, world.Position(3, 3), "pirate_raider",
    ) is True
    pad = gm.entities[0]
    assert pad.loot_data == {"reveals_site": True}
    assert pad.name == loot_module.PAD_NAME


def test_reveal_pad_pickup_consumes_and_reveals(monkeypatch):
    gm = _floor_map()
    revealed = []
    monkeypatch.setattr(digs, "reveal_site", lambda ctx: revealed.append(ctx))
    ctx = SimpleNamespace(known_rumors=[], game_map=gm)
    loot_module.spawn_pad_entity(gm, world.Position(4, 4), {"reveals_site": True})
    pad = gm.entities[0]
    loot_module._open_single_loot_pickup(ctx, pad)
    assert pad not in gm.entities
    assert revealed == [ctx]


def test_wreck_pad_scatters_on_hit(monkeypatch):
    gm = _floor_map()
    gm.entities.append(world.Entity(
        char="@", fg=(255, 255, 255), pos=world.Position(0, 0), name="P",
    ))
    monkeypatch.setattr(digs.engine.RNG, "randint", lambda a, b: 1)
    assert digs.maybe_spawn_wreck_pad(gm) is True
    assert len(gm.entities) == 2
    assert gm.entities[1].loot_data == {"reveals_site": True}
    monkeypatch.setattr(digs.engine.RNG, "randint", lambda a, b: DOOR_RATES["derelict_pad"])
    assert digs.maybe_spawn_wreck_pad(_floor_map()) is False


def test_terminal_roll_reveals_on_hit(monkeypatch):
    revealed = []
    monkeypatch.setattr(digs, "reveal_site", lambda ctx: revealed.append(ctx))
    monkeypatch.setattr(digs.engine.RNG, "randint", lambda a, b: 1)
    ctx = SimpleNamespace()
    assert digs.maybe_reveal_from_terminal(ctx) is True
    assert revealed == [ctx]
    monkeypatch.setattr(digs.engine.RNG, "randint", lambda a, b: DOOR_RATES["terminal"])
    assert digs.maybe_reveal_from_terminal(ctx) is False
    assert revealed == [ctx]


def test_door_rates_match_the_settled_opening_guesses():
    assert DOOR_RATES == {"humanoid_pad": 12, "derelict_pad": 8, "terminal": 6}
    assert "civillian_bystander" not in HUMANOID_PAD_DROPPERS


def test_wreck_pad_lands_off_occupied_cells(monkeypatch):
    """The scatter respects the occupied set: with one free cell left,
    the pad lands exactly there."""
    gm = _floor_map()
    for y in range(8):
        for x in range(8):
            if (x, y) != (5, 6):
                gm.entities.append(world.Entity(
                    char="x", fg=(0, 0, 0), pos=world.Position(x, y), name="x",
                ))
    monkeypatch.setattr(digs.engine.RNG, "randint", lambda a, b: 1)
    assert digs.maybe_spawn_wreck_pad(gm) is True
    pad = gm.entities[-1]
    assert (pad.pos.x, pad.pos.y) == (5, 6)


def test_wreck_pad_needs_a_free_cell(monkeypatch):
    gm = _floor_map()
    for y in range(8):
        for x in range(8):
            gm.entities.append(world.Entity(
                char="x", fg=(0, 0, 0), pos=world.Position(x, y), name="x",
            ))
    monkeypatch.setattr(digs.engine.RNG, "randint", lambda a, b: 1)
    assert digs.maybe_spawn_wreck_pad(gm) is False
    assert len(gm.entities) == 64


# --- menu rows, dig entry, placeholder loot (doc 42 phase 4, step 4) --------

import random

from src.spacehack.data.digs import DIG_LOOT_SPEC, DigLootSpec


def test_site_loot_rows_scale_by_tier_and_floor():
    spec = find_planet_spec("mars")
    rng = random.Random(7)
    rows = digs.site_loot_rows(spec, 1, 2, rng)
    assert len(rows) == 2
    produced = {good for good, _ in spec.produces}
    for good, qty in rows:
        assert good in produced
        assert qty == DIG_LOOT_SPEC.base_qty
    deep = digs.site_loot_rows(
        dataclasses.replace(spec, mission_tier=3), 3, 1, rng,
    )
    assert deep[0][1] == (
        DIG_LOOT_SPEC.base_qty
        + DIG_LOOT_SPEC.qty_per_tier * 2
        + DIG_LOOT_SPEC.qty_per_floor * 2
    )


def test_loot_spec_is_pluggable(monkeypatch):
    """The placeholder is a config: swapping the spec changes the
    rows (SETTLED 35 — the loot doc expands it in place)."""
    from src.spacehack.data import digs as digs_data
    custom = DigLootSpec(cache_count=(1, 1), base_qty=9, qty_per_tier=0, qty_per_floor=0)
    monkeypatch.setattr(digs_data, "DIG_LOOT_SPEC", custom)
    spec = find_planet_spec("mars")
    rows = digs.site_loot_rows(spec, 1, 1, random.Random(1))
    assert rows[0][1] == 9


def test_generate_dig_scatters_caches(monkeypatch):
    ctx, site = _dig_world(monkeypatch, depth=2)
    f1, _ = digs.get_or_generate_floor(ctx, site, 1)
    caches = [
        e for e in f1.entities
        if (e.loot_data or {}).get("good_id")
    ]
    assert 2 <= len(caches) <= 3
    produced = {good for good, _ in find_planet_spec("mars").produces}
    for cache in caches:
        assert cache.loot_data["good_id"] in produced


def test_generate_dig_without_produces_has_no_caches(monkeypatch):
    spec = dataclasses.replace(find_planet_spec("mars"), produces=())
    monkeypatch.setattr(digs, "list_planet_specs", lambda: [spec])
    monkeypatch.setattr(digs, "site_depth", lambda spec, sid: 1)
    monkeypatch.setattr(digs, "find_planet_spec", lambda pid: spec)
    ctx, site = _dig_world(monkeypatch, depth=1)
    f1, _ = digs.get_or_generate_floor(ctx, site, 1)
    assert not [
        e for e in f1.entities if (e.loot_data or {}).get("good_id")
    ]


def test_enter_dig_site_installs_surface_entry_idiom(monkeypatch):
    ctx, site = _dig_world(monkeypatch, depth=2)
    space_map = world.GameMap(width=4, height=4, tiles=[
        [world.DUNGEON_FLOOR for _ in range(4)] for _ in range(4)
    ], entities=[])
    space_player = world.Entity(
        char="@", fg=(255, 255, 255), pos=world.Position(1, 1), name="P",
    )
    ctx.ground_hp = ctx.ground_max_hp = 30
    state = SimpleNamespace(
        ctx=ctx, game_map=space_map, player=space_player,
        log=SimpleNamespace(add=lambda *_: None), current_mode="space",
    )
    result = digs.enter_dig_site(state, SimpleNamespace(id=site["planet"]), site["id"])
    assert result == "CONTINUE"
    assert state.current_mode == "dungeon"
    assert state.space_game_map is space_map
    assert state.space_player is space_player
    assert state.game_map.location_name == site["name"]
    key = digs.cache_key(site["planet"], site["id"], 1)
    assert ctx.interiors[key] is state.game_map
    assert state.player in state.game_map.entities


def test_reentering_a_dig_site_scrubs_the_stale_player(monkeypatch):
    """Save-inside-floor → Continue → re-enter: the cached floor's old
    '@' is gone, one player only."""
    ctx, site = _dig_world(monkeypatch, depth=1)
    state = SimpleNamespace(
        ctx=ctx,
        game_map=world.GameMap(width=4, height=4, tiles=[
            [world.DUNGEON_FLOOR for _ in range(4)] for _ in range(4)
        ], entities=[]),
        player=world.Entity(
            char="@", fg=(255, 255, 255), pos=world.Position(1, 1), name="P",
        ),
        log=SimpleNamespace(add=lambda *_: None), current_mode="space",
    )
    ctx.ground_hp = ctx.ground_max_hp = 30
    digs.enter_dig_site(state, SimpleNamespace(id=site["planet"]), site["id"])
    first_player = state.player
    # Leave (state returns to the space pair), then re-enter.
    state.game_map, state.player = state.space_game_map, state.space_player
    digs.enter_dig_site(state, SimpleNamespace(id=site["planet"]), site["id"])
    assert not any(e is first_player for e in state.game_map.entities)
    assert [e for e in state.game_map.entities if e.char == "@"] == [state.player]


def test_planet_menu_dispatch_reaches_dig_entry(monkeypatch):
    """The planet-wall dispatch unpacks (outcome, site_id) and enters
    the dig (the mock pins the seam)."""
    from src.spacehack import game_interactions
    ctx, site = _dig_world(monkeypatch, depth=1)
    entered = []
    monkeypatch.setattr(
        game_interactions, "_run_planet_menu",
        lambda _ctx, _planet: (game_interactions.PlanetMenuOutcome.DIG, site["id"]),
    )
    monkeypatch.setattr(
        digs, "enter_dig_site",
        lambda state, planet_obj, site_id: entered.append(site_id) or "CONTINUE",
    )
    state = SimpleNamespace(ctx=ctx, log=SimpleNamespace(add=lambda *_: None))
    assert game_interactions._resolve_planet_wall(state, site["planet"]) == "CONTINUE"
    assert entered == [site["id"]]


def test_caches_never_cover_transition_tiles(monkeypatch):
    """A cache glyph must never hide a stair: across seeds and floors,
    no cache sits on an exit/stairs tile (the underlay render contract
    would paint the '%' over the '>' )."""
    for seed in (1, 7, 99):
        monkeypatch.setattr(engine, "INIT_SEED", seed)
        ctx, site = _dig_world(monkeypatch, depth=3, chance=1.0)
        for floor in (1, 2):
            game_map, _ = digs.get_or_generate_floor(ctx, site, floor)
            transition_kinds = {
                (x, y)
                for y in range(game_map.height)
                for x in range(game_map.width)
                if game_map.tiles[y][x].kind in {"exit", "stairs_up", "stairs_down"}
            }
            for e in game_map.entities:
                if (e.loot_data or {}).get("good_id"):
                    assert (e.pos.x, e.pos.y) not in transition_kinds


def test_discovered_rows_scope_to_the_bumped_planet(monkeypatch):
    """The menu filter shows only this planet's sites — a foreign
    site's row never appears here."""
    from src.spacehack.menus import _planet
    ctx = SimpleNamespace(discovered_sites=[
        {"id": "s1", "planet": "mars", "name": "Sunken Vault"},
        {"id": "s2", "planet": "venus", "name": "Rusted Warren"},
    ])
    assert [site["id"] for site in _planet._discovered_on(ctx, "mars")] == ["s1"]
    assert _planet._discovered_on(ctx, "earth") == []
    assert _planet._discovered_on(SimpleNamespace(discovered_sites=[]), "mars") == []


def test_shift_m_grant_reveals(monkeypatch):
    """The Shift+M dev grant plays the full reveal idiom."""
    from src.spacehack import dev_mode
    ctx, seen = _ctx(monkeypatch)
    site = dev_mode.reveal_dev_dig_site(ctx)
    assert ctx.discovered_sites == [site]
    assert len(seen) == 1  # the readout played
