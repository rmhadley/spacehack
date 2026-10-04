"""Space enemy band resolver (doc 48 phase 7, SETTLED 39).

One band vocabulary, both theaters: this module imports the ground
band machinery (levels, budgets, quality ladders, the shared
largest-remainder allocator) and never re-derives it. A ship's band
is SPEC-AUTHORED (SETTLED 39 — the class ladder IS the band ladder;
nothing stamps a band at spawn), so :func:`derive_skills` reads the
spec itself: pilot skills come from the band's effective-level budget
split by the spec's ``skill_weights`` (gunnery/piloting/engineering).
Every piece of flown equipment — weapons AND modules — rolls quality
at the band's ladder through ONE helper (band 1 equals the KILL
rates, so nothing nerfs). Pure functions only: callers pass ``rng``.

``SKILL_BASE`` is the ships-only tuning dial (the honest claim):
band 1 preserves today's QUALITY rates, not today's hand-authored
skill sums — the dial lands band-1 totals inside today's fixed-roster
range (40-45) and playtest tunes from there. Band 0 (derelicts) is
flat base.
"""

from __future__ import annotations

from .ground_scale import allocate_budget, band_budget, quality_rates

# Skills mirror the player's cap. The BASE is the ships-only dial:
# 11 puts a band-1 three-skill total at 43 — inside today's authored
# 40-45 sums. Ground keeps its own base-10 six-block (STAT_BASE).
SKILL_BASE: int = 11
SKILL_CAP: int = 100


def derive_skills(spec) -> tuple[int, int, int]:
    """Gunnery/piloting/engineering from the spec's band + weights.

    Module bonuses, the per-spec reconciliation dials, and the cap
    fold at the build site (``_build_enemy``) — this is the pure
    band math only.
    """
    floors = allocate_budget(band_budget(spec.band), spec.skill_weights)
    return tuple(
        min(SKILL_CAP, SKILL_BASE + points) for points in floors
    )


def roll_flown_equipment(item_type: str, ids, band: int, rng,
                         quality_floor: int = 0):
    """Fly-time quality roll for weapons AND modules (doc 47.3 +
    48 SETTLED 39): every id rolls the band's ladder at combat entry
    — the ship tanks, shoots, and is captured with these exact
    instances. Band 1 equals the flat KILL ladder.

    ``quality_floor`` (doc 48 SETTLED 52, consortium hunters) clamps
    UP to the floor rung — ``max(floor, rolled)`` — so no stripped
    piece is ever base quality; the top tier's odds never move. No
    player path calls with a floor, so floor 0 draws identically."""
    from .data.quality import roll_quality
    from .ship import StoredEquipment

    rates = quality_rates(band)
    return tuple(
        StoredEquipment(
            item_type, item_id,
            quality=max(quality_floor, roll_quality(rates, rng)),
        )
        for item_id in ids
    )
