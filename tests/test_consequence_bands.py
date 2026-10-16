"""The consequence bands (doc 102 SETTLED 3/4/15): static scars
keyed on burn, one function set, planet valence shifting the LOCAL
read — with the dead zone absolute (burn <= 3 reads free ANYWHERE).

Two regression instruments (SETTLED 12 + the advisor's second pin):
the bit-identical burn-0-vs-burn-3 walk across every socioeconomic
readout, and the exact-multiplier boundary walk.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import chrome
from src.spacehack.game_context import GameContext


def _ctx(burn: int = 0, level: int = 10):
    ctx = GameContext(
        context=None, character_info={"species_id": "human"},
        log=None, game_map=None, player=None, stats=None,
    )
    ctx.log = SimpleNamespace(
        add=lambda _m, **_k: None,
        add_colored=lambda _m, _c, **_k: None,
    )
    ctx.player_level = level
    ctx.ego_burn = burn
    ctx.current_city_id = "mars"
    return ctx


class TestBandFunction:
    def test_boundaries(self):
        assert [chrome.band(b) for b in (0, 3)] == [0, 0]
        assert [chrome.band(b) for b in (4, 7)] == [1, 1]
        assert [chrome.band(b) for b in (8, 11)] == [2, 2]
        assert chrome.band(12) == 3
        assert chrome.band(25) == 3

    def test_names(self):
        assert [chrome.band_name(i) for i in range(4)] == [
            "Natural", "Tainted", "Chromed", "Psycho",
        ]

    def test_local_band_valence_compositions(self):
        assert chrome.local_band(_ctx(3), "earth") == 0    # dead zone anywhere
        assert chrome.local_band(_ctx(4), "mars") == 1     # neutral taint
        assert chrome.local_band(_ctx(4), "earth") == 2    # strict reads harsher
        assert chrome.local_band(_ctx(4), "venus") == 0    # haven reads it free
        assert chrome.local_band(_ctx(8), "venus") == 1    # chromed reads tainted
        assert chrome.local_band(_ctx(12), "venus") == 2
        assert chrome.local_band(_ctx(12), "earth") == 3

    def test_multiplier_tables(self):
        assert [chrome.service_multiplier(i) for i in range(4)] == [
            1.00, 1.05, 1.15, 1.30,
        ]

    def test_rep_gain_tables_and_neutrals(self):
        assert chrome.rep_gain_multiplier("merchant", 1) == 0.95
        assert chrome.rep_gain_multiplier("militia", 3) == 0.70
        assert chrome.rep_gain_multiplier("pirate", 2) == 1.15
        assert chrome.rep_gain_multiplier("consortium", 3) == 1.30
        # Labs is a guild, not a rep faction; unknowns read neutral.
        assert chrome.rep_gain_multiplier("labs", 3) == 1.00
        assert chrome.rep_gain_multiplier("strangers", 2) == 1.00


class TestDeadZonePin:
    """SETTLED 3/12: burn <= 3 costs nothing ANYWHERE — two
    identical characters at burn 0 vs burn 3 read bit-identical on
    every socioeconomic surface, at every valence extreme."""

    def _readouts(self, burn: int) -> dict:
        from src.spacehack import trade
        from src.spacehack.faction import modify_rep
        from src.spacehack.menus import _armory, _mechanic
        ctx = _ctx(burn)
        ctx.economy_state = {"mars": {"food_rations": 5}, "earth": {"food_rations": 5}, "venus": {"food_rations": 5}}
        ctx.faction_reputation = {"merchant": 20, "militia": 20, "pirate": 20, "consortium": 20}
        out = {}
        for planet in ("mars", "earth", "venus"):
            out[f"buy:{planet}"] = trade._unit_price(ctx, planet, "food_rations")
            out[f"sell:{planet}"] = trade._sell_price(ctx, planet, "food_rations")
        _ship = SimpleNamespace(price=1000, max_fuel=10)
        _owned = SimpleNamespace(fuel=0, hull_damage_pct=50)
        out["repair"] = _mechanic._repair_preview(_owned, _ship, ctx)
        out["refuel_per_unit"] = _mechanic._refuel_preview(_owned, _ship, 10**6, ctx)[1]
        out["armory_buy"] = _armory._buy_price(ctx, 100)
        out["armory_sell"] = _armory._sell_price("light_vest", 0, ctx)
        for faction in ("merchant", "militia", "pirate", "consortium"):
            ctx.faction_reputation = {f: 20 for f in ctx.faction_reputation}
            before = dict(ctx.faction_reputation)
            modify_rep(ctx, faction, 10)
            out[f"rep:{faction}"] = ctx.faction_reputation[faction] - before[faction]
        return out

    def test_burn_zero_vs_burn_three_is_bit_identical(self):
        _zero = self._readouts(0)
        _three = self._readouts(3)
        assert _zero == _three, (
            f"dead-zone leak: {[k for k in _zero if _zero[k] != _three[k]]}"
        )


class TestMultiplierPin:
    """The advisor's second instrument (home corrected at the
    audit): the exact multiplier at the band boundary — burn 4 on a
    NEUTRAL port reads x1.05 pay / x0.95 receive; strict and
    tolerant ports compose the valence."""

    def test_neutral_boundary_is_exact(self):
        from src.spacehack import trade
        from src.spacehack.menus import _armory, _mechanic
        _base = _ctx(0)
        _taint = _ctx(4)
        for ctx in (_base, _taint):
            ctx.economy_state = {"mars": {"food_rations": 5}}
        _buy0 = trade._unit_price(_base, "mars", "food_rations")
        _buy4 = trade._unit_price(_taint, "mars", "food_rations")
        assert _buy4 == int(_buy0 * 1.05)
        _sell0 = trade._sell_price(_base, "mars", "food_rations")
        _sell4 = trade._sell_price(_taint, "mars", "food_rations")
        assert _sell4 == max(1, int(_sell0 * 0.95))
        assert _armory._buy_price(_taint, 100) == 105
        assert _armory._sell_price("light_vest", 0, _taint) == max(
            1, _armory._sell_price("light_vest", 0, _base) * 95 // 100,
        )
        _ship = SimpleNamespace(price=1000, max_fuel=10)
        _owned = SimpleNamespace(fuel=0, hull_damage_pct=50)
        assert _mechanic._repair_preview(_owned, _ship, _taint) == int(
            _mechanic._repair_preview(_owned, _ship, _base) * 1.05,
        )

    def test_strict_and_tolerant_compose_the_valence(self):
        """Self-relative per planet (stock targets differ across
        ports): each port's burn-4 price against its own burn-0."""
        from src.spacehack import trade
        _taint = _ctx(4)
        _natural = _ctx(0)
        for _c in (_taint, _natural):
            _c.economy_state = {
                "mars": {"food_rations": 5},
                "earth": {"food_rations": 5},
                "venus": {"food_rations": 5},
            }
        # mars (neutral): x1.05. earth (strict): x1.15. venus
        # (haven): reads burn 4 free — its own natural price.
        for planet, ratio in (("mars", 1.05), ("earth", 1.15)):
            _nat = trade._unit_price(_natural, planet, "food_rations")
            assert trade._unit_price(_taint, planet, "food_rations") == int(
                _nat * ratio,
            )
        assert trade._unit_price(_taint, "venus", "food_rations") == (
            trade._unit_price(_natural, "venus", "food_rations")
        )


