from tests.support.asyncutil import run, as_async
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
    assert rows[0].text == "Med Pack [1/3]"
    detail = _item_stack_detail(ctx.ground_expedition_items[0])
    assert "Restore HP" in detail
    assert "regen" not in detail  # the registry id never leaks


def test_character_rows_show_current_and_max_for_all_stackable_items():
    from src.spacehack.character_screen import _backpack_item_rows

    ctx = SimpleNamespace(
        ground_expedition_items=[
            GroundItemStack("consumable", "med_pack", 3),
            GroundItemStack("consumable", "stim", 1),
        ],
    )

    assert [row.text for row in _backpack_item_rows(ctx)] == [
        "Med Pack [3/3]",
        "Combat Stim [1/2]",
    ]


def test_character_consumable_action_uses_a_charge(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.character_screen import _manage_pack_stack

    ctx = _context(
        hp=7,
        items=[GroundItemStack("consumable", "med_pack", 1)],
    )
    monkeypatch.setattr(
        pygame_story, "choose", as_async(lambda *args, **kwargs: "STACK_USE:0"),
    )

    assert run(_manage_pack_stack(ctx, "PACK_STACK:0", in_ground_combat=False)) == "USE"
    assert ctx.ground_expedition_items == []
    # Doc 103 Build C's 5-everywhere shape: the instant 5 (7 -> 12),
    # the regen applied for the steps to spend — never a full heal.
    assert ctx.ground_hp == 12
    assert ctx.active_statuses["regen"].remaining_turns == 3


def test_character_consumable_action_can_discard_a_stack(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.character_screen import _manage_pack_stack

    ctx = _context(items=[GroundItemStack("consumable", "med_pack", 1)])
    monkeypatch.setattr(
        pygame_story, "choose", as_async(lambda *args, **kwargs: "STACK_DISCARD:0"),
    )

    assert run(_manage_pack_stack(ctx, "PACK_STACK:0", in_ground_combat=False)) == "DISCARD"
    assert ctx.ground_expedition_items == []
    dropped = [e for e in ctx.game_map.entities if e.loot_data is not None]
    assert len(dropped) == 1
    assert dropped[0].pos == ctx.player.pos
    assert dropped[0].loot_data == {
        "item_type": "consumable", "item_id": "med_pack", "quantity": 1,
    }


def test_character_consumable_options_hide_discard_without_a_floor(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.character_screen import _manage_consumable_stack

    captured = {}
    ctx = _context(items=[GroundItemStack("consumable", "med_pack", 1)])
    monkeypatch.setattr(
        pygame_story, "choose",
        as_async(lambda *args, **kwargs: captured.update(kwargs) or "__BACK__"),
    )

    assert run(
        _manage_consumable_stack(
            ctx, 0, in_ground_combat=False, floor_available=False,
        )
    ) is None
    assert captured["options"] == (("Use", "STACK_USE:0"),)


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
        installed_chrome=[],
        active_statuses={},
        log=SimpleNamespace(
            add=lambda message: messages.append(message),
            add_colored=lambda message, _color: messages.append(message),
        ),
        messages=messages,
    )


def test_med_pack_outside_combat_is_instant_5_plus_regen():
    """Doc 103 Build C's 5-everywhere ruling: the out-of-combat use
    restores the instant 5 AND applies the regen status — the FULL
    heal is retired."""
    ctx = _context(
        hp=7,
        items=[GroundItemStack("consumable", "med_pack", 2)],
    )

    assert use_consumable(ctx, 0, in_combat=False)
    assert ctx.ground_hp == 12  # 7 + 5, NOT the full heal
    assert ctx.active_statuses["regen"].remaining_turns == 3
    assert ctx.active_statuses["regen"].theater == "ground"
    assert "Med Pack: +5 HP." in ctx.messages
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


def test_stim_outside_combat_is_legal_and_applies():
    """Doc 103 Build C (q12a): the stim is exploration-legal — one
    charge spends, the status applies (its duration then walks down
    on steps; no AP pool exists out of combat)."""
    ctx = _context(items=[GroundItemStack("consumable", "stim", 1)])

    assert use_consumable(ctx, 0, in_combat=False)
    assert ctx.active_statuses["stim"].remaining_turns == 3
    assert ctx.ground_expedition_items == []


def test_combat_med_pack_heals_and_refreshes_three_turn_regen():
    ctx = _context(
        hp=10,
        items=[GroundItemStack("consumable", "med_pack", 2)],
    )
    _rules_ground.init(ctx, [], ctx.game_map)

    assert use_consumable(ctx, 0, in_combat=True)
    assert _rules_ground.player_hp(ctx) == 17
    assert _rules_ground.player_ap(ctx) == 3
    assert "Med Pack: +5 HP." in ctx.messages
    status = ctx.active_statuses["regen"]
    assert status.remaining_turns == 3
    assert status.source == "Med Pack"

    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_hp(ctx) == 19
    assert _rules_ground.player_ap(ctx) == 4
    assert "Med Pack regeneration: +2 HP." in ctx.messages
    assert ctx.active_statuses["regen"].remaining_turns == 2


def test_second_combat_med_pack_refreshes_instead_of_stacking():
    ctx = _context(
        hp=10,
        items=[GroundItemStack("consumable", "med_pack", 2)],
    )
    _rules_ground.init(ctx, [], ctx.game_map)

    assert use_consumable(ctx, 0, in_combat=True)
    _rules_ground.reset_turn(ctx)
    assert use_consumable(ctx, 0, in_combat=True)
    status = ctx.active_statuses["regen"]
    assert status.remaining_turns == 3
    assert len(ctx.active_statuses) == 1


def test_combat_stim_adds_one_ap_for_three_following_turns():
    ctx = _context(items=[GroundItemStack("consumable", "stim", 1)])
    _rules_ground.init(ctx, [], ctx.game_map)

    assert use_consumable(ctx, 0, in_combat=True)
    assert _rules_ground.player_ap(ctx) == 3
    assert ctx.active_statuses["stim"].remaining_turns == 3

    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_ap(ctx) == 5
    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_ap(ctx) == 5
    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_ap(ctx) == 5
    _rules_ground.reset_turn(ctx)
    assert _rules_ground.player_ap(ctx) == 4
    assert "stim" not in ctx.active_statuses


def test_consumable_use_rejects_insufficient_combat_ap_without_mutation():
    ctx = _context(items=[GroundItemStack("consumable", "stim", 1)])
    _rules_ground.init(ctx, [], ctx.game_map)
    _rules_ground.set_player_ap(ctx, 0)

    assert not use_consumable(ctx, 0, in_combat=True)
    assert ctx.ground_expedition_items == [
        GroundItemStack("consumable", "stim", 1),
    ]


def test_regen_ticks_three_times_then_expires_cleanly():
    """The 3-round regen heals exactly 3 times and logs its source on
    EVERY tick including the expiring one (the engine drops the entry
    at the boundary; the adapter's source snapshot keeps the third
    line's attribution), then leaves nothing behind."""
    from src.spacehack.combat import _statuses

    ctx = _context(hp=10)
    _rules_ground.init(ctx, [], ctx.game_map)
    _statuses.apply(
        ctx.active_statuses, "regen", source="Med Pack", theater="ground",
    )

    for _ in range(3):
        _rules_ground.reset_turn(ctx)
    assert ctx.messages.count("Med Pack regeneration: +2 HP.") == 3
    assert ctx.active_statuses == {}


def test_repay_line_lands_after_a_shared_boundary_regen_tick():
    """The loan's repay line logs AFTER the walk (today's repay-last
    shape): a regen sharing the boundary keeps its tick line first."""
    from src.spacehack.combat import _statuses
    from src.spacehack.data.statuses import NEURAL_STIM_LOAN_ID

    ctx = _context(hp=10)
    _rules_ground.init(ctx, [], ctx.game_map)
    _statuses.apply(ctx.active_statuses, NEURAL_STIM_LOAN_ID, theater="ground")
    _statuses.apply(
        ctx.active_statuses, "regen", source="Med Pack", theater="ground",
    )

    _rules_ground.reset_turn(ctx)
    _tick = ctx.messages.index("Med Pack regeneration: +2 HP.")
    _repay = ctx.messages.index("Reality slows as the Neural Stim's effect wears off.")
    assert _tick < _repay


def test_item_stack_detail_keys_on_ap_first_never_renders_zero_hp():
    """Doc 103 Build C's branch re-key (advisor catch 2): both legal
    rows carry exploration_legal now, so the detail format keys on
    combat_ap_bonus FIRST — the stim renders its AP format, the med
    pack the ruled 5-everywhere text (prose ledger #4)."""
    from src.spacehack.character_screen import _item_stack_detail

    _stim = _item_stack_detail(GroundItemStack("consumable", "stim", 1))
    assert _stim.endswith("+1 AP x3")
    assert "HP" not in _stim  # never "+0 HP"

    _med = _item_stack_detail(GroundItemStack("consumable", "med_pack", 1))
    assert _med.endswith("+5 HP/+2 HP x3")
    assert "combat" not in _med  # the 5-everywhere prefix drop


def test_stim_at_full_hp_still_applies():
    """The refusal is the REGEN row's waste protection, not a bare HP
    gate: a stim at full HP is legal pre-buffing (doc 103 Build C)."""
    ctx = _context(
        hp=23,
        items=[GroundItemStack("consumable", "stim", 1)],
    )

    assert use_consumable(ctx, 0, in_combat=False)
    assert ctx.active_statuses["stim"].remaining_turns == 3
    assert ctx.ground_expedition_items == []
