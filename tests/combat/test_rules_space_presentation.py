"""Tests for live space-combat shield-bubble presentation."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import world, pygame_overlay, pygame_target_card
from src.spacehack.combat import _rules_space, _space_presentation
from src.spacehack.combat._types import EnemyInstance


def _state(*, player_shields=12, enemy_shields=8, active=True):
    player_entity = world.Entity(
        "@", (255, 255, 255), world.Position(7, 5),
        ship_id="scout", owned=True,
    )
    enemy_entity = world.Entity(
        "P", (255, 100, 100), world.Position(11, 6),
        npc_ship_id="pirate_scout",
    )
    ctx = SimpleNamespace()
    state = _rules_space.SpaceCombatState(
        ctx=ctx,
        console=None,
        game_map=SimpleNamespace(width=30, height=20),
        log=None,
        player_state={
            "shields": player_shields,
            "max_shields": 20,
            "pos": world.Position(7, 5),
        },
        enemy_insts=[SimpleNamespace(
            alive=True,
            shields=enemy_shields,
            max_shields=16,
            pos=world.Position(11, 6),
        )],
        enemy_ents={0: enemy_entity},
        player_ent=player_entity,
        active=active,
    )
    return ctx, state


def test_presentation_bubbles_use_live_shields_and_camera():
    ctx, state = _state()
    old_state = _rules_space._state
    _rules_space._state = state
    try:
        assert _rules_space.presentation_shield_bubbles(
            ctx=ctx, camera_x=3, camera_y=2,
        ) == (
            # player: 7 - 3, 5 - 2, 12/20 strength
            pygame_overlay.ShieldBubble(4, 3, 1, 1, 0.6),
            # enemy: 11 - 3, 6 - 2, 8/16 strength
            pygame_overlay.ShieldBubble(8, 4, 1, 1, 0.5),
        )
    finally:
        _rules_space._state = old_state


def test_presentation_bubbles_omit_zero_shields_and_inactive_combat():
    ctx, state = _state(player_shields=0, enemy_shields=0)
    old_state = _rules_space._state
    _rules_space._state = state
    try:
        assert _rules_space.presentation_shield_bubbles(ctx=ctx) == ()
        state.active = False
        assert _rules_space.presentation_shield_bubbles(ctx=ctx) == ()
    finally:
        _rules_space._state = old_state


def test_presentation_bubbles_reject_unrelated_context():
    _ctx, state = _state()
    old_state = _rules_space._state
    _rules_space._state = state
    try:
        assert _rules_space.presentation_shield_bubbles(ctx=SimpleNamespace()) == ()
    finally:
        _rules_space._state = old_state


# ---------------------------------------------------------------------------
# Combat locks — combat participants must not be patrolled mid-fight
# ---------------------------------------------------------------------------


def test_check_reinforcements_locks_combat_entities_before_tick(monkeypatch):
    """Enemies are frozen from the ambient patrol pass BEFORE move_npcs
    runs, so they can't drift/despawn mid-combat (the 'enemy
    disappeared' bug)."""
    ctx, state = _state()
    old_state = _rules_space._state
    _rules_space._state = state
    _lock_seen = []
    try:
        from src.spacehack import npc_ships, navigation

        def _fake_tick(ctx, game_map):
            _lock_seen.append(getattr(state.enemy_ents[0], "combat_locked", False))

        monkeypatch.setattr(npc_ships, "move_npcs", _fake_tick)
        monkeypatch.setattr(
            navigation, "_detect_combat_encounter",
            lambda *a, **k: None,
        )

        _rules_space.check_reinforcements(ctx, SimpleNamespace())
    finally:
        _rules_space._state = old_state

    assert _lock_seen == [True]
    assert getattr(state.enemy_ents[0], "combat_locked", False) is True


def test_sync_state_releases_combat_locks(monkeypatch):
    """When combat ends (victory/defeat), the survivors resume patrolling."""
    ctx, state = _state()
    ctx.player_owned_ship = None  # read by sync_state before the patched helpers
    state.enemy_ents[0].combat_locked = True
    old_state = _rules_space._state
    _rules_space._state = state
    try:
        monkeypatch.setattr(_rules_space, "_sync_back_hull", lambda *a, **k: None)
        monkeypatch.setattr(_rules_space, "_sync_back_ammo", lambda *a, **k: None)
        _rules_space.sync_state(ctx)
    finally:
        _rules_space._state = old_state

    assert not hasattr(state.enemy_ents[0], "combat_locked")
    assert state.active is False


# ---------------------------------------------------------------------------
# Floating target card
# ---------------------------------------------------------------------------


def _card_enemy():
    return EnemyInstance(
        spec_id="pirate_scout",
        name="Pirate Scout",
        char="P",
        fg=(255, 100, 100),
        hull=20,
        max_hull=30,
        shields=8,
        max_shields=10,
        ap_remaining=2,
        ap_total=3,
        pos=world.Position(5, 3),
        weapons=("light_laser",),
    )


