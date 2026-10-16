"""The dodge amendment (doc 102 SETTLED 7): the 60 cap binds the
piloting base only; the movement term rides on top per-tile. The
ground twin stays untouched; the Piloting Jack's coefficient stamps
the player's combat state at init.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack.combat import _space_init
from src.spacehack.combat._ground_math import calc_ground_move_dodge
from src.spacehack.combat._types import EnemyInstance


class TestGroundTwinUntouched:
    def test_ground_move_dodge_keeps_the_points_cap(self):
        """The GROUND twin is unchanged in 4.1 (no t1 source touches
        it): +5/cell, capped at 30."""
        assert calc_ground_move_dodge(1) == 5
        assert calc_ground_move_dodge(6) == 30
        assert calc_ground_move_dodge(9) == 30


class TestEnemyCoefficientDefault:
    def test_space_enemy_field_defaults_to_base_five(self):
        _enemy = EnemyInstance(
            spec_id="pirate_scout", name="Pirate Scout", char="P",
            fg=(255, 100, 100),
        )
        assert _enemy.dodge_tile_coefficient == 5


class TestPlayerStateStamp:
    def test_init_stamps_five_plus_the_worn_grant(self, monkeypatch):
        """build_initial_enemies stamps
        ``dodge_tile_coefficient = 5 + chrome dodge_tile_bonus`` where
        ctx is in scope (the init builders stay ctx-free)."""

        def _fake_build(*_args, **_kwargs):
            _ps = {"placeholder": True}
            _ei = SimpleNamespace()
            return _ps, _ei

        monkeypatch.setattr(
            "src.spacehack.combat._space_init.init_combat_state", _fake_build,
        )
        from src.spacehack.chrome import ChromeEffects
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(dodge_tile_bonus=1),
        )
        _ps, _enemies = _space_init.build_initial_enemies(
            SimpleNamespace(installed_chrome=["terminus_piloting_jack"]),
            SimpleNamespace(), SimpleNamespace(), None, None,
            [SimpleNamespace()], [None],
            ap_bonus=0, plasma_ap_discount=0, max_power_bonus=0,
        )
        assert _ps["dodge_tile_coefficient"] == 6

        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(),
        )
        _ps, _enemies = _space_init.build_initial_enemies(
            SimpleNamespace(installed_chrome=[]),
            SimpleNamespace(), SimpleNamespace(), None, None,
            [SimpleNamespace()], [None],
            ap_bonus=0, plasma_ap_discount=0, max_power_bonus=0,
        )
        assert _ps["dodge_tile_coefficient"] == 5
