"""The Nano Mesh (doc 102 SETTLED 9): x1.25 on the worn armor's
total DR while HP is strictly below half — a per-hit conditional
coefficient, never a flat add, on both actors. Below-half reads
PER HIT (HP can cross half mid-burst).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack.chrome import ChromeEffects
from src.spacehack.combat import _rules_ground
from src.spacehack.combat._ground_math import soak_with_mesh
from src.spacehack.combat._ground_types import GroundCombatState


class TestSoakConditional:
    def test_not_worn_is_identity(self):
        assert soak_with_mesh(8, False, 1, 100) == 8

    def test_worn_above_half_is_identity(self):
        assert soak_with_mesh(8, True, 51, 100) == 8

    def test_exactly_half_is_not_strictly_below(self):
        assert soak_with_mesh(8, True, 50, 100) == 8

    def test_strictly_below_multiplies(self):
        assert soak_with_mesh(8, True, 49, 100) == 10  # 8 x 1.25
        assert soak_with_mesh(3, True, 1, 100) == 3  # 3.75 -> 3


def _mesh_state(hp: int, max_hp: int = 40, nano_mesh: bool = True):
    ctx = SimpleNamespace(
        installed_chrome=["terminus_nano_mesh"] if nano_mesh else [],
    )
    return GroundCombatState(
        ctx=ctx, game_map=None,
        player_hp=hp, player_max_hp=max_hp, armor_defense=8,
    )


class TestPlayerSoak:
    def test_reads_chrome_and_live_hp_per_hit(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(nano_mesh=True),
        )
        _state = _mesh_state(20)  # exactly half
        assert _rules_ground.player_soak(_state) == 8
        _state.player_hp = 19  # one under half, mid-burst
        assert _rules_ground.player_soak(_state) == 10

    def test_unworn_state_reads_base(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(),
        )
        assert _rules_ground.player_soak(_mesh_state(1)) == 8


def _ground_ctx():
    return SimpleNamespace(
        player_traits=[],
        equipped_ground_armor={},
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        character_info={"species_id": "human"},
        installed_chrome=[],
    )


def _mesh_enemy(nano_mesh: bool, hp: int = 3):
    from src.spacehack.combat._ground_types import GroundEnemyInstance
    return GroundEnemyInstance(
        entity=None, spec=SimpleNamespace(name="Dummy"),
        hp=hp, max_hp=30, armor=8, nano_mesh=nano_mesh,
    )


class TestEnemySideSymmetry:
    def test_damage_subtracts_the_mesh_soak(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(),
        )
        _plain = _rules_ground.damage(
            "kinetic_pistol", _mesh_enemy(False), _ground_ctx(),
        )[0]
        _meshed = _rules_ground.damage(
            "kinetic_pistol", _mesh_enemy(True), _ground_ctx(),
        )[0]
        # Same raw hit; the mesh's x1.25 on armor 8 (8 -> 10) soaks
        # 2 more, floored at 1.
        assert _meshed == max(1, _plain - 2)


class TestEnemyShotResolution:
    def test_roll_ground_shot_reads_the_live_soak(self, monkeypatch):
        from src.spacehack.combat import _ai_ground
        monkeypatch.setattr(
            _ai_ground, "RNG",
            SimpleNamespace(randint=lambda *_a: 1),  # always hit
        )
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(nano_mesh=True),
        )
        _ctx = SimpleNamespace(ground_stats=SimpleNamespace(reflexes=10))
        _stats = SimpleNamespace(reflexes=10, strength=10)
        _old = _rules_ground._state

        _rules_ground._state = _mesh_state(20)  # exactly half: base 8
        try:
            _hit, _at_half, _ = _ai_ground._roll_ground_shot(
                _ctx, "battle_rifle", _stats, 8, 0, 5,
            )
            _rules_ground._state.player_hp = 19  # below half: soak 10
            _hit, _below_half, _ = _ai_ground._roll_ground_shot(
                _ctx, "battle_rifle", _stats, 8, 0, 5,
            )
        finally:
            _rules_ground._state = _old
        assert _hit
        assert _below_half == _at_half - 2  # 8 -> 10 soak on the same hit

    def test_stateless_caller_keeps_the_threaded_base(self, monkeypatch):
        from src.spacehack.combat import _ai_ground
        monkeypatch.setattr(
            _ai_ground, "RNG",
            SimpleNamespace(randint=lambda *_a: 1),
        )
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(nano_mesh=True),
        )
        _ctx = SimpleNamespace(ground_stats=SimpleNamespace(reflexes=10))
        _stats = SimpleNamespace(reflexes=10, strength=10)
        _old = _rules_ground._state
        _rules_ground._state = None
        try:
            _hit, _dmg, _ = _ai_ground._roll_ground_shot(
                _ctx, "battle_rifle", _stats, 8, 0, 5,
            )
            # The threaded base stands in: battle_rifle 28 - 8, NOT
            # the live soak's 28 - 10.
            assert (_hit, _dmg) == (True, 20)
        finally:
            _rules_ground._state = _old


class TestBlastVictimSoak:
    def test_blast_enemy_victims_soak_through_the_mesh(self):
        from src.spacehack.combat._ground_blast import apply_explosive_enemy_hit
        from src.spacehack.combat._ground_types import GroundEnemyInstance
        from src.spacehack import world

        def _blast_victim(nano_mesh: bool):
            return GroundEnemyInstance(
                entity=world.Entity("V", (200, 200, 200), world.Position(1, 1)),
                spec=SimpleNamespace(name="Victim"),
                hp=3, max_hp=30, armor=8, nano_mesh=nano_mesh,
            )

        _ctx = SimpleNamespace(
            ground_stats=SimpleNamespace(reflexes=10, strength=10),
            player_traits=[],
        )
        _primary = _blast_victim(False)
        _meshed = _blast_victim(True)  # below half (hp 3 of 30)
        _plain = _blast_victim(False)
        _meshed_result = apply_explosive_enemy_hit(
            "grenade_launcher", _meshed, _primary, _ctx,
        )
        _plain_result = apply_explosive_enemy_hit(
            "grenade_launcher", _plain, _primary, _ctx,
        )
        assert _meshed_result is not None and _plain_result is not None
        # Same blast, one victim meshed below half: armor 8 -> 10 soaks
        # 2 more of the full damage; the splash share halves that to 1.
        assert _plain_result[1] - _meshed_result[1] == 1
