"""Tests for developer-only playtesting shortcuts."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import src.spacehack.dev_mode as dev_mode
from src.spacehack.dev_mode import (
    advance_main_quest,
    apply_dev_ground_loadout,
    main_quest_faction_menu,
    _best_ground_armor,
    _best_ground_weapon,
    _dev_faction_label,
)
from src.spacehack.input_helpers import _is_shift_o_press
from src.spacehack.pygame_engine import PygameInputEvent
from src.spacehack.ground_equipment import GroundWeaponInstance


def _key_o(shift: bool) -> PygameInputEvent:
    """Build an O key event with the requested modifier state."""
    return PygameInputEvent(kind="keydown", key_name="o", shift=shift)


def test_shift_o_predicate_requires_shift_modifier():
    """Only shifted O activates the dev shortcut."""
    assert _is_shift_o_press(_key_o(True))
    assert _is_shift_o_press(_key_o(True))
    assert not _is_shift_o_press(_key_o(False))
    assert not _is_shift_o_press(SimpleNamespace())


def test_main_quest_faction_menu_lists_all_four_chains():
    """The Act 0 shortcut exposes every normal faction path."""
    _menu = main_quest_faction_menu()

    assert _menu.options == (
        ("militia", "Militia"),
        ("merchants", "Merchants"),
        ("bar", "Free Captains"),
        ("lab", "Research Lab"),
    )
    assert set(_menu.descriptions) == {"militia", "merchants", "bar", "lab"}


def test_pygame_faction_frames_keep_fixed_descriptions_and_ids():
    """Dev faction items use the shared menu's stable descriptions."""
    frames = dev_mode._pygame_faction_frames(main_quest_faction_menu())

    assert len(frames) == 4
    assert [item.action for item in frames[0].items] == [
        "militia", "merchants", "bar", "lab",
    ]
    assert frames[0].items[0].description == (
        "Order, procedure, and a sanctioned breach."
    )
    assert frames[2].selected == 2
    assert frames[2].items[2].label == "Free Captains"


def test_pygame_faction_picker_maps_select_and_preserves_outcome(monkeypatch):
    """Pygame selection returns the same opaque faction ID and Outcome."""
    from src.spacehack import pygame_menu

    monkeypatch.setattr(pygame_menu, "run_for_context", lambda *args, **kwargs: (
        "SELECT", "lab", 3,
    ))

    result = dev_mode._run_pygame_faction_pick(
        object(), main_quest_faction_menu(),
    )

    assert result == (dev_mode.Outcome.CONFIRM, "lab")


def test_pygame_faction_picker_ignores_guide_like_legacy_picker(monkeypatch):
    """GUIDE is a no-op here because the legacy dev picker has no guide route."""
    from src.spacehack import pygame_menu

    outcomes = iter((("GUIDE", "", 0), ("SELECT", "militia", 0)))
    monkeypatch.setattr(pygame_menu, "run_for_context", lambda *args, **kwargs: next(outcomes))

    assert dev_mode._run_pygame_faction_pick(
        object(), main_quest_faction_menu(),
    ) == (dev_mode.Outcome.CONFIRM, "militia")


def test_pygame_faction_picker_rejects_invalid_action_and_empty_menu(monkeypatch):
    """Invalid worker data and empty menus remain safe fallback cases."""
    from src.spacehack import pygame_menu, ui

    monkeypatch.setattr(pygame_menu, "run_for_context", lambda *args, **kwargs: (
        "SELECT", "not-a-faction", 0,
    ))
    assert dev_mode._run_pygame_faction_pick(
        object(), main_quest_faction_menu(),
    ) is None

    empty = ui.MenuScreen(
        title="Empty", instruction="", options=(), descriptions={},
    )
    assert dev_mode._run_pygame_faction_pick(object(), empty) is None


def test_choose_main_quest_faction_uses_pygame_when_enabled(monkeypatch):
    """The developer shortcut routes through the shared menu when active."""
    from src.spacehack import pygame_menu

    seen = {}
    monkeypatch.setattr(pygame_menu, "enabled", lambda: True)
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda context, frames, **kwargs: seen.update(
            context=context, frames=frames,
        ) or ("SELECT", "bar", 2),
    )

    context = object()
    assert dev_mode.choose_main_quest_faction(context) == (
        dev_mode.Outcome.CONFIRM, "bar",
    )
    assert seen["context"] is context
    assert seen["frames"][0].items[2].action == "bar"


