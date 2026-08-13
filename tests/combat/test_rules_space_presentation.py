"""Tests for live space-combat shield-bubble presentation."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import world, pygame_overlay
from src.spacehack.combat import _rules_space


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
    """When combat ends (victory/flee), the survivors resume patrolling."""
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
