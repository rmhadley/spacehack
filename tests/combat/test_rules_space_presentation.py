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
