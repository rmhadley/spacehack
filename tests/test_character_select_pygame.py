"""Tests for the Pygame character-creation presentation seam."""

from __future__ import annotations
from tests.support.asyncutil import run, as_async

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

    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        as_async(
            lambda context, frames, **kwargs: captured.update(
            context=context, frames=frames,
        ) or ("SELECT", "human", 0)
        ),
    )

    outcome, selected_id = run(input_helpers._run_pick(SimpleNamespace(), menu))

    assert outcome is input_helpers.Outcome.CONFIRM
    assert selected_id == "human"
    assert captured["frames"][0].items[0].action == "human"


def test_run_confirm_maps_pygame_terminal_outcomes(monkeypatch):
    species = SimpleNamespace(name="Human", description="Adaptable.")
    klass = SimpleNamespace(name="Pirate", description="Dangerous.", credits=25)
    monkeypatch.setattr(input_helpers, "find_species", lambda _id: species)
    monkeypatch.setattr(input_helpers, "find_class", lambda _id: klass)
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        as_async(lambda *args, **kwargs: ("SELECT", "CONFIRM", 0)),
    )

    assert run(input_helpers._run_confirm(SimpleNamespace(), "human", "pirate")) is input_helpers.Outcome.CONFIRM


def test_character_picker_rejects_non_character_menu_without_fallback():
    menu = ui.MenuScreen(
        "Choose", "hint", (("human", "Human"),), {"human": "desc"},
    )

    try:
        run(input_helpers._run_pick(SimpleNamespace(), menu))
    except RuntimeError as exc:
        assert "requires the shared Pygame runtime" in str(exc)
    else:
        raise AssertionError("non-character menus must use the shared Pygame runtime")


def test_character_picker_ignores_guide_then_preserves_quit(monkeypatch):
    menu = ui.MenuScreen(
        "Choose Your Species", "hint", (("human", "Human"),), {"human": "desc"},
    )
    outcomes = iter((("GUIDE", "", 0), ("QUIT", "", 0)))
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        as_async(lambda *args, **kwargs: next(outcomes)),
    )

    assert run(input_helpers._run_pick(SimpleNamespace(), menu)) == (
        input_helpers.Outcome.QUIT,
        None,
    )


def test_character_picker_rejects_invalid_action_without_fallback(monkeypatch):
    menu = ui.MenuScreen(
        "Choose Your Class", "hint", (("merchant", "Merchant"),), {"merchant": "desc"},
    )
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        as_async(lambda *args, **kwargs: ("SELECT", "not-a-class", 0)),
    )

    try:
        run(input_helpers._run_pick(SimpleNamespace(), menu))
    except RuntimeError as exc:
        assert "returned no outcome" in str(exc)
    else:
        raise AssertionError("invalid Pygame actions must be rejected explicitly")


def test_empty_character_picker_rejects_missing_pygame_outcome():
    menu = ui.MenuScreen("Choose Your Species", "hint", (), {})

    try:
        run(input_helpers._run_pick(SimpleNamespace(), menu))
    except RuntimeError as exc:
        assert "returned no outcome" in str(exc)
    else:
        raise AssertionError("empty character pickers must be rejected explicitly")


def test_character_confirm_ignores_guide_then_preserves_quit(monkeypatch):
    species = SimpleNamespace(name="Human", description="Adaptable.")
    klass = SimpleNamespace(name="Pirate", description="Dangerous.", credits=25)
    monkeypatch.setattr(input_helpers, "find_species", lambda _id: species)
    monkeypatch.setattr(input_helpers, "find_class", lambda _id: klass)
    outcomes = iter((("GUIDE", "", 0), ("QUIT", "", 0)))
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        as_async(lambda *args, **kwargs: next(outcomes)),
    )

    assert run(input_helpers._run_confirm(SimpleNamespace(), "human", "pirate")) is input_helpers.Outcome.QUIT


