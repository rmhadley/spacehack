"""Bandolier pure-core pins (doc 52 phase 1).

Cap clamps, multi-caliber independence, and the ctx mutation wrapper —
the store swap's shared core, tested in isolation per the pure-function
test contract.
"""

from types import SimpleNamespace

import pytest

from src.spacehack.bandolier import (
    add_rounds,
    effective_cap,
    refill,
    space_remaining,
)


def test_add_rounds_fills_to_cap_and_ignores_overflow():
    pool = add_rounds({"kinetic_pistol": 150}, "kinetic_pistol", 40, 160)
    assert pool["kinetic_pistol"] == 160


def test_add_rounds_is_pure_and_opens_a_new_caliber():
    start = {"rifle_round": 10}
    pool = add_rounds(start, "kinetic_pistol", 40, 160)
    assert start == {"rifle_round": 10}
    assert pool == {"rifle_round": 10, "kinetic_pistol": 40}


def test_add_rounds_at_cap_returns_equivalent_pool():
    start = {"grenade": 18}
    assert add_rounds(start, "grenade", 6, 18) == start


def test_calibers_are_independent_pools():
    pool = {}
    pool = add_rounds(pool, "kinetic_pistol", 160, 160)
    pool = add_rounds(pool, "energy_cell", 90, 250)
    assert pool == {"kinetic_pistol": 160, "energy_cell": 90}


def test_space_remaining_reads_headroom():
    bandolier = {"rocket": 4}
    assert space_remaining(bandolier, "rocket", 10) == 6
    assert space_remaining(bandolier, "kinetic_pistol", 160) == 160


def test_effective_cap_resolves_catalog_caps_and_bonus_seam():
    assert effective_cap("kinetic_pistol") == 160
    assert effective_cap("rocket") == 10
    assert effective_cap("rocket", bonus=5) == 15


def test_effective_cap_rejects_unknown_caliber():
    with pytest.raises(KeyError):
        effective_cap("black_powder")


def test_refill_mutates_ctx_and_reports_accepted_rounds():
    ctx = SimpleNamespace(bandolier={"kinetic_pistol": 120})
    assert refill(ctx, "kinetic_pistol", 40) == 40
    assert ctx.bandolier["kinetic_pistol"] == 160
    assert refill(ctx, "kinetic_pistol", 10) == 0
    assert ctx.bandolier["kinetic_pistol"] == 160


def test_carried_ammo_types_unions_sets_in_catalog_order():
    from src.spacehack.bandolier import carried_ammo_types

    weapons = [
        SimpleNamespace(weapon_id="kinetic_rifle"),      # active
        SimpleNamespace(weapon_id="kinetic_pistol"),     # active (pair mate below)
        SimpleNamespace(weapon_id="kinetic_pistol"),     # duplicate caliber
        SimpleNamespace(weapon_id="laser_pistol"),       # holstered
        SimpleNamespace(weapon_id="mono_blade"),         # melee — no caliber
    ]
    assert carried_ammo_types(weapons) == (
        "kinetic_pistol", "rifle_round", "energy_cell",
    )


def test_carried_ammo_types_skips_unknown_weapon_ids():
    from src.spacehack.bandolier import carried_ammo_types

    assert carried_ammo_types([SimpleNamespace(weapon_id="musket")]) == ()


def test_hud_codes_cover_every_catalog_caliber():
    from src.spacehack.bandolier import HUD_CODES
    from src.spacehack.data.ground_items import list_ground_ammo

    catalog_calibers = {spec.ammo_type for spec in list_ground_ammo()}
    assert set(HUD_CODES) == catalog_calibers
