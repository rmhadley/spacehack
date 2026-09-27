"""Tests for the doc 49 phase-2 class layer — data + rep tables.

Pins SETTLED 4-7 verbatim: per-class spreads on the +6 stat-point
budget, starting credits, the re-ruled `_CLASS_REP` effective
standings, and SETTLED 5's universal "hull HP is ship + modules"
ruling (no `hp_base` field, no hull readout on HudStats).
"""

from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.character import starting_pilot_skills, starting_ground_stats, starting_stats
from src.spacehack.data.classes import find_class, list_classes
from src.spacehack.faction import starting_reputation


# class_id -> (gunnery, piloting, engineering, reflexes, strength, stamina)
# class-only contribution at creation (spread on top of base 10).
_EXPECTED_SPREADS: dict[str, tuple[int, int, int, int, int, int]] = {
    "pirate": (3, 0, 0, 0, 3, 0),
    "merchant": (0, 0, 4, 0, 0, 2),
    "bounty_hunter": (2, 2, 0, 2, 0, 0),
}

_EXPECTED_CREDITS: dict[str, int] = {
    "pirate": 25,
    "merchant": 75,
    "bounty_hunter": 50,
}

# Effective starting standings per class (defaults + class deltas,
# clamped) — the numbers the class card's rep row shows (SETTLED 5/6/7).
_EXPECTED_EFFECTIVE_REP: dict[str, dict[str, int]] = {
    "pirate": {"pirate": -70, "merchant": -10, "militia": 30},
    "merchant": {"pirate": -100, "merchant": 30, "militia": 50},
    "bounty_hunter": {"pirate": -100, "merchant": 10, "militia": 70},
}


def test_roster_is_the_three_settled_classes_in_menu_order():
    assert [c.id for c in list_classes()] == [
        "pirate", "merchant", "bounty_hunter",
    ]


def test_every_class_spread_matches_settled_rulings():
    for cid, expected in _EXPECTED_SPREADS.items():
        spec = find_class(cid)
        got = (
            spec.skill_bonus.gunnery,
            spec.skill_bonus.piloting,
            spec.skill_bonus.engineering,
            spec.ground_bonus.reflexes,
            spec.ground_bonus.strength,
            spec.ground_bonus.stamina,
        )
        assert got == expected, f"{cid}: expected {expected}, got {got}"


def test_every_class_spends_exactly_the_six_point_budget():
    """SETTLED 4: the class layer mirrors the species +6 pool (read
    off the live spec, not the fixture above)."""
    for spec in list_classes():
        spent = (
            spec.skill_bonus.gunnery + spec.skill_bonus.piloting
            + spec.skill_bonus.engineering + spec.ground_bonus.reflexes
            + spec.ground_bonus.strength + spec.ground_bonus.stamina
        )
        assert spent == 6, f"{spec.id} stat budget: got {spent}"


def test_credits_match_settled_rulings():
    for cid, expected in _EXPECTED_CREDITS.items():
        assert find_class(cid).credits == expected, cid


def test_effective_starting_rep_matches_settled_tables():
    for cid, expected in _EXPECTED_EFFECTIVE_REP.items():
        result = starting_reputation("human", cid)
        for faction, rep in expected.items():
            assert result[faction] == rep, (
                f"{cid} vs {faction}: expected {rep}, got {result[faction]}"
            )


def test_hp_base_field_is_gone():
    """SETTLED 5 (universal): hull HP is ship + modules, never a class
    stat — the field must not exist on the spec."""
    assert "hp_base" not in {f.name for f in fields(find_class("pirate"))}


def test_starting_stats_carries_no_hull_readout():
    """HudStats starts with credits + skills only (doc 49 SETTLED 5)."""
    stats = starting_stats("human", "pirate")
    assert not hasattr(stats, "hp")
    assert not hasattr(stats, "max_hp")
    assert stats.credits == 25