def test_stats_tab_lists_owned_identity_gear():
    """The rig and cut-out are visible on the C screen once owned —
    the Gear line lists only what's installed (doc 40 user report)."""
    from types import SimpleNamespace

    from src.spacehack.character_screen import _stats_frame

    def _ctx(**flags):
        base = dict(
            player_level=1, player_xp=0, player_skill_points=0,
            player_traits=[], character_info={},
            stats=SimpleNamespace(gunnery=10, piloting=10, engineering=10),
            ground_stats=SimpleNamespace(
                gunnery=10, piloting=10, engineering=10, stamina=10,
                force=10, resilience=10,
            ),
            transponder_cutout=False, transponder_rig=False,
        )
        base.update(flags)
        return SimpleNamespace(**base)

    _body = _stats_frame(_ctx(), "T", 0, 10, selected=0).body
    assert not any("Gear:" in line for line in _body), "nothing owned, no line"

    _body = _stats_frame(_ctx(transponder_rig=True), "T", 0, 10, selected=0).body
    _gear = [line for line in _body if line.startswith("Gear:")]
    assert _gear == ["Gear: clone rig"]

    _body = _stats_frame(
        _ctx(transponder_rig=True, transponder_cutout=True),
        "T", 0, 10, selected=0,
    ).body
    assert "Gear: transponder cut-out, clone rig" in _body


class TestSpeciesSplitPicker:
    """Doc 49 SETTLED 2: left cycling options, right the species card."""

    def test_left_options_follow_roster_order_with_species_ids(self):
        frame = ui.species_split_frame(0)
        assert [(row.label, row.action) for row in frame.left_rows] == [
            ("Human", "human"), ("Martian", "martian"),
            ("Cygnian", "cygnian"), ("Sirian", "sirian"),
            ("Lalandan", "lalandan"),
        ]

    def test_card_follows_the_selection(self):
        assert ui.species_split_frame(1).right_label == "@ - MARTIAN - Mars (Sol)"
        assert ui.species_split_frame(4).right_label == (
            "Q - LALANDAN - Whisper - the Vault (Lalande)"
        )

    def test_card_title_carries_identity_in_species_color(self):
        frame = ui.species_split_frame(2)
        assert frame.right_label == "& - CYGNIAN - Cygni b - the orbital yards (Cygni)"
        assert frame.right_label_color == (170, 130, 230)
        assert ui.species_split_frame(0).right_label == "@ - HUMAN - Earth (Sol)"

    def test_card_body_opens_straight_into_the_numbers(self):
        """The title carries identity; the body has no name/home rows."""
        labels = [row.label for row in ui.species_split_frame(1).right_rows]
        assert labels[0] == "--- STARTING STATS ---"
        assert not any("Home:" in label for label in labels)
        assert not any(label.startswith("Martian") for label in labels)

    def test_card_pins_settled_numbers(self):
        def _labels(index):
            return [row.label for row in ui.species_split_frame(index).right_rows]
        assert "Strength 12, Stamina 14, rest 10" in _labels(1)
        assert "Armor 2   HP 29" in _labels(1)
        assert "Reflexes 16, Strength 5, Stamina 5, rest 10" in _labels(4)
        assert "Armor 0   HP 22" in _labels(4)
        assert "All stats 11" in _labels(0)

    def test_card_bottom_shows_trait_name_and_description(self):
        labels = [row.label for row in ui.species_split_frame(1).right_rows]
        assert "Sturdy" in labels
        joined = " ".join(labels)
        assert "+2 armor defense and +2 melee damage" in joined

    def test_card_rows_fit_the_split_viewport(self):
        for index in range(5):
            assert len(ui.species_split_frame(index).right_rows) <= 11

    def test_run_species_pick_falls_back_to_generic_menu(self, monkeypatch):
        from src.spacehack import pygame_split
        captured = {}
        monkeypatch.setattr(pygame_split, "enabled", lambda: False)
        monkeypatch.setattr(
            pygame_menu,
            "run_for_context",
            as_async(
                lambda context, frames, **kwargs: captured.update(
                    frames=frames,
                ) or ("SELECT", "martian", 0)
            ),
        )
        outcome, species_id = run(input_helpers._run_species_pick(SimpleNamespace()))
        assert outcome is input_helpers.Outcome.CONFIRM
        assert species_id == "martian"
        assert captured["frames"][0].items[1].action == "martian"

    def test_run_species_pick_rejects_invalid_action(self, monkeypatch):
        """An invalid SELECT action maps to the None no-outcome result,
        which title_flow turns into a hard error."""
        from src.spacehack import pygame_split
        monkeypatch.setattr(pygame_split, "enabled", lambda: False)
        monkeypatch.setattr(
            pygame_menu,
            "run_for_context",
            as_async(lambda *args, **kwargs: ("SELECT", "not-a-species", 0)),
        )
        assert run(input_helpers._run_species_pick(SimpleNamespace())) is None
