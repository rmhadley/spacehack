"""Regression tests for ship upgrades preserving installed equipment."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import __main__ as game_main
from src.spacehack import message_log, ship as ship_module, world
from src.spacehack.data.planets import hangar_anchor
from src.spacehack.hud import HudStats


def _purchase_context(old_ship: ship_module.OwnedShip, credits: int = 10_000):
    """Build the small context/map needed by the purchase helper."""
    old_entity = world.Entity(
        char="t",
        fg=(180, 200, 220),
        pos=world.Position(5, 5),
        name="Your Ship: Old Bess",
        ship_id=old_ship.ship_id,
        owned=True,
    )
    blocker = world.Entity(
        char="s",
        fg=(130, 220, 255),
        pos=world.Position(6, 5),
        name="Scout",
        ship_id="scout",
    )
    game_map = world.GameMap(
        width=12,
        height=12,
        tiles=[[world.FLOOR for _ in range(12)] for _ in range(12)],
        entities=[old_entity, blocker],
    )
    return SimpleNamespace(
        stats=HudStats(hp=30, max_hp=30, credits=credits),
        ship_storage=[],
        player_owned_ship=old_ship,
        log=message_log.MessageLog(capacity=20),
        game_map=game_map,
        current_city_id="earth",
    ), game_map, old_entity, blocker


def test_ship_upgrade_moves_old_loadout_to_storage_and_keeps_new_starting_loadout():
    old_ship = ship_module.OwnedShip(
        ship_id="starter",
        weapons=("light_missile", "light_laser"),
        modules=("shield_mk1", "shield_mk1"),
        mission_reserved=7,
    )
    old_ship.weapon_ammo[0] = 1
    ctx, game_map, old_entity, blocker = _purchase_context(old_ship)
    new_ship = ship_module.find_ship("scout")

    purchased = game_main._complete_ship_purchase(
        ctx,
        game_map,
        blocker,
        new_ship,
        old_ship,
        effective_price=4_750,
        trade_in_value=250,
    )

    assert purchased is ctx.player_owned_ship
    assert purchased.ship_id == "scout"
    assert purchased.weapons == new_ship.start_weapons
    assert purchased.modules == new_ship.start_modules
    assert purchased.mission_reserved == 7
    assert ctx.stats.credits == 5_250
    assert old_entity not in game_map.entities
    assert blocker.owned is True
    assert blocker.pos == hangar_anchor("earth")
    assert ctx.ship_storage == [
        ship_module.StoredEquipment("weapon", "light_missile", 1),
        ship_module.StoredEquipment("weapon", "light_laser"),
        ship_module.StoredEquipment("module", "shield_mk1"),
        ship_module.StoredEquipment("module", "shield_mk1"),
    ]


def test_unaffordable_ship_upgrade_leaves_old_ship_and_storage_unchanged():
    old_ship = ship_module.OwnedShip(
        ship_id="starter",
        weapons=("light_laser",),
        modules=("shield_mk1",),
    )
    ctx, game_map, old_entity, blocker = _purchase_context(old_ship, credits=100)
    new_ship = ship_module.find_ship("scout")

    purchased = game_main._complete_ship_purchase(
        ctx,
        game_map,
        blocker,
        new_ship,
        old_ship,
        effective_price=4_750,
        trade_in_value=250,
    )

    assert purchased is None
    assert ctx.stats.credits == 100
    assert ctx.player_owned_ship is old_ship
    assert old_ship.weapons == ("light_laser",)
    assert old_ship.modules == ("shield_mk1",)
    assert ctx.ship_storage == []
    assert old_entity in game_map.entities
    assert blocker.owned is False
    assert blocker.pos == world.Position(6, 5)


def test_ship_buy_result_buy_routes_through_upgrade_transfer():
    """The real BUY result seam performs the transfer and replacement."""
    old_ship = ship_module.OwnedShip(
        ship_id="starter",
        weapons=("light_missile",),
        modules=("shield_mk1",),
    )
    ctx, game_map, old_entity, blocker = _purchase_context(old_ship, credits=4_750)
    new_ship = ship_module.find_ship("scout")

    purchased = game_main._apply_ship_buy_result(
        ctx,
        game_map,
        blocker,
        new_ship,
        old_ship,
        game_main.ShipBuyOutcome.BUY,
        effective_price=4_750,
        trade_in_value=250,
    )

    assert purchased is ctx.player_owned_ship
    assert purchased.ship_id == "scout"
    assert purchased.weapons == new_ship.start_weapons
    assert ctx.stats.credits == 0
    assert old_entity not in game_map.entities
    assert ctx.ship_storage == [
        ship_module.StoredEquipment("weapon", "light_missile", 4),
        ship_module.StoredEquipment("module", "shield_mk1"),
    ]


def test_ship_upgrade_preserves_existing_trade_in_price_without_equipment_value():
    old_ship = ship_module.OwnedShip(ship_id="starter", weapons=("light_laser",))
    ctx, game_map, _, blocker = _purchase_context(old_ship, credits=4_750)
    new_ship = ship_module.find_ship("scout")

    purchased = game_main._complete_ship_purchase(
        ctx,
        game_map,
        blocker,
        new_ship,
        old_ship,
        effective_price=new_ship.price - 250,
        trade_in_value=250,
    )

    assert purchased is not None
    assert ctx.stats.credits == 0
    assert any("trade-in 250$" in entry.text for entry in ctx.log.history())
    assert not any("sold" in entry.text.lower() for entry in ctx.log.history())


def test_ship_buy_back_outcome_does_not_mutate_upgrade_state(monkeypatch):
    """Canceling the buy modal leaves the pending trade-in untouched."""
    from src.spacehack import pygame_screen
    from src.spacehack.menus import _ship_buy

    old_ship = ship_module.OwnedShip(
        ship_id="starter",
        weapons=("light_missile",),
        modules=("shield_mk1",),
    )
    ctx, game_map, old_entity, blocker = _purchase_context(old_ship, credits=4_750)
    ctx.context = object()
    new_ship = ship_module.find_ship("scout")
    monkeypatch.setattr(
        pygame_screen,
        "run_for_context",
        lambda *_args, **_kwargs: ("BACK", "", 0),
    )

    result = _ship_buy._run_pygame_ship_buy(ctx, new_ship, 4_750)

    assert result is game_main.ShipBuyOutcome.BACK
    assert ctx.stats.credits == 4_750
    assert ctx.player_owned_ship is old_ship
    assert ctx.ship_storage == []
    assert old_entity in game_map.entities
    assert blocker.owned is False