def test_human_combined_start_values_per_class():
    """The card's combined rows: human (all 11s) + each class spread."""
    skills = starting_pilot_skills("human", "pirate")
    assert (skills.gunnery, skills.piloting, skills.engineering) == (14, 11, 11)
    ground = starting_ground_stats("human", "pirate")
    assert (ground.reflexes, ground.strength, ground.stamina) == (11, 14, 11)

    skills = starting_pilot_skills("human", "merchant")
    assert (skills.gunnery, skills.piloting, skills.engineering) == (11, 11, 15)
    ground = starting_ground_stats("human", "merchant")
    assert (ground.reflexes, ground.strength, ground.stamina) == (11, 11, 13)

    skills = starting_pilot_skills("human", "bounty_hunter")
    assert (skills.gunnery, skills.piloting, skills.engineering) == (13, 13, 11)
    ground = starting_ground_stats("human", "bounty_hunter")
    assert (ground.reflexes, ground.strength, ground.stamina) == (13, 11, 11)


# ---------------------------------------------------------------------------
# Class trait layer (doc 49 phase 2, step 2) — registry + two-trait grant
# ---------------------------------------------------------------------------

from src.spacehack.data.traits.core import ALL_TRAITS, CLASS_TRAITS, trait_name


# The user-approved card wording, verbatim (SETTLED 5/6/7 + brief).
_EXPECTED_DESCRIPTIONS: dict[str, str] = {
    "pirate": "+10 smuggler's hold on every ship\nFirst attack: +hit, +damage",
    "merchant": "+10 cargo space on every ship\n+5% sell, -5% buy at stations",
    "bounty_hunter": (
        "+5% evade in space and ground combat\nMissile racks hold double"
    ),
}


def test_class_traits_registry_names_and_descriptions_verbatim():
    assert set(CLASS_TRAITS) == {"pirate", "merchant", "bounty_hunter"}
    for tid, desc in _EXPECTED_DESCRIPTIONS.items():
        trait = CLASS_TRAITS[tid]
        assert trait.name == find_class(tid).name, tid
        assert trait.description == desc, tid


def test_class_trait_ids_match_their_class_spec():
    for spec in list_classes():
        assert spec.trait_id == spec.id


def test_trait_name_resolves_class_traits():
    assert trait_name("pirate") == "Pirate"
    assert trait_name("merchant") == "Merchant"
    assert trait_name("bounty_hunter") == "Bounty Hunter"


def test_class_traits_never_appear_in_the_milestone_pool():
    milestone_ids = {t.id for t in ALL_TRAITS}
    assert not (set(CLASS_TRAITS) & milestone_ids)


def test_two_trait_creation_grant_per_class_and_species_sample():
    """Every fresh character holds exactly two traits: species' + class'."""
    from types import SimpleNamespace

    from src.spacehack import message_log, world
    from src.spacehack.data.species import find_species
    from src.spacehack.game_context import GameContext
    from src.spacehack.game_loop import _configure_new_context
    from src.spacehack.hud import HudStats

    def _fresh_ctx(species_id, class_id):
        _tiles = [[world.Tile("floor", ".", True, (200, 200, 200), (0, 0, 0))]
                  for _ in range(3)]
        return GameContext(
            context=SimpleNamespace(),
            character_info={"species_id": species_id, "class_id": class_id},
            log=message_log.MessageLog(capacity=4),
            game_map=world.GameMap(width=1, height=3, tiles=_tiles, entities=[]),
            player=world.Entity(
                char="@", fg=(255, 255, 255),
                pos=world.Position(0, 1), name="Player",
            ),
            stats=HudStats(credits=50),
        )

    for species_id in ("human", "martian", "lalandan"):
        for class_id in ("pirate", "merchant", "bounty_hunter"):
            ctx = _fresh_ctx(species_id, class_id)
            _configure_new_context(ctx, species_id, class_id, False)
            assert ctx.player_traits == [
                find_species(species_id).trait_id, class_id,
            ], f"{species_id} x {class_id}"
