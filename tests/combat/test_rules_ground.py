"""Tests for combat/_rules_ground.py — pure formula functions.

Ground combat accuracy, damage, and movement dodge — same
invisible-regression risk as space combat math.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from types import SimpleNamespace

import pytest

from src.spacehack import ui, world, pygame_target_card
from src.spacehack.combat import _loop, _rules_ground
from src.spacehack.engine import HUD_WIDTH, SCREEN_HEIGHT, SCREEN_WIDTH
from src.spacehack.framebuffer import FrameBuffer
from src.spacehack.combat import _ground_render
from src.spacehack.combat import _ground_presentation
from src.spacehack.combat._rules_ground import (
    _ground_hit_chance_raw,
    _ground_damage_raw,
    _calc_ground_move_dodge,
    _ground_point_blank_penalty,
)
from src.spacehack.ground_equipment import (
    GroundItemStack,
    GroundWeaponInstance,
    weapon_instance as _weapon,
)


def test_ground_volley_costs_uses_max_ap():
    from src.spacehack.data.ground_weapons import find_ground_weapon
    from src.spacehack.hud import volley_costs
    # fists (AP 1), power_fist (AP 2) — ground has no power economy, so
    # the burst AP (max-once) is the whole volley cost.
    assert volley_costs(["fists", "power_fist"], [True, True], find_ground_weapon) == (2, 2, 0)
    assert volley_costs(["fists", "power_fist"], [True, False], find_ground_weapon) == (1, 1, 0)


# ---------------------------------------------------------------------------
# _ground_hit_chance_raw
# ---------------------------------------------------------------------------

class TestGroundHitChanceRaw:
    """accuracy + att_reflexes//2 - tgt_reflexes//2 - dodge + hit_bonus,
    clamped 5-95."""

    def test_basic(self):
        """fists: accuracy=90, reflexes 20 vs 10,
        no dodge → 90 + 10 - 5 = 95."""
        chance = _ground_hit_chance_raw("fists", 20, 10, 0, 0)
        assert chance == 95

    def test_attacker_advantage(self):
        """High reflexes attacker."""
        chance = _ground_hit_chance_raw("fists", 40, 10, 0, 0)
        # 85 + 20 - 5 = 100 → clamped 95
        assert chance == 95

    def test_target_dodge(self):
        """Movement dodge reduces hit chance."""
        chance = _ground_hit_chance_raw("fists", 20, 10, 20, 0)
        # 90 + 10 - 5 - 20 = 75
        assert chance == 75

    def test_hit_bonus(self):
        """Sharpshooter +10%."""
        chance = _ground_hit_chance_raw("fists", 20, 10, 0, hit_bonus=10)
        # 85 + 10 - 5 + 10 = 100 → 95
        assert chance == 95

    def test_clamped_low(self):
        chance = _ground_hit_chance_raw("fists", 0, 100, 200, 0)
        assert chance == 5

    def test_point_blank_penalty_can_be_applied(self):
        chance = _ground_hit_chance_raw(
            "kinetic_rifle", 20, 10, range_penalty=35,
        )
        assert chance == 38


# ---------------------------------------------------------------------------
# _ground_damage_raw
# ---------------------------------------------------------------------------

class TestGroundDamageRaw:
    """Base damage + str//10 (melee only) - armor, min 1."""

    def test_basic(self):
        """fists: damage=1 (melee), str=20 → +2, armor=0 → 3."""
        dmg = _ground_damage_raw("fists", 20, 0)
        assert dmg == 3  # 1 + 2 - 0

    def test_armor_mitigation(self):
        """armor=3 reduces damage by 3."""
        dmg = _ground_damage_raw("fists", 20, 3)
        assert dmg == 1  # 2 + 2 - 3 = 1

    def test_no_strength_bonus_ranged(self):
        """Ranged weapons don't get the str//10 bonus."""
        # laser_pistol: damage=4, energy type (no str bonus)
        dmg = _ground_damage_raw("laser_pistol", 50, 0)
        assert dmg == 4  # 4 + 0 - 0

    def test_min_1(self):
        """Never below 1 damage."""
        dmg = _ground_damage_raw("fists", 0, 100)
        assert dmg == 1

    def test_plasma_halves_armor(self):
        """plasma_pistol dmg 8 vs armor 6 → 6//2=3 → 5."""
        assert _ground_damage_raw("plasma_pistol", 10, 6) == 5

    def test_plasma_odd_armor_rounds_down(self):
        """armor 5 → 5//2=2 → plasma_pistol 8 - 2 = 6."""
        assert _ground_damage_raw("plasma_pistol", 10, 5) == 6

    def test_melee_bonus_applies_to_melee_only(self):
        assert _ground_damage_raw("fists", 10, 0, melee_bonus=2) == 4  # 1+1+2
        assert _ground_damage_raw("laser_pistol", 50, 0, melee_bonus=2) == 4

    def test_armor_bypass_ignores_armor_entirely(self):
        """mono_blade dmg 13, str 20 → +2, armor 3 ignored → 15."""
        assert _ground_damage_raw("mono_blade", 20, 3) == 15

    def test_armor_bypass_still_gets_strength_bonus(self):
        """Bypass removes armor but keeps the melee strength bonus."""
        assert _ground_damage_raw("mono_blade", 40, 100) == 17  # 13 + 4 - 0


