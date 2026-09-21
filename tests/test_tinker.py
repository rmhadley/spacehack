"""Tinker-kit apply flow (doc 47 phase 5): eligibility, chooser, bump.

One kit = +1 tier on one eligible owned entry — equipped weapons and
armor, pack gear, ship-storage modules, installed modules (SETTLED
33) — capped at prototype (SETTLED 31), consumed only on a completed
bump.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.support.asyncutil import as_async, run

from src.spacehack.ground_consumables import (
    KIT_EFFECT_ID,
    KIT_ITEM_ID,
    consume_kit_charge,
    is_tinker_kit,
)
from src.spacehack.ground_equipment import (
    GroundItemStack,
    GroundWeaponInstance,
    StoredGroundEquipment,
    weapon_instance,
)
from src.spacehack.ship import OwnedShip, StoredEquipment
from src.spacehack.tinker import NO_TARGETS_LINE, try_manage_kit


def _messages():
    lines = []
    return lines, SimpleNamespace(
        add=lines.append,
        add_colored=lambda message, _color: lines.append(message),
    )


def _context(items=None, **overrides):
    messages, log = _messages()
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("kinetic_pistol")],
        equipped_ground_armor={"body": StoredGroundEquipment("armor", "light_vest")},
        ground_expedition_inventory=[StoredGroundEquipment("weapon", "combat_knife")],
        ground_armory_storage=[StoredGroundEquipment("armor", "heavy_vest")],
        ground_armory_items=[],
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        ground_hp=20,
        ground_max_hp=23,
        ship_storage=[StoredEquipment("module", "shield_mk1")],
        player_owned_ship=OwnedShip(
            ship_id="starter",
            modules=(StoredEquipment("module", "compact_reactor"),),
        ),
        ground_expedition_items=list(items or []),
        log=log,
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx, messages


def _kit_stack(quantity: int = 2) -> GroundItemStack:
    return GroundItemStack("consumable", KIT_ITEM_ID, quantity)


class TestEligibility:
    """Quality 0-2 with no randart seed, across all six containers."""

    def test_lists_one_row_per_eligible_entry_across_all_containers(self):
        from src.spacehack.tinker import chooser_rows, eligible_targets

        ctx, _ = _context()
        keys = [key for _label, key in chooser_rows(eligible_targets(ctx))]

        assert keys == [
            "KIT:WEAPON:0", "KIT:ARMOR:body", "KIT:PACK:0",
            "KIT:ARMORY_STORAGE:0", "KIT:STORED:0", "KIT:INSTALLED:0",
        ]

    def test_t3_and_legendary_rows_never_appear(self):
        from src.spacehack.tinker import eligible_targets

        ctx, _ = _context(
            equipped_ground_weapons=[
                weapon_instance("kinetic_pistol", quality=3),
                weapon_instance("combat_knife", quality=4),
            ],
            ship_storage=[
                StoredEquipment("module", "shield_mk1", quality=3),
                StoredEquipment("module", "reactor_mk2", quality=4, randart_seed=77),
                StoredEquipment("module", "compact_reactor", quality=2),
            ],
            equipped_ground_armor={},
            ground_expedition_inventory=[],
            ground_armory_storage=[],
            player_owned_ship=OwnedShip(ship_id="starter"),
        )
        assert [t.key for t in eligible_targets(ctx)] == ["KIT:STORED:2"]

    def test_rows_preview_current_to_next_token(self):
        from src.spacehack.tinker import chooser_rows, eligible_targets

        ctx, _ = _context()
        rows = {key: label for label, key in chooser_rows(eligible_targets(ctx))}
        assert rows["KIT:WEAPON:0"] == "Kinetic Pistol -> Modded Kinetic Pistol"
        assert rows["KIT:STORED:0"] == "Shield Mk. 1 -> Modded Shield Mk. 1"
        assert rows["KIT:ARMORY_STORAGE:0"] == (
            "Heavy Armor Vest -> Modded Heavy Armor Vest"
        )

    def test_pack_rows_cover_weapons_and_armor_only(self):
        from src.spacehack.tinker import eligible_targets

        ctx, _ = _context(
            ground_expedition_inventory=[
                StoredGroundEquipment("weapon", "combat_knife"),
                StoredGroundEquipment("armor", "light_vest", quality=2),
                GroundItemStack("ammo", "pistol_rounds", 5),
            ],
        )
        assert [t.key for t in eligible_targets(ctx) if t.key.startswith("KIT:PACK")] == [
            "KIT:PACK:0", "KIT:PACK:1",
        ]


class TestApply:
    """The bump: one tier up, everything else preserved, stats derived."""

    def _choose_returning(self, key):
        from src.spacehack import pygame_story

        return pygame_story, as_async(lambda *args, **kwargs: key)

    def test_bump_each_container_through_the_full_flow(self, monkeypatch):
        from src.spacehack.data.quality import (
            effective_module_spec, effective_weapon_spec,
        )
        from src.spacehack.ground_equipment import display_name

        ctx, messages = _context(items=[_kit_stack(6)])
        targets = [
            "KIT:WEAPON:0", "KIT:ARMOR:body", "KIT:PACK:0",
            "KIT:ARMORY_STORAGE:0", "KIT:STORED:0", "KIT:INSTALLED:0",
        ]
        for key in targets:
            pygame_story, fake = self._choose_returning(key)
            monkeypatch.setattr(pygame_story, "choose", fake)
            assert run(try_manage_kit(ctx, 0)) is True

        assert ctx.equipped_ground_weapons[0].quality == 1
        assert ctx.equipped_ground_armor["body"].quality == 1
        assert ctx.ground_expedition_inventory[0].quality == 1
        assert ctx.ground_armory_storage[0].quality == 1
        assert ctx.ship_storage[0].quality == 1
        assert ctx.player_owned_ship.modules[0].quality == 1
        assert ctx.ground_expedition_items == []  # 6 charges, all spent
        assert messages == [
            "Tinker kit: Kinetic Pistol is now Modded.",
            "Tinker kit: Light Armor Vest is now Modded.",
            "Tinker kit: Combat Knife is now Modded.",
            "Tinker kit: Heavy Armor Vest is now Modded.",
            "Tinker kit: Shield Mk. 1 is now Modded.",
            "Tinker kit: Compact Reactor Mk. 1 is now Modded.",
        ]
        # Stats and labels re-derive from the raised tier.
        assert display_name("weapon", "kinetic_pistol", 1) == "Modded Kinetic Pistol"
        assert effective_weapon_spec("kinetic_pistol", 1).damage > effective_weapon_spec(
            "kinetic_pistol",
        ).damage
        assert effective_module_spec("shield_mk1", 1).max_shield_bonus > (
            effective_module_spec("shield_mk1").max_shield_bonus
        )

    def test_bump_preserves_loaded_ammo_and_instance_fields(self, monkeypatch):

        ctx, _ = _context(
            equipped_ground_weapons=[
                GroundWeaponInstance("kinetic_pistol", 6, 0),
            ],
            equipped_ground_armor={},
            ground_expedition_inventory=[],
            ground_armory_storage=[],
            ship_storage=[],
            player_owned_ship=OwnedShip(ship_id="starter"),
            items=[_kit_stack()],
        )
        pygame_story, fake = self._choose_returning("KIT:WEAPON:0")
        monkeypatch.setattr(pygame_story, "choose", fake)

        assert run(try_manage_kit(ctx, 0)) is True
        raised = ctx.equipped_ground_weapons[0]
        assert (raised.weapon_id, raised.loaded_ammo, raised.quality) == (
            "kinetic_pistol", 6, 1,
        )

    def test_backing_out_consumes_nothing(self, monkeypatch):
        ctx, messages = _context(items=[_kit_stack(2)])
        pygame_story, fake = self._choose_returning("__BACK__")
        monkeypatch.setattr(pygame_story, "choose", fake)

        assert run(try_manage_kit(ctx, 0)) is False
        assert ctx.ground_expedition_items == [_kit_stack(2)]
        assert ctx.equipped_ground_weapons[0].quality == 0
        assert messages == []

    def test_window_close_inside_the_chooser_raises_systemexit(
        self, monkeypatch,
    ):
        import pytest

        ctx, _ = _context(items=[_kit_stack(2)])
        pygame_story, fake = self._choose_returning("__QUIT__")
        monkeypatch.setattr(pygame_story, "choose", fake)

        with pytest.raises(SystemExit):
            run(try_manage_kit(ctx, 0))
        assert ctx.ground_expedition_items == [_kit_stack(2)]
        assert ctx.equipped_ground_weapons[0].quality == 0

    def test_no_eligible_target_states_it_and_consumes_nothing(self):
        ctx, messages = _context(
            equipped_ground_weapons=[weapon_instance("kinetic_pistol", quality=3)],
            equipped_ground_armor={},
            ground_expedition_inventory=[],
            ground_armory_storage=[],
            ship_storage=[],
            player_owned_ship=OwnedShip(ship_id="starter"),
            items=[_kit_stack(2)],
        )

        assert run(try_manage_kit(ctx, 0)) is False
        assert messages == [NO_TARGETS_LINE]
        assert ctx.ground_expedition_items == [_kit_stack(2)]

    def test_non_kit_stack_returns_none_to_fall_through(self, monkeypatch):
        ctx, _ = _context(items=[GroundItemStack("consumable", "med_pack", 1)])
        pygame_story, fake = self._choose_returning(None)
        monkeypatch.setattr(pygame_story, "choose", fake)

        assert run(try_manage_kit(ctx, 0)) is None
        assert ctx.ground_expedition_items == [
            GroundItemStack("consumable", "med_pack", 1),
        ]


class TestConsume:
    """One charge per apply; the empty stack removes itself."""

    def test_consume_decrements_then_removes_the_empty_stack(self):
        stack_2, _ = _context(items=[_kit_stack(2)])
        assert consume_kit_charge(stack_2, 0) is True
        assert stack_2.ground_expedition_items == [_kit_stack(1)]

        assert consume_kit_charge(stack_2, 0) is True
        assert stack_2.ground_expedition_items == []

    def test_consume_rejects_non_kit_and_invalid_indexes(self):
        ctx, _ = _context(
            items=[GroundItemStack("consumable", "med_pack", 1)],
        )
        assert consume_kit_charge(ctx, 0) is False
        assert consume_kit_charge(ctx, 7) is False
        assert ctx.ground_expedition_items == [
            GroundItemStack("consumable", "med_pack", 1),
        ]


class TestKitIdentity:
    """The authored constants tie the catalog row to the predicate."""

    def test_catalog_row_matches_the_kit_constants(self):
        from src.spacehack.data.ground_items import find_ground_consumable

        spec = find_ground_consumable(KIT_ITEM_ID)
        assert is_tinker_kit(spec) is True
        assert spec.effect_id == KIT_EFFECT_ID
        assert is_tinker_kit(find_ground_consumable("med_pack")) is False


class TestManageDispatch:
    """The C screen's Use routes kits to tinker, never use_consumable."""

    def test_manage_stack_use_on_a_kit_applies_via_tinker(self, monkeypatch):
        from src.spacehack import pygame_story
        from src.spacehack.character_screen import _manage_pack_stack

        ctx, messages = _context(items=[_kit_stack(2)])

        def _fake_choose(*args, **kwargs):
            if kwargs.get("title") == "CONSUMABLE":
                return "STACK_USE:0"
            return "KIT:WEAPON:0"

        def _explode(*args, **kwargs):
            raise AssertionError("use_consumable must never run for a kit")

        monkeypatch.setattr(pygame_story, "choose", as_async(_fake_choose))
        monkeypatch.setattr(
            "src.spacehack.ground_consumables.use_consumable", _explode,
        )

        assert run(_manage_pack_stack(ctx, "PACK_STACK:0", in_ground_combat=False)) == "USE"
        assert ctx.equipped_ground_weapons[0].quality == 1
        assert ctx.ground_expedition_items == [_kit_stack(1)]
        assert messages == ["Tinker kit: Kinetic Pistol is now Modded."]

    def test_manage_stack_use_on_med_pack_still_calls_use_consumable(
        self, monkeypatch,
    ):
        from src.spacehack import pygame_story
        from src.spacehack.character_screen import _manage_pack_stack
        from src.spacehack.ground_equipment import GroundItemStack as Stack

        ctx = SimpleNamespace(
            ground_expedition_items=[Stack("consumable", "med_pack", 1)],
            ground_hp=7,
            ground_max_hp=23,
            log=SimpleNamespace(add=lambda _m: None),
        )
        monkeypatch.setattr(
            pygame_story, "choose",
            as_async(lambda *args, **kwargs: "STACK_USE:0"),
        )

        assert run(
            _manage_pack_stack(ctx, "PACK_STACK:0", in_ground_combat=False),
        ) == "USE"
        assert ctx.ground_hp == 23
        assert ctx.ground_expedition_items == []


