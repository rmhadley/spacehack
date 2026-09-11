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


# ----- indoor purchases (doc 45 phase 2: buy indoors, park outside) -----


def _indoor_purchase_context(old_ship, credits=10_000):
    """Parent pad (old owned ship) + spaceport interior (display ships).

    Maps are 40x40 so Earth's hangar anchor (25, 27) is in bounds.
    """
    old_entity = world.Entity(
        char="t", fg=(180, 200, 220), pos=world.Position(5, 5),
        name="Your Ship: Old Bess", ship_id=old_ship.ship_id, owned=True,
    )
    parent = world.GameMap(
        width=40, height=40,
        tiles=[[world.FLOOR for _ in range(40)] for _ in range(40)],
        entities=[old_entity],
    )
    display = world.Entity(
        char="s", fg=(130, 220, 255), pos=world.Position(4, 3),
        name="Ship: Scout", ship_id="scout",
    )
    other_display = world.Entity(
        char="H", fg=(140, 210, 140), pos=world.Position(8, 3),
        name="Ship: Hauler", ship_id="hauler",
    )
    interior = world.GameMap(
        width=40, height=40,
        tiles=[[world.FLOOR for _ in range(40)] for _ in range(40)],
        entities=[display, other_display],
    )
    interior.city_interior_id = "city:earth:spaceport"
    ctx = SimpleNamespace(
        stats=HudStats(hp=30, max_hp=30, credits=credits),
        ship_storage=[],
        player_owned_ship=old_ship,
        log=message_log.MessageLog(capacity=20),
        game_map=interior,
        current_city_id="earth",
    )
    return ctx, parent, interior, old_entity, display


def test_indoor_buy_parks_on_parent_pad_and_empties_showroom():
    old_ship = ship_module.OwnedShip(
        ship_id="starter",
        weapons=("light_laser",),
        modules=("shield_mk1",),
        mission_reserved=3,
    )
    ctx, parent, interior, old_entity, display = _indoor_purchase_context(old_ship)
    new_ship = ship_module.find_ship("scout")

    purchased = game_main._complete_ship_purchase(
        ctx, parent, display, new_ship, old_ship,
        effective_price=4_750, trade_in_value=250,
        interior_map=interior,
    )

    anchor = hangar_anchor("earth")
    owned = [e for e in parent.entities if e.owned]
    assert [(e.ship_id, e.pos.x, e.pos.y) for e in owned] == [
        ("scout", anchor.x, anchor.y),
    ]
    assert old_entity not in parent.entities  # trade-in left the pad
    assert not [e for e in interior.entities if e.ship_id and not e.owned]
    assert purchased is ctx.player_owned_ship
    assert purchased.mission_reserved == 3
    assert purchased.weapons == new_ship.start_weapons
    assert ctx.stats.credits == 10_000 - 4_750
    assert ctx.ship_storage == [
        ship_module.StoredEquipment("weapon", "light_laser"),
        ship_module.StoredEquipment("module", "shield_mk1"),
    ]


def test_indoor_buy_skips_occupied_anchor_to_nearest_free_cell():
    old_ship = ship_module.OwnedShip(ship_id="starter")
    ctx, parent, interior, _old, display = _indoor_purchase_context(old_ship)
    anchor = hangar_anchor("earth")  # (25, 27)
    # Park a nuisance exactly on the anchor; the purchase must find the
    # nearest free cell instead of stacking entities. (25, 26) is the
    # first ring-1 cell in the ring scan that is walkable and free.
    parent.entities.append(world.Entity(
        char="=", fg=(1, 2, 3), pos=anchor, name="Trade Terminal",
    ))

    purchased = game_main._complete_ship_purchase(
        ctx, parent, display, ship_module.find_ship("scout"), old_ship,
        effective_price=4_750, trade_in_value=250, interior_map=interior,
    )

    assert purchased is not None
    parked = [e for e in parent.entities if e.owned][0]
    assert (parked.pos.x, parked.pos.y) == (25, 26)


def test_nearest_free_cell_rings_out_and_falls_back_to_anchor():
    from src.spacehack.game_flow import _nearest_free_cell

    def _floor_map(width, height, occupied=()):
        game_map = world.GameMap(
            width=width, height=height,
            tiles=[[world.FLOOR for _ in range(width)] for _ in range(height)],
            entities=[
                world.Entity(char="x", fg=(1, 1, 1),
                             pos=world.Position(x, y), name="blocker")
                for x, y in occupied
            ],
        )
        return game_map

    # Anchor blocked -> first free ring-1 cell in scan order.
    ring = _floor_map(3, 3, occupied=[(1, 1)])
    assert _nearest_free_cell(ring, world.Position(1, 1)) == world.Position(1, 0)

    # Anchor one step outside the map -> nearest in-bounds free cell.
    corner = _floor_map(3, 3)
    assert _nearest_free_cell(corner, world.Position(3, 3)) == world.Position(2, 2)

    # Every cell occupied -> the anchor itself (documented backstop).
    full = _floor_map(3, 3, occupied=[
        (x, y) for x in range(3) for y in range(3)
    ])
    assert _nearest_free_cell(full, world.Position(1, 1)) == world.Position(1, 1)