class TestEnemyDetailLines:
    def _enemy(self, armor=0, weapon_id=""):
        return _rules_ground.GroundEnemyInstance(
            entity=SimpleNamespace(),
            spec=SimpleNamespace(armor=armor),
            weapon_id=weapon_id,
        )

    def test_unarmored_enemy_reports_arm_0(self):
        assert _ground_presentation.enemy_detail_lines(self._enemy(armor=0)) == (
            "ARM 0", "Unarmed", "",
        )

    def test_armored_enemy_reports_armor_value(self):
        assert _ground_presentation.enemy_detail_lines(
            self._enemy(armor=3, weapon_id="drone_laser"),
        )[0] == "ARM 3"

    def test_weapon_lines_split_name_from_dmg_range(self):
        _armor, _name, _stats = _ground_presentation.enemy_detail_lines(
            self._enemy(armor=1, weapon_id="frost_bolt"),
        )
        assert _name == "Frost Bolt"
        assert _stats == "DMG 4  RNG 1-5"

    def test_melee_weapon_reports_range_1_1(self):
        _armor, _name, _stats = _ground_presentation.enemy_detail_lines(
            self._enemy(weapon_id="combat_knife"),
        )
        assert _stats == "DMG 3  RNG 1-1"

    def test_unknown_weapon_falls_back_to_unarmed(self):
        assert _ground_presentation.enemy_detail_lines(
            self._enemy(weapon_id="missing_weapon"),
        )[1] == "Unarmed"


class TestEnemyThreatColor:
    def _enemy(self, weapon_id=""):
        return _rules_ground.GroundEnemyInstance(
            entity=SimpleNamespace(),
            spec=SimpleNamespace(armor=0),
            weapon_id=weapon_id,
        )

    def test_in_range_is_danger(self):
        assert _ground_presentation.enemy_threat_color(
            self._enemy("frost_bolt"), 3,
        ) == _ground_presentation.COLOR_DIST_DANGER

    def test_out_of_range_is_safe(self):
        assert _ground_presentation.enemy_threat_color(
            self._enemy("frost_bolt"), 9,
        ) == _ground_presentation.COLOR_DIST_SAFE

    def test_inside_min_range_is_too_close(self):
        # kinetic_rifle min_range=2: adjacent is too close to fire.
        assert _ground_presentation.enemy_threat_color(
            self._enemy("kinetic_rifle"), 1,
        ) == _ground_presentation.COLOR_DIST_TOO_CLOSE

    def test_unarmed_is_dim(self):
        assert _ground_presentation.enemy_threat_color(
            self._enemy(), 3,
        ) == ui.COLOR_VALUE_DIM


def test_damage_subtracts_enemy_armor_and_applies_cybernetic_melee():
    """Player melee vs an armored enemy: armor reduces, cyber arms add."""
    _enemy = _rules_ground.GroundEnemyInstance(
        entity=SimpleNamespace(),
        spec=SimpleNamespace(armor=3),
        hp=30,
    )
    _ctx = SimpleNamespace(
        ground_stats=SimpleNamespace(strength=20),
        equipped_ground_armor={"hands": "cybernetic_arms"},
    )
    _dmg, _glance = _rules_ground.damage("fists", _enemy, _ctx)
    assert _dmg == 2  # 1 + 2 (str) + 2 (cyber arms) - 3 (armor)
    assert _glance is False
    assert _enemy.hp == 28


# ---------------------------------------------------------------------------
# _calc_ground_move_dodge
# ---------------------------------------------------------------------------

class TestGroundPointBlankPenalty:
    def test_no_penalty_at_or_beyond_min_range(self):
        assert _ground_point_blank_penalty("kinetic_rifle", 2) == 0
        assert _ground_point_blank_penalty("kinetic_rifle", 4) == 0

    def test_penalty_scales_inside_min_range(self):
        assert _ground_point_blank_penalty("kinetic_rifle", 1) == 35
        assert _ground_point_blank_penalty("kinetic_rifle", 0) == 70