class TestSaveLoad:
    """Kits ride the existing field-item save; raised gear its quality."""

    def test_kit_stack_and_raised_gear_round_trip(self):
        from src.spacehack.saveload_ground import (
            _ground_fields, _restore_ground_fields,
        )

        ctx, _ = _context(
            items=[_kit_stack(2)],
            equipped_ground_weapons=[weapon_instance("kinetic_pistol", quality=2)],
        )
        data = _ground_fields(ctx)

        fresh, _ = _context(items=[])
        _restore_ground_fields(fresh, data)

        assert fresh.ground_expedition_items == [_kit_stack(2)]
        assert fresh.equipped_ground_weapons[0].quality == 2
        assert fresh.equipped_ground_armor["body"] == StoredGroundEquipment(
            "armor", "light_vest",
        )
        assert fresh.ground_armory_storage == [StoredGroundEquipment(
            "armor", "heavy_vest",
        )]

    def test_legacy_saves_without_kits_load_clean(self):
        from src.spacehack.saveload_ground import (
            _ground_fields, _restore_ground_fields,
        )

        ctx, _ = _context(items=[])
        data = _ground_fields(ctx)
        data["ground_expedition_items"] = [
            {"item_type": "consumable", "item_id": "med_pack", "quantity": 1},
        ]

        fresh, _ = _context()
        _restore_ground_fields(fresh, data)
        assert fresh.ground_expedition_items == [
            GroundItemStack("consumable", "med_pack", 1),
        ]
