"""Tests for the doc 49 species layer — the five-species roster.

Pins SETTLED 1's table verbatim: per-species starting stats (base 10 +
spread, read species-only via an unknown class id), the +6 stat-point
budget, glyph/color/home/trait fields, and SETTLED 3-B's identical
starting reputation across every species.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.character import (
    GROUND_STAT_BASE,
    PILOT_SKILL_BASE,
)
from src.spacehack.data.species import find_species, list_species
from src.spacehack.faction import starting_reputation


# species_id -> (gunnery, piloting, engineering, reflexes, strength, stamina)
# at creation, species-only (base 10 + spread) — SETTLED 1's "start" column.
_EXPECTED_START_STATS: dict[str, tuple[int, int, int, int, int, int]] = {
    "human": (11, 11, 11, 11, 11, 11),
    "martian": (10, 10, 10, 10, 12, 14),
    "cygnian": (12, 14, 10, 10, 10, 10),
    "sirian": (14, 10, 10, 12, 10, 10),
    "lalandan": (10, 10, 10, 16, 5, 5),
}

# species_id -> (glyph, color, trait_id, hp_bonus)
_EXPECTED_IDENTITY: dict[str, tuple[str, tuple[int, int, int], str, int]] = {
    "human": ("@", (255, 255, 255), "fast_learner", 0),
    "martian": ("@", (130, 225, 90), "sturdy", 2),
    "cygnian": ("&", (170, 130, 230), "momentum", 0),
    "sirian": ("\u2666", (185, 215, 245), "longshot", 0),
    "lalandan": ("Q", (255, 130, 195), "nimble", 0),
}


def test_roster_is_the_five_settled_species_in_menu_order():
    assert [s.id for s in list_species()] == [
        "human", "martian", "cygnian", "sirian", "lalandan",
    ]


def test_every_species_start_stats_match_settled_table():
    """Species-only start values = base + spread, read straight off the
    spec (the class layer adds its own spread on top at creation)."""
    for sid, expected in _EXPECTED_START_STATS.items():
        spec = find_species(sid)
        got = (
            PILOT_SKILL_BASE + spec.skill_bonus.gunnery,
            PILOT_SKILL_BASE + spec.skill_bonus.piloting,
            PILOT_SKILL_BASE + spec.skill_bonus.engineering,
            GROUND_STAT_BASE + spec.ground_bonus.reflexes,
            GROUND_STAT_BASE + spec.ground_bonus.strength,
            GROUND_STAT_BASE + spec.ground_bonus.stamina,
        )
        assert got == expected, f"{sid}: expected {expected}, got {got}"


def test_plus_six_stat_budget_holds_except_lalandan():
    """Every species spends +6 stat points; Lalandan is the −4 exception."""
    for sid in _EXPECTED_START_STATS:
        spread = _EXPECTED_START_STATS[sid]
        total = sum(v - 10 for v in spread)
        expected = -4 if sid == "lalandan" else 6
        assert total == expected, f"{sid} stat budget: expected {expected}, got {total}"


def test_glyph_color_trait_and_hp_bonus_fields():
    for sid, (glyph, color, trait_id, hp_bonus) in _EXPECTED_IDENTITY.items():
        spec = find_species(sid)
        assert spec.glyph == glyph, f"{sid} glyph"
        assert spec.color == color, f"{sid} color"
        assert spec.trait_id == trait_id, f"{sid} trait_id"
        assert spec.hp_bonus == hp_bonus, f"{sid} hp_bonus"


def test_sirian_glyph_is_the_cp437_diamond():
    """The diamond is U+2666 (procedurally patched), never U+25C6."""
    assert find_species("sirian").glyph == "\u2666"
    assert find_species("sirian").glyph != "\u25c6"


def test_exotic_glyphs_collide_with_no_roster_species_sibling():
    """The three exotic chars are pairwise distinct (map-readability)."""
    glyphs = [find_species(sid).glyph for sid in ("cygnian", "sirian", "lalandan")]
    assert len(set(glyphs)) == 3


def test_starting_reputation_identical_across_all_five_species():
    """SETTLED 3-B: species never changes starting rep."""
    baseline = starting_reputation("human", "merchant")
    for sid in _EXPECTED_START_STATS:
        assert starting_reputation(sid, "merchant") == baseline, sid