class TestGroundCanFire:
    def test_min_range_weapon_has_emergency_point_blank_action(self):
        _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)]
        _game_map = world.GameMap(5, 5, _tiles, [])
        _player = world.Entity(
            "@", (255, 255, 255), world.Position(2, 2), "Player",
        )
        _enemy = world.Entity(
            "D", (255, 100, 100), world.Position(2, 3), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _game_map.entities.extend((_player, _enemy))
        _ctx = SimpleNamespace(
            player=_player,
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
            ground_hp=23,
            ground_max_hp=23,
            equipped_ground_weapons=[_weapon("kinetic_rifle")],
            equipped_ground_armor={},
            player_traits=[],
            log=SimpleNamespace(
                add=lambda _message: None,
                add_colored=lambda _message, _color: None,
            ),
        )

        _rules_ground.init(_ctx, [_enemy], _game_map)

        _ok, _reason = _rules_ground.can_fire(0, _ctx)

        assert _ok
        assert "Emergency point-blank shot" in _reason


class TestGroundPointBlankFire:
    def test_two_adjacent_drones_do_not_softlock_min_range_rifles(self, monkeypatch):
        _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)]
        _game_map = world.GameMap(5, 5, _tiles, [])
        _player = world.Entity(
            "@", (255, 255, 255), world.Position(2, 2), "Player",
        )
        _left = world.Entity(
            "D", (255, 100, 100), world.Position(2, 1), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _right = world.Entity(
            "D", (255, 100, 100), world.Position(2, 3), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _game_map.entities.extend((_player, _left, _right))
        _messages = []
        _ctx = SimpleNamespace(
            player=_player,
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
            ground_hp=23,
            ground_max_hp=23,
            equipped_ground_weapons=[_weapon("kinetic_rifle"), _weapon("kinetic_rifle")],
            equipped_ground_armor={},
            player_traits=[],
            log=SimpleNamespace(
                add=_messages.append,
                add_colored=lambda _message, _color: _messages.append(_message),
            ),
        )

        _rules_ground.init(_ctx, [_left, _right], _game_map)
        monkeypatch.setattr(_rules_ground, "animate_fire", lambda *args, **kwargs: None)
        monkeypatch.setattr(_loop, "RNG", SimpleNamespace(randint=lambda *_args: 1))

        _loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0)

        assert _rules_ground.player_ap(_ctx) == 2
        assert _left.hp < 39
        assert any("Emergency point-blank shot" in _message for _message in _messages)

    def test_point_blank_still_requires_clear_los(self, monkeypatch):
        _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)]
        _tiles[3][2] = world.DUNGEON_WALL
        _game_map = world.GameMap(5, 5, _tiles, [])
        _player = world.Entity(
            "@", (255, 255, 255), world.Position(2, 2), "Player",
        )
        _enemy = world.Entity(
            "D", (255, 100, 100), world.Position(2, 4), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _game_map.entities.extend((_player, _enemy))
        _ctx = SimpleNamespace(
            player=_player,
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
            ground_hp=23,
            ground_max_hp=23,
            equipped_ground_weapons=[_weapon("kinetic_rifle")],
            equipped_ground_armor={},
            player_traits=[],
            log=SimpleNamespace(
                add=lambda _message: None,
                add_colored=lambda _message, _color: None,
            ),
        )

        _rules_ground.init(_ctx, [_enemy], _game_map)
        monkeypatch.setattr(
            _rules_ground,
            "_find_gw",
            lambda _weapon_id: SimpleNamespace(min_range=3, max_range=7, ap_cost=2),
        )

        _ok, _reason = _rules_ground.can_fire(0, _ctx)

        assert not _ok
        assert _reason == "Blocked by wall"

    def test_point_blank_still_requires_ap(self):
        _tiles = [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)]
        _game_map = world.GameMap(5, 5, _tiles, [])
        _player = world.Entity(
            "@", (255, 255, 255), world.Position(2, 2), "Player",
        )
        _enemy = world.Entity(
            "D", (255, 100, 100), world.Position(2, 3), "Assault Drone",
            npc_char_id="assault_drone",
        )
        _game_map.entities.extend((_player, _enemy))
        _ctx = SimpleNamespace(
            player=_player,
            ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
            ground_hp=23,
            ground_max_hp=23,
            equipped_ground_weapons=[_weapon("kinetic_rifle")],
            equipped_ground_armor={},
            player_traits=[],
            log=SimpleNamespace(
                add=lambda _message: None,
                add_colored=lambda _message, _color: None,
            ),
        )

        _rules_ground.init(_ctx, [_enemy], _game_map)
        _rules_ground.set_player_ap(_ctx, 0)

        _ok, _reason = _rules_ground.can_fire(0, _ctx)

        assert not _ok
        assert "Need 2 AP" in _reason


def test_refresh_equipment_state_rebuilds_weapon_and_armor_cache(monkeypatch):
    _ctx = SimpleNamespace(
        equipped_ground_weapons=[_weapon("laser_pistol")],
        equipped_ground_armor={"body": "heavy_vest"},
    )
    monkeypatch.setattr(
        _rules_ground,
        "_state",
        _rules_ground.GroundCombatState(
        ctx=_ctx,
        game_map=SimpleNamespace(),
        active_weapon_list=[False, True],
            armor_defense=0,
        ),
    )

    _ctx.equipped_ground_weapons[:] = [_weapon("laser_rifle")]
    _rules_ground.refresh_equipment_state(_ctx)

    assert _rules_ground._state.active_weapon_list == [False]
    assert _rules_ground._state.armor_defense == 5


class TestCalcGroundMoveDodge:
    def test_no_movement(self):
        assert _calc_ground_move_dodge(0) == 0

    def test_one_cell(self):
        assert _calc_ground_move_dodge(1) == 5

    def test_four_cells(self):
        assert _calc_ground_move_dodge(4) == 20

    def test_cap(self):
        """7 cells → 30 (capped, not 35)."""
        assert _calc_ground_move_dodge(7) == 30


# ---------------------------------------------------------------------------
# range_line_hidden — targeting line suppressed during animations / enemy turn
# ---------------------------------------------------------------------------

def _ground_fixture():
    """Minimal map + ctx + console for render_frame-style tests."""
    _tiles = [[world.DUNGEON_FLOOR for _ in range(7)] for _ in range(7)]
    _game_map = world.GameMap(7, 7, _tiles, [])
    _player = world.Entity(
        "@", (255, 255, 255), world.Position(3, 3), "Player",
    )
    _enemy = world.Entity(
        "D", (255, 100, 100), world.Position(3, 5), "Assault Drone",
        npc_char_id="assault_drone",
    )
    _game_map.entities.extend((_player, _enemy))
    _ctx = SimpleNamespace(
        player=_player,
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        ground_hp=23,
        ground_max_hp=23,
        equipped_ground_weapons=[_weapon("fists")],
        equipped_ground_armor={},
        player_traits=[],
        log=SimpleNamespace(
            add=lambda _message: None,
            add_colored=lambda _message, _color: None,
        ),
    )
    _console = SimpleNamespace(clear=lambda: None, print=lambda *a, **k: None)
    return _ctx, _game_map, _console, _enemy