def test_pygame_faction_picker_maps_back_quit_and_propagates_failure(monkeypatch):
    """Cancel/quit remain distinct, while worker failure is explicit."""
    from src.spacehack import pygame_menu

    monkeypatch.setattr(pygame_menu, "run_for_context", lambda *args, **kwargs: (
        "BACK", "", 0,
    ))
    assert dev_mode._run_pygame_faction_pick(
        object(), main_quest_faction_menu(),
    ) == (dev_mode.Outcome.BACK, None)

    monkeypatch.setattr(pygame_menu, "run_for_context", lambda *args, **kwargs: (
        "QUIT", "", 0,
    ))
    assert dev_mode._run_pygame_faction_pick(
        object(), main_quest_faction_menu(),
    ) == (dev_mode.Outcome.QUIT, None)

    def unavailable(*args, **kwargs):
        raise pygame_menu.PygameMenuUnavailable("missing")

    monkeypatch.setattr(pygame_menu, "run_for_context", unavailable)
    try:
        dev_mode._run_pygame_faction_pick(
            object(), main_quest_faction_menu(),
        )
    except pygame_menu.PygameMenuUnavailable as exc:
        assert str(exc) == "missing"
    else:
        raise AssertionError("dev faction picker must not fall back to an unavailable renderer")


def test_choose_main_quest_faction_delegates_to_picker(monkeypatch):
    """The UI wrapper returns the picker result without mutating game state."""
    _expected = (dev_mode.Outcome.CONFIRM, "lab")
    _seen = []

    def _fake_pick(context, menu):
        _seen.append((context, menu))
        return _expected

    monkeypatch.setattr(dev_mode, "_run_pygame_faction_pick", _fake_pick)
    _context = object()

    assert dev_mode.choose_main_quest_faction(_context) == _expected
    assert _seen[0][0] is _context
    assert _seen[0][1].selected_id == "militia"


@pytest.mark.parametrize("faction_id", ("militia", "merchants", "bar", "lab"))
def test_advance_main_quest_records_selected_faction(faction_id):
    """The shortcut creates door state and mirrors normal faction lock-in."""
    _ctx = SimpleNamespace(
        main_quest_progress={},
        main_quest_chain="",
        main_quest_backing=set(),
        log=MagicMock(),
    )

    advance_main_quest(_ctx, faction_id)

    assert _ctx.main_quest_chain == faction_id
    assert _ctx.main_quest_backing == {faction_id}
    assert _ctx.main_quest_progress == {
        "prologue_signal": "completed",
        "prologue_mars_unlocked": "completed",
        "prologue_mars_entrance": "completed",
        "prologue_seek_help": "completed",
        "prologue_open": "active",
    }
    _ctx.log.add.assert_called_once_with(
        f"[DEV MODE] Act 0 skipped as {_dev_faction_label(faction_id)} - "
        "the Mars door can now be opened."
    )


def test_advance_main_quest_rejects_unknown_faction():
    """Invalid developer input cannot create an impossible quest chain."""
    _ctx = SimpleNamespace(
        main_quest_progress={},
        main_quest_chain="",
        main_quest_backing=set(),
        log=MagicMock(),
    )

    with pytest.raises(ValueError, match="Unknown developer faction"):
        advance_main_quest(_ctx, "pirates")


def test_best_ground_armor_selects_highest_defense_per_slot():
    """Developer armor selection covers every slot with strongest gear."""
    assert _best_ground_armor() == {
        "head": "assault_helmet",
        "body": "powered_vest",
        "hands": "powered_gloves",
        "legs": "assault_greaves",
        "feet": "mag_boots",
    }


def test_best_ground_weapon_selects_highest_damage():
    """Developer weapon selection returns the single strongest weapon."""
    assert _best_ground_weapon() == "rocket_launcher"


def test_dev_ground_loadout_equips_rocket_launcher_pack_and_best_armor(monkeypatch):
    """Dev mode grants the complete ground loadout and logs it."""
    monkeypatch.setenv("SPACEHACK_DEV", "1")
    _ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        ground_expedition_inventory=[],
        ground_stats=SimpleNamespace(strength=10),
        log=MagicMock(),
    )

    apply_dev_ground_loadout(_ctx)

    assert _ctx.equipped_ground_weapons == [
        GroundWeaponInstance("rocket_launcher", 4),
    ]
    assert _ctx.equipped_ground_armor == {
        "head": "assault_helmet",
        "body": "powered_vest",
        "hands": "powered_gloves",
        "legs": "assault_greaves",
        "feet": "mag_boots",
    }
    assert [e.item_id for e in _ctx.ground_expedition_inventory] == [
        "plasma_caster", "railgun", "power_fist", "power_fist",
        "ion_blaster", "mono_blade",
    ]
    assert _ctx.ground_stats.strength == 30
    _ctx.log.add.assert_called_once_with(
        "[DEV MODE] Rocket Launcher equipped + T4 pack + best armor."
    )


def test_dev_ground_loadout_does_nothing_without_dev_flag(monkeypatch):
    """Normal new games retain their default empty ground loadout."""
    monkeypatch.delenv("SPACEHACK_DEV", raising=False)
    _ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        log=MagicMock(),
    )

    apply_dev_ground_loadout(_ctx)

    assert _ctx.equipped_ground_weapons == []
    assert _ctx.equipped_ground_armor == {}
    _ctx.log.add.assert_not_called()


