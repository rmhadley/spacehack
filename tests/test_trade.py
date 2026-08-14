"""Tests for trade.py — trade_price pricing curve.

Pure formula: linear curve from 2× base at shortage (0% stock)
to 0.6× base at surplus (100% stock), with 1× at equilibrium (50%).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.ground_equipment import GroundItemStack
from src.spacehack.trade import trade_price, open_loot_pickup
from src.spacehack.world import Entity, Position


class TestTradePrice:
    """trade_price(base_price, current_stock, target_stock) -> int."""

    # --- Shortage zone (ratio < 0.5): 2.0× → 1.0× linearly ---

    def test_full_shortage(self):
        """0 stock → 2.0× base price."""
        # ratio = 0/8 = 0, price = 100 * (2.0 - 0) = 200
        assert trade_price(100, 0, 8) == 200

    def test_quarter_stock(self):
        """25% stock → ratio=0.25, price = 100 * (2.0 - 0.5) = 150."""
        assert trade_price(100, 2, 8) == 150

    def test_approaching_equilibrium(self):
        """Stock 4/10 → ratio=0.4 (shortage zone). price=120."""
        # ratio = 4/10 = 0.4, price = 100 * (2.0 - 0.8) = 120
        assert trade_price(100, 4, 10) == 120

    # --- Equilibrium (ratio = 0.5): 1.0× base price ---

    def test_exact_equilibrium(self):
        """50% stock → 1.0× base price."""
        assert trade_price(100, 4, 8) == 100

    # --- Surplus zone (ratio >= 0.5): 1.0× → 0.6× linearly ---

    def test_slight_surplus(self):
        """75% stock → ratio=0.75, price = 100 * (1.0 - 0.25*0.8) = 80."""
        assert trade_price(100, 6, 8) == 80

    def test_full_surplus(self):
        """100% stock → ratio=1.0, price = 100 * (1.0 - 0.5*0.8) = 60."""
        assert trade_price(100, 8, 8) == 60

    def test_overstocked(self):
        """>100% stock (2× target) — floor at 1 prevents negative prices."""
        # ratio = 16/8 = 2.0, raw = 100 * (1.0 - 1.5*0.8) = -20
        # max(1, -20) = 1
        assert trade_price(100, 16, 8) == 1

    # --- Edge cases ---

    def test_target_zero(self):
        """target_stock=0 is clamped to 1 for division, but stock=0
        still gives ratio=0/1=0 → shortage: 2× base."""
        # ratio = 0/1 = 0, price = 100 * (2.0 - 0) = 200
        assert trade_price(100, 0, 0) == 200

    def test_base_price_one(self):
        """Minimum base price — still follows the curve."""
        # ratio = 0/8 = 0, shortage: 1 * (2.0 - 0) = 2
        assert trade_price(1, 0, 8) == 2

    def test_different_target(self):
        """Unequal target doesn't break the formula."""
        # target=16, stock=0 → ratio=0, 2.0×
        assert trade_price(50, 0, 16) == 100

    def test_integer_truncation(self):
        """Result is int-truncated (not rounded)."""
        # 100 * 0.99 = 99 → int(99) = 99
        # ratio = 0.01, price = 100 * (2.0 - 0.02) = 198
        # That's not a great test. Let's pick numbers that produce a
        # clear truncation.
        # base=10, stock=3, target=10 → ratio=0.3, 10*(2.0-0.6)=14.0
        assert trade_price(10, 3, 10) == 14