def _patch_render_deps(monkeypatch, line_calls: list) -> None:
    """Neutralize render_frame's heavy deps; record range-line calls."""
    monkeypatch.setattr(
        _ground_render, "_ground_range_line",
        lambda *a, **k: line_calls.append(a),
    )
    monkeypatch.setattr(
        _ground_render, "world",
        SimpleNamespace(
            camera_for_view=lambda *a, **k: (0, 0, 0, 0),
            render_world_view=lambda *a, **k: None,
        ),
    )
    monkeypatch.setattr(_ground_render, "_paint_target_highlight", lambda *a, **k: None)
    monkeypatch.setattr(
        _ground_render, "_ml",
        SimpleNamespace(render_message_log=lambda *a, **k: None),
    )
    monkeypatch.setattr(_ground_render, "_bar_str", lambda *a, **k: "########")


def test_ground_player_hp_row_shows_current_max_and_active_regen():
    """The player row uses numeric HP and shows the next regen amount."""
    _ctx, _game_map, _console, _enemy = _ground_fixture()
    _ctx.ground_hp = 10
    _rules_ground.init(_ctx, [_enemy], _game_map)
    _rules_ground.apply_consumable_effect(
        _ctx,
        SimpleNamespace(
            effect_id="restore_hp",
            name="Med Pack",
            combat_heal_amount=5,
            combat_regen_amount=2,
            combat_ap_bonus=0,
            duration_turns=3,
        ),
    )
    _frame = FrameBuffer(SCREEN_WIDTH, SCREEN_HEIGHT)
    _ground_render._render_player_panel(_frame, _ctx)
    _hud_x = SCREEN_WIDTH - HUD_WIDTH
    _row = "".join(
        _frame.cell(x, 3).char
        for x in range(_hud_x, SCREEN_WIDTH)
    ).rstrip()
    assert _row
    assert "HP  ####... 15/23 +2" in _row


def test_ground_ap_row_shows_blue_temporary_stim_bonus():
    """An active Combat Stim is visible beside the base AP pool."""
    _ctx, _game_map, _console, _enemy = _ground_fixture()
    _rules_ground.init(_ctx, [_enemy], _game_map)
    _rules_ground.apply_consumable_effect(
        _ctx,
        SimpleNamespace(
            effect_id="stim",
            name="Combat Stim",
            combat_heal_amount=0,
            combat_regen_amount=0,
            combat_ap_bonus=1,
            duration_turns=3,
        ),
    )
    _frame = FrameBuffer(SCREEN_WIDTH, SCREEN_HEIGHT)
    _ground_render._render_player_panel(_frame, _ctx)
    _hud_x = SCREEN_WIDTH - HUD_WIDTH
    _row = "".join(
        _frame.cell(x, 4).char
        for x in range(_hud_x, SCREEN_WIDTH)
    ).rstrip()
    assert _row == "AP: 4/4 +1"
    assert _frame.cell(_hud_x + 8, 4).fg == _ground_render._COLOR_GROUND_TEMP_AP

    for _ in range(4):
        _rules_ground.reset_turn(_ctx)
    _frame = FrameBuffer(SCREEN_WIDTH, SCREEN_HEIGHT)
    _ground_render._render_player_panel(_frame, _ctx)
    _row = "".join(
        _frame.cell(x, 4).char
        for x in range(_hud_x, SCREEN_WIDTH)
    ).rstrip()
    assert _row == "AP: 4/4"


class TestRangeLineHidden:
    def test_render_frame_skips_line_when_flag_set(self, monkeypatch):
        """The line is a player-turn affordance: drawn on the idle
        frame, suppressed when range_line_hidden is set (animation /
        enemy-turn frames)."""
        _ctx, _game_map, _console, _enemy = _ground_fixture()
        _rules_ground.init(_ctx, [_enemy], _game_map)
        _line_calls: list = []
        _patch_render_deps(monkeypatch, _line_calls)

        _rules_ground.render_frame(_console, _ctx, _game_map)
        assert len(_line_calls) == 1  # idle frame: line drawn

        _rules_ground._state.range_line_hidden = True
        _rules_ground.render_frame(_console, _ctx, _game_map)
        assert len(_line_calls) == 1  # suppressed: no new call

    def test_animate_fire_hides_line_for_shot_duration(self, monkeypatch):
        """The flag is set for the whole animation and restored after."""
        _ctx, _game_map, _console, _enemy = _ground_fixture()
        _rules_ground.init(_ctx, [_enemy], _game_map)
        _line_calls: list = []
        _patch_render_deps(monkeypatch, _line_calls)

        _flags_seen: list = []

        def _fake_shot(console, ctx, game_map, from_pos, to_pos, weapon_id,
                       *, is_hit, damage, render_callback):
            _flags_seen.append(_rules_ground._state.range_line_hidden)
            render_callback(console, ctx, game_map)  # one frame mid-shot

        monkeypatch.setattr(_rules_ground, "_animate_ground_shot", _fake_shot)
        _rules_ground._state.range_line_hidden = False

        _rules_ground.animate_fire(
            _console, _ctx, _game_map,
            world.Position(3, 3), world.Position(3, 5), True,
            None, weapon_id="fists",
        )

        assert _flags_seen == [True]
        assert _line_calls == []  # the mid-shot frame drew no range line
        assert _rules_ground._state.range_line_hidden is False  # restored

    def test_run_enemy_turns_hides_line_for_whole_enemy_turn(self, monkeypatch):
        """The flag is set across the entire enemy turn and restored."""
        _ctx, _game_map, _, _enemy = _ground_fixture()
        _rules_ground.init(_ctx, [_enemy], _game_map)

        _flags_seen: list = []

        def _fake_impl(ctx, game_map, _enemy_ai):
            _flags_seen.append(_rules_ground._state.range_line_hidden)
            return 0

        monkeypatch.setattr(_rules_ground, "_run_enemy_turns_impl", _fake_impl)
        _rules_ground._state.range_line_hidden = False

        _result = _rules_ground.run_enemy_turns(_ctx, _game_map)

        assert _flags_seen == [True]
        assert _result == 0
        assert _rules_ground._state.range_line_hidden is False  # restored

    def test_flag_restored_even_on_exception(self, monkeypatch):
        """try/finally semantics: an error mid-turn leaves the flag clean."""
        _ctx, _game_map, _, _enemy = _ground_fixture()
        _rules_ground.init(_ctx, [_enemy], _game_map)

        def _boom(ctx, game_map, _enemy_ai):
            raise RuntimeError("boom")

        monkeypatch.setattr(_rules_ground, "_run_enemy_turns_impl", _boom)
        _rules_ground._state.range_line_hidden = False

        with pytest.raises(RuntimeError):
            _rules_ground.run_enemy_turns(_ctx, _game_map)
        assert _rules_ground._state.range_line_hidden is False