class TestRepGains:
    def test_positive_deltas_scale_and_losses_do_not(self):
        from src.spacehack.faction import modify_rep
        ctx = _ctx(12)  # psycho: merchant x0.70, pirate x1.30
        ctx.faction_reputation = {"merchant": 20, "pirate": 20}
        modify_rep(ctx, "merchant", 10)
        modify_rep(ctx, "pirate", 10)
        assert ctx.faction_reputation["merchant"] == 20 + int(10 * 0.70)
        assert ctx.faction_reputation["pirate"] == 20 + int(10 * 1.30)
        modify_rep(ctx, "merchant", -10)
        assert ctx.faction_reputation["merchant"] == 20 + 7 - 10  # unchanged loss

    def test_dead_zone_rep_is_untouched(self):
        from src.spacehack.faction import modify_rep
        for burn in (0, 3):
            ctx = _ctx(burn)
            ctx.faction_reputation = {"merchant": 20, "pirate": 20}
            modify_rep(ctx, "merchant", 10)
            modify_rep(ctx, "pirate", 10)
            assert ctx.faction_reputation == {"merchant": 30, "pirate": 30}


class TestBoardBands:
    def test_dead_zone_keeps_the_pre_chrome_board(self):
        from src.spacehack.mission._board import _faction_tier_band
        for burn in (0, 3):
            ctx = _ctx(burn)
            assert _faction_tier_band(ctx, "bar", 4, "mars") == (1, 4)

    def test_middle_bands_cap_pirate_trust_work(self):
        from src.spacehack.mission._board import _faction_tier_band
        for burn in (4, 8):
            ctx = _ctx(burn)
            assert _faction_tier_band(ctx, "bar", 4, "mars") == (1, 2)
        # psycho posts everything.
        assert _faction_tier_band(_ctx(12), "bar", 4, "mars") == (1, 4)
        # other guilds are unaffected.
        assert _faction_tier_band(_ctx(8), "merchants", 4, "mars") == (1, 4)


