"""Tests for the first post-prison Act 1 orbit beat."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.spacehack import dungeon_extensions, world
from src.spacehack.data.main_quest import find_main_quest_step

from src.spacehack.main_quest import _act1
from src.spacehack.main_quest._core import _schedule_next_step
from src.spacehack.main_quest._breadcrumb import current_main_quest_objective
from src.spacehack.main_quest._gates import check_quest_gates
from src.spacehack import __main__ as game_main


def _ctx():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from support.quest_ctx import quest_ctx

    return quest_ctx(
        chain="lab",
        progress={"act1_prison": "completed"},
        city_id="mars",
        post_prison_orbit_seen=False,
        dungeon_extension=SimpleNamespace(state_flags={"prison_data_extracted"}),
    )


def test_mars_surface_detection_supports_current_and_legacy_maps():
    ctx = _ctx()
    _surface_map = object()
    ctx.interiors = {"surface:mars": _surface_map}

    assert game_main._is_mars_surface_map(ctx, _surface_map)
    assert game_main._is_mars_surface_map(
        ctx,
        SimpleNamespace(interior_cache_key="surface:mars"),
    )
    assert game_main._is_mars_facility_map(
        ctx,
        SimpleNamespace(extension_id="mars_alien_prison"),
    )
    assert not game_main._is_mars_surface_map(ctx, object())
    assert not game_main._is_mars_facility_map(
        ctx,
        SimpleNamespace(extension_id="other_facility"),
    )


def test_surface_exit_notifies_only_for_mars_and_only_once(monkeypatch):
    ctx = _ctx()
    _mars_surface = object()
    ctx.interiors = {"surface:mars": _mars_surface}
    _calls = []
    monkeypatch.setattr(
        game_main,
        "_maybe_show_post_prison_orbit",
        lambda _ctx, _city, **_kwargs: _calls.append((_ctx, _city)) or True,
    )

    assert game_main._notify_surface_exit(ctx, _mars_surface)
    assert _calls == [(ctx, "mars")]
    assert not game_main._notify_surface_exit(ctx, object())
    assert _calls == [(ctx, "mars")]


def test_mars_departure_helper_triggers_from_mars_launch(monkeypatch):
    """The disclosure helper remains available for the actual Mars launch."""
    ctx = _ctx()
    _calls = []

    monkeypatch.setattr(
        game_main.main_quest_module,
        "play_scene",
        lambda _ctx, _step_id, **_kwargs: _calls.append(_ctx) or True,
    )

    assert game_main._maybe_show_post_prison_orbit(ctx, "mars")
    assert _calls == [ctx]
    assert not game_main._maybe_show_post_prison_orbit(ctx, "earth")
    assert _calls == [ctx]


def test_prison_exit_then_mars_launch_shows_orbit_disclosure_once(monkeypatch):
    """The real exit-then-launch sequence delivers the disclosure once."""
    ctx = _ctx()
    ctx.context = None
    _parent_map = world.GameMap(
        12, 12,
        [[world.DUNGEON_FLOOR for _ in range(12)] for _ in range(12)],
        [],
    )
    _parent_player = world.Entity(
        "@", (255, 255, 255), world.Position(4, 5), "Player",
    )
    _parent_map.entities.append(_parent_player)
    ctx.interiors = {"surface:mars": _parent_map}
    ctx.dungeon_extension = None
    _extension_map, _ = dungeon_extensions.enter_extension(
        ctx,
        _parent_map,
        _parent_player,
        extension_id="mars_alien_prison",
        parent_map_key="surface:mars",
    )
    ctx.dungeon_extension.state_flags.add("prison_data_extracted")
    dungeon_extensions.leave_extension(ctx, _extension_map)
    ctx.time_day = 1
    ctx.time_month = 1
    ctx.time_year = 2200
    ctx.context = SimpleNamespace(present=lambda _console: None)

    monkeypatch.setattr(
        _act1,
        "_pygame_disposition_choice",
        lambda _ctx: "delivered",
    )

    _launch_calls = []
    monkeypatch.setattr(
        game_main,
        "_launch_to_space",
        lambda *_args, **_kwargs: (
            _launch_calls.append(True) or (_parent_map, _parent_player)
        ),
    )
    _owned_ship = SimpleNamespace(ship_id="starter")
    _hangar_ship = world.Entity(
        "S", (255, 255, 255), world.Position(5, 5), "Owned ship",
        ship_id="starter", owned=True,
    )
    _parent_map.entities.append(_hangar_ship)

    assert not ctx.post_prison_orbit_seen
    _space_map, _space_player = game_main._launch_owned_ship(
        ctx,
        object(),
        game_main.ShipMenuAction.LAUNCH,
        _owned_ship,
        _parent_map,
        _parent_player,
        "mars",
        object(),
    )
    assert _launch_calls == [True]
    assert (_space_map, _space_player) == (_parent_map, _parent_player)
    assert ctx.post_prison_orbit_seen
    assert ctx.main_quest_disposition == "delivered"
    _launch_from_city_result = game_main._launch_owned_ship(
        ctx,
        object(),
        game_main.ShipMenuAction.LAUNCH,
        _owned_ship,
        _parent_map,
        _parent_player,
        "mars",
        object(),
    )
    assert _launch_from_city_result == (_parent_map, _parent_player)
    assert _launch_calls == [True, True]
    assert ctx.post_prison_orbit_seen


def test_prison_completion_shows_departure_breadcrumb_before_orbit_scene():
    """The completed prison opening still has a required Mars handoff."""
    ctx = _ctx()

    assert current_main_quest_objective(ctx) == (
        "Leave Mars",
        "Return to your ship and launch from Mars. The recovered archive "
        "is waiting for its first reading.",
    )

    ctx.post_prison_orbit_seen = True
    assert current_main_quest_objective(ctx) is None


def test_orbit_scene_requires_completed_prison_and_mars_departure():
    ctx = _ctx()

    assert _act1._orbit_scene_is_ready(ctx)

    ctx.current_city_id = "earth"
    assert not _act1._orbit_scene_is_ready(ctx)

    ctx.current_city_id = "mars"
    ctx.dungeon_extension = None
    assert _act1._orbit_scene_is_ready(ctx)

    ctx.main_quest_progress["act1_prison"] = "active"
    assert not _act1._orbit_scene_is_ready(ctx)


def test_space_mode_boundary_delivers_post_prison_scene(monkeypatch):
    ctx = _ctx()
    ctx.dungeon_extension = None
    _calls = []
    monkeypatch.setattr(
        game_main.main_quest_module,
        "play_scene",
        lambda _ctx, _step_id, **_kwargs: _calls.append(_ctx) or True,
    )

    assert game_main._maybe_show_post_prison_orbit_in_space(ctx, "space")
    assert _calls == [ctx]

    ctx.current_city_id = "earth"
    assert not game_main._maybe_show_post_prison_orbit_in_space(ctx, "space")
    assert _calls == [ctx]
    assert not game_main._maybe_show_post_prison_orbit_in_space(ctx, "dungeon")
    assert _calls == [ctx]


def test_missing_space_state_rebuild_is_limited_to_mars_surface():
    ctx = _ctx()
    ctx.interiors = {"surface:mars": object()}
    _mars_surface = ctx.interiors["surface:mars"]
    assert game_main._is_mars_surface_map(ctx, _mars_surface)
    assert not game_main._is_mars_surface_map(ctx, SimpleNamespace(wreck_spawn_id="wreck"))


def test_real_mars_surface_exit_rebuilds_missing_space_state(monkeypatch):
    ctx = _ctx()
    ctx.time_day = 1
    ctx.time_month = 1
    ctx.time_year = 2200
    ctx.context = SimpleNamespace(present=lambda _console: None)
    _mars_surface = object()
    ctx.interiors = {"surface:mars": _mars_surface}
    _ship = SimpleNamespace(ship_id="starter")
    _space_map = object()
    _space_player = object()
    _modal_calls = []
    monkeypatch.setattr(
        game_main.ship_module,
        "find_ship",
        lambda _ship_id: _ship,
    )
    monkeypatch.setattr(
        game_main,
        "_build_space_return",
        lambda _ctx, _city, _spec: (_space_map, _space_player),
    )
    monkeypatch.setattr(
        _act1,
        "_pygame_disposition_choice",
        lambda _ctx: _modal_calls.append(True) or "kept",
    )

    _result = game_main._handle_dungeon_exit_tile(
        ctx,
        "exit",
        _mars_surface,
        None,
        None,
        _ship,
        [],
        ctx.log,
    )

    assert _result == (_space_map, _space_player, "space")
    assert (ctx.game_map, ctx.player) == (_space_map, _space_player)
    assert ctx.post_prison_orbit_seen
    assert ctx.main_quest_disposition == "kept"
    assert _modal_calls == [True]
    assert any(
        "return to Mars orbit" in entry.text
        for entry in ctx.log.recent(n=8)
    )
    assert not game_main._maybe_show_post_prison_orbit_in_space(ctx, "space")
    assert _modal_calls == [True]


def test_loaded_mars_prison_exit_does_not_require_surface_cache_identity(monkeypatch):
    """A Continue-restored prison map still reaches the orbit handoff."""
    ctx = _ctx()
    ctx.current_city_id = "earth"
    ctx.time_day = 1
    ctx.time_month = 1
    ctx.time_year = 2200
    ctx.context = SimpleNamespace(present=lambda _console: None)
    ctx.interiors = {}
    _loaded_prison = SimpleNamespace(
        extension_id="mars_alien_prison",
        extension_floor=1,
    )
    _space_map = object()
    _space_player = object()
    _ship = SimpleNamespace(ship_id="starter")
    monkeypatch.setattr(
        game_main.ship_module,
        "find_ship",
        lambda _ship_id: _ship,
    )
    monkeypatch.setattr(
        game_main,
        "_build_space_return",
        lambda _ctx, _city, _spec: (_space_map, _space_player),
    )
    monkeypatch.setattr(
        _act1,
        "_pygame_disposition_choice",
        lambda _ctx: "delivered",
    )

    result = game_main._handle_dungeon_exit_tile(
        ctx,
        "exit",
        _loaded_prison,
        None,
        None,
        _ship,
        [],
        ctx.log,
    )

    assert result == (_space_map, _space_player, "space")
    assert ctx.post_prison_orbit_seen
    assert ctx.main_quest_disposition == "delivered"
    assert any(
        "return to Mars orbit" in entry.text
        for entry in ctx.log.recent(n=8)
    )


def test_orbit_scene_can_resolve_from_prison_without_city_context(monkeypatch):
    ctx = _ctx()
    ctx.current_city_id = "earth"
    ctx.context = SimpleNamespace(present=lambda _console: None)
    ctx.time_day = 1
    ctx.time_month = 1
    ctx.time_year = 2200
    monkeypatch.setattr(
        _act1,
        "_pygame_disposition_choice",
        lambda _ctx: "delivered",
    )

    assert not _act1.maybe_show_post_prison_orbit(ctx)
    assert _act1.maybe_show_post_prison_orbit(ctx, from_mars_prison=True)
    assert ctx.post_prison_orbit_seen
    assert ctx.main_quest_disposition == "delivered"


def test_interrupted_prison_exit_retries_from_space_without_city_context(monkeypatch):
    ctx = _ctx()
    ctx.current_city_id = "earth"
    _mars_surface = object()
    ctx.interiors = {"surface:mars": _mars_surface}
    _calls = []

    def _resolve(_ctx, _step_id, *, from_mars_prison=False):
        _calls.append(from_mars_prison)
        return len(_calls) == 2

    monkeypatch.setattr(
        game_main.main_quest_module,
        "play_scene",
        _resolve,
    )

    assert not game_main._notify_surface_exit(ctx, _mars_surface)
    assert ctx.post_prison_orbit_pending
    assert game_main._maybe_show_post_prison_orbit_in_space(ctx, "space")
    assert _calls == [True, True]
    assert not ctx.post_prison_orbit_pending


def test_derelict_exit_keeps_hull_breach_message():
    ctx = _ctx()
    _wreck = SimpleNamespace(wreck_spawn_id="random-wreck")
    _space_map = object()
    _space_player = object()

    result = game_main._leave_dungeon_to_space(
        ctx,
        _wreck,
        _space_map,
        _space_player,
        None,
        [],
        ctx.log,
    )

    assert result == (_space_map, _space_player)
    assert any(
        "hull breach" in entry.text
        for entry in ctx.log.recent(n=8)
    )

def test_epilogue_breadcrumb_is_consistent_for_every_faction(monkeypatch):
    """Delivered: every chain's breadcrumb is its own reward step (title,
    faction contact, world). Kept: no step - the pending summon carries
    the solo teaser (doc 38)."""
    for _faction, _npc_world in (
        ("merchants", "Earth"), ("militia", "Earth"), ("bar", "Earth"),
        ("lab", "Mercury"),
    ):
        ctx = _ctx()
        ctx.main_quest_chain = _faction
        ctx.time_day, ctx.time_month, ctx.time_year = 1, 1, 2200

        _act1._apply_disposition(ctx, _act1.DISPOSITION_DELIVERED)
        title, description = current_main_quest_objective(ctx)
        assert title == find_main_quest_step(
            f"epilogue_reward_{_faction}"
        ).title
        assert _npc_world in description

        ctx = _ctx()
        ctx.main_quest_chain = _faction
        ctx.time_day, ctx.time_month, ctx.time_year = 1, 1, 2200
        _act1._apply_disposition(ctx, _act1.DISPOSITION_KEPT)
        assert (
            ctx.main_quest_progress.get(f"epilogue_reward_{_faction}", "") == ""
        ), "kept never unlocks a reward step"
        assert ctx.main_quest_pending_message == "The archive is yours alone"


def test_schedule_next_step_is_idempotent_and_can_unlock_after_gate():
    ctx = _ctx()
    ctx.main_quest_chain = "merchants"
    ctx.time_day, ctx.time_month, ctx.time_year = 1, 1, 2200

    # Explicit-next form (how the epilogue unlocks reward steps):
    # idempotent, and a wait_days=0 source unlocks immediately.
    assert _schedule_next_step(
        ctx, "act1_prison", next_step_id="epilogue_reward_merchants"
    )
    assert not _schedule_next_step(
        ctx, "act1_prison", next_step_id="epilogue_reward_merchants"
    )
    # act1_prison carries a wait: the reward step gates, then unlocks.
    assert "epilogue_reward_merchants" in ctx.main_quest_gate
    ctx.time_day, ctx.time_month, ctx.time_year = 1, 3, 2200
    assert check_quest_gates(ctx)
    assert (
        ctx.main_quest_progress["epilogue_reward_merchants"] == "available"
    )
    assert not ctx.main_quest_gate



def test_wolf_camp_layout_contract():
    """Uniform rows, one entrance, no void padding (the v7 prison bug
    class), ornaments present."""
    from src.spacehack import landmark as landmark_module
    from src.spacehack.data.planets import find_planet_spec

    asset = landmark_module.load_landmark("wolf_camp")
    widths = {len(row) for row in asset.tiles}
    assert len(widths) == 1
    assert not any(t.kind == "void" for r in asset.tiles for t in r)
    entrances = sum(
        t.kind in {"dungeon_door", "landmark_entrance"}
        for r in asset.tiles for t in r
    )
    assert entrances == 1
    # balance: guardians doubled over Mars but tier-2 only
    params = find_planet_spec("wolf_b").dungeon_params
    assert params.cache_guardian_pool == ()  # guardians authored in the layout
    assert find_main_quest_step("mer_q2_strike").delve_layout_id == "wolf_camp"


def test_wolf_delve_stamps_camp_cache_and_guardians():
    """prepare_delve_site: the camp stamps, the cache lands inside it
    (deepest interior cell), and two sentry guardians hold the room."""
    from types import SimpleNamespace

    from src.spacehack.data.planets import find_planet_spec
    from src.spacehack.dungeon import generate_dungeon
    from src.spacehack.engine import seed_rng
    from src.spacehack.main_quest._delve import prepare_delve_site

    ctx = SimpleNamespace(
        main_quest_progress={"mer_q2_strike": "active"},
        main_quest_gate={}, main_quest_chain="merchants",
        log=SimpleNamespace(add=lambda *_a: None),
    )
    seed_rng(1)
    spec = find_planet_spec("wolf_b")
    game_map, spawn = generate_dungeon(spec.dungeon_params)
    assert prepare_delve_site(ctx, game_map, spawn, "wolf_b") is True

    cache = next(
        (e for e in game_map.entities if getattr(e, "main_quest_step_id", "") == "mer_q2_strike"),
        None,
    )
    assert cache is not None
    footprint = getattr(game_map, "landmark_footprint", set()) or set()
    assert (cache.pos.x, cache.pos.y) in footprint, "cache must sit inside the camp"
    assert game_map.tiles[cache.pos.y][cache.pos.x].walkable

    guards = [
        e for e in game_map.entities
        if e.npc_char_id == "sentry_drone"
    ]
    assert len(guards) == 2
    for g in guards:
        assert max(abs(g.pos.x - cache.pos.x), abs(g.pos.y - cache.pos.y)) <= 10


def test_survey_a_layout_contract():
    """The generated survey ship parses through the real loader with
    every marker reachable, consortium crew (not pirates) inside, void
    outside the hull, and loot on the map (doc 32 iteration)."""
    from src.spacehack.dungeon import load_layout

    game_map, spawn = load_layout("survey_a", loot_budget=None)
    assert game_map.width == 92 and game_map.height == 34
    assert any(
        t.kind == "void" for row in game_map.tiles for t in row
    ), "void outside the hull keeps the silhouette readable"
    enemies = [e.npc_char_id for e in game_map.entities if e.npc_char_id]
    assert {"consortium_enforcer", "consortium_gunner"} <= set(enemies)
    assert not any(eid.startswith("pirate") for eid in enemies)
    assert any(
        getattr(e, "loot_data", None) for e in game_map.entities
    ), "guaranteed loot containers must spawn"


def test_mer_q5_uses_the_survey_ship():
    from src.spacehack.data.main_quest import find_main_quest_step

    step = find_main_quest_step("mer_q6_survey")
    assert step.salvage_layout_id == "survey_a"


def test_mercury_vault_layout_contract():
    """Uniform rows, one entrance, no void padding (the v7 prison bug
    class), ornaments present; one leftover sentry - the assault spike
    stays pulled (doc 35)."""
    from src.spacehack import landmark as landmark_module
    from src.spacehack.data.planets import find_planet_spec

    asset = landmark_module.load_landmark("mercury_vault")
    widths = {len(row) for row in asset.tiles}
    assert len(widths) == 1
    assert not any(t.kind == "void" for r in asset.tiles for t in r)
    # one explicit link marker; interior doors are free (the strong
    # room keeps its own vault door); the cache site is authored
    assert sum(
        t.kind == "landmark_entrance" for r in asset.tiles for t in r
    ) == 1
    assert sum(
        t.kind == "dungeon_door" for r in asset.tiles for t in r
    ) == 1
    assert sum(
        t.kind == "quest_cache" for r in asset.tiles for t in r
    ) == 1
    assert sum(
        t.kind == "quest_cache" for r in asset.tiles for t in r
    ) == 1
    # balance: a single tier-2 watch drone - this delve lands almost
    # immediately after the Mars caves, so lighter than wolf_b's pair
    params = find_planet_spec("mercury").dungeon_params
    assert params.cache_guardian_pool == ()  # guardians authored in the layout
    # the cache site is step data, not a planet->layout dict
    assert find_main_quest_step("mil_q2_cache").delve_layout_id == "mercury_vault"


def test_mercury_delve_stamps_vault_cache_and_guardian():
    """prepare_delve_site: the vault stamps, the requisition cache
    lands inside it (the strong room, deepest interior cell), and the
    watch drone holds the room."""
    from types import SimpleNamespace

    from src.spacehack.data.planets import find_planet_spec
    from src.spacehack.dungeon import generate_dungeon
    from src.spacehack.engine import seed_rng
    from src.spacehack.main_quest._delve import prepare_delve_site

    ctx = SimpleNamespace(
        main_quest_progress={"mil_q2_cache": "active"},
        main_quest_gate={}, main_quest_chain="militia",
        log=SimpleNamespace(add=lambda *_a: None),
    )
    seed_rng(1)
    spec = find_planet_spec("mercury")
    game_map, spawn = generate_dungeon(spec.dungeon_params)
    assert prepare_delve_site(ctx, game_map, spawn, "mercury") is True

    cache = next(
        (e for e in game_map.entities if getattr(e, "main_quest_step_id", "") == "mil_q2_cache"),
        None,
    )
    assert cache is not None
    footprint = getattr(game_map, "landmark_footprint", set()) or set()
    assert (cache.pos.x, cache.pos.y) in footprint, "cache must sit inside the vault"
    # the cache lands at the authored QUEST_CACHE marker, not a code
    # heuristic: same offset within the stamped footprint as in the asset
    from src.spacehack import landmark as landmark_module
    vault = landmark_module.load_landmark("mercury_vault")
    mx, my = next(
        (x, y)
        for y, row in enumerate(vault.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "quest_cache"
    )
    origin = (min(x for x, _ in footprint), min(y for _, y in footprint))
    assert (cache.pos.x, cache.pos.y) == (origin[0] + mx, origin[1] + my)
    # the marker cell normalized to floor - only the entity renders
    assert game_map.tiles[cache.pos.y][cache.pos.x].kind == "dungeon_floor"
    assert cache.loot_data == {"goods": [("sealed_requisition", 1)]}

    guards = [
        e for e in game_map.entities
        if e.npc_char_id == "sentry_drone"
    ]
    assert len(guards) == 1
    assert max(
        abs(guards[0].pos.x - cache.pos.x),
        abs(guards[0].pos.y - cache.pos.y),
    ) <= 10


def test_delve_layout_variants_pick_then_fallback_order():
    """Camp variants are weighted data on the step: one candidate is
    chosen per build and the rest stay as stamp fallbacks (doc 35 —
    authored vault variants with strategic cache sites)."""
    from src.spacehack.engine import seed_rng
    from src.spacehack.main_quest._delve import _delve_layout_candidates

    # No variants: the single layout stands alone.
    assert _delve_layout_candidates("mercury_vault", ()) == ["mercury_vault"]
    assert _delve_layout_candidates("", ()) == []

    # Variants: every layout appears exactly once, weighted pick first.
    variants = (("mercury_vault", 3), ("mercury_vault_b", 1))
    seen = set()
    for seed in range(12):
        seed_rng(seed)
        candidates = _delve_layout_candidates("ignored", variants)
        assert sorted(candidates) == ["mercury_vault", "mercury_vault_b"]
        assert candidates[0] in {"mercury_vault", "mercury_vault_b"}
        seen.add(candidates[0])
    assert seen == {"mercury_vault", "mercury_vault_b"}, "weights must matter"


def test_barnards_cache_layout_contract():
    """The old crew's staging cache: uniform rows, one entrance marker,
    authored cell site, one leftover sentry (standing assault-drone
    ruling; doc 36)."""
    from src.spacehack import landmark as landmark_module
    from src.spacehack.data.main_quest import find_main_quest_step
    from src.spacehack.data.planets import find_planet_spec

    asset = landmark_module.load_landmark("barnards_cache")
    widths = {len(row) for row in asset.tiles}
    assert len(widths) == 1
    assert not any(t.kind == "void" for r in asset.tiles for t in r)
    assert sum(t.kind == "landmark_entrance" for r in asset.tiles for t in r) == 1
    assert sum(t.kind == "quest_cache" for r in asset.tiles for t in r) == 1
    assert find_main_quest_step("bar_q3_rigparts").delve_layout_id == "barnards_cache"
    params = find_planet_spec("barnards_b").dungeon_params
    assert params.cache_guardian_pool == ()  # guardians authored in the layout


def test_barnards_delve_stamps_cache_site_and_guardian():
    """prepare_delve_site: the cache stamps, the power cell lands at the
    authored marker offset, and the watch drone holds the room."""
    from types import SimpleNamespace

    from src.spacehack import landmark as landmark_module
    from src.spacehack.data.planets import find_planet_spec
    from src.spacehack.dungeon import generate_dungeon
    from src.spacehack.engine import seed_rng
    from src.spacehack.main_quest._delve import prepare_delve_site

    ctx = SimpleNamespace(
        main_quest_progress={"bar_q3_rigparts": "active"},
        main_quest_gate={}, main_quest_chain="bar",
        log=SimpleNamespace(add=lambda *_a: None),
    )
    seed_rng(1)
    spec = find_planet_spec("barnards_b")
    game_map, spawn = generate_dungeon(spec.dungeon_params)
    assert prepare_delve_site(ctx, game_map, spawn, "barnards_b") is True

    cache = next(
        (e for e in game_map.entities
         if getattr(e, "main_quest_step_id", "") == "bar_q3_rigparts"),
        None,
    )
    assert cache is not None
    footprint = getattr(game_map, "landmark_footprint", set()) or set()
    assert (cache.pos.x, cache.pos.y) in footprint
    asset = landmark_module.load_landmark("barnards_cache")
    mx, my = next(
        (x, y)
        for y, row in enumerate(asset.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "quest_cache"
    )
    origin = (min(x for x, _ in footprint), min(y for _, y in footprint))
    assert (cache.pos.x, cache.pos.y) == (origin[0] + mx, origin[1] + my)
    assert game_map.tiles[cache.pos.y][cache.pos.x].kind == "dungeon_floor"
    assert cache.loot_data == {"goods": [("power_cell", 1)]}

    guards = [e for e in game_map.entities if e.npc_char_id == "sentry_drone"]
    assert len(guards) == 1
    assert max(
        abs(guards[0].pos.x - cache.pos.x), abs(guards[0].pos.y - cache.pos.y),
    ) <= 10


def test_delivered_unlocks_the_chain_reward_step_and_pays():
    """The disposition branch: delivered makes the chain's reward step
    live; completing it pays (merchants: the bond's return)."""
    from src.spacehack.main_quest._core import complete_step

    ctx = _ctx()
    ctx.main_quest_chain = "merchants"
    ctx.time_day, ctx.time_month, ctx.time_year = 1, 1, 2200
    ctx.stats = SimpleNamespace(credits=0)
    ctx.player_xp, ctx.player_level, ctx.player_skill_points = 0, 1, 0
    ctx.main_quest_backing = set()

    _act1._apply_disposition(ctx, _act1.DISPOSITION_DELIVERED)
    assert ctx.main_quest_progress["epilogue_reward_merchants"] == "available"
    assert ctx.main_quest_disposition == "delivered"

    assert complete_step(ctx, "epilogue_reward_merchants")
    assert ctx.stats.credits == 12000  # the 8,000cr bond, with its return


def test_delivered_reward_perks_per_chain():
    """The non-merchants chains pay in QUEST PERKS (free trait grants,
    never milestone picks), not credits."""
    from src.spacehack.data.traits.core import ALL_TRAITS, QUEST_PERKS

    perks = {
        "militia": "warrant_license",
        "bar": "smugglers_instinct",
        "lab": "lab_credentials",
    }
    milestone_ids = {t.id for t in ALL_TRAITS}
    for chain, perk in perks.items():
        step = find_main_quest_step(f"epilogue_reward_{chain}")
        assert step.rewards_trait == perk, chain
        assert perk in QUEST_PERKS and perk not in milestone_ids, chain
        assert step.rewards_credits == 0, chain


def test_kept_disposition_sets_no_step_and_teases_the_line():
    ctx = _ctx()
    ctx.main_quest_chain = "bar"
    ctx.time_day, ctx.time_month, ctx.time_year = 1, 1, 2200

    _act1._apply_disposition(ctx, _act1.DISPOSITION_KEPT)
    assert ctx.main_quest_disposition == "kept"
    assert ctx.main_quest_progress == {"act1_prison": "completed"}
    assert ctx.main_quest_pending_message == "The archive is yours alone"
    assert "Luyten Line" in ctx.main_quest_pending_objective


def test_pre_epilogue_save_migrates_to_the_disposition_branch():
    """Old saves carry disclosure values + research steps; any
    disclosure maps to delivered, research ids vanish, and a save
    that reached the first translation counts as reward-collected."""
    from src.spacehack.main_quest import check_quest_gates

    ctx = _ctx()
    ctx.main_quest_chain = "militia"
    ctx.main_quest_disclosure = "diagnostic_fragment"
    ctx.main_quest_progress["research_alpha"] = "completed"
    ctx.main_quest_progress["research_alpha_report"] = "completed"

    check_quest_gates(ctx)

    assert ctx.main_quest_disposition == "delivered"
    assert "research_alpha" not in ctx.main_quest_progress
    assert ctx.main_quest_progress["epilogue_reward_militia"] == "completed"

    # A save that only started the handoff keeps the reward live
    # (scheduled, not completed — the orbit scene already fired for
    # those saves, so the reward unlocks via the gate sweep).
    ctx2 = _ctx()
    ctx2.main_quest_chain = "bar"
    ctx2.main_quest_disclosure = "archive_sealed"
    ctx2.time_day, ctx2.time_month, ctx2.time_year = 1, 1, 2200
    ctx2.main_quest_gate["epilogue_reward_bar"] = (1, 1, 2200)
    check_quest_gates(ctx2)
    assert ctx2.main_quest_disposition == "delivered"
    assert ctx2.main_quest_progress.get("epilogue_reward_bar", "") == "available"