def _card_map(width=80, height=54):
    _tiles = [[world.DUNGEON_FLOOR for _ in range(width)] for _ in range(height)]
    return world.GameMap(width, height, _tiles, [])


def test_space_card_rows_show_hull_shield_ap_and_weapons():
    rows = _space_presentation._space_card_rows(_card_enemy(), hit_chance=62)
    _segs = [seg for row in rows for seg in row]
    assert [t for t, _c in _segs] == [
        "Pirate Scout", "HULL 20/30", "  HIT 62%", "SHD 8/10", "AP 3",
        "Light Laser", "DMG 4  RNG 1-5", "[V] hide",
    ]


def test_space_target_card_quick_row_shows_selected_resource_costs():
    ctx = SimpleNamespace(player_traits=())
    state = _rules_space.SpaceCombatState(
        ctx=ctx,
        console=None,
        game_map=_card_map(),
        log=None,
        player_state={
            "pos": world.Position(0, 0),
            "ap_remaining": 4,
            "ap_total": 4,
            "power_pool": 26,
            "gunnery": 20,
            "hull": 8,
            "max_hull": 26,
        },
        enemy_insts=[
            EnemyInstance(
                spec_id="pirate_scout",
                name="Pirate Scout",
                char="P",
                fg=(255, 100, 100),
                hull=4,
                max_hull=25,
                pos=world.Position(5, 3),
                weapons=("light_laser",),
            ),
        ],
        target_idx=0,
        weapons_list=["light_laser"],
        active_weapons=[True],
    )
    old_state = _rules_space._state
    _rules_space._state = state
    try:
        card = _rules_space.presentation_target_card(ctx=ctx)
    finally:
        _rules_space._state = old_state

    assert card is not None
    assert card.quick_rows == (
        (("4 AP -1/26 POW -4/25 HP", pygame_target_card.TARGET_CARD_TEXT),),
    )


def test_space_card_rows_omit_shield_when_unshielded():
    enemy = _card_enemy()
    enemy.shields = 0
    enemy.max_shields = 0
    rows = _space_presentation._space_card_rows(enemy, hit_chance=None)
    _segs = [seg for row in rows for seg in row]
    assert [t for t, _c in _segs] == [
        "Pirate Scout", "HULL 20/30", "  HIT --", "AP 3",
        "Light Laser", "DMG 4  RNG 1-5", "[V] hide",
    ]


def test_space_card_rows_color_hit_chance_by_range_band():
    from src.spacehack.hud import COLOR_RANGE_GREEN, COLOR_RANGE_RED
    rows = _space_presentation._space_card_rows(
        _card_enemy(), hit_chance=62, hit_color=COLOR_RANGE_GREEN,
    )
    _segs = [seg for row in rows for seg in row]
    assert _segs[2] == ("  HIT 62%", COLOR_RANGE_GREEN)
    # No hit chance (no active weapon) → plain text color.
    rows = _space_presentation._space_card_rows(
        _card_enemy(), hit_chance=None, hit_color=COLOR_RANGE_RED,
    )
    _segs = [seg for row in rows for seg in row]
    assert _segs[2] == ("  HIT --", pygame_target_card.TARGET_CARD_TEXT)


def test_volley_costs_takes_max_ap_and_sums_power():
    from src.spacehack.data.weapons import find_weapon
    from src.spacehack.hud import volley_costs
    # light_laser (energy, AP 1, POW 1), heavy_laser (energy, AP 1, POW 2),
    # light_missile (missile, AP 2, no power): burst AP is the max-once
    # cost, power genuinely sums across energy/plasma weapons only.
    _weapons = ["light_laser", "heavy_laser", "light_missile"]
    assert volley_costs(_weapons, [True, True, True], find_weapon) == (3, 2, 3)
    assert volley_costs(_weapons, [True, False, True], find_weapon) == (2, 2, 1)
    # No toggle data → every weapon counts (matches the display fallback).
    assert volley_costs(_weapons, None, find_weapon) == (3, 2, 3)


def test_range_band_color_matches_targeting_line():
    from src.spacehack.hud import (
        COLOR_RANGE_GREEN,
        COLOR_RANGE_ORANGE,
        COLOR_RANGE_RED,
        COLOR_RANGE_YELLOW,
        range_band_color,
    )
    # Green inside the close-bonus zone (max_range // 2).
    assert range_band_color(2, 5, 1) == COLOR_RANGE_GREEN
    # Yellow within normal range.
    assert range_band_color(4, 5, 1) == COLOR_RANGE_YELLOW
    # Red beyond max range.
    assert range_band_color(7, 5, 1) == COLOR_RANGE_RED
    # Orange reserved for inside-min-range bands the line itself uses.
    assert range_band_color(3, 2, 4) == COLOR_RANGE_ORANGE