class TestStrictRowTrim:
    """The strict-port row loss (SETTLED 4) — trimmed AFTER the
    procedural fill (the reviewer catch: trimming before it just
    swaps a static row for a procedural one)."""

    def _filled_count(self, ctx, planet_id):
        from src.spacehack.mission._board import (
            MissionBoard, fill_empty_slots,
        )
        board = MissionBoard(
            npc_id="wolf_barkeep", slots=[None] * 5, max_slots=5,
            planet_id=planet_id,
        )
        import random
        ctx2 = ctx
        ctx2.tutorial_mode = False
        ctx2.tutorial_complete = True
        ctx2.player_traits = []
        ctx2.completed_mission_ids = set()
        ctx2.player_active_missions = []
        fill_empty_slots(
            board, planet_tier=4, completed_ids=frozenset(),
            active_ids=frozenset(), planet_id=planet_id,
            generated={}, rng=random.Random(7), ctx=ctx2,
        )
        return sum(1 for slot in board.slots if slot is not None)

    def test_dead_zone_keeps_every_row_on_strict_ports(self):
        for burn in (0, 3):
            assert self._filled_count(_ctx(burn), "earth") == self._filled_count(
                _ctx(0), "earth",
            )

    def test_strict_port_loses_a_row_at_the_chromed_read(self):
        _natural = self._filled_count(_ctx(0), "earth")
        # burn 8 = base band 2; earth (+1) reads 3 -> trim fires.
        _chromed = self._filled_count(_ctx(8), "earth")
        assert _chromed == _natural - 1
        # mars (neutral) at burn 8: local band 2, no valence -> no trim.
        assert self._filled_count(_ctx(8), "mars") == self._filled_count(_ctx(0), "mars")


class TestRefuelComposition:
    """Fuel bands the TOTAL (per-unit is 1$; a per-unit composition
    truncates to nothing — the reviewer catch)."""

    def test_refuel_total_bands_and_dead_zone_holds(self):
        from src.spacehack.menus import _mechanic
        _ship = SimpleNamespace(price=1000, max_fuel=10)
        _owned = SimpleNamespace(fuel=0)
        _a = _mechanic._refuel_preview(_owned, _ship, 10**6, _ctx(0))
        _b = _mechanic._refuel_preview(_owned, _ship, 10**6, _ctx(3))
        _c = _mechanic._refuel_preview(_owned, _ship, 10**6, _ctx(4))
        assert _a == _b == (10, 10)          # dead zone: 10 units for 10$
        assert _c == (10, int(10 * 1.05))    # taint: same units, higher total
        _psycho = _mechanic._refuel_preview(_owned, _ship, 10**6, _ctx(12))
        assert _psycho == (10, 13)
