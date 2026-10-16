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
        _ctx = SimpleNamespace(installed_chrome=["terminus_neural_stim"], log=_log)
        _old = _rules_space._state
        _rules_space._state = _space_state(_ctx)
        try:
            run(_rules_space.activate_core(_ctx))
            _ps = _rules_space._state.player_state
            assert _ps["ap_remaining"] == 5  # 3 + 2
            assert _ps["stim_loan_ap"] == -1
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
        _ctx = SimpleNamespace(installed_chrome=["terminus_neural_stim"], log=_log)
        _old = _rules_space._state
        _rules_space._state = _space_state(_ctx, ap=4)
        try:
            run(_rules_space.activate_core(_ctx))
            _rules_space.reset_turn(_ctx)  # next round: -1, cd 3 -> 2
            _ps = _rules_space._state.player_state
            assert "stim_loan_ap" not in _ps  # consumed exactly once
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

    def test_no_core_logs_the_ruled_line(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(),
        )
        _log, lines = _log_spy()
        _ctx = SimpleNamespace(installed_chrome=[], log=_log)
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
        _ctx = SimpleNamespace(installed_chrome=["terminus_neural_stim"], log=_log)
        _old = _rules_ground._state
        _rules_ground._state = _ground_state(_ctx)
        try:
            run(_rules_ground.activate_core(_ctx))
            _state = _rules_ground._state
            assert _state.player_ap == 6  # 4 + 2
            assert _state.core_cooldown == 3
            assert lines == [ACTIVATION]
            _effect = _state.active_consumable_effects["neural_stim"]
            assert (_effect.remaining_turns, _effect.ap_bonus) == (1, -1)
        finally:
            _rules_ground._state = _old

    def test_reset_repay_once_and_ticks_cooldown(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(has_core=True),
        )
        _log, lines = _log_spy()
        _ctx = SimpleNamespace(installed_chrome=["terminus_neural_stim"], log=_log)
        _old = _rules_ground._state
        _rules_ground._state = _ground_state(_ctx)
        try:
            run(_rules_ground.activate_core(_ctx))
            _rules_ground.reset_turn(_ctx)  # -1 this reset, loan consumed
            _state = _rules_ground._state
            assert "neural_stim" not in _state.active_consumable_effects
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
        _ctx = SimpleNamespace(installed_chrome=[], log=_log)
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