def test_hit_color_for_weapon_none_when_unarmed_or_unknown():
    from src.spacehack.combat._card_presentation import hit_color_for_weapon
    from src.spacehack.hud import COLOR_RANGE_RED
    _pos = world.Position(5, 3)
    _ppos = world.Position(0, 0)
    assert hit_color_for_weapon(None, _pos, _ppos, _space_presentation._find_w) is None
    assert hit_color_for_weapon("missing_gun", _pos, _ppos, _space_presentation._find_w) is None
    # (0,0) → (5,3) is ~5.8u, beyond light_laser's max range (5) → red.
    assert hit_color_for_weapon("light_laser", _pos, _ppos, _space_presentation._find_w) == COLOR_RANGE_RED


def test_space_build_target_card_colors_hit_by_weapon_range():
    from src.spacehack.hud import COLOR_RANGE_RED

    card = _space_presentation.build_target_card(
        _card_enemy(),
        game_map=_card_map(),
        player_pos=world.Position(0, 0),
        region_w=80,
        region_h=54,
        hit_chance=55,
        hit_weapon_id="light_laser",
        avoid_positions=(world.Position(0, 0), world.Position(5, 3)),
    )

    assert card is not None
    _segs = [seg for row in card.rows for seg in row]
    assert _segs[2] == ("  HIT 55%", COLOR_RANGE_RED)


def test_space_build_target_card_anchors_and_avoids():
    card = _space_presentation.build_target_card(
        _card_enemy(),
        game_map=_card_map(),
        player_pos=world.Position(0, 0),
        region_w=80,
        region_h=54,
        hit_chance=55,
        avoid_positions=(world.Position(0, 0), world.Position(5, 3)),
    )

    assert card is not None
    assert (card.x, card.y) == (5, 3)
    assert card.player_cell == (0, 0)
    assert card.avoid_cells == ((0, 0), (5, 3))


def test_presentation_target_card_toggles_and_requires_active():
    ctx = SimpleNamespace(player_traits=())
    state = _rules_space.SpaceCombatState(
        ctx=ctx,
        console=None,
        game_map=_card_map(),
        log=None,
        player_state={"pos": world.Position(0, 0)},
        enemy_insts=[_card_enemy()],
        target_idx=0,
        weapons_list=(),
        active_weapons=(),
    )
    old_state = _rules_space._state
    _rules_space._state = state
    try:
        card = _rules_space.presentation_target_card(ctx=ctx)
        assert card is not None
        assert card.rows[0] == (("Pirate Scout", pygame_target_card.TARGET_CARD_TITLE),)

        _rules_space.toggle_target_card(ctx)
        assert _rules_space.presentation_target_card(ctx=ctx) is None

        _rules_space.toggle_target_card(ctx)
        state.active = False
        assert _rules_space.presentation_target_card(ctx=ctx) is None
    finally:
        _rules_space._state = old_state


# ---------------------------------------------------------------------------
# Kill XP (granted at kill time, not in the victory pass)
# ---------------------------------------------------------------------------

def test_finalize_kill_awards_hull_based_xp_and_counts_kill_once(monkeypatch):
    """A space kill grants base_hull * 2 XP at kill time and one total_kills.

    Regression: the old lookup passed the NPC-spec id (``pirate_scout``)
    straight to the ship catalog, which raised KeyError and silently
    dropped the XP until the victory pass (and flee-adjacent paths missed
    it entirely).
    """
    from src.spacehack.data.npc_ships import find_npc_ship
    from src.spacehack.data.ships import find_ship

    monkeypatch.setattr(_rules_space, "_spawn_loot_drops", lambda *a, **k: None)

    ctx = SimpleNamespace(
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        player_traits=[],
        player_counters=SimpleNamespace(total_kills=0),
        log=SimpleNamespace(add_colored=lambda *a, **k: None),
    )
    state = _rules_space.SpaceCombatState(
        ctx=ctx,
        console=None,
        game_map=SimpleNamespace(entities=[]),
        log=None,
        enemy_specs=[find_npc_ship("pirate_scout")],
        enemy_insts=[EnemyInstance(
            spec_id="pirate_scout", name="Pirate Scout", char="p",
            fg=(255, 100, 100), pos=world.Position(11, 6),
        )],
        cr=_rules_space.CombatResult(),
    )
    old_state = _rules_space._state
    _rules_space._state = state
    try:
        _rules_space._finalize_kill(
            ctx, SimpleNamespace(entities=[]), state.enemy_insts[0], None,
        )
    finally:
        _rules_space._state = old_state

    _sc = find_ship("scout")
    assert ctx.player_xp == _sc.base_hull * 2
    assert ctx.player_counters.total_kills == 1
    assert state.cr.defeated_spec_ids == ["pirate_scout"]