def test_advance_main_quest_does_not_reopen_completed_door():
    """Repeating the shortcut cannot move an already-open door backward."""
    _ctx = SimpleNamespace(
        main_quest_progress={"prologue_open": "completed"},
        main_quest_chain="militia",
        main_quest_backing={"militia"},
        log=MagicMock(),
    )

    advance_main_quest(_ctx, "militia")

    assert _ctx.main_quest_progress["prologue_open"] == "completed"


# ----- Dev city teleport (Shift+T) --------------------------------------


def test_city_teleport_options_cover_every_ported_city():
    """Every landable spec appears exactly once, labelled with its system."""
    from src.spacehack.data.planets import has_landable_port, list_planet_specs

    options = dev_mode.city_teleport_options()
    ids = [planet_id for planet_id, _label in options]
    assert ids and len(ids) == len(set(ids))
    assert set(ids) == {
        spec.id for spec in list_planet_specs() if has_landable_port(spec.id)
    }
    by_id = dict(options)
    assert by_id["mars"] == "Mars - Sol"
    assert by_id["sirius_station"] == "Binary Station - Sirius"
    assert [label for _pid, label in options] == sorted(
        label for _pid, label in options
    )


def test_system_for_planet_resolves_planets_and_stations():
    from src.spacehack.data.solar_systems import system_for_planet

    assert system_for_planet("mars").id == "sol"
    assert system_for_planet("sirius_station").id == "sirius"
    assert system_for_planet("depot").id in {"epsilon_eridani", "tau_ceti"}
    with pytest.raises(KeyError):
        system_for_planet("no_such_city")


def test_land_at_city_switches_system_and_enters_city(monkeypatch):
    """Teleporting to a distant city switches the module-level system and
    lands through the production path: city mode, ids synced, player on
    the hangar apron."""
    from src.spacehack import game_interactions, solar_system as solar_module

    ctx = SimpleNamespace(
        current_city_id="earth",
        game_map=None,
        player=object(),
        militia_scanned=[],
        ground_hp=23,
        ground_max_hp=23,
    )
    state = game_interactions.GameLoopState(
        ctx=ctx,
        console=object(),
        map_w=40,
        map_h=24,
        log=SimpleNamespace(add=lambda _msg: None),
        stats=object(),
        game_map=object(),
        player=object(),
        current_mode="space",
        current_city_id="earth",
        player_owned_ship=None,
        player_active_missions=[],
    )
    monkeypatch.setattr(game_interactions, "_run_cargo_scan", lambda _ctx, _pid: None)
    monkeypatch.setattr(
        game_interactions.main_quest_module,
        "spawn_quest_npcs",
        lambda _ctx, _map, _pid, **_kw: None,
    )
    monkeypatch.setattr(
        game_interactions, "_animate_ship_to_y",
        lambda *_args, **_kw: None,
    )

    result = game_interactions.land_at_city(state, "tc_b")

    assert result == "CONTINUE"
    assert solar_module.current_solar_system_id == "tau_ceti"
    assert state.current_mode == "city"
    assert state.current_city_id == "tc_b"
    assert ctx.current_city_id == "tc_b"
    assert ctx.game_map is state.game_map
    assert state.player in state.game_map.entities
    # Cleanup: restore the default system other tests rely on.
    solar_module.set_current_solar_system("sol")


def test_land_at_city_rejects_portless_planet():
    from src.spacehack import game_interactions

    messages = []
    state = SimpleNamespace(
        ctx=SimpleNamespace(militia_scanned=[], ground_hp=23, ground_max_hp=23),
        log=SimpleNamespace(add=messages.append),
    )

    result = game_interactions.land_at_city(state, "no_such_city")

    assert result == "CONTINUE"
    assert messages and "no port" in messages[0]


def test_shift_s_predicate_requires_shift_modifier():
    from src.spacehack.input_helpers import _is_shift_s_press

    pressed = PygameInputEvent(kind="keydown", key_name="s", shift=True)
    assert _is_shift_s_press(pressed)
    bare = PygameInputEvent(kind="keydown", key_name="s")
    assert not _is_shift_s_press(bare)
    other = PygameInputEvent(kind="keydown", key_name="x", shift=True)
    assert not _is_shift_s_press(other)


def test_reroll_run_seed_reseeds_fresh_entropy():
    """The dev reroll always produces NEW entropy — even under a pinned
    SPACEHACK_SEED, a manual reroll wants new randomness."""
    import os

    import src.spacehack.engine as engine
    from src.spacehack.engine import reroll_run_seed

    old = os.environ.pop("SPACEHACK_SEED", None)
    try:
        os.environ["SPACEHACK_SEED"] = "99"
        first = reroll_run_seed()
        state_after_first = engine.RNG.getstate()  # via module: seed_rng rebinds RNG
        second = reroll_run_seed()
        assert first != 99 and second != 99, "manual reroll ignores the pin"
        assert first != second, "each reroll is fresh entropy"
        assert engine.RNG.getstate() != state_after_first
    finally:
        if old is not None:
            os.environ["SPACEHACK_SEED"] = old
