"""Tests for the first post-prison Act 1 orbit beat."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import message_log
from src.spacehack.data.main_quest import find_main_quest_step
from src.spacehack.data.planets.ac_station import SPEC as AC_STATION
from src.spacehack.main_quest import _act1
from src.spacehack import __main__ as game_main


def _ctx():
    return SimpleNamespace(
        current_city_id="mars",
        post_prison_orbit_seen=False,
        main_quest_disclosure="",
        main_quest_progress={"act1_prison": "completed"},
        main_quest_chain="lab",
        dungeon_extension=SimpleNamespace(state_flags={"prison_data_extracted"}),
        log=message_log.MessageLog(capacity=6),
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


def test_mars_departure_helper_triggers_from_any_launch_path(monkeypatch):
    """City launch and prison-extension departure share one trigger."""
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


def test_orbit_scene_requires_extraction_and_mars_departure():
    ctx = _ctx()

    assert _act1._orbit_scene_is_ready(ctx)

    ctx.current_city_id = "earth"
    assert not _act1._orbit_scene_is_ready(ctx)

    ctx.current_city_id = "mars"
    ctx.dungeon_extension.state_flags.clear()
    assert not _act1._orbit_scene_is_ready(ctx)


def test_disclosure_choices_persist_and_unlock_research_alpha():
    for choice in _act1.OrbitDisclosure:
        ctx = _ctx()

        _act1._apply_disclosure(ctx, choice)

        assert ctx.post_prison_orbit_seen
        assert ctx.main_quest_disclosure == choice.value
        assert ctx.main_quest_progress["research_alpha"] == "available"
        assert any("first interpretation" in entry.text for entry in ctx.log.recent(n=6))


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