# ---------------------------------------------------------------------------
# combat_locked — engaged enemies must not be patrol-moved mid-fight
# ---------------------------------------------------------------------------


def test_init_locks_engaged_enemies():
    """Combat participants are frozen from move_ground_npcs on init."""
    _ctx, _game_map, _, _enemy = _ground_fixture()
    _rules_ground.init(_ctx, [_enemy], _game_map)

    assert getattr(_enemy, "combat_locked", False) is True


def test_init_applies_cybernetic_ap_and_hp_bonuses():
    """Cybernetic legs add +1 AP; cybernetic torso adds +3 max ground HP."""
    _ctx, _game_map, _, _enemy = _ground_fixture()
    _ctx.equipped_ground_armor = {"legs": "cybernetic_legs", "body": "cybernetic_torso"}
    _rules_ground.init(_ctx, [_enemy], _game_map)

    assert _rules_ground.player_ap_total(_ctx) == 5  # 4 + 1
    assert _rules_ground.player_max_hp(_ctx) == 26  # 20 + 10//3 + 3


def test_check_reinforcements_locks_joins_before_patrol_tick(monkeypatch):
    """Mid-fight joins (refresh_engaged) are frozen before move_ground_npcs."""
    _ctx, _game_map, _, _enemy = _ground_fixture()
    _rules_ground.init(_ctx, [_enemy], _game_map)
    # Simulate a fresh join that was never locked by init: drop the flag
    # and re-add the instance to the state.
    _joiner = world.Entity(
        "p", (255, 100, 100), world.Position(1, 1),
        npc_char_id="dust_prowler",
    )
    _rules_ground._state.enemies.append(
        _rules_ground.GroundEnemyInstance(entity=_joiner, spec=None)
    )

    from src.spacehack import ground_npcs
    _lock_seen = []

    def _fake_move(ctx, game_map):
        _lock_seen.append(getattr(_joiner, "combat_locked", False))

    monkeypatch.setattr(ground_npcs, "move_ground_npcs", _fake_move)

    _rules_ground.check_reinforcements(_ctx, _game_map)

    assert _lock_seen == [True]
    assert getattr(_joiner, "combat_locked", False) is True


def test_sync_state_releases_engaged_enemies():
    """After the fight, survivors resume patrol/wander behaviour."""
    _ctx, _game_map, _, _enemy = _ground_fixture()
    _rules_ground.init(_ctx, [_enemy], _game_map)
    assert getattr(_enemy, "combat_locked", False) is True

    _rules_ground.sync_state(_ctx)

    assert not hasattr(_enemy, "combat_locked")


def _target_card_enemy(weapon_id="drone_laser", x=5, y=3, armor=3, name="Assault Drone"):
    return _rules_ground.GroundEnemyInstance(
        entity=world.Entity("D", (255, 100, 100), world.Position(x, y), name),
        spec=SimpleNamespace(name=name, armor=armor),
        weapon_id=weapon_id,
        hp=12,
        max_hp=30,
    )


