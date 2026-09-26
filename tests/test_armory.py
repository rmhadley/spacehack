"""Phase 3 tests for armory inventory gating (resolve_armory_inventory)."""

from __future__ import annotations
from tests.support.asyncutil import run, as_async

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
    assert "Damage: 42" in detail


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


def _field_purchase_context(credits=100):
    lines = []
    return SimpleNamespace(
        context=object(),
        stats=SimpleNamespace(credits=credits),
        ground_stats=SimpleNamespace(strength=10),
        bandolier={},
        ground_armory_items=[],
        ground_expedition_items=[],
        ground_armory_storage=[],
        ground_expedition_inventory=[],
        log=SimpleNamespace(add=lines.append),
        _lines=lines,
    )


def test_restock_rows_list_every_caliber_unconditionally():
    """SETTLED 5: every caliber is a row regardless of loadout; the
    detail reads the current reserve against the effective cap."""
    ctx = SimpleNamespace(bandolier={"kinetic_pistol": 132})

    rows = _armory._restock_rows(ctx)

    actions = [row.action for row in rows]
    for ammo_id in (
        "pistol_rounds", "rifle_rounds", "shotgun_shells",
        "energy_cells", "grenades", "rockets",
    ):
        assert f"RESTOCK:{ammo_id}" in actions
    pistol = next(row for row in rows if row.action == "RESTOCK:pistol_rounds")
    assert pistol.label == "Pistol Rounds"
    assert "Reserve 132/160" in pistol.detail
    assert "1$/round" in pistol.detail
    empty = next(row for row in rows if row.action == "RESTOCK:rockets")
    assert "Reserve 0/10" in empty.detail


def test_buy_rows_include_ground_consumables():
    rows = _armory._buy_consumable_rows()

    assert any(row.action == "BUY_CONSUMABLE:med_pack" for row in rows)
    med_pack = next(row for row in rows if row.label == "Med Pack")
    assert "Restore HP" in med_pack.detail
    assert "restore_hp" not in med_pack.detail


def test_buy_rows_exclude_loot_only_consumables():
    rows = _armory._buy_consumable_rows()

    assert not any(
        row.action == "BUY_CONSUMABLE:tinker_kit" for row in rows
    )


def test_armory_and_expedition_rows_show_field_item_stack_quantities():
    """Consumables are the only stack class the armory still moves
    (doc 52.2 — ammo retired to the bandolier)."""
    stacks = [
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
        "Med Pack [3/3]",
        "Combat Stim [1/2]",
    )
    assert tuple(row.label for row in armory_rows[1:]) == expected
    assert tuple(row.label for row in expedition_rows[1:]) == expected


def test_armory_action_dispatcher_routes_restock_rows(monkeypatch):
    """RESTOCK rows ride the dispatcher (the split runner's entry), not
    just the inner handler — the playtest crash: an unrouted prefix
    raised ValueError -> 'frame could not be rebuilt'."""
    from src.spacehack import pygame_quantity

    ctx = _field_purchase_context(credits=100)
    monkeypatch.setattr(
        pygame_quantity, "run_for_context",
        as_async(lambda *_args, **_kwargs: 40),
    )

    assert run(
        _armory._apply_pygame_armory_action(ctx, "RESTOCK:pistol_rounds", 0, 0),
    ) is True

    assert ctx.bandolier == {"kinetic_pistol": 40}
    assert ctx.stats.credits == 60


def test_restock_charges_rounds_added_times_price_per_round(monkeypatch):
    """SETTLED 2: rounds-actually-added x price_per_round; the tutorial
    arithmetic survives (40 pistol rounds for exactly 40 credits)."""
    from src.spacehack import pygame_quantity

    ctx = _field_purchase_context(credits=100)
    ctx.bandolier = {"kinetic_pistol": 120}
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(zip(("context", "ctx", "label", "maximum", "price"), args))
        captured.update(kwargs)
        return 40

    monkeypatch.setattr(pygame_quantity, "run_for_context", as_async(fake_run))

    run(_armory._restock_bandolier(ctx, "pistol_rounds"))

    assert ctx.bandolier == {"kinetic_pistol": 160}
    assert ctx.stats.credits == 60
    assert captured["label"] == "RESTOCK Pistol Rounds"
    assert captured["maximum"] == 40
    assert captured["price"] == 1
    assert captured["prefill"] == 40
    # The retirement pin: restock touches bandolier + credits only.
    assert ctx.ground_armory_items == []
    assert ctx.ground_expedition_items == []


