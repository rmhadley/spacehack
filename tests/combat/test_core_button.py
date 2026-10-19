"""The Neural Stim core button (doc 102 SETTLED 8): ONE keybind
(``a``), both theaters, +2 AP this round / -1 next round (the
loan), cooldown 3 rounds. The ruled prose (ledger 3-6) lands
verbatim from the shared chrome.py home; the debt's HUD line is
deliberately absent (declined).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.chrome import ChromeEffects
from src.spacehack.combat import _loop, _rules_ground, _rules_space
from tests.support.asyncutil import run


class TestKeybind:
    def test_a_maps_to_core(self):
        assert _loop._key_action("a") == "CORE"

    def test_both_rules_adapters_expose_activate_core(self):
        assert callable(_rules_space.activate_core)
        assert callable(_rules_ground.activate_core)

    def test_the_dispatch_seam_awaits_the_hook(self, monkeypatch):
        """The loop's rules-hook seam awaits every hook — pressing
        ``a`` must resolve through it without crashing (reviewer
        catch: a sync hook raises TypeError post-effect)."""
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(has_core=True),
        )
        _log, _lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=["terminus_neural_stim"], log=_log,
            active_statuses={},
        )
        _old = _rules_ground._state
        _rules_ground._state = _ground_state(_ctx)
        try:
            _fake_rules = SimpleNamespace(activate_core=_rules_ground.activate_core)
            run(_loop._run_rules_hook(
                _ctx, _fake_rules, "activate_core",
                "No neural core installed.",
            ))
            assert _rules_ground._state.player_ap == 6
        finally:
            _rules_ground._state = _old


def _space_state(ctx, ap: int = 3):
    _tiles = [[world.DUNGEON_FLOOR for _ in range(11)] for _ in range(11)]
    return _rules_space.SpaceCombatState(
        ctx=ctx,
        console=None,
        game_map=world.GameMap(11, 11, _tiles, []),
        log=None,
        player_state={
            "pos": world.Position(0, 0),
            "ap_remaining": ap, "ap_total": ap,
            "ap_gain_twentieths": 60, "ap_carry_twentieths": 0,
            "piloting": 0, "engineering": 0, "hull": 50, "max_hull": 50,
            "shields": 0, "max_shields": 0, "shield_regen_rate": 0,
            "power_pool": 10, "max_power": 10, "power_gen": 0,
            "stim_cooldown": 0,
        },
        enemy_insts=[],
        weapons_list=["light_laser"],
        active_weapons=[True],
    )


def _log_spy():
    lines = []
    return SimpleNamespace(
        add=lambda _m, **_k: None,
        add_colored=lambda text, _color, **_k: lines.append(text),
    ), lines


ACTIVATION = (
    "You activate the Terminus Neural Stim and your senses heighten "
    "as energy courses through you."
)
REPAYMENT = "Reality slows as the Neural Stim's effect wears off."


class TestSpaceCore:
    def test_pop_grants_loan_and_cooldown(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(has_core=True),
        )
        _log, lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=["terminus_neural_stim"], log=_log,
            active_statuses={},
        )
        _old = _rules_space._state
        _rules_space._state = _space_state(_ctx)
        try:
            run(_rules_space.activate_core(_ctx))
            _ps = _rules_space._state.player_state
            assert _ps["ap_remaining"] == 5  # 3 + 2
            _loan = _ctx.active_statuses["neural_stim_loan"]
            assert _loan.remaining_turns == 1
            assert _loan.theater == "space"
            assert _ps["stim_cooldown"] == 3
            assert lines == [ACTIVATION]

            # Popping again inside the cooldown: refused, nothing moves.
            run(_rules_space.activate_core(_ctx))
            assert lines[-1] == "Neural Stim recharging: 3 rounds."
            assert _ps["ap_remaining"] == 5
        finally:
            _rules_space._state = _old

    def test_reset_repay_once_and_ticks_cooldown(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(has_core=True),
        )
        _log, lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=["terminus_neural_stim"], log=_log,
            active_statuses={},
        )
        _old = _rules_space._state
        _rules_space._state = _space_state(_ctx, ap=4)
        try:
            run(_rules_space.activate_core(_ctx))
            _rules_space.reset_turn(_ctx)  # next round: -1, cd 3 -> 2
            _ps = _rules_space._state.player_state
            assert "neural_stim_loan" not in _ctx.active_statuses  # once
            assert _ps["stim_cooldown"] == 2
            assert lines[-1] == REPAYMENT
            assert _ps["ap_total"] == 2  # 3 AP gain (piloting 0) - 1 loan

            _rules_space.reset_turn(_ctx)  # no second repayment
            assert lines[-1] == REPAYMENT
            assert _ps["stim_cooldown"] == 1
            _rules_space.reset_turn(_ctx)
            assert _ps["stim_cooldown"] == 0  # ready again
        finally:
            _rules_space._state = _old

    def test_sync_state_defuses_a_live_loan(self, monkeypatch):
        """The container outlives the fight now (doc 103 Build A,
        advisor catch 4): sync_state explicitly defuses — a popped but
        unpaid loan never bleeds -1 AP into the player's next space
        fight (today the loan key died with the fight's player_state)."""
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(has_core=True),
        )
        _log, _lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=["terminus_neural_stim"], log=_log,
            player_owned_ship=None,
            active_statuses={},
        )
        _old = _rules_space._state
        _rules_space._state = _space_state(_ctx)
        try:
            run(_rules_space.activate_core(_ctx))
            assert "neural_stim_loan" in _ctx.active_statuses
            _rules_space.sync_state(_ctx)
            assert _ctx.active_statuses == {}  # defused, silently
            assert _lines == [ACTIVATION]  # no repay line on defuse
        finally:
            _rules_space._state = _old

    def test_no_core_logs_the_ruled_line(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(),
        )
        _log, lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=[], log=_log, active_statuses={},
        )
        _old = _rules_space._state
        _rules_space._state = _space_state(_ctx)
        try:
            run(_rules_space.activate_core(_ctx))
            assert lines == ["No neural core installed."]
            assert _rules_space._state.player_state["ap_remaining"] == 3
        finally:
            _rules_space._state = _old


