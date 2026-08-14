"""Phase 3 tests for armory inventory gating (resolve_armory_inventory)."""

from __future__ import annotations

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
