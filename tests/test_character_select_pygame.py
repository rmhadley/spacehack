"""Tests for the Pygame character-creation presentation seam."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import input_helpers, pygame_menu, ui


def test_character_picker_frames_reserve_descriptions_for_every_selection():
    menu = ui.MenuScreen(
        title="Choose Your Species",
        instruction="ARROW KEYS navigate - ENTER select - ESC start over",
        options=(("human", "Human"), ("martian", "Martian")),
        descriptions={
            "human": "A long human description.",
            "martian": "A much longer Martian description with more detail.",
        },
    )

    frames = input_helpers._pygame_pick_frames(menu)

    assert len(frames) == 2
    assert [item.action for item in frames[0].items] == ["human", "martian"]
    assert frames[0].items[1].description == menu.descriptions["martian"]
    assert frames[0].selected == 0
    assert frames[1].selected == 1
    assert frames[0].items == frames[1].items


def test_character_confirm_frame_keeps_identity_and_credits_in_fixed_menu():
    species = SimpleNamespace(
        name="Martian",
        description="Adapted to the red planet.",
    )
    klass = SimpleNamespace(
        name="Merchant",
        description="A capable trader.",
        credits=75,
    )

    frame = input_helpers._pygame_confirm_frame(species, klass)

    assert frame.title == "CHARACTER CREATION"
    assert "MARTIAN MERCHANT" in frame.body
    assert "SPECIES: Adapted to the red planet." in frame.body
    assert "CLASS: A capable trader." in frame.body
    assert frame.items[0].label == "BEGIN JOURNEY"
    assert frame.items[0].description == "Starting credits: 75$"
    assert frame.items[0].action == "CONFIRM"


def test_run_pick_uses_shared_pygame_menu_and_preserves_opaque_species_id(monkeypatch):
    menu = ui.MenuScreen(
        "Choose Your Species", "hint", (("human", "Human"),), {"human": "desc"},
    )
    captured = {}

    monkeypatch.setattr(input_helpers, "_pygame_character_enabled", lambda: True)
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda context, frames, **kwargs: captured.update(
            context=context, frames=frames,
        ) or ("SELECT", "human", 0),
    )

    outcome, selected_id = input_helpers._run_pick(SimpleNamespace(), menu)

    assert outcome is input_helpers.Outcome.CONFIRM
    assert selected_id == "human"
    assert captured["frames"][0].items[0].action == "human"


def test_run_confirm_maps_pygame_terminal_outcomes(monkeypatch):
    species = SimpleNamespace(name="Human", description="Adaptable.")
    klass = SimpleNamespace(name="Pirate", description="Dangerous.", credits=25)
    monkeypatch.setattr(input_helpers, "find_species", lambda _id: species)
    monkeypatch.setattr(input_helpers, "find_class", lambda _id: klass)
    monkeypatch.setattr(input_helpers, "_pygame_character_enabled", lambda: True)
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: ("SELECT", "CONFIRM", 0),
    )

    assert input_helpers._run_confirm(SimpleNamespace(), "human", "pirate") is input_helpers.Outcome.CONFIRM


def test_character_picker_rejects_non_character_menu_without_tcod_fallback():
    menu = ui.MenuScreen(
        "Choose", "hint", (("human", "Human"),), {"human": "desc"},
    )

    try:
        input_helpers._run_pick(SimpleNamespace(), menu)
    except RuntimeError as exc:
        assert "requires the shared Pygame runtime" in str(exc)
    else:
        raise AssertionError("non-character menus must use the shared Pygame runtime")


def test_character_picker_ignores_guide_then_preserves_quit(monkeypatch):
    menu = ui.MenuScreen(
        "Choose Your Species", "hint", (("human", "Human"),), {"human": "desc"},
    )
    outcomes = iter((("GUIDE", "", 0), ("QUIT", "", 0)))
    monkeypatch.setattr(input_helpers, "_pygame_character_enabled", lambda: True)
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: next(outcomes),
    )

    assert input_helpers._run_pick(SimpleNamespace(), menu) == (
        input_helpers.Outcome.QUIT,
        None,
    )


def test_character_picker_rejects_invalid_action_without_tcod_fallback(monkeypatch):
    menu = ui.MenuScreen(
        "Choose Your Class", "hint", (("merchant", "Merchant"),), {"merchant": "desc"},
    )
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: ("SELECT", "not-a-class", 0),
    )

    try:
        input_helpers._run_pick(SimpleNamespace(), menu)
    except RuntimeError as exc:
        assert "returned no outcome" in str(exc)
    else:
        raise AssertionError("invalid Pygame actions must be rejected explicitly")


def test_empty_character_picker_rejects_missing_pygame_outcome():
    menu = ui.MenuScreen("Choose Your Species", "hint", (), {})

    try:
        input_helpers._run_pick(SimpleNamespace(), menu)
    except RuntimeError as exc:
        assert "returned no outcome" in str(exc)
    else:
        raise AssertionError("empty character pickers must be rejected explicitly")


def test_character_confirm_ignores_guide_then_preserves_quit(monkeypatch):
    species = SimpleNamespace(name="Human", description="Adaptable.")
    klass = SimpleNamespace(name="Pirate", description="Dangerous.", credits=25)
    monkeypatch.setattr(input_helpers, "find_species", lambda _id: species)
    monkeypatch.setattr(input_helpers, "find_class", lambda _id: klass)
    monkeypatch.setattr(input_helpers, "_pygame_character_enabled", lambda: True)
    outcomes = iter((("GUIDE", "", 0), ("QUIT", "", 0)))
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: next(outcomes),
    )

    assert input_helpers._run_confirm(SimpleNamespace(), "human", "pirate") is input_helpers.Outcome.QUIT
