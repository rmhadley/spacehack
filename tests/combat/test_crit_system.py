"""The crit system (doc 102 SETTLED 6): crit chance and crit damage
as actor-read stats — base 0% / x1.5, all three theaters (ground
melee, ground ranged, space direct fire). Missiles never crit
(they never pass a crit multiplier); the zero-chance guard keeps
chrome-less fights' RNG streams bit-identical (kill-draws
doctrine).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.chrome import ChromeEffects
from src.spacehack.combat import _actions, _rules_ground, _rules_space
from src.spacehack.combat._animations import _COLOR_DAMAGE_CRIT, _damage_popup_for
from src.spacehack.combat._ground_types import GroundEnemyInstance
from src.spacehack.combat._messages import enemy_attack_line, player_attack_line
from src.spacehack.combat._stats import _crit_multiplier, _roll_crit
from src.spacehack.combat._types import EnemyInstance


class TestCritMath:
    def test_multiplier_points_are_additive_on_15(self):
        assert _crit_multiplier(0) == 1.5
        assert _crit_multiplier(5) == 1.55  # the ruled arms example
        assert _crit_multiplier(10) == 1.6

    def test_zero_chance_consumes_no_rng_draw(self):
        from src.spacehack.engine import RNG
        RNG.seed(777)
        _before = RNG.getstate()
        assert _roll_crit(0) is False
        assert _roll_crit(-3) is False
        assert RNG.getstate() == _before

    def test_certain_chance_always_crits(self):
        assert _roll_crit(100) is True


class TestResolveDamageCritKwarg:
    def test_default_multiplier_unchanged_and_crit_scales(self, monkeypatch):
        monkeypatch.setattr(
            _actions, "RNG",
            SimpleNamespace(randint=lambda *_a: 50, uniform=lambda *_a: 1.0),
        )
        assert _actions.resolve_damage("light_laser", 100, 0)[0] == 4
        assert _actions.resolve_damage("light_laser", 100, 0, crit_mult=1.5)[0] == 6


def _space_fixture():
    """A minimal live space-combat state with the player at (0,0)."""
    _ctx = SimpleNamespace(
        player_traits=[],
        player_counters=SimpleNamespace(laser_shots=0),
        player=world.Entity("@", (255, 255, 255), world.Position(0, 0), "Player"),
        log=SimpleNamespace(
            add=lambda _message, **_kwargs: None,
            add_colored=lambda _message, _color, **_kwargs: None,
        ),
        installed_chrome=[],
    )
    _tiles = [[world.DUNGEON_FLOOR for _ in range(11)] for _ in range(11)]
    _state = _rules_space.SpaceCombatState(
        ctx=_ctx,
        console=None,
        game_map=world.GameMap(11, 11, _tiles, []),
        log=None,
        player_state={
            "pos": world.Position(0, 0),
            "gunnery": 10,
            "ap_remaining": 8,
            "power_pool": 20,
            "max_power": 20,
            "weapons": ("light_laser",),
            "weapon_ammo": {0: 4},
        },
        enemy_insts=[],
        weapons_list=["light_laser"],
        active_weapons=[True],
    )
    _old = _rules_space._state
    _rules_space._state = _state
    return _ctx, _old


class TestSpacePlayerSite:
    def test_crit_reads_chrome_and_multiplies(self, monkeypatch):
        _ctx, _old = _space_fixture()
        monkeypatch.setattr(
            _actions, "RNG",
            SimpleNamespace(randint=lambda *_a: 50, uniform=lambda *_a: 1.0),
        )
        try:
            _enemy = EnemyInstance(
                spec_id="pirate_scout", name="Pirate Scout", char="P",
                fg=(255, 100, 100), pos=world.Position(6, 0),
                hull=100, max_hull=100, pilot_piloting=0,
            )
            monkeypatch.setattr(
                "src.spacehack.chrome.installed_effects",
                lambda _ids: ChromeEffects(),
            )
            _plain, _glance, _crit = _rules_space.damage(
                "light_laser", _enemy, _ctx,
            )
            assert (_plain, _crit) == (4, False)

            monkeypatch.setattr(
                "src.spacehack.chrome.installed_effects",
                lambda _ids: ChromeEffects(
                    crit_chance_space=100, crit_damage_points=10,
                ),
            )
            _enemy2 = EnemyInstance(
                spec_id="pirate_scout", name="Pirate Scout", char="P",
                fg=(255, 100, 100), pos=world.Position(6, 0),
                hull=100, max_hull=100, pilot_piloting=0,
            )
            _dmg, _glance, _crit = _rules_space.damage(
                "light_laser", _enemy2, _ctx,
            )
            assert (_dmg, _crit) == (6, True)  # 4 x 1.6, additive points
        finally:
            _rules_space._state = _old


def _ground_ctx():
    return SimpleNamespace(
        player_traits=[],
        equipped_ground_armor={},
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        character_info={"species_id": "human"},
        installed_chrome=[],
    )


def _ground_enemy():
    return GroundEnemyInstance(
        entity=None, spec=SimpleNamespace(name="Test Dummy"), armor=0,
    )


class TestGroundSites:
    def test_melee_crit_multiplies_and_garnish_rides_the_melee_term(
        self, monkeypatch,
    ):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(melee_damage_bonus=2),
        )
        _plain = _rules_ground.damage("fists", _ground_enemy(), _ground_ctx())[0]

        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(
                crit_chance_melee=100, crit_damage_points=10,
                melee_damage_bonus=2,
            ),
        )
        _dmg, _glance, _crit = _rules_ground.damage(
            "fists", _ground_enemy(), _ground_ctx(),
        )
        assert _crit is True
        assert _dmg == int(_plain * 1.6)

    def test_ranged_crit_uses_the_ranged_chance(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(),
        )
        _plain = _rules_ground.damage(
            "kinetic_pistol", _ground_enemy(), _ground_ctx(),
        )[0]

        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(crit_chance_ranged=100),
        )
        _dmg, _, _crit = _rules_ground.damage(
            "kinetic_pistol", _ground_enemy(), _ground_ctx(),
        )
        assert _crit is True
        assert _dmg == int(_plain * 1.5)

    def test_muscle_fibers_garnish_is_melee_only(self, monkeypatch):
        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(),
        )
        _melee_plain = _rules_ground.damage(
            "fists", _ground_enemy(), _ground_ctx(),
        )[0]
        _ranged_plain = _rules_ground.damage(
            "kinetic_pistol", _ground_enemy(), _ground_ctx(),
        )[0]

        monkeypatch.setattr(
            "src.spacehack.chrome.installed_effects",
            lambda _ids: ChromeEffects(melee_damage_bonus=2),
        )
        assert _rules_ground.damage("fists", _ground_enemy(), _ground_ctx())[0] == (
            _melee_plain + 2
        )
        assert _rules_ground.damage(
            "kinetic_pistol", _ground_enemy(), _ground_ctx(),
        )[0] == _ranged_plain


class TestCritFeedback:
    def test_popup_label_and_color(self):
        assert _damage_popup_for(10, 0, False, crit=True) == (
            "CRIT -10", _COLOR_DAMAGE_CRIT,
        )

    def test_crit_label_wins_over_glance(self):
        assert _damage_popup_for(10, 0, False, glancing=True, crit=True)[0] == (
            "CRIT -10"
        )

    def test_strip_hits_still_show_the_strip_line(self):
        assert _damage_popup_for(0, 4, True, crit=True) == (
            "-4", (120, 220, 255),
        )

    def test_player_line_carries_the_crit_verb(self):
        _line = player_attack_line(
            "light_laser", "Light Laser", "Pirate Scout",
            hit=True, hull_dmg=9, is_crit=True,
        )
        assert "critically hits for 9 damage!" in str(_line)

    def test_enemy_line_carries_the_crit_verb(self):
        _line = enemy_attack_line(
            "Pirate Scout", "light_laser", "Light Laser",
            hit=True, hull_dmg=9, is_crit=True,
        )
        assert "critically hits for 9 damage!" in str(_line)

    def test_crit_glance_labels_the_crit(self):
        _line = player_attack_line(
            "light_laser", "Light Laser", "Pirate Scout",
            hit=True, hull_dmg=7, is_glancing=True, is_crit=True,
        )
        assert "critically hits for 7 damage!" in str(_line)


class TestEnemyContainerDefaults:
    def test_space_enemy_crit_fields_default_to_zero(self):
        _enemy = EnemyInstance(
            spec_id="pirate_scout", name="Pirate Scout", char="P",
            fg=(255, 100, 100),
        )
        assert (_enemy.crit_chance, _enemy.crit_damage_points) == (0, 0)


class TestEnemyHitResolutionOrder:
    """The hit tuple's twin booleans (strip, glancing) must arrive in
    the caller's unpack order — a crossed pair silently swaps the log
    line's strip/glance clause (reviewer catch, 4.1 commit 2)."""

    def test_strip_and_glance_positions_are_not_crossed(self):
        from src.spacehack.combat import _ai as _ai_mod
        _state = SimpleNamespace(
            player_state={
                "pos": world.Position(0, 0), "hull": 100, "shields": 0,
                "piloting": 100,  # glance threshold 50: roll 50 glances
            },
        )
        _ei = EnemyInstance(
            spec_id="pirate_scout", name="Pirate Scout", char="P",
            fg=(255, 100, 100), pos=world.Position(3, 0),
            hull=100, max_hull=100, pilot_piloting=0,
            crit_chance=100, crit_damage_points=0,
        )
        import src.spacehack.combat._actions as _actions_mod
        _real_rng = _actions_mod.RNG
        _actions_mod.RNG = SimpleNamespace(
            randint=lambda *_a: 50, uniform=lambda *_a: 1.0,
        )
        try:
            import src.spacehack.engine as _engine
            _real_engine_rng = _engine.RNG
            _engine.RNG = SimpleNamespace(randint=lambda *_a: 50)
            try:
                _dmg, _sdmg, _fh, _strip, _glance, _crit, _popup = (
                    _ai_mod._enemy_hit_resolution(
                        _state, _ei, "light_laser", 0,
                    )
                )
            finally:
                _engine.RNG = _real_engine_rng
        finally:
            _actions_mod.RNG = _real_rng
        # light_laser vs shields 0: no strip; piloting 100 + roll 50
        # glances; crit_chance 100 crits. Positions must agree.
        assert _strip is False
        assert _glance is True
        assert _crit is True
        assert _popup == ("CRIT -3", (255, 60, 60))  # 4 x 0.5 glance x 1.5 crit
