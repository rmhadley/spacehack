"""Consortium content tests (doc 48 phase 11, SETTLED 50-54).

The hunt's two ships, the three ground rungs, the quality floors, the
reskin, and the exposure guard (SETTLED 12 — nothing procedural
spawns consortium).
"""

import random

from src.spacehack import ground_scale, space_scale
from src.spacehack.data.npc_chars import list_npc_chars
from src.spacehack.data.npc_ships import find_npc_ship, list_npc_ships
from src.spacehack.data.ships import find_ship
from src.spacehack.data.solar_systems import list_solar_systems


# --- the two hunter ships (SETTLED 52) --------------------------------------

def test_hunter_registry_pins():
    hunter = find_npc_ship("consortium_hunter")
    assert hunter.name == "Consortium Hunter"
    assert hunter.ship_id == "cruiser"
    assert hunter.char == find_ship("cruiser").char
    assert hunter.fg == (90, 120, 200)
    assert hunter.faction == "consortium"
    assert hunter.band == 2
    assert hunter.elite is False
    assert hunter.capture_layout_id == "cruiser_crew"
    assert hunter.quality_floor == 1


def test_dreadnought_registry_pins():
    anchor = find_npc_ship("consortium_dreadnought")
    assert anchor.name == "Consortium Dreadnought"
    assert anchor.ship_id == "frigate"
    assert anchor.char == find_ship("frigate").char
    assert anchor.fg == (90, 120, 200)
    assert anchor.faction == "consortium"
    assert anchor.band == 3
    assert anchor.elite is True  # the bold-F hunt anchor (SETTLED 33/50)
    assert anchor.capture_layout_id == "frigate_crew"
    assert anchor.quality_floor == 1
    assert anchor.shield_regen_rate == 2  # the captain/patrol_heavy class


def test_hunters_fly_existing_ids_only():
    """No new module or weapon ids (SETTLED 52 stop point)."""
    from src.spacehack.data.modules import find_module
    from src.spacehack.data.weapons import find_weapon

    for spec_id in ("consortium_hunter", "consortium_dreadnought"):
        spec = find_npc_ship(spec_id)
        for weapon_id in spec.weapons:
            find_weapon(weapon_id)  # raises KeyError on an unknown id
        for module_id in spec.modules:
            find_module(module_id)


def test_no_system_spawn_table_fields_consortium():
    """SETTLED 12/52: the two hunt beats are the hunters' ONLY spawn
    surfaces — no ``npc_spawn_table`` seat anywhere."""
    for system in list_solar_systems():
        for npc_id, _weight in system.npc_spawn_table:
            spec = find_npc_ship(npc_id)
            assert spec.faction != "consortium", (
                f"{system.id} spawn table seats {npc_id}"
            )


# --- the quality floor (SETTLED 51/52) --------------------------------------

def test_flown_floor_zero_is_bit_identical():
    """Floor 0 draws identically to the no-floor path — one RNG draw
    either way, no player path carries a floor."""
    for band in (0, 1, 4):
        ids = ("light_laser", "heavy_missile", "shield_mk1")
        plain = space_scale.roll_flown_equipment(
            "weapon", ids, band, random.Random(7),
        )
        floored = space_scale.roll_flown_equipment(
            "weapon", ids, band, random.Random(7), quality_floor=0,
        )
        assert plain == floored


def test_flown_floor_one_never_rolls_base():
    weapons = space_scale.roll_flown_equipment(
        "weapon", ("light_laser", "heavy_laser", "light_laser"),
        2, random.Random(11), quality_floor=1,
    )
    modules = space_scale.roll_flown_equipment(
        "module", ("shield_mk1", "targeting_computer"), 2,
        random.Random(12), quality_floor=1,
    )
    for entry in weapons + modules:
        assert entry.quality >= 1


def test_flown_floor_clamp_distribution_is_pinned():
    """CLAMP semantics (SETTLED 52): the below-floor mass lumps onto
    the floor rung; every higher tier's count is UNCHANGED."""
    ids = tuple(f"mod_{i}" for i in range(4000))
    plain = [
        entry.quality for entry in space_scale.roll_flown_equipment(
            "module", ids, 2, random.Random(99),
        )
    ]
    floored = [
        entry.quality for entry in space_scale.roll_flown_equipment(
            "module", ids, 2, random.Random(99), quality_floor=2,
        )
    ]
    assert set(floored) >= {2, 3}
    assert all(q >= 2 for q in floored)
    assert floored.count(3) == plain.count(3)
    assert floored.count(2) == plain.count(2) + plain.count(1) + plain.count(0)


def test_ground_roll_slot_floors_the_equip_draw():
    rng_a, rng_b = random.Random(3), random.Random(3)
    plain = ground_scale.roll_slot(("pistols",), (), 2, rng_a)
    floored = ground_scale.roll_slot(
        ("pistols",), (), 2, rng_b, quality_floor=1,
    )
    assert plain[0] == floored[0]  # same family/tier window draws
    assert floored[1] >= 1
    assert floored[1] >= plain[1]  # the clamp only ever raises


def test_rolled_weapon_quality_floor_zero_unchanged():
    rng_a, rng_b = random.Random(5), random.Random(5)
    for _ in range(50):
        plain = ground_scale.rolled_weapon_quality("kinetic_pistol", 2, rng_a)
        floored = ground_scale.rolled_weapon_quality(
            "kinetic_pistol", 2, rng_b, quality_floor=0,
        )
        assert plain == floored


def test_every_default_spec_carries_no_floor():
    """The floor is authored on the consortium rows only (SETTLED 51/
    52); every other row stays floor-0 in both registries."""
    for spec in list_npc_ships():
        if spec.faction != "consortium":
            assert spec.quality_floor == 0, spec.id
    for spec in list_npc_chars():
        if spec.faction != "consortium":
            assert spec.quality_floor == 0, spec.id