def test_restock_maximum_binds_at_affordability(monkeypatch):
    from src.spacehack import pygame_quantity

    ctx = _field_purchase_context(credits=30)
    ctx.bandolier = {"kinetic_pistol": 0}
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(zip(("label", "maximum", "price"), args[2:]))
        return 30

    monkeypatch.setattr(pygame_quantity, "run_for_context", as_async(fake_run))

    run(_armory._restock_bandolier(ctx, "pistol_rounds"))

    assert captured["maximum"] == 30
    assert ctx.bandolier == {"kinetic_pistol": 30}
    assert ctx.stats.credits == 0


def test_restock_at_cap_logs_full_and_changes_nothing():
    ctx = _field_purchase_context(credits=100)
    ctx.bandolier = {"kinetic_pistol": 160}

    run(_armory._restock_bandolier(ctx, "pistol_rounds"))

    assert ctx.bandolier == {"kinetic_pistol": 160}
    assert ctx.stats.credits == 100
    assert any("already full" in line for line in ctx._lines)


def test_restock_without_credits_logs_affordability():
    ctx = _field_purchase_context(credits=0)
    ctx.bandolier = {"kinetic_pistol": 0}

    run(_armory._restock_bandolier(ctx, "pistol_rounds"))

    assert ctx.bandolier == {"kinetic_pistol": 0}
    assert ctx.stats.credits == 0
    assert any("cannot afford" in line for line in ctx._lines)


def test_purchase_ground_consumable_to_armory_storage(monkeypatch):
    from src.spacehack.menus import _armory_field_items

    ctx = _field_purchase_context(credits=100)
    monkeypatch.setattr(
        _armory_field_items, "_choose_field_item_quantity", as_async(lambda *_args: 1),
    )

    run(
        _armory._purchase_field_item(
        ctx, "med_pack", ground_equipment.ARMORY_STORAGE,
    )
    )

    assert ctx.stats.credits == 40
    assert ctx.ground_armory_items == [
        ground_equipment.GroundItemStack("consumable", "med_pack", 1),
    ]


def test_purchase_ground_consumable_does_not_mutate_when_pack_cannot_fit(monkeypatch):
    """A full Expedition Pack refuses the purchase without mutation —
    the maximum guard fires before the quantity modal ever opens."""
    from src.spacehack import pygame_quantity

    ctx = _field_purchase_context(credits=100)
    ctx.ground_expedition_inventory = [
        ground_equipment.StoredGroundEquipment("armor", "light_helmet"),
        ground_equipment.StoredGroundEquipment("armor", "light_vest"),
        ground_equipment.StoredGroundEquipment("armor", "combat_boots"),
        ground_equipment.StoredGroundEquipment("weapon", "combat_knife"),
    ]
    calls = []
    monkeypatch.setattr(
        pygame_quantity, "run_for_context",
        as_async(lambda *_args, **_kwargs: calls.append(1) or 1),
    )

    run(
        _armory._purchase_field_item(
            ctx, "med_pack", ground_equipment.EXPEDITION_INVENTORY,
        )
    )

    assert calls == []
    assert ctx.stats.credits == 100
    assert ctx.ground_expedition_items == []
    assert any("cannot hold any more" in line for line in ctx._lines)


def test_storage_rows_colour_the_tiered_names():
    from spacehack.ground_equipment import StoredGroundEquipment
    from spacehack.menus._armory import _storage_rows

    rows = _storage_rows(
        [StoredGroundEquipment("weapon", "mono_blade", 2)],
        "MANAGE_ARMORY_STORAGE",
    )

    assert rows[1].label == "Overclocked Mono Blade"
    assert rows[1].runs == (("Overclocked Mono Blade", (130, 210, 240)),)


def test_log_equipped_colours_the_tiered_name():
    from types import SimpleNamespace as NS

    from spacehack import message_log
    from spacehack.ground_equipment import StoredGroundEquipment
    from spacehack.menus._armory import _log_equipped

    log = message_log.MessageLog()
    _log_equipped(
        NS(log=log), StoredGroundEquipment("weapon", "mono_blade", 3),
    )

    entry = log.history()[-1]
    assert entry.text == "Equipped Prototype Mono Blade."
    assert entry.runs == (
        ("Equipped ", None),
        ("Prototype Mono Blade", (190, 140, 255)),
        (".", None),
    )