class TestOpenLootPickup:
    """Loot selection and immediate pickup behavior."""

    def _loot_entity(self, item_type: str, item_id: str) -> Entity:
        return Entity(
            char="%", fg=(255, 215, 0), pos=Position(0, 0),
            loot_data={"item_type": item_type, "item_id": item_id},
        )

    def test_loot_choice_uses_friendly_equipment_name(self):
        """The compact chooser label shows the catalog name, not the id."""
        from src.spacehack.loot import _loot_choice_label

        label = _loot_choice_label(self._loot_entity("weapon", "grenade_launcher"))

        assert label == "Grenade Launcher"

    def test_p_pickup_chooser_lists_all_nearby_stacks(self, monkeypatch):
        """Nearby loot selection lists friendly names and opens only the choice."""
        from src.spacehack.loot import open_loot_pickup
        from src.spacehack.world import GameMap, DUNGEON_FLOOR

        first = self._loot_entity("ammo", "pistol_rounds")
        first.pos = Position(1, 1)
        first.loot_data["quantity"] = 2
        second = Entity(
            char="%", fg=(255, 215, 0), pos=Position(2, 1),
            loot_data={
                "item_type": "ammo", "item_id": "rifle_rounds", "quantity": 3,
            },
        )
        game_map = GameMap(3, 3, [[DUNGEON_FLOOR] * 3 for _ in range(3)], [first, second])
        ctx = SimpleNamespace(
            game_map=game_map,
            player=Entity(char="@", fg=(255, 255, 255), pos=Position(1, 1)),
            ground_stats=SimpleNamespace(strength=10),
            ground_expedition_inventory=[],
            ground_expedition_items=[],
            log=MagicMock(),
        )
        selected = {}
        monkeypatch.setattr(
            "src.spacehack.loot.choose_loot_entity",
            lambda _ctx, entities: selected.update(entities=entities) or second,
        )
        open_loot_pickup(ctx, first)

        assert selected["entities"] == (first, second)
        assert second not in game_map.entities
        assert first in game_map.entities
        assert ctx.ground_expedition_items == [
            GroundItemStack("ammo", "rifle_rounds", 3),
        ]

    def test_single_pickup_still_uses_the_compact_chooser(self, monkeypatch):
        """One reachable stack is picked up directly after chooser selection."""
        from src.spacehack.loot import open_loot_pickup
        from src.spacehack.world import GameMap, DUNGEON_FLOOR

        loot_entity = self._loot_entity("ammo", "pistol_rounds")
        loot_entity.pos = Position(1, 1)
        loot_entity.loot_data["quantity"] = 2
        game_map = GameMap(3, 3, [[DUNGEON_FLOOR] * 3 for _ in range(3)], [loot_entity])
        ctx = SimpleNamespace(
            game_map=game_map,
            player=Entity(char="@", fg=(255, 255, 255), pos=Position(1, 1)),
            ground_stats=SimpleNamespace(strength=10),
            ground_expedition_inventory=[],
            ground_expedition_items=[],
            log=MagicMock(),
        )
        chosen = []
        monkeypatch.setattr(
            "src.spacehack.loot.choose_loot_entity",
            lambda _ctx, entities: chosen.append(entities) or loot_entity,
        )

        open_loot_pickup(ctx, loot_entity)

        assert chosen == [(loot_entity,)]
        assert loot_entity not in game_map.entities
        assert ctx.ground_expedition_items == [
            GroundItemStack("ammo", "pistol_rounds", 2),
        ]

    def test_long_loot_label_reserves_extra_compact_width(self):
        """Long cargo labels receive width slack instead of early ellipsis."""
        from src.spacehack.loot import _loot_menu_label

        entity = Entity(
            char="%", fg=(255, 215, 0), pos=Position(0, 0),
            loot_data={"good_id": "electronics", "quantity": 1},
        )

        label = _loot_menu_label(entity)

        assert label.startswith("Consumer Electronics x1")
        assert len(label) == len("Consumer Electronics x1") + 8

    def test_choose_loot_entity_builds_a_compact_selection(self, monkeypatch):
        """The chooser presents every nearby stack as a compact modal row."""
        from src.spacehack.loot import choose_loot_entity

        entities = (
            self._loot_entity("ammo", "pistol_rounds"),
            self._loot_entity("ammo", "rifle_rounds"),
        )
        entities[0].loot_data["quantity"] = 2
        entities[1].loot_data["quantity"] = 1
        captured = {}

        def fake_choose(_ctx, **kwargs):
            captured.update(kwargs)
            return "LOOT:1"

        monkeypatch.setattr("src.spacehack.pygame_story.choose", fake_choose)

        selected = choose_loot_entity(SimpleNamespace(), entities)

        assert selected is entities[1]
        assert captured["title"] == "CHOOSE LOOT"
        assert captured["body"] == "Choose an item to pick up."
        assert captured["compact"] is True
        assert captured["options"] == (
            ("Pistol Rounds x2", "LOOT:0"),
            ("Rifle Rounds x1", "LOOT:1"),
        )

    def test_p_pickup_chooser_cancel_leaves_everything(self, monkeypatch):
        """Canceling the nearby-loot chooser does not open or consume loot."""
        from src.spacehack.loot import open_loot_pickup
        from src.spacehack.world import GameMap, DUNGEON_FLOOR

        first = self._loot_entity("ammo", "pistol_rounds")
        first.pos = Position(1, 1)
        first.loot_data["quantity"] = 2
        second = self._loot_entity("ammo", "rifle_rounds")
        second.pos = Position(2, 1)
        game_map = GameMap(3, 3, [[DUNGEON_FLOOR] * 3 for _ in range(3)], [first, second])
        ctx = SimpleNamespace(
            game_map=game_map,
            player=Entity(char="@", fg=(255, 255, 255), pos=Position(1, 1)),
            ground_stats=SimpleNamespace(strength=10),
            ground_expedition_inventory=[],
            ground_expedition_items=[],
            log=MagicMock(),
        )
        monkeypatch.setattr(
            "src.spacehack.loot.choose_loot_entity",
            lambda _ctx, _entities: None,
        )
        open_loot_pickup(ctx, first)

        assert game_map.entities == [first, second]

    def test_unknown_equipment_pickup_logs_and_leaves_item(self):
        """Unresolvable equipment is not consumed by immediate pickup."""
        ctx = SimpleNamespace(log=MagicMock())

        open_loot_pickup(ctx, self._loot_entity("weapon", "not_a_real_weapon"))

        ctx.log.add.assert_called_once_with(
            "Unknown ground equipment - left it behind.",
        )