def _ground_state(ctx):
    return _rules_ground.GroundCombatState(
        ctx=ctx, game_map=None, player_ap=4, player_ap_total=4,
        player_ap_gain_twentieths=80,
    )


class TestGroundCore:
    def test_pop_grants_loan_and_cooldown(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(has_core=True),
        )
        _log, lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=["terminus_neural_stim"], log=_log,
            active_statuses={},
        )
        _old = _rules_ground._state
        _rules_ground._state = _ground_state(_ctx)
        try:
            run(_rules_ground.activate_core(_ctx))
            _state = _rules_ground._state
            assert _state.player_ap == 6  # 4 + 2
            assert _state.core_cooldown == 3
            assert lines == [ACTIVATION]
            _loan = _ctx.active_statuses["neural_stim_loan"]
            assert _loan.remaining_turns == 1
            from src.spacehack.data.statuses import find_status
            assert find_status("neural_stim_loan").ap_per_round == -1
        finally:
            _rules_ground._state = _old

    def test_reset_repay_once_and_ticks_cooldown(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(has_core=True),
        )
        _log, lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=["terminus_neural_stim"], log=_log,
            active_statuses={},
        )
        _old = _rules_ground._state
        _rules_ground._state = _ground_state(_ctx)
        try:
            run(_rules_ground.activate_core(_ctx))
            _rules_ground.reset_turn(_ctx)  # -1 this reset, loan consumed
            _state = _rules_ground._state
            assert "neural_stim_loan" not in _ctx.active_statuses
            assert _state.player_ap == 3  # 4 AP gain - 1 loan
            assert _state.core_cooldown == 2
            assert lines[-1] == REPAYMENT

            _rules_ground.reset_turn(_ctx)  # no second repayment
            assert lines[-1] == REPAYMENT
            assert _state.player_ap == 4
            assert _state.core_cooldown == 1
        finally:
            _rules_ground._state = _old

    def test_no_core_logs_the_ruled_line(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(),
        )
        _log, lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=[], log=_log, active_statuses={},
        )
        _old = _rules_ground._state
        _rules_ground._state = _ground_state(_ctx)
        try:
            run(_rules_ground.activate_core(_ctx))
            assert lines == ["No neural core installed."]
            assert _rules_ground._state.player_ap == 4
        finally:
            _rules_ground._state = _old


class TestHudRows:
    def test_space_row_states(self, monkeypatch):
        from src.spacehack.hud_combat import _stim_hud_row
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(has_core=True),
        )
        _ctx = SimpleNamespace(installed_chrome=["terminus_neural_stim"])
        assert _stim_hud_row({"stim_cooldown": 0}, _ctx)[0] == "STIM (a): READY"
        assert _stim_hud_row({"stim_cooldown": 2}, _ctx)[0] == "STIM (a): 2 ROUNDS"
        # No ctx / no core: no row at all.
        assert _stim_hud_row({"stim_cooldown": 2}, None) is None

    def test_ground_row_states(self, monkeypatch):
        from src.spacehack.combat._ground_render import _stim_hud_row
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(has_core=True),
        )
        _ctx = SimpleNamespace(installed_chrome=["terminus_neural_stim"])
        _old = _rules_ground._state
        _rules_ground._state = _ground_state(_ctx)
        try:
            assert _stim_hud_row(_ctx)[0] == "STIM (a): READY"
            _rules_ground._state.core_cooldown = 2
            assert _stim_hud_row(_ctx)[0] == "STIM (a): 2 ROUNDS"
        finally:
            _rules_ground._state = _old


