"""Tests for xp.py — XP curve formulas.

xp_for_level and _xp_to_next produce 60 threshold values. A single
off-by-one in the loop body shifts every level from 2–60, which is
completely invisible to manual playtesting.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.xp import (
    MAX_PLAYER_LEVEL,
    SKILL_POINTS_PER_LEVEL,
    _qualifying_traits,
    _xp_to_next,
    add_xp,
    demolitionist_splash_bonus,
    ground_damage_reduction,
    ground_evade_bonus,
    ground_max_hp_bonus,
    laser_specialist_hit_bonus,
    missileer_hit_bonus,
    pack_mule_capacity_bonus,
    plasma_savant_ap_discount,
    systems_expert_power_bonus,
    xp_for_level,
)


# Design doc table (docs/design/complete/02_DESIGN_XP_LEVELING.md).
# Cumulative XP to reach each level. Curve: level k costs 40 + 25*k
# (level 2 = 90, unchanged from the old curve so the tutorial top-up
# to level 2 still lands the same).
_CUMULATIVE_XP: dict[int, int] = {
    1: 0,
    2: 90,
    3: 205,
    4: 345,
    5: 510,
    6: 700,
    7: 915,
    8: 1155,
    9: 1420,
    10: 1710,
    11: 2025,
    12: 2365,
    13: 2730,
    14: 3120,
    15: 3535,
    16: 3975,
    17: 4440,
    18: 4930,
    19: 5445,
    20: 5985,
    21: 6550,
    22: 7140,
    23: 7755,
    24: 8395,
    25: 9060,
    26: 9750,
    27: 10465,
    28: 11205,
    29: 11970,
    30: 12760,
    31: 13575,
    32: 14415,
    33: 15280,
    34: 16170,
    35: 17085,
    36: 18025,
    37: 18990,
    38: 19980,
    39: 20995,
    40: 22035,
    41: 23100,
    42: 24190,
    43: 25305,
    44: 26445,
    45: 27610,
    46: 28800,
    47: 30015,
    48: 31255,
    49: 32520,
    50: 33810,
    51: 35125,
    52: 36465,
    53: 37830,
    54: 39220,
    55: 40635,
    56: 42075,
    57: 43540,
    58: 45030,
    59: 46545,
    60: 48085,
}


class TestXpForLevel:
    """Verify every threshold in the design doc table."""

    def test_all_levels(self):
        for level, expected in _CUMULATIVE_XP.items():
            assert xp_for_level(level) == expected, (
                f"Level {level}: expected {expected}, got {xp_for_level(level)}"
            )

    def test_level_1(self):
        """Level 1 is always 0 XP."""
        assert xp_for_level(1) == 0

    def test_monotonic(self):
        """Each level costs more than the last."""
        prev = 0
        for level in range(2, 61):
            cur = xp_for_level(level)
            assert cur > prev, f"Level {level}: {cur} <= {prev}"
            prev = cur


class TestTraitQualification:
    def _ctx(self, *, piloting=10, total_kills=0):
        return SimpleNamespace(
            stats=SimpleNamespace(
                gunnery=10, piloting=piloting, engineering=10,
            ),
            player_counters=SimpleNamespace(
                deliveries_completed=0,
                merchant_missions_completed=0,
                bar_missions_completed=0,
                bounty_missions_completed=0,
                total_kills=total_kills,
                melee_kills=0,
                explosive_hits=0,
                laser_shots=0,
                missile_shots=0,
                plasma_shots=0,
                railgun_kills=0,
                focused_shots=0,
            ),
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
            player_traits=[],
            faction_reputation={},
        )

    def test_ace_pilot_uses_piloting_not_flee_counter(self):
        _traits = _qualifying_traits(
            self._ctx(piloting=40),
        )

        assert "ace_pilot" in {trait.id for trait in _traits}

    def test_ace_pilot_does_not_use_old_flee_counter(self):
        _traits = _qualifying_traits(self._ctx(piloting=10))

        assert "ace_pilot" not in {trait.id for trait in _traits}

    def test_juggernaut_keeps_kill_requirement(self):
        _traits = _qualifying_traits(self._ctx(total_kills=30))

        assert "juggernaut" in {trait.id for trait in _traits}

    def test_charger_requires_40_melee_kills(self):
        _ctx = self._ctx(total_kills=40)
        _ctx.player_counters.melee_kills = 40

        _traits = _qualifying_traits(_ctx)

        assert "charger" in {trait.id for trait in _traits}

    def test_charger_does_not_use_total_kills(self):
        _traits = _qualifying_traits(self._ctx(total_kills=40))

        assert "charger" not in {trait.id for trait in _traits}

    def test_deadshot_requires_25_railgun_kills(self):
        _ctx = self._ctx()
        _ctx.player_counters.railgun_kills = 25

        _traits = _qualifying_traits(_ctx)

        assert "deadshot" in {trait.id for trait in _traits}

    def test_deadshot_does_not_use_total_kills(self):
        _traits = _qualifying_traits(self._ctx(total_kills=25))

        assert "deadshot" not in {trait.id for trait in _traits}

    def test_focus_requires_15_focused_shots(self):
        _ctx = self._ctx()
        _ctx.player_counters.focused_shots = 15

        _traits = _qualifying_traits(_ctx)

        assert "focus" in {trait.id for trait in _traits}

    def test_focus_does_not_use_total_kills(self):
        _traits = _qualifying_traits(self._ctx(total_kills=15))

        assert "focus" not in {trait.id for trait in _traits}

    def test_juggernaut_reduces_each_ground_hit(self):
        assert ground_damage_reduction(
            SimpleNamespace(player_traits=["juggernaut"]),
        ) == 1
        assert ground_damage_reduction(
            SimpleNamespace(player_traits=[]),
        ) == 0

    def test_faction_career_traits_require_20_missions_for_their_faction(self):
        _ctx = self._ctx()
        _ctx.player_counters.merchant_missions_completed = 20
        _ctx.player_counters.bar_missions_completed = 20
        _ctx.player_counters.bounty_missions_completed = 20

        _ids = {trait.id for trait in _qualifying_traits(_ctx)}

        assert {"hauler", "fixer", "hunter"} <= _ids

    def test_faction_career_traits_do_not_use_legacy_counters(self):
        _ctx = self._ctx()
        _ctx.player_counters.deliveries_completed = 20
        _ctx.player_counters.bounties_completed = 20

        _ids = {trait.id for trait in _qualifying_traits(_ctx)}

        assert not {"hauler", "fixer", "hunter"} & _ids

    def test_specialization_requirements_use_their_focus_counters(self):
        _ctx = self._ctx()
        _ctx.ground_stats = SimpleNamespace(reflexes=40, strength=40, stamina=40)
        _ctx.stats.engineering = 40
        _ctx.player_counters.explosive_hits = 15
        _ctx.player_counters.laser_shots = 100
        _ctx.player_counters.missile_shots = 15
        _ctx.player_counters.plasma_shots = 100
        _ctx.player_counters.focused_shots = 15

        _ids = {trait.id for trait in _qualifying_traits(_ctx)}

        assert {
            "evasive", "pack_mule", "ironclad", "systems_expert",
            "demolitionist", "laser_specialist", "missileer", "plasma_savant",
            "focus",
        } <= _ids

    def test_specialization_effect_helpers(self):
        _ctx = SimpleNamespace(
            player_traits=[
                "evasive", "pack_mule", "ironclad", "systems_expert",
                "demolitionist", "laser_specialist", "missileer", "plasma_savant",
            ],
        )

        assert ground_evade_bonus(_ctx) == 5
        assert pack_mule_capacity_bonus(_ctx) == 2
        assert ground_max_hp_bonus(_ctx) == 6
        assert systems_expert_power_bonus(_ctx) == 10
        assert demolitionist_splash_bonus(_ctx) == 25
        assert laser_specialist_hit_bonus(_ctx) == 10
        assert missileer_hit_bonus(_ctx) == 10
        assert plasma_savant_ap_discount(_ctx) == 1


class TestXpToNext:
    """Per-level cost: 40 + (level + 1) * 25."""

    def test_level_1_to_2(self):
        """40 + 2*25 = 90 (unchanged from the old curve — tutorial top-up safe)."""
        assert _xp_to_next(1) == 90

    def test_level_5_to_6(self):
        """40 + 6*25 = 190."""
        assert _xp_to_next(5) == 190

    def test_level_20_to_21(self):
        """40 + 21*25 = 565."""
        assert _xp_to_next(20) == 565

    def test_level_29_to_30(self):
        """40 + 30*25 = 790."""
        assert _xp_to_next(29) == 790

    def test_level_59_to_60(self):
        """40 + 60*25 = 1540 — the final rung to cap."""
        assert _xp_to_next(59) == 1540

    def test_sum_matches_cumulative(self):
        """Sum of _xp_to_next(1) through _xp_to_next(n-1) equals xp_for_level(n)."""
        for level in range(2, 61):
            total = sum(_xp_to_next(l) for l in range(1, level))
            assert total == xp_for_level(level), (
                f"Level {level}: sum of costs = {total}, "
                f"xp_for_level = {xp_for_level(level)}"
            )


class TestAddXp:
    """Level-up grants and trait milestone triggers."""

    def _ctx(self):
        return SimpleNamespace(
            player_xp=0,
            player_level=1,
            player_skill_points=0,
            log=SimpleNamespace(add_colored=lambda *_a, **_k: None),
        )

    def test_level_cap_and_sp_per_level(self):
        """Cap is 60 and every level grants 5 skill points."""
        assert MAX_PLAYER_LEVEL == 60
        assert SKILL_POINTS_PER_LEVEL == 5
        assert SKILL_POINTS_PER_LEVEL * (MAX_PLAYER_LEVEL - 1) == 295

    def test_grants_5_sp_per_level(self, monkeypatch):
        import src.spacehack.trait_screen as _ts
        monkeypatch.setattr(_ts, "open_trait_selection", lambda ctx: None)

        ctx = self._ctx()
        # 300 XP clears level 3 (cumulative 205) with a little spill.
        add_xp(ctx, 300)
        assert ctx.player_level == 3
        assert ctx.player_skill_points == 10

    def test_trait_milestones_at_40_and_50(self, monkeypatch):
        import src.spacehack.trait_screen as _ts
        calls: list[int] = []
        monkeypatch.setattr(
            _ts, "open_trait_selection", lambda ctx: calls.append(ctx.player_level),
        )

        ctx = self._ctx()
        add_xp(ctx, xp_for_level(51))
        assert ctx.player_level == 51
        assert calls == [40, 50]
        assert ctx.player_skill_points == 5 * 50

    def test_no_milestone_below_40(self, monkeypatch):
        import src.spacehack.trait_screen as _ts
        calls: list[int] = []
        monkeypatch.setattr(
            _ts, "open_trait_selection", lambda ctx: calls.append(ctx.player_level),
        )

        ctx = self._ctx()
        add_xp(ctx, xp_for_level(39))
        assert ctx.player_level == 39
        assert calls == []
