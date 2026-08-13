"""Tests for the player-facing in-game manual catalog and presenter contract."""

from types import SimpleNamespace

from src.spacehack import help as game_help
from src.spacehack.data.guide import GUIDE_SECTIONS


def test_guide_titles_are_unique_and_context_topics_exist():
    titles = [section.title for section in GUIDE_SECTIONS]

    assert len(titles) == len(set(titles))
    assert {
        "Trading & Economy",
        "Missions",
        "Ships & Equipment",
        "Navigation & Jump Gates",
        "Character & Skills",
        "NPCs & Factions",
    } <= set(titles)


def test_guide_sections_are_concise_and_nonempty():
    assert GUIDE_SECTIONS
    assert all(section.title.strip() for section in GUIDE_SECTIONS)
    assert all(section.body.strip() for section in GUIDE_SECTIONS)
    assert max(len(section.body) for section in GUIDE_SECTIONS) < 3000


def test_guide_is_player_facing_and_spoiler_free():
    manual = "\n".join(
        f"{section.title}\n{section.body}" for section in GUIDE_SECTIONS
    ).casefold()

    forbidden_terms = (
        "developer mode",
        "procedural",
        "implementation",
        "is_smuggle",
        "floor 5",
        "act 1",
        "rng",
        "formula",
        "clamped",
    )
    assert not any(term in manual for term in forbidden_terms)


def test_guide_index_handles_contextual_and_invalid_topics():
    assert game_help._guide_index(None) is None
    assert game_help._guide_index("  missions ") == next(
        index for index, section in enumerate(GUIDE_SECTIONS)
        if section.title == "Missions"
    )
    assert game_help._guide_index(0) == 0
    assert game_help._guide_index(-1) is None
    assert game_help._guide_index(len(GUIDE_SECTIONS)) is None
    assert game_help._guide_index("missing topic") is None


def test_guide_rejects_malformed_section_actions(monkeypatch):
    monkeypatch.setattr(
        "src.spacehack.pygame_screen.run_for_context",
        lambda *_args, **_kwargs: ("SELECT", "SECTION:not-an-index", 0),
    )

    result = game_help._run_pygame_help(SimpleNamespace(context=None))

    assert result is None
