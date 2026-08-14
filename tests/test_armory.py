"""Phase 3 tests for armory inventory gating (resolve_armory_inventory)."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import ground_equipment
from src.spacehack.data.ground_armor import find_ground_armor
from src.spacehack.data.ground_weapons import find_ground_weapon
from src.spacehack.data.planets import find_planet_spec, resolve_armory_inventory
from src.spacehack.menus import _armory


def test_earth_uses_fixed_t1_armory_stock_verbatim():
    spec = find_planet_spec("earth")
    weapons, armor = resolve_armory_inventory("earth", 1)

    assert weapons == spec.armory_weapons
    assert armor == spec.armory_armor
    assert "shotgun" in weapons
    assert "kinetic_rifle" not in weapons
    assert all(find_ground_weapon(w).tech_level == 1 for w in weapons)
    assert all(find_ground_armor(a).tech_level == 1 for a in armor)


def test_mars_stock_spans_t1_and_t2_including_plasma_and_cybernetics():
    weapons, armor = resolve_armory_inventory("mars", 1)

    assert "plasma_pistol" in weapons
    assert "cybernetic_eyes" in armor
    assert "cybernetic_arms" in armor
    assert all(find_ground_weapon(w).tech_level <= 2 for w in weapons)
    assert all(find_ground_armor(a).tech_level <= 2 for a in armor)


def test_unfixed_high_tier_planet_samples_shop_available_tiered_subset():
    weapons, armor = resolve_armory_inventory("blockade", 1)

    assert 0 < len(weapons) <= 4
    assert 0 < len(armor) <= 6
    assert all(find_ground_weapon(w).shop_available for w in weapons)
    assert "fists" not in weapons
    assert all(find_ground_weapon(w).tech_level <= 4 for w in weapons)
    assert all(find_ground_armor(a).tech_level <= 4 for a in armor)


def test_low_tier_unfixed_planet_excludes_high_tier_gear():
    # Mercury is tech_level 1 with no armory override: only T1 shop gear.
    weapons, armor = resolve_armory_inventory("mercury", 1)

    assert weapons
    assert all(find_ground_weapon(w).tech_level == 1 for w in weapons)
    assert all(find_ground_armor(a).tech_level == 1 for a in armor)


def test_weapon_detail_shows_damage_type():
    detail = _armory._weapon_detail(find_ground_weapon("plasma_caster"))

    assert "Plasma" in detail
    assert "Damage: 24" in detail


def test_weapon_detail_shows_armor_bypass():
    bypass = _armory._weapon_detail(find_ground_weapon("mono_blade"))
    normal = _armory._weapon_detail(find_ground_weapon("power_fist"))

    assert "Armor bypass" in bypass
    assert "Armor bypass" not in normal


def test_armor_detail_shows_cybernetic_effects():
    detail = _armory._armor_detail(find_ground_armor("cybernetic_legs"))

    assert "Defense: 0" in detail
    assert "+1 AP" in detail


def test_armory_stock_is_deterministic_per_month_and_does_not_advance_rng():
    """Sampled stock is keyed on (planet, month), not the shared RNG stream."""
    from src.spacehack.engine import RNG, set_init_seed

    set_init_seed(12345)
    before = RNG.getstate()
    first = resolve_armory_inventory("blockade", 1)

    assert resolve_armory_inventory("blockade", 1) == first
    assert RNG.getstate() == before


def test_armory_stock_rolls_over_with_the_month_clock():
    """A different month yields a freshly sampled, deterministic stock."""
    from src.spacehack.engine import set_init_seed

    set_init_seed(12345)
    month_1 = resolve_armory_inventory("blockade", 1)
    month_2 = resolve_armory_inventory("blockade", 2)

    assert month_1 != month_2


def _ammo_purchase_context(credits=100):
    return SimpleNamespace(
        context=object(),
        stats=SimpleNamespace(credits=credits),
        ground_stats=SimpleNamespace(strength=10),
        ground_armory_items=[],
        ground_expedition_items=[],
        ground_armory_storage=[],
        ground_expedition_inventory=[],
        log=SimpleNamespace(add=lambda _message: None),
    )


def test_buy_rows_include_authored_ground_ammo():
    rows = _armory._buy_ammo_rows()

    assert any(row.action == "BUY_AMMO:pistol_rounds" for row in rows)
    assert any(row.label == "Pistol Rounds" for row in rows)


def test_buy_rows_include_ground_consumables():
    rows = _armory._buy_consumable_rows()

    assert any(row.action == "BUY_CONSUMABLE:med_pack" for row in rows)
    med_pack = next(row for row in rows if row.label == "Med Pack")
    assert "Restore HP" in med_pack.detail
    assert "restore_hp" not in med_pack.detail


def test_armory_and_expedition_rows_show_field_item_stack_quantities():
    stacks = [
        ground_equipment.GroundItemStack("ammo", "pistol_rounds", 12),
        ground_equipment.GroundItemStack("consumable", "med_pack", 3),
        ground_equipment.GroundItemStack("consumable", "stim", 1),
    ]

    armory_rows = _armory._field_item_rows(
        stacks, "MANAGE_ARMORY_ITEM", "FIELD ITEMS",
    )
    expedition_rows = _armory._field_item_rows(
        stacks, "MANAGE_EXPEDITION_ITEM", "FIELD ITEMS",
    )

    expected = (
        "Pistol Rounds [12/40]",
        "Med Pack [3/3]",
        "Combat Stim [1/2]",
    )
    assert tuple(row.label for row in armory_rows[1:]) == expected
    assert tuple(row.label for row in expedition_rows[1:]) == expected


def test_purchase_ground_ammo_to_armory_storage(monkeypatch):
    ctx = _ammo_purchase_context(credits=100)
    monkeypatch.setattr(
        _armory, "_choose_field_item_quantity", lambda *_args: 12,
    )

    _armory._purchase_field_item(
        ctx, "pistol_rounds", ground_equipment.ARMORY_STORAGE,
    )

    assert ctx.stats.credits == 88
    assert ctx.ground_armory_items == [
        ground_equipment.GroundItemStack("ammo", "pistol_rounds", 12),
    ]
    assert ctx.ground_expedition_items == []


def test_purchase_ground_ammo_to_pack_respects_pack_capacity(monkeypatch):
    ctx = _ammo_purchase_context(credits=100)
    monkeypatch.setattr(
        _armory, "_choose_field_item_quantity", lambda *_args: 40,
    )

    _armory._purchase_field_item(
        ctx, "pistol_rounds", ground_equipment.EXPEDITION_INVENTORY,
    )

    assert ctx.stats.credits == 60
    assert ctx.ground_expedition_items == [
        ground_equipment.GroundItemStack("ammo", "pistol_rounds", 40),
    ]


def test_purchase_ground_consumable_to_armory_storage(monkeypatch):
    ctx = _ammo_purchase_context(credits=100)
    monkeypatch.setattr(
        _armory, "_choose_field_item_quantity", lambda *_args: 1,
    )

    _armory._purchase_field_item(
        ctx, "med_pack", ground_equipment.ARMORY_STORAGE, "consumable",
    )

    assert ctx.stats.credits == 40
    assert ctx.ground_armory_items == [
        ground_equipment.GroundItemStack("consumable", "med_pack", 1),
    ]


def test_purchase_ground_ammo_does_not_mutate_when_pack_cannot_fit(monkeypatch):
    ctx = _ammo_purchase_context(credits=100)
    ctx.ground_expedition_inventory = [
        ground_equipment.StoredGroundEquipment("armor", "light_helmet"),
        ground_equipment.StoredGroundEquipment("armor", "light_vest"),
        ground_equipment.StoredGroundEquipment("armor", "combat_boots"),
        ground_equipment.StoredGroundEquipment("weapon", "combat_knife"),
    ]
    monkeypatch.setattr(
        _armory, "_choose_field_item_quantity", lambda *_args: 1,
    )

    _armory._purchase_field_item(
        ctx, "pistol_rounds", ground_equipment.EXPEDITION_INVENTORY,
    )

    assert ctx.stats.credits == 100
    assert ctx.ground_expedition_items == []
