"""Tests for the first post-prison Act 1 orbit beat."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from src.spacehack import dungeon_extensions, message_log, world
from src.spacehack.data.main_quest import find_main_quest_step
from src.spacehack.data.main_quest.act1_post_prison import find_archive_disclosure
from src.spacehack.data.planets.ac_station import SPEC as AC_STATION

from src.spacehack.main_quest import _act1
from src.spacehack.main_quest._core import _schedule_next_step
from src.spacehack.main_quest._objectives import maybe_complete_visit
from src.spacehack.main_quest._breadcrumb import current_main_quest_objective
from src.spacehack.main_quest._gates import check_quest_gates
from src.spacehack import __main__ as game_main


def _ctx():
    return SimpleNamespace(
        current_city_id="mars",
        post_prison_orbit_seen=False,
        main_quest_disclosure="",
        main_quest_progress={"act1_prison": "completed"},
        main_quest_chain="lab",
        main_quest_gate={},
        main_quest_pending_message="",
        main_quest_pending_objective="",
        dungeon_extension=SimpleNamespace(state_flags={"prison_data_extracted"}),
        log=message_log.MessageLog(capacity=6),
        main_quest_complete=False,
        player_active_missions=[],
    )


def test_research_alpha_is_cataloged_as_an_alpha_centauri_visit():
    step = find_main_quest_step("research_alpha")

    assert step.requires_step == "act1_prison"
    assert step.objective_type == "visit"
    assert step.requires_npc_id == "research_officer"
    assert step.trigger_planet_id == "ac_station"
    _dialogue = step.dialogues["research_officer"]
    assert _dialogue.option_label == "Begin the first interpretation"
    assert "Do not call it a map yet" in _dialogue.intro
    assert "layered signal" in _dialogue.intro
    assert "translate the simplest recurring symbols" in _dialogue.intro
    assert "Before we call it a map" not in _dialogue.intro
    # active/complete variants were removed as dead: research_alpha is
    # auto_advance + trigger_on_talk, so the talk modal always shows
    # the NPC flavor while this step is live (see tools/audit_story_text.py)
    assert step.auto_advance
    assert step.wait_days == 14
    # The summon text belongs to the GATING step (research_alpha, whose
    # 14-day wait unlocks the report); the report itself has no gate.
    assert "processing cluster" in step.ready_message
    _report = find_main_quest_step("research_alpha_report")
    assert _report.requires_step == "research_alpha"
    assert _report.objective_type == "visit"
    assert _report.wait_days == 0
    assert _report.ready_message == ""

    prison = find_main_quest_step("act1_prison")
    assert not prison.auto_advance
    assert prison.wait_days == 60
    assert "archive handoff is ready" in prison.ready_message
    assert "Alpha Centauri" in prison.ready_message


def test_archive_disclosure_catalog_is_frozen_and_keyed():
    _spec = find_archive_disclosure("diagnostic_fragment")

    assert _spec.label == "Transmit a diagnostic fragment"
    assert _spec.waiting_title == "Awaiting fragment analysis..."
    assert "independent reading" in _spec.ready_message

    try:
        find_archive_disclosure("not-a-real-disclosure")
    except KeyError as _error:
        assert "not-a-real-disclosure" in str(_error)
    else:
        raise AssertionError("unknown archive disclosure keys must fail")

    try:
        _spec.label = "mutated"
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("archive disclosure data must be frozen")


def test_alpha_centauri_station_research_contacts():
    _building_npcs = {building.npc_id for building in AC_STATION.buildings}

    assert {"archive_research_officer", "research_officer"} <= _building_npcs
    # The archive override supplies the post-prison officer; the lab
    # slot resolves through the global catalog (no xenolinguist
    # override — she is now a dynamic quest NPC via quest_npc_spots).
    assert dict(AC_STATION.npc_overrides)["archive_research_officer"].id == "research_officer"
    assert "research_officer" not in dict(AC_STATION.npc_overrides)
    assert ("xenolinguist", "lab") in AC_STATION.quest_npc_spots


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
        "_pygame_orbit_choice",
        lambda _ctx: "diagnostic_fragment",
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
    assert ctx.main_quest_disclosure == "diagnostic_fragment"
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


def test_quest_log_distinguishes_prison_handoff_from_final_resolution():
    """The quest log reserves its completion label for the actual ending."""
    from unittest.mock import MagicMock

    from src.spacehack.menus._quest_log import render_quest_log
    from src.spacehack.engine import SCREEN_HEIGHT, SCREEN_WIDTH

    ctx = _ctx()
    _console = MagicMock()
    render_quest_log(
        _console, ctx,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
    )
    _handoff_text = [
        call.kwargs.get("string", call.args[2] if len(call.args) > 2 else "")
        for call in _console.print.call_args_list
    ]
    assert "Leave Mars" in _handoff_text
    assert "(main quest complete)" not in _handoff_text

    ctx.main_quest_complete = True
    _console.reset_mock()
    render_quest_log(
        _console, ctx,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
    )
    _final_text = [
        call.kwargs.get("string", call.args[2] if len(call.args) > 2 else "")
        for call in _console.print.call_args_list
    ]
    assert "(main quest complete)" in _final_text


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
        "_pygame_orbit_choice",
        lambda _ctx: _modal_calls.append(True) or "diagnostic_fragment",
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
    assert ctx.main_quest_disclosure == "diagnostic_fragment"
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
        "_pygame_orbit_choice",
        lambda _ctx: "diagnostic_fragment",
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
    assert ctx.main_quest_disclosure == "diagnostic_fragment"
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
        "_pygame_orbit_choice",
        lambda _ctx: "diagnostic_fragment",
    )

    assert not _act1.maybe_show_post_prison_orbit(ctx)
    assert _act1.maybe_show_post_prison_orbit(ctx, from_mars_prison=True)
    assert ctx.post_prison_orbit_seen
    assert ctx.main_quest_disclosure == "diagnostic_fragment"


def test_pygame_orbit_guide_reopens_choice_before_disclosure(monkeypatch):
    ctx = _ctx()
    _choices = iter(("__GUIDE__", "archive_sealed"))
    _calls = []

    monkeypatch.setattr(
        _act1,
        "_pygame_orbit_choice",
        lambda _ctx: _calls.append(True) or next(_choices),
    )

    assert _act1.maybe_show_post_prison_orbit(ctx)
    assert _calls == [True, True]
    assert ctx.post_prison_orbit_seen
    assert ctx.main_quest_disclosure == "archive_sealed"


def test_interrupted_orbit_scene_preserves_choice_until_confirmation(monkeypatch):
    ctx = _ctx()
    ctx.context = SimpleNamespace(present=lambda _console: None)
    ctx.time_day = 1
    ctx.time_month = 1
    ctx.time_year = 2200
    _choices = iter(("__QUIT__", "diagnostic_fragment"))
    monkeypatch.setattr(
        _act1,
        "_pygame_orbit_choice",
        lambda _ctx: next(_choices),
    )

    assert not _act1.maybe_show_post_prison_orbit(ctx)
    assert not ctx.post_prison_orbit_seen
    assert not ctx.main_quest_disclosure

    assert _act1.maybe_show_post_prison_orbit(ctx)
    assert ctx.post_prison_orbit_seen
    assert ctx.main_quest_disclosure == "diagnostic_fragment"


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


def test_disclosure_choices_use_context_appropriate_handoffs():
    for choice in _act1.OrbitDisclosure:
        ctx = _ctx()
        ctx.time_day = 1
        ctx.time_month = 1
        ctx.time_year = 2200

        _act1._apply_disclosure(ctx, choice)

        assert ctx.post_prison_orbit_seen
        assert ctx.main_quest_disclosure == choice.value
        if choice is _act1.OrbitDisclosure.ARCHIVE_SEALED:
            assert ctx.main_quest_progress["research_alpha"] == "available"
            assert not ctx.main_quest_gate
            _title, _description = current_main_quest_objective(ctx)
            assert _title == "Deliver the sealed archive"
            assert "intact recovered archive" in _description
            assert "Alpha Centauri" in _description
            assert any("ready for delivery" in entry.text for entry in ctx.log.recent(n=6))
        else:
            assert "research_alpha" not in ctx.main_quest_progress
            assert ctx.main_quest_gate["research_alpha"] == (1, 3, 2200)
            _title, _description = current_main_quest_objective(ctx)
            if choice is _act1.OrbitDisclosure.DIAGNOSTIC_FRAGMENT:
                assert _title == "Awaiting fragment analysis..."
                assert "diagnostic fragment" in _description
            else:
                assert _title == "Awaiting a secure handoff..."
                assert "secure route" in _description
            assert "Alpha Centauri" in _description
            assert any("handoff requires time" in entry.text for entry in ctx.log.recent(n=6))


def test_research_handoff_starts_processing_gate_then_unlocks_report(monkeypatch):
    ctx = _ctx()
    monkeypatch.setattr(
        "src.spacehack.main_quest._objectives.show_step_readout",
        lambda _ctx, _step: None,
    )
    ctx.main_quest_progress["research_alpha"] = "available"
    ctx.time_day = 1
    ctx.time_month = 1
    ctx.time_year = 2200
    ctx.stats = SimpleNamespace(credits=0)
    ctx.player_xp = 0
    ctx.player_level = 1
    ctx.player_skill_points = 0
    ctx.player_traits = []
    ctx.player_counters = SimpleNamespace()
    ctx.player_gunnery_bonus = 0
    ctx.player_piloting_bonus = 0
    ctx.player_engineering_bonus = 0

    assert maybe_complete_visit(ctx, "research_officer")
    assert ctx.main_quest_progress["research_alpha"] == "completed"
    assert ctx.main_quest_gate["research_alpha_report"] == (15, 1, 2200)
    _title, _description = current_main_quest_objective(ctx)
    assert _title == "Awaiting the first translation..."
    assert "processing cluster" in _description

    ctx.time_day = 15
    assert check_quest_gates(ctx)
    assert not ctx.main_quest_gate
    assert ctx.main_quest_progress["research_alpha_report"] == "available"
    assert "initial translation" in ctx.main_quest_pending_message


def test_old_instant_research_completion_migrates_to_translation_gate():
    ctx = _ctx()
    ctx.time_day = 1
    ctx.time_month = 1
    ctx.time_year = 2200
    ctx.main_quest_progress["research_alpha"] = "completed"

    assert not check_quest_gates(ctx)
    assert ctx.main_quest_gate["research_alpha_report"] == (15, 1, 2200)
    _title, _description = current_main_quest_objective(ctx)
    assert _title == "Awaiting the first translation..."
    assert "processing cluster" in _description


def test_old_sealed_archive_gate_migrates_to_immediate_delivery():
    ctx = _ctx()
    ctx.main_quest_disclosure = "archive_sealed"
    ctx.main_quest_gate["research_alpha"] = (1, 3, 2200)
    ctx.main_quest_pending_message = "The old sealed-archive summon."

    assert not check_quest_gates(ctx)
    assert ctx.main_quest_progress["research_alpha"] == "available"
    assert not ctx.main_quest_gate
    assert not ctx.main_quest_pending_message


def test_gate_refreshes_stale_saved_act1_summon_text():
    ctx = _ctx()
    ctx.main_quest_progress["research_alpha"] = "available"
    ctx.main_quest_pending_message = (
        "The archive comparison is ready. Report to the Research Officer at "
        "Alpha Centauri's Science Port when you choose; the work will wait "
        "for you, but the signal will not become clearer on its own."
    )
    ctx.main_quest_pending_objective = "Take the archive to Alpha Centauri."

    assert not check_quest_gates(ctx)

    assert "archive handoff is ready" in ctx.main_quest_pending_message
    assert not ctx.main_quest_pending_message.startswith(
        "The archive comparison is ready."
    )


def test_preliminary_review_breadcrumb_is_consistent_for_every_faction():
    for _faction in ("militia", "merchants", "bar", "lab"):
        ctx = _ctx()
        ctx.main_quest_chain = _faction
        ctx.time_day = 1
        ctx.time_month = 1
        ctx.time_year = 2200

        _act1._apply_disclosure(ctx, _act1.OrbitDisclosure.DIAGNOSTIC_FRAGMENT)

        _title, _description = current_main_quest_objective(ctx)
        assert _title == "Awaiting fragment analysis..."
        assert _faction.capitalize() not in _title
        assert "diagnostic fragment" in _description
        assert "Alpha Centauri" in _description
        assert "independent reading" in _description

        ctx = _ctx()
        ctx.main_quest_chain = _faction
        ctx.time_day = 1
        ctx.time_month = 1
        ctx.time_year = 2200
        _act1._apply_disclosure(ctx, _act1.OrbitDisclosure.SAFE_DESTINATION)

        _title, _description = current_main_quest_objective(ctx)
        assert _title == "Awaiting a secure handoff..."
        assert "secure route" in _description
        assert "diagnostic fragment" not in _description
        assert "Alpha Centauri" in _description


def test_schedule_next_step_is_idempotent_and_can_unlock_after_gate():
    ctx = _ctx()
    ctx.time_day = 1
    ctx.time_month = 1
    ctx.time_year = 2200

    assert _schedule_next_step(ctx, "act1_prison", next_step_id="research_alpha")
    assert not _schedule_next_step(ctx, "act1_prison", next_step_id="research_alpha")
    ctx.time_day = 1
    ctx.time_month = 3
    ctx.time_year = 2200
    assert check_quest_gates(ctx)
    assert ctx.main_quest_progress["research_alpha"] == "available"
    assert not ctx.main_quest_gate
    assert "archive handoff is ready" in ctx.main_quest_pending_message
    assert "Alpha Centauri" in ctx.main_quest_pending_message
    assert "Alpha Centauri" in ctx.main_quest_pending_objective
    assert "archive comparison is ready" not in ctx.main_quest_pending_message


# ----- Wolf 359 b delve: camp + cache + guardians (doc 32 iteration) ----


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
    assert params.cache_guardian_count == 2
    assert set(params.cache_guardian_pool) == {"sentry_drone"}


def test_wolf_delve_stamps_camp_cache_and_guardians():
    """prepare_delve_site: the camp stamps, the cache lands inside it
    (deepest interior cell), and two sentry guardians hold the room."""
    from types import SimpleNamespace

    from src.spacehack.data.planets import find_planet_spec
    from src.spacehack.dungeon import generate_dungeon
    from src.spacehack.engine import seed_rng
    from src.spacehack.main_quest._act0 import prepare_delve_site

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