class TestBuildTargetCard:
    def test_resolves_weapon_stats_and_viewport_position(self):
        enemy = _target_card_enemy()
        _tiles = [[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(6)]
        _game_map = world.GameMap(8, 6, _tiles, [enemy.entity])

        card = _ground_presentation.build_target_card(
            enemy,
            game_map=_game_map,
            player_pos=world.Position(2, 2),
            region_w=8,
            region_h=6,
            hit_chance=62,
            avoid_positions=(world.Position(2, 2), world.Position(5, 3)),
        )

        assert card is not None
        assert (card.x, card.y) == (5, 3)
        assert card.player_cell == (2, 2)
        assert card.avoid_cells == ((2, 2), (5, 3))
        _segs = [seg for row in card.rows for seg in row]
        assert [t for t, _c in _segs] == [
            "Assault Drone", "HP 12/30", "  HIT 62%", "ARM 3  AP 4",
            "Drone Laser", "DMG 4  RNG 1-6", "[V] hide",
        ]
        assert _segs[0][1] == pygame_target_card.TARGET_CARD_TITLE
        assert _segs[4][1] == pygame_target_card.TARGET_CARD_DIM

    def test_unarmed_enemy_has_blank_weapon_and_no_hit_chance(self):
        enemy = _target_card_enemy(weapon_id="")
        _tiles = [[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(6)]
        _game_map = world.GameMap(8, 6, _tiles, [enemy.entity])

        card = _ground_presentation.build_target_card(
            enemy,
            game_map=_game_map,
            player_pos=world.Position(2, 2),
            region_w=8,
            region_h=6,
        )

        assert card is not None
        assert card.avoid_cells == ()
        _segs = [seg for row in card.rows for seg in row]
        assert [t for t, _c in _segs] == [
            "Assault Drone", "HP 12/30", "  HIT --", "ARM 3  AP 4",
            "Unarmed", "[V] hide",
        ]

    def test_hit_chance_colored_by_range_band(self):
        from src.spacehack.hud import COLOR_RANGE_YELLOW

        enemy = _target_card_enemy()
        _tiles = [[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(6)]
        _game_map = world.GameMap(8, 6, _tiles, [enemy.entity])

        # Player (2,2) → enemy (5,3) is ~3.2u: inside frost_bolt's max
        # range (5) but beyond its close-bonus zone (2) → yellow.
        card = _ground_presentation.build_target_card(
            enemy,
            game_map=_game_map,
            player_pos=world.Position(2, 2),
            region_w=8,
            region_h=6,
            hit_chance=62,
            hit_weapon_id="frost_bolt",
            avoid_positions=(world.Position(2, 2), world.Position(5, 3)),
        )

        assert card is not None
        _segs = [seg for row in card.rows for seg in row]
        assert _segs[2] == ("  HIT 62%", COLOR_RANGE_YELLOW)

    def test_avoid_positions_are_culled_when_off_view(self):
        enemy = _target_card_enemy()
        _tiles = [[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(6)]
        _game_map = world.GameMap(8, 6, _tiles, [enemy.entity])

        card = _ground_presentation.build_target_card(
            enemy,
            game_map=_game_map,
            player_pos=world.Position(2, 2),
            region_w=8,
            region_h=6,
            avoid_positions=(world.Position(2, 2), world.Position(30, 30)),
        )

        # The (30, 30) position is outside the 8x6 viewport and is dropped.
        assert card.avoid_cells == ((2, 2),)

    def test_off_viewport_target_returns_none(self):
        enemy = _target_card_enemy(x=15, y=5)
        _tiles = [[world.DUNGEON_FLOOR for _ in range(20)] for _ in range(12)]
        _game_map = world.GameMap(20, 12, _tiles, [enemy.entity])

        card = _ground_presentation.build_target_card(
            enemy,
            game_map=_game_map,
            player_pos=world.Position(2, 2),
            region_w=8,
            region_h=6,
        )

        assert card is None


class TestTargetCardToggle:
    def test_card_shown_by_default_and_toggle_hides(self):
        _ctx, _game_map, _, _enemy = _ground_fixture()
        _rules_ground.init(_ctx, [_enemy], _game_map)

        card = _rules_ground.presentation_target_card(ctx=_ctx)
        assert card is not None
        assert card.rows[0] == (("Assault Drone", pygame_target_card.TARGET_CARD_TITLE),)

        _rules_ground.toggle_target_card(_ctx)

        assert _rules_ground.presentation_target_card(ctx=_ctx) is None

    def test_toggle_target_card_flips_state(self):
        _ctx, _game_map, _, _enemy = _ground_fixture()
        _rules_ground.init(_ctx, [_enemy], _game_map)

        assert _rules_ground._state.show_target_card is True
        _rules_ground.toggle_target_card(_ctx)
        assert _rules_ground._state.show_target_card is False
        _rules_ground.toggle_target_card(_ctx)
        assert _rules_ground._state.show_target_card is True


def test_finish_combat_deletes_autosave_on_defeat(monkeypatch):
    """The shared combat seam invalidates saves for ground and space death."""
    deleted = []
    monkeypatch.setattr(_loop, "_delete_save", lambda: deleted.append(True))
    _rules = SimpleNamespace(
        sync_state=lambda _ctx: None,
        get_combat_result=lambda: SimpleNamespace(),
    )
    _ctx = SimpleNamespace()

    _result = _loop._finish_combat(_ctx, _rules, "DEFEAT", None)

    assert _result.outcome == "DEFEAT"
    assert deleted == [True]


# ---------------------------------------------------------------------------
# Explosive splash and friendly fire
# ---------------------------------------------------------------------------


def _explosive_fixture(*, player_pos=world.Position(3, 3)):
    """Build a rocket-launcher combat state with adjacent enemies."""
    _tiles = [[world.DUNGEON_FLOOR for _ in range(9)] for _ in range(9)]
    _game_map = world.GameMap(9, 9, _tiles, [])
    _player = world.Entity(
        "@", (255, 255, 255), player_pos, "Player",
    )
    _primary = world.Entity(
        "D", (255, 100, 100), world.Position(3, 5), "Primary",
        npc_char_id="assault_drone",
    )
    _neighbor = world.Entity(
        "D", (255, 100, 100), world.Position(4, 5), "Neighbor",
        npc_char_id="assault_drone",
    )
    _game_map.entities.extend((_player, _primary, _neighbor))
    _ctx = SimpleNamespace(
        player=_player,
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        ground_hp=23,
        ground_max_hp=23,
        equipped_ground_weapons=[_weapon("rocket_launcher")],
        equipped_ground_armor={},
        ground_expedition_items=[GroundItemStack("ammo", "rockets", 4)],
        player_traits=[],
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        log=SimpleNamespace(
            add=lambda _message: None,
            add_colored=lambda _message, _color: None,
        ),
    )
    _rules_ground.init(_ctx, [_primary, _neighbor], _game_map)
    return _ctx, _game_map, _primary, _neighbor


def test_explosive_blast_hits_primary_full_and_neighbors_half():
    _ctx, _game_map, _primary, _neighbor = _explosive_fixture()

    _primary_instance = _rules_ground._state.enemies[0]
    _hits, _player_damage = _rules_ground.explosive_blast(
        "rocket_launcher", _primary_instance, _ctx,
    )

    assert [(enemy.name, damage, primary) for enemy, damage, primary in _hits] == [
        ("Assault Drone", 27, True),
        ("Assault Drone", 13, False),
    ]
    assert _player_damage == 0
    assert _primary.hp == 12
    assert _neighbor.hp == 26


def test_explosive_blast_has_friendly_fire_and_armor_mitigation():
    _ctx, _game_map, _primary, _neighbor = _explosive_fixture(
        player_pos=world.Position(3, 4),
    )

    _primary_instance = _rules_ground._state.enemies[0]
    _hits, _player_damage = _rules_ground.explosive_blast(
        "rocket_launcher", _primary_instance, _ctx,
    )

    assert _player_damage == 15  # half of the 30-damage unarmored blast
    assert _rules_ground.player_hp(_ctx) == 8


def test_explosive_miss_splashes_primary_and_neighbors_for_half_damage():
    _ctx, _game_map, _primary, _neighbor = _explosive_fixture()

    _primary_instance = _rules_ground._state.enemies[0]
    _hits, _player_damage = _rules_ground.explosive_blast(
        "rocket_launcher", _primary_instance, _ctx, primary_hit=False,
    )

    assert [(enemy.name, damage, primary) for enemy, damage, primary in _hits] == [
        ("Assault Drone", 13, False),
        ("Assault Drone", 13, False),
    ]
    assert _player_damage == 0
    assert _primary.hp == 26
    assert _neighbor.hp == 26


def test_explosive_miss_can_still_damage_player_with_friendly_fire():
    _ctx, _game_map, _primary, _neighbor = _explosive_fixture(
        player_pos=world.Position(3, 4),
    )

    _primary_instance = _rules_ground._state.enemies[0]
    _hits, _player_damage = _rules_ground.explosive_blast(
        "rocket_launcher", _primary_instance, _ctx, primary_hit=False,
    )

    assert _hits == (
        (_rules_ground._state.enemies[0], 13, False),
        (_rules_ground._state.enemies[1], 13, False),
    )
    assert _player_damage == 15
    assert _rules_ground.player_hp(_ctx) == 8
    assert _primary.hp == 26


def test_explosive_fire_consumes_one_round_and_resolves_adjacent_kill(monkeypatch):
    _ctx, _game_map, _primary, _neighbor = _explosive_fixture()
    _rules_ground._state.enemies[1].hp = 5
    _neighbor.hp = 5
    monkeypatch.setattr(_rules_ground, "animate_fire", lambda *args, **kwargs: None)
    monkeypatch.setattr(_loop, "RNG", SimpleNamespace(randint=lambda *_args: 1))

    _loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0)

    assert _ctx.equipped_ground_weapons[0] == GroundWeaponInstance("rocket_launcher", 3)
    assert _ctx.ground_expedition_items == [GroundItemStack("ammo", "rockets", 4)]
    assert _neighbor not in _game_map.entities
    assert _primary in _game_map.entities
    assert _rules_ground.player_ap(_ctx) == 1


def test_explosive_miss_consumes_round_and_resolves_neighbor_splash(monkeypatch):
    _ctx, _game_map, _primary, _neighbor = _explosive_fixture()
    monkeypatch.setattr(_rules_ground, "animate_fire", lambda *args, **kwargs: None)
    monkeypatch.setattr(_loop, "RNG", SimpleNamespace(randint=lambda *_args: 100))

    _loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0)

    assert _ctx.equipped_ground_weapons[0] == GroundWeaponInstance("rocket_launcher", 3)
    assert _primary in _game_map.entities
    assert _neighbor in _game_map.entities
    assert _primary.hp == 26
    assert _neighbor.hp == 26
    assert _rules_ground.player_ap(_ctx) == 1


def test_ground_balance_roles_keep_explosives_burstier_than_infinite_plasma():
    """Catalog guardrails for the first hybrid-ammo balance pass."""
    from src.spacehack.data.ground_weapons import find_ground_weapon

    _rocket = find_ground_weapon("rocket_launcher")
    _grenade = find_ground_weapon("grenade_launcher")
    _railgun = find_ground_weapon("railgun")
    _caster = find_ground_weapon("plasma_caster")
    _plasma_pistol = find_ground_weapon("plasma_pistol")
    _carbine = find_ground_weapon("laser_carbine")
    _vibroblade = find_ground_weapon("vibroblade")

    assert (_rocket.damage, _rocket.accuracy, _rocket.reload_ap_cost) == (30, 55, 2)
    assert (_grenade.damage, _grenade.accuracy) == (16, 60)
    assert _railgun.ap_cost == 2
    assert _rocket.damage > _caster.damage
    assert _rocket.ammo_capacity == 4
    assert _caster.ammo_capacity == -1
    assert _plasma_pistol.ap_cost == 2
    assert _carbine.ap_cost == 2
    assert _vibroblade.ap_cost == 2


# ---------------------------------------------------------------------------
# Ammo gating, consumption, and reload (design doc 19, Phase 3)
# ---------------------------------------------------------------------------


def _ammo_ctx(weapon_id: str, loaded: int, *, reserve: int = 0):
    """Build a ground-combat ctx with one weapon instance and optional ammo."""
    _ctx, _game_map, _, _enemy = _ground_fixture()
    _ctx.equipped_ground_weapons = [GroundWeaponInstance(weapon_id, loaded)]
    _ctx.ground_expedition_items = []
    if reserve:
        from src.spacehack.data.ground_weapons import find_ground_weapon
        from src.spacehack.data.ground_items import list_ground_ammo
        ammo_type = find_ground_weapon(weapon_id).ammo_type
        ammo_id = next(a.id for a in list_ground_ammo() if a.ammo_type == ammo_type)
        _ctx.ground_expedition_items = [GroundItemStack("ammo", ammo_id, reserve)]
    _rules_ground.init(_ctx, [_enemy], _game_map)
    return _ctx, _game_map, _enemy


def test_can_fire_blocks_empty_magazine():
    _ctx, _game_map, _enemy = _ammo_ctx("kinetic_pistol", 0)
    _ok, _reason = _rules_ground.can_fire(0, _ctx)
    assert not _ok
    assert "Empty magazine" in _reason


def test_consume_shot_decrements_loaded_ammo():
    _ctx = SimpleNamespace(
        equipped_ground_weapons=[GroundWeaponInstance("kinetic_pistol", 5)],
    )
    _rules_ground.consume_shot(0, _ctx)
    assert _ctx.equipped_ground_weapons == [GroundWeaponInstance("kinetic_pistol", 4)]


def test_reload_weapon_fills_magazine_and_charges_ap():
    _ctx, _game_map, _enemy = _ammo_ctx("kinetic_pistol", 3, reserve=40)
    _rules_ground.set_player_ap(_ctx, 3)

    assert _rules_ground.reload_weapon(_ctx) is True

    assert _ctx.equipped_ground_weapons == [GroundWeaponInstance("kinetic_pistol", 12)]
    assert _ctx.ground_expedition_items == [GroundItemStack("ammo", "pistol_rounds", 31)]
    assert _rules_ground.player_ap(_ctx) == 2


def test_reload_weapon_missing_ammo_leaves_state_and_ap_unchanged():
    _ctx, _game_map, _enemy = _ammo_ctx("kinetic_pistol", 3)
    _rules_ground.set_player_ap(_ctx, 3)

    assert _rules_ground.reload_weapon(_ctx) is False

    assert _ctx.equipped_ground_weapons == [GroundWeaponInstance("kinetic_pistol", 3)]
    assert _rules_ground.player_ap(_ctx) == 3


def _dual_wield_ammo_ctx():
    """Build a two-weapon combat context with both magazines reloadable."""
    _ctx, _game_map, _console, _enemy = _ground_fixture()
    _ctx.equipped_ground_weapons = [
        GroundWeaponInstance("kinetic_pistol", 3),
        GroundWeaponInstance("kinetic_pistol", 11),
    ]
    _ctx.ground_expedition_items = [GroundItemStack("ammo", "pistol_rounds", 40)]
    _rules_ground.init(_ctx, [_enemy], _game_map)
    _rules_ground.set_player_ap(_ctx, 3)
    return _ctx


def test_reload_weapon_chooses_between_multiple_active_weapons(monkeypatch):
    from src.spacehack import pygame_story

    _ctx = _dual_wield_ammo_ctx()
    choices = []

    def _choose(_ctx, **kwargs):
        choices.append(kwargs["options"])
        return "RELOAD_SLOT:1"

    monkeypatch.setattr(pygame_story, "choose", _choose)

    assert _rules_ground.reload_weapon(_ctx) is True
    assert len(choices) == 1
    assert choices[0] == (
        ("Kinetic Pistol 3/12 RES 40", "RELOAD_SLOT:0"),
        ("Kinetic Pistol 11/12 RES 40", "RELOAD_SLOT:1"),
    )
    assert _ctx.equipped_ground_weapons == [
        GroundWeaponInstance("kinetic_pistol", 3),
        GroundWeaponInstance("kinetic_pistol", 12),
    ]
    assert _ctx.ground_expedition_items == [GroundItemStack("ammo", "pistol_rounds", 39)]
    assert _rules_ground.player_ap(_ctx) == 2


def test_reload_weapon_modal_cancel_preserves_both_weapons(monkeypatch):
    from src.spacehack import pygame_story

    _ctx = _dual_wield_ammo_ctx()
    monkeypatch.setattr(
        pygame_story, "choose", lambda *_args, **_kwargs: "__BACK__",
    )

    assert _rules_ground.reload_weapon(_ctx) is False
    assert _ctx.equipped_ground_weapons == [
        GroundWeaponInstance("kinetic_pistol", 3),
        GroundWeaponInstance("kinetic_pistol", 11),
    ]
    assert _ctx.ground_expedition_items == [GroundItemStack("ammo", "pistol_rounds", 40)]
    assert _rules_ground.player_ap(_ctx) == 3


def test_reload_weapon_modal_rejects_an_invalid_slot(monkeypatch):
    from src.spacehack import pygame_story

    _ctx = _dual_wield_ammo_ctx()
    monkeypatch.setattr(
        pygame_story, "choose", lambda *_args, **_kwargs: "RELOAD_SLOT:99",
    )

    assert _rules_ground.reload_weapon(_ctx) is False
    assert _ctx.equipped_ground_weapons == [
        GroundWeaponInstance("kinetic_pistol", 3),
        GroundWeaponInstance("kinetic_pistol", 11),
    ]
    assert _rules_ground.player_ap(_ctx) == 3
