from tests.support.asyncutil import run, as_async
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
        as_async(lambda *_args, **_kwargs: ("SELECT", "SECTION:not-an-index", 0)),
    )

    result = run(game_help._run_pygame_help(SimpleNamespace(context=None)))

    assert result is None


def test_guide_controls_lists_weapon_set_swap():
    """Doc 51 phase 2: the X weapon-set swap carries a Controls entry."""
    controls = next(
        section for section in GUIDE_SECTIONS
        if section.title == "Controls & Keybindings"
    )
    assert "- X: swap weapon sets (free while exploring, 1 AP in combat)" in controls.body


def test_guide_ground_gear_describes_the_bandolier():
    """Doc 52.3: the ammunition paragraph teaches the bandolier (per-
    caliber reserves, armory/pickup top-ups, carry limits) — the pack-
    stack interaction is gone."""
    gear = next(
        section for section in GUIDE_SECTIONS if section.title == "Ground Gear"
    )
    assert (
        "Reloadable weapons draw from your ammo storage - the rounds "
        "you carry for each caliber, topped up at any armory or from "
        "battlefield pickups, up to a per-caliber carry limit." in gear.body
    )
    assert "Expedition Pack" not in gear.body.split("Consumables:")[0]
    assert "Buy ground ammo" not in gear.body
    assert "Melee and plasma weapons never need ammunition." in gear.body


def test_guide_ground_combat_reload_reads_bandolier():
    """Doc 52.3 audit catch: the Ground Combat R line stays store-agnostic
    to the bandolier, never the retired pack stack."""
    combat = next(
        section for section in GUIDE_SECTIONS if section.title == "Combat"
    )
    assert "press R to reload from your ammo storage." in combat.body
    assert "ammunition in your pack" not in combat.body


def test_guide_armory_intro_names_reserve_top_up():
    """Doc 52.3 audit catch: the armory intro no longer sells ground
    ammunition as stock — it tops up reserves."""
    gear = next(
        section for section in GUIDE_SECTIONS if section.title == "Ground Gear"
    )
    assert (
        "The armory terminal sells personal weapons and armour for when "
        "you leave your ship, and tops up your ammunition reserves." in gear.body
    )
    assert "ground \nammunition" not in gear.body
