"""Phase 3 tests for armory inventory gating (resolve_armory_inventory)."""

from __future__ import annotations

from src.spacehack.data.ground_armor import find_ground_armor
from src.spacehack.data.ground_weapons import find_ground_weapon
from src.spacehack.data.planets import find_planet_spec, resolve_armory_inventory


def test_earth_uses_fixed_t1_armory_stock_verbatim():
    spec = find_planet_spec("earth")
    weapons, armor = resolve_armory_inventory("earth")

    assert weapons == spec.armory_weapons
    assert armor == spec.armory_armor
    assert "shotgun" in weapons
    assert "kinetic_rifle" not in weapons
    assert all(find_ground_weapon(w).tech_level == 1 for w in weapons)
    assert all(find_ground_armor(a).tech_level == 1 for a in armor)


def test_mars_stock_spans_t1_and_t2_including_plasma_and_cybernetics():
    weapons, armor = resolve_armory_inventory("mars")

    assert "plasma_pistol" in weapons
    assert "cybernetic_eyes" in armor
    assert "cybernetic_arms" in armor
    assert all(find_ground_weapon(w).tech_level <= 2 for w in weapons)
    assert all(find_ground_armor(a).tech_level <= 2 for a in armor)


def test_unfixed_high_tier_planet_samples_shop_available_tiered_subset():
    weapons, armor = resolve_armory_inventory("blockade")

    assert 0 < len(weapons) <= 4
    assert 0 < len(armor) <= 6
    assert all(find_ground_weapon(w).shop_available for w in weapons)
    assert "fists" not in weapons
    assert all(find_ground_weapon(w).tech_level <= 4 for w in weapons)
    assert all(find_ground_armor(a).tech_level <= 4 for a in armor)


def test_low_tier_unfixed_planet_excludes_high_tier_gear():
    # Mercury is tech_level 1 with no armory override: only T1 shop gear.
    weapons, armor = resolve_armory_inventory("mercury")

    assert weapons
    assert all(find_ground_weapon(w).tech_level == 1 for w in weapons)
    assert all(find_ground_armor(a).tech_level == 1 for a in armor)