class TestFightEndCarry:
    """Doc 103 Build C: every fight-end site flips to the
    field-keyed defuse — carried rows WALK OUT (q13: you keep your
    burns), the loans still never bleed, and the abnormal-end
    recovery path keeps carried rows too."""

    def _carry_ctx(self):
        from src.spacehack.combat import _statuses
        from src.spacehack.data.statuses import (
            NEURAL_STIM_LOAN_ID, REGEN_ID, STAGGERED_ID,
        )

        _log, _lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=[], log=_log, active_statuses={},
            ground_hp=10, ground_max_hp=10,
        )
        _statuses.apply(_ctx.active_statuses, REGEN_ID, theater="ground")
        _statuses.apply(_ctx.active_statuses, STAGGERED_ID, theater="ground")
        _statuses.apply(_ctx.active_statuses, NEURAL_STIM_LOAN_ID, theater="ground")
        return _ctx, _lines, (REGEN_ID, STAGGERED_ID, NEURAL_STIM_LOAN_ID)

    def test_ground_sync_carries_rows_drops_the_loan(self):
        _ctx, _lines, (_regen, _stag, _loan) = self._carry_ctx()
        _tiles = [[world.DUNGEON_FLOOR for _ in range(11)] for _ in range(11)]
        _state = _rules_ground.GroundCombatState(
            ctx=_ctx, game_map=world.GameMap(11, 11, _tiles, []),
            player_hp=8, player_max_hp=10,
        )
        _old = _rules_ground._state
        _rules_ground._state = _state
        try:
            _rules_ground.sync_state(_ctx)
            assert set(_ctx.active_statuses) == {_regen, _stag}
            assert _lines == []  # silent — no expire lines on defuse
        finally:
            _rules_ground._state = _old

    def test_carried_staggered_applies_at_the_next_fight_resets(self):
        from src.spacehack.data.statuses import STAGGERED_ID

        _ctx, _lines, _ids = self._carry_ctx()
        _old = _rules_ground._state
        _rules_ground._state = _ground_state(_ctx)
        try:
            _rules_ground.reset_turn(_ctx)
            # Base gain 4 AP; the carried staggered AND the loan both
            # fold their -1 this boundary (4 - 1 - 1 = 2).
            assert _rules_ground._state.player_ap == 2
            assert _ctx.active_statuses[STAGGERED_ID].remaining_turns == 1
            # The loan fired exactly once and is gone.
            assert "neural_stim_loan" not in _ctx.active_statuses
        finally:
            _rules_ground._state = _old

    def test_stale_session_recovery_keeps_carried_rows(self):
        from src.spacehack.data.statuses import NEURAL_STIM_LOAN_ID

        _ctx, _lines, (_regen, _stag, _loan) = self._carry_ctx()
        _old = _rules_ground._state
        _rules_ground._state = None
        try:
            _rules_ground._defuse_stale_session(_ctx)
            # Carried rows survive the abnormal-end recovery path
            # (q13); the fight class and the loans drop.
            assert set(_ctx.active_statuses) == {_regen, _stag}
            assert NEURAL_STIM_LOAN_ID not in _ctx.active_statuses
        finally:
            _rules_ground._state = _old

    def test_space_sync_carries_rows_drops_the_loan(self):
        _ctx, _lines, (_regen, _stag, _loan) = self._carry_ctx()
        _old = _rules_space._state
        _rules_space._state = _space_state(
            SimpleNamespace(active_statuses=_ctx.active_statuses),
        )
        _ctx.player_owned_ship = None
        try:
            _rules_space.sync_state(_ctx)
            assert set(_ctx.active_statuses) == {_regen, _stag}
        finally:
            _rules_space._state = _old

    def test_space_fight_init_carries_rows(self):
        from src.spacehack.combat import _statuses
        from src.spacehack.data.statuses import (
            NEURAL_STIM_LOAN_ID, REGEN_ID, STIM_ID,
        )

        _log, _lines = _log_spy()
        _ctx = SimpleNamespace(
            installed_chrome=[], log=_log, active_statuses={},
        )
        _statuses.apply(_ctx.active_statuses, REGEN_ID, theater="ground")
        _statuses.apply(_ctx.active_statuses, STIM_ID, theater="ground")
        _statuses.apply(_ctx.active_statuses, NEURAL_STIM_LOAN_ID, theater="ground")
        _tiles = [[world.DUNGEON_FLOOR for _ in range(11)] for _ in range(11)]
        _old = _rules_space._state
        _rules_space._state = None
        try:
            _rules_space._activate_combat_state(
                _ctx, None, world.GameMap(11, 11, _tiles, []), None,
                _space_state(_ctx).player_state, [], [], [], None,
                ["light_laser"], [True],
            )
            # Fight init keeps the carried rows; the loan dies young.
            assert set(_ctx.active_statuses) == {REGEN_ID, STIM_ID}
            assert NEURAL_STIM_LOAN_ID not in _ctx.active_statuses
        finally:
            _rules_space._state = _old
