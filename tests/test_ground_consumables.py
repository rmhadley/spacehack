"""Phase 5 tests for ground consumable use and temporary effects."""

from types import SimpleNamespace

from src.spacehack import world
from src.spacehack.combat import _rules_ground
from src.spacehack.ground_consumables import use_consumable
from src.spacehack.ground_equipment import GroundItemStack, weapon_instance


def test_character_rows_make_consumables_selectable():
    from src.spacehack.character_screen import _backpack_item_rows, _item_stack_detail

    ctx = SimpleNamespace(
        ground_expedition_items=[GroundItemStack("consumable", "med_pack", 1)],
    )
    rows = _backpack_item_rows(ctx)

    assert rows[0].action == "PACK_STACK:0"
    assert rows[0].selectable is True
    detail = _item_stack_detail(ctx.ground_expedition_items[0])
    assert "Restore HP" in detail
    assert "restore_hp" not in detail


def test_character_consumable_action_uses_a_charge(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.character_screen import _manage_pack_stack

    ctx = _context(
        hp=7,
        items=[GroundItemStack("consumable", "med_pack", 1)],
    )
    monkeypatch.setattr(
        pygame_story, "choose", lambda *args, **kwargs: "STACK_USE:0",
    )

    assert _manage_pack_stack(ctx, "PACK_STACK:0", in_ground_combat=False) == "USE"
    assert ctx.ground_expedition_items == []
    assert ctx.ground_hp == 23


def test_character_consumable_action_can_discard_a_stack(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.character_screen import _manage_pack_stack

    ctx = _context(items=[GroundItemStack("consumable", "med_pack", 1)])
    monkeypatch.setattr(
        pygame_story, "choose", lambda *args, **kwargs: "STACK_DISCARD:0",
    )

    assert _manage_pack_stack(ctx, "PACK_STACK:0", in_ground_combat=False) == "DISCARD"
    assert ctx.ground_expedition_items == []


def _context(hp=10, items=None):
    player = world.Entity("@", (255, 255, 255), world.Position(2, 2), "Player")
    game_map = world.GameMap(
        5, 5,
        [[world.DUNGEON_FLOOR for _ in range(5)] for _ in range(5)],
        [player],
    )
    messages = []
    return SimpleNamespace(
        player=player,
        game_map=game_map,
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        ground_hp=hp,
        ground_max_hp=23,
        equipped_ground_weapons=[weapon_instance("fists")],
        equipped_ground_armor={},
        ground_expedition_items=list(items or []),
        player_traits=[],
        log=SimpleNamespace(
            add=lambda message: messages.append(message),
            add_colored=lambda message, _color: messages.append(message),
        ),
        messages=messages,
    )


def test_med_pack_fully_heals_outside_combat_and_consumes_one_charge():
    ctx = _context(
        hp=7,
        items=[GroundItemStack("consumable", "med_pack", 2)],
    )

    assert use_consumable(ctx, 0, in_combat=False)
    assert ctx.ground_hp == 23
    assert ctx.ground_expedition_items == [
        GroundItemStack("consumable", "med_pack", 1),
    ]


def test_med_pack_is_not_consumed_outside_combat_when_hp_is_full():
    ctx = _context(
        hp=23,
        items=[GroundItemStack("consumable", "med_pack", 2)],
    )

    assert not use_consumable(ctx, 0, in_combat=False)
    assert ctx.ground_expedition_items == [
        GroundItemStack("consumable", "med_pack", 2),
    ]


def test_stim_is_combat_only():
    ctx = _context(items=[GroundItemStack("consumable", "stim", 1)])

    assert not use_consumable(ctx, 0, in_combat=False)
    assert ctx.ground_expedition_items == [
        GroundItemStack("consumable", "stim", 1),
    ]


def test_combat_med_pack_heals_and_refreshes_three_turn_regen():
    ctx = _context(
        hp=10,
        items=[GroundItemStack("consumable", "med_pack", 2)],
    )
    _rules_ground.init(ctx, [], ctx.game_map)

    assert use_consumable(ctx, 0, in_combat=True)
    assert _rules_ground.player_hp(ctx) == 15
    assert _rules_ground.player_ap(ctx) == 3
    effect = _rules_ground._state.active_consumable_effects["restore_hp"]
    assert effect.remaining_turns == 3

    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_hp(ctx) == 17
    assert _rules_ground.player_ap(ctx) == 4
    assert _rules_ground._state.active_consumable_effects["restore_hp"].remaining_turns == 2


def test_second_combat_med_pack_refreshes_instead_of_stacking():
    ctx = _context(
        hp=10,
        items=[GroundItemStack("consumable", "med_pack", 2)],
    )
    _rules_ground.init(ctx, [], ctx.game_map)

    assert use_consumable(ctx, 0, in_combat=True)
    _rules_ground.reset_turn(ctx)
    assert use_consumable(ctx, 0, in_combat=True)
    effect = _rules_ground._state.active_consumable_effects["restore_hp"]
    assert effect.remaining_turns == 3
    assert len(_rules_ground._state.active_consumable_effects) == 1


def test_combat_stim_adds_one_ap_for_three_following_turns():
    ctx = _context(items=[GroundItemStack("consumable", "stim", 1)])
    _rules_ground.init(ctx, [], ctx.game_map)

    assert use_consumable(ctx, 0, in_combat=True)
    assert _rules_ground.player_ap(ctx) == 3
    assert _rules_ground._state.active_consumable_effects["stim"].remaining_turns == 3

    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_ap(ctx) == 5
    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_ap(ctx) == 5
    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_ap(ctx) == 5
    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_ap(ctx) == 4
    assert "stim" not in _rules_ground._state.active_consumable_effects


def test_consumable_use_rejects_insufficient_combat_ap_without_mutation():
    ctx = _context(items=[GroundItemStack("consumable", "stim", 1)])
    _rules_ground.init(ctx, [], ctx.game_map)
    _rules_ground.set_player_ap(ctx, 0)

    assert not use_consumable(ctx, 0, in_combat=True)
    assert ctx.ground_expedition_items == [
        GroundItemStack("consumable", "stim", 1),
    ]
