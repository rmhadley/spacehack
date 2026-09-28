"""Tests for xp.py — XP curve formulas.

xp_for_level and _xp_to_next produce 60 threshold values. A single
off-by-one in the loop body shifts every level from 2–60, which is
completely invisible to manual playtesting.
"""

from __future__ import annotations
from tests.support.asyncutil import run, as_async

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
    refresh_ground_max_hp,
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
        monkeypatch.setattr(_ts, "open_trait_selection", as_async(lambda ctx: None))

        ctx = self._ctx()
        # 300 XP clears level 3 (cumulative 205) with a little spill.
        run(add_xp(ctx, 300))
        assert ctx.player_level == 3
        assert ctx.player_skill_points == 10

    def test_trait_milestones_at_40_and_50(self, monkeypatch):
        import src.spacehack.trait_screen as _ts
        calls: list[int] = []
        monkeypatch.setattr(
            _ts, "open_trait_selection", as_async(lambda ctx: calls.append(ctx.player_level)),
        )

        ctx = self._ctx()
        run(add_xp(ctx, xp_for_level(51)))
        assert ctx.player_level == 51
        assert calls == [40, 50]
        assert ctx.player_skill_points == 5 * 50

    def test_no_milestone_below_40(self, monkeypatch):
        import src.spacehack.trait_screen as _ts
        calls: list[int] = []
        monkeypatch.setattr(
            _ts, "open_trait_selection", as_async(lambda ctx: calls.append(ctx.player_level)),
        )

        ctx = self._ctx()
        run(add_xp(ctx, xp_for_level(39)))
        assert ctx.player_level == 39
        assert calls == []


class TestGroundMaxHpRefresh:
    """Out-of-combat changes to the live max-HP inputs must resync the
    stored ``ground_hp``/``ground_max_hp`` pair (user report 2026-09-28:
    stamina 34 promises 20 + 34//2 = 37; the HUD kept the stale 35
    synced at stamina 30)."""

    def _ctx(self, stamina=30, hp=35, max_hp=35, traits=()):
        return SimpleNamespace(
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=stamina),
            stats=SimpleNamespace(gunnery=10, piloting=10, engineering=10),
            equipped_ground_armor={},
            player_traits=list(traits),
            character_info={"species_id": "human"},
            ground_hp=hp,
            ground_max_hp=max_hp,
            player_skill_points=0,
        )

    def test_user_repro_four_stamina_spends_land_the_promised_max(self):
        from src.spacehack.xp import _apply_skill_point

        ctx = self._ctx()
        ctx.player_skill_points = 4
        # 30->31 is an odd step: no max growth (15 == 30//2 == 31//2).
        assert _apply_skill_point(ctx, "stamina") is True
        assert (ctx.ground_hp, ctx.ground_max_hp) == (35, 35)
        assert _apply_skill_point(ctx, "stamina") is True  # 32 -> 36
        assert (ctx.ground_hp, ctx.ground_max_hp) == (36, 36)
        assert _apply_skill_point(ctx, "stamina") is True  # 33: odd step
        assert _apply_skill_point(ctx, "stamina") is True  # 34 -> 37
        assert ctx.ground_stats.stamina == 34
        assert (ctx.ground_hp, ctx.ground_max_hp) == (37, 37)

    def test_non_stamina_spends_do_not_touch_stored_hp(self):
        from src.spacehack.xp import _apply_skill_point

        ctx = self._ctx()
        ctx.player_skill_points = 1
        assert _apply_skill_point(ctx, "gunnery") is True
        assert (ctx.ground_hp, ctx.ground_max_hp) == (35, 35)

    def test_wounded_hp_keeps_its_deficit_when_the_max_grows(self):
        ctx = self._ctx(stamina=34, hp=30, max_hp=35)
        refresh_ground_max_hp(ctx)
        assert (ctx.ground_hp, ctx.ground_max_hp) == (32, 37)

    def test_lower_max_clamps_current_hp(self):
        """Unequipping hp-bonus armor must not leave hp above max."""
        ctx = self._ctx(stamina=34, hp=38, max_hp=40)
        refresh_ground_max_hp(ctx)
        assert (ctx.ground_hp, ctx.ground_max_hp) == (37, 37)

    def test_active_combat_state_follows_a_growing_max(self, monkeypatch):
        from src.spacehack.combat import _rules_ground

        ctx = self._ctx(stamina=34, hp=30, max_hp=35)
        state = SimpleNamespace(ctx=ctx, player_hp=30, player_max_hp=35)
        monkeypatch.setattr(_rules_ground, "_state", state)
        refresh_ground_max_hp(ctx)
        assert (state.player_hp, state.player_max_hp) == (32, 37)

    def test_combat_propagation_grows_on_the_states_own_max(self, monkeypatch):
        """Divergent pair at call time (stale ctx max 35, combat entry's
        fresh state max 40, formula now 43): the combat state grows
        relative to ITS max (40 + 3 = 39), not the ctx pair's."""
        from src.spacehack.combat import _rules_ground

        ctx = self._ctx(stamina=34, hp=35, max_hp=35, traits=["ironclad"])
        state = SimpleNamespace(ctx=ctx, player_hp=36, player_max_hp=40)
        monkeypatch.setattr(_rules_ground, "_state", state)
        refresh_ground_max_hp(ctx)
        assert (state.player_hp, state.player_max_hp) == (39, 43)

    def test_active_combat_state_clamps_to_a_shrinking_max(self, monkeypatch):
        from src.spacehack.combat import _rules_ground
        from src.spacehack.ground_equipment import StoredGroundEquipment

        # 20 + 17 + Ironclad 6 + vest 3 = 46 synced; the vest is lost.
        ctx = self._ctx(stamina=34, hp=46, max_hp=46, traits=["ironclad"])
        ctx.equipped_ground_armor["body"] = StoredGroundEquipment(
            "armor", "cybernetic_torso",
        )
        state = SimpleNamespace(ctx=ctx, player_hp=46, player_max_hp=46)
        monkeypatch.setattr(_rules_ground, "_state", state)
        ctx.equipped_ground_armor.pop("body")
        refresh_ground_max_hp(ctx)
        assert (ctx.ground_hp, ctx.ground_max_hp) == (43, 43)
        assert (state.player_hp, state.player_max_hp) == (43, 43)

    def test_ironclad_pick_grows_the_stored_max_immediately(self):
        from src.spacehack.trait_screen import _apply_ironclad_hp

        ctx = self._ctx(stamina=34, hp=37, max_hp=37, traits=["ironclad"])
        _apply_ironclad_hp(ctx, "ironclad")
        assert (ctx.ground_hp, ctx.ground_max_hp) == (43, 43)

    def test_selling_hp_bonus_armor_resyncs_the_stored_max(self):
        """The armory manage path (SELL_ARMOR) is a live input change —
        the worn Cybernetic Torso's +3 must leave the stored max."""
        from src.spacehack.ground_equipment import StoredGroundEquipment
        from src.spacehack.menus._armory import _apply_manage_choice

        ctx = self._ctx(stamina=34, hp=40, max_hp=40)
        ctx.equipped_ground_armor["body"] = StoredGroundEquipment(
            "armor", "cybernetic_torso",
        )
        ctx.ground_armory_storage = []
        ctx.stats = SimpleNamespace(credits=0)
        assert (ctx.ground_hp, ctx.ground_max_hp) == (40, 40)

        _apply_manage_choice(ctx, "SELL_ARMOR:body")

        assert ctx.equipped_ground_armor == {}
        assert (ctx.ground_hp, ctx.ground_max_hp) == (37, 37)