def test_resolve_ship_blocker_routes_buys_by_interior_stamp(monkeypatch):
    """The interior stamp on the active map decides where the purchase parks."""
    from src.spacehack import game_interactions

    monkeypatch.setattr(
        game_interactions, "_run_ship_buy",
        lambda *args, **kwargs: game_main.ShipBuyOutcome.BUY,
    )
    old_ship = ship_module.OwnedShip(ship_id="starter")

    # Indoors: the display is stripped, a fresh owned entity parks on the pad.
    ctx, parent, interior, _old, display = _indoor_purchase_context(old_ship)
    state = SimpleNamespace(
        ctx=ctx, console=None, log=ctx.log, game_map=interior, player=None,
        city_game_map=parent, city_player=None, current_city_id="earth",
        player_owned_ship=old_ship, current_mode="dungeon",
    )
    game_interactions._resolve_ship_blocker(state, display)
    anchor = hangar_anchor("earth")
    assert [(e.ship_id, e.pos.x, e.pos.y) for e in parent.entities if e.owned] == [
        ("scout", anchor.x, anchor.y),
    ]
    assert not [e for e in interior.entities if e.ship_id and not e.owned]

    # Outdoors: the display itself is re-anchored and claimed (no new entity).
    ctx, parent, interior, _old, display = _indoor_purchase_context(old_ship)
    display.pos = world.Position(6, 5)
    parent.entities.append(display)
    state = SimpleNamespace(
        ctx=ctx, console=None, log=ctx.log, game_map=parent, player=None,
        city_game_map=parent, city_player=None, current_city_id="earth",
        player_owned_ship=old_ship, current_mode="city",
    )
    game_interactions._resolve_ship_blocker(state, display)
    assert display.owned is True
    assert (display.pos.x, display.pos.y) == (anchor.x, anchor.y)
    assert len([e for e in parent.entities if e.owned]) == 1


def test_unaffordable_indoor_buy_leaves_room_and_pad_unchanged():
    old_ship = ship_module.OwnedShip(ship_id="starter", weapons=("light_laser",))
    ctx, parent, interior, old_entity, display = _indoor_purchase_context(
        old_ship, credits=100,
    )

    purchased = game_main._complete_ship_purchase(
        ctx, parent, display, ship_module.find_ship("scout"), old_ship,
        effective_price=4_750, trade_in_value=250, interior_map=interior,
    )

    assert purchased is None
    assert ctx.stats.credits == 100
    assert ctx.player_owned_ship is old_ship
    assert old_entity in parent.entities
    assert len([e for e in interior.entities if e.ship_id and not e.owned]) == 2
    assert display.owned is False  # display never re-anchored or claimed


def test_indoor_resume_parks_exactly_one_owned_entity_matching_purchase():
    """The resume twin must park the same single entity the purchase did."""
    from src.spacehack.city_interiors import restore_city_interior_parent
    from src.spacehack.saveload_maps import _make_ship_entity

    old_ship = ship_module.OwnedShip(ship_id="starter")
    ctx, parent, interior, _old, display = _indoor_purchase_context(old_ship)
    purchased = game_main._complete_ship_purchase(
        ctx, parent, display, ship_module.find_ship("scout"), old_ship,
        effective_price=4_750, trade_in_value=250, interior_map=interior,
    )
    bought = [e for e in parent.entities if e.owned][0]

    interior.city_building_label = "spaceport"
    rebuilt = SimpleNamespace(game_map=interior, city_id="earth")
    restore_city_interior_parent(ctx, rebuilt)
    resumed_parent = interior.city_parent_map
    resumed = [e for e in resumed_parent.entities if e.owned]

    assert len(resumed) == 1
    assert resumed[0].ship_id == bought.ship_id
    assert resumed[0].name == bought.name
    assert (resumed[0].pos.x, resumed[0].pos.y) == (bought.pos.x, bought.pos.y)
    # ...and the same shape the save/load rebuild path parks.
    anchor = hangar_anchor("earth")
    assert (resumed[0].name, resumed[0].ship_id) == (
        _make_ship_entity(purchased, anchor).name,
        _make_ship_entity(purchased, anchor).ship_id,
    )


def test_too_expensive_outcome_names_the_shortfall():
    old_ship = ship_module.OwnedShip(ship_id="starter")
    ctx, parent, interior, _old, _display = _indoor_purchase_context(
        old_ship, credits=100,
    )

    purchased = game_main._apply_ship_buy_result(
        ctx, parent, None, ship_module.find_ship("scout"), old_ship,
        game_main.ShipBuyOutcome.TOO_EXPENSIVE,
        effective_price=4_750, trade_in_value=250,
    )

    assert purchased is None
    assert ctx.stats.credits == 100
    assert "4650$ short" in ctx.log.history()[-1].text
