"""Tests for the first post-prison Act 1 orbit beat."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import dungeon_extensions, message_log, ui, world
from src.spacehack.data.main_quest import find_main_quest_step
from src.spacehack.data.planets.ac_station import SPEC as AC_STATION
from src.spacehack.main_quest import _act1
from src.spacehack.main_quest._core import _schedule_next_step
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
    assert step.dialogues["research_officer"].option_label == (
        "Begin the first interpretation"
    )
    assert not step.auto_advance
    assert step.wait_days == 0

    prison = find_main_quest_step("act1_prison")
    assert not prison.auto_advance
    assert prison.wait_days == 60
    assert "preliminary archive review" in prison.ready_message
    assert "Alpha Centauri" in prison.ready_message


def test_alpha_centauri_station_keeps_both_research_contacts():
    _building_npcs = {building.npc_id for building in AC_STATION.buildings}

    assert {"archive_research_officer", "research_officer"} <= _building_npcs
    assert dict(AC_STATION.npc_overrides)["research_officer"].id == "xenolinguist"
    assert dict(AC_STATION.npc_overrides)["archive_research_officer"].id == "research_officer"


def test_prison_floor_one_departure_is_the_extension_exit_boundary():
    """Only Floor 1 of the alien prison counts as the `<` departure."""
    ctx = _ctx()
    ctx.dungeon_extension.extension_id = "mars_alien_prison"
    ctx.dungeon_extension.current_floor = 1
    assert game_main._is_prison_floor_one_departure(ctx)

    ctx.dungeon_extension.current_floor = 2
    assert not game_main._is_prison_floor_one_departure(ctx)

    ctx.dungeon_extension.current_floor = 1
    ctx.dungeon_extension.extension_id = "other_extension"
    assert not game_main._is_prison_floor_one_departure(ctx)


def test_generic_dungeon_exit_does_not_count_as_prison_departure():
    """A Mars derelict exit cannot accidentally launch the prison scene."""
    ctx = _ctx()
    ctx.dungeon_extension = SimpleNamespace(
        extension_id="other_extension",
        current_floor=1,
    )

    assert not game_main._is_prison_floor_one_departure(ctx)


def test_mars_departure_helper_triggers_from_mars_launch(monkeypatch):
    """The disclosure helper remains available for the actual Mars launch."""
    ctx = _ctx()
    _calls = []

    monkeypatch.setattr(
        game_main.main_quest_module,
        "maybe_show_post_prison_orbit",
        lambda _ctx: _calls.append(_ctx) or True,
    )

    assert game_main._maybe_show_post_prison_orbit(ctx, "mars")
    assert _calls == [ctx]
    assert not game_main._maybe_show_post_prison_orbit(ctx, "earth")
    assert _calls == [ctx]


def test_prison_exit_then_mars_launch_shows_orbit_disclosure_once(monkeypatch):
    """The real exit-then-launch sequence delivers the disclosure once."""
    import tcod.event

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

    monkeypatch.setattr(_act1, "make_console", lambda: object())
    monkeypatch.setattr(
        ui.Modal,
        "run",
        lambda _modal, _render, update: update(
            tcod.event.KeyDown(
                scancode=tcod.event.Scancode.RETURN,
                sym=ui._ENTER_SYMS[0],
                mod=0,
            )
        ),
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


def test_orbit_scene_requires_extraction_and_mars_departure():
    ctx = _ctx()

    assert _act1._orbit_scene_is_ready(ctx)

    ctx.current_city_id = "earth"
    assert not _act1._orbit_scene_is_ready(ctx)

    ctx.current_city_id = "mars"
    ctx.dungeon_extension.state_flags.clear()
    assert not _act1._orbit_scene_is_ready(ctx)


def test_disclosure_choices_schedule_research_after_a_sandbox_gate():
    for choice in _act1.OrbitDisclosure:
        ctx = _ctx()
        ctx.time_day = 1
        ctx.time_month = 1
        ctx.time_year = 2200

        _act1._apply_disclosure(ctx, choice)

        assert ctx.post_prison_orbit_seen
        assert ctx.main_quest_disclosure == choice.value
        assert "research_alpha" not in ctx.main_quest_progress
        assert ctx.main_quest_gate["research_alpha"] == (1, 3, 2200)
        _title, _description = current_main_quest_objective(ctx)
        assert _title == "Awaiting preliminary archive review..."
        assert "Alpha Centauri" in _description
        assert any("preliminary comparison" in entry.text for entry in ctx.log.recent(n=6))


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

    assert "preliminary archive review is complete" in ctx.main_quest_pending_message
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

        _act1._apply_disclosure(ctx, _act1.OrbitDisclosure.ARCHIVE_SEALED)

        _title, _description = current_main_quest_objective(ctx)
        assert _title == "Awaiting preliminary archive review..."
        assert _faction.capitalize() not in _title
        assert "Alpha Centauri" in _description
        assert "independent reading" in _description


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
    assert "preliminary archive review is complete" in ctx.main_quest_pending_message
    assert "Alpha Centauri" in ctx.main_quest_pending_message
    assert "Alpha Centauri" in ctx.main_quest_pending_objective
    assert "archive comparison is ready" not in ctx.main_quest_pending_message


def test_orbit_menu_navigation_wraps_and_escape_does_not_resolve():
    ctx = _ctx()
    selected = 0

    from src.spacehack import ui

    down = SimpleNamespace(sym=ui._DOWN_SYMS[0])
    escape = SimpleNamespace(sym=ui._ESCAPE_SYMS[0])

    import tcod.event

    selected = 0
    for _ in range(3):
        event = tcod.event.KeyDown(
            scancode=tcod.event.Scancode.DOWN,
            sym=down.sym,
            mod=0,
        )
        outcome, selected = _act1._update_orbit_scene(event, selected)
        assert outcome is _act1.OrbitSceneOutcome.IGNORE
    assert selected == 0

    outcome, selected = _act1._update_orbit_scene(
        tcod.event.KeyDown(
            scancode=tcod.event.Scancode.ESCAPE,
            sym=escape.sym,
            mod=0,
        ), selected,
    )
    assert outcome is _act1.OrbitSceneOutcome.CONFIRM
    assert selected == 1
