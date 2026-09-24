"""Space band resolver tests (doc 48 phase 7, SETTLED 39).

Pure-function coverage for band-derived pilot skills and the fly-time
equipment rolls, plus the band/skill-weight data lint over every
NpcShipSpec row.
"""

from types import SimpleNamespace

import pytest

from src.spacehack import space_scale
from src.spacehack.data.npc_ships import find_npc_ship, list_npc_ships
from src.spacehack.ground_scale import allocate_budget, band_budget


class AlwaysHit:
    """Every 1-in-N roll hits: every quality roll lands tier 3."""

    def randint(self, low, high):
        return 1


class AlwaysMiss:
    """Every 1-in-N roll misses: everything rolls base quality."""

    def randint(self, low, high):
        return 2


def _spec(band, weights):
    return SimpleNamespace(band=band, skill_weights=weights)


# --- band authoring --------------------------------------------------------


def test_pirate_ladder_bands():
    bands = [find_npc_ship(f"pirate_{name}").band for name in (
        "scout", "hound", "raider", "marauder", "captain", "warlord",
    )]
    assert bands == [1, 2, 2, 3, 3, 4]


def test_militia_weight_ladder_bands():
    assert find_npc_ship("militia_patrol_light").band == 1
    assert find_npc_ship("militia_patrol").band == 2
    assert find_npc_ship("militia_patrol_heavy").band == 3
    # The Line ruling (SETTLED 39 addition): the picket carries band 2.
    assert find_npc_ship("militia_blockade").band == 2


def test_merchant_wealth_ladder_bands():
    ladder = [find_npc_ship(f"merchant_{name}").band for name in (
        "hauler", "freighter", "caravan",
    )]
    assert ladder == [1, 2, 3]


def test_derelicts_carry_no_band():
    assert [find_npc_ship(f"derelict_{name}").band for name in (
        "scout", "freighter",
    )] == [0, 0]


def test_every_banded_spec_authors_weights_summing_to_one():
    for spec in list_npc_ships():
        if spec.band == 0:
            continue
        assert len(spec.skill_weights) == 3, spec.id
        assert abs(sum(spec.skill_weights) - 1.0) < 0.01, spec.id
        assert all(w > 0 for w in spec.skill_weights), spec.id


def test_merchants_are_piloting_light():
    """The merchant dial (SETTLED 39): piloting takes the smallest
    share so cornered merchants stay non-threats — the derived
    passive dodge (int(piloting * 0.5)) stays <= 10 against today's
    ~6-7 read."""
    for spec in list_npc_ships():
        if spec.faction != "merchant":
            continue
        g, p, e = space_scale.derive_skills(spec)
        assert spec.skill_weights[1] == min(spec.skill_weights), spec.id
        assert int(p * 0.5) <= 10, f"{spec.id}: dodge {int(p * 0.5)}"


# --- skill derivation --------------------------------------------------------


def test_band_0_is_flat_base():
    assert space_scale.derive_skills(_spec(0, (0.25, 0.5, 0.25))) == (
        space_scale.SKILL_BASE, space_scale.SKILL_BASE, space_scale.SKILL_BASE,
    )


def test_band_totals_are_base_plus_budget():
    """The honest-claim dial pinned: band-1 total = 43 (inside today's
    authored 40-45 fixed-roster sums); every band adds its full budget."""
    for band in (1, 2, 3, 4):
        skills = space_scale.derive_skills(_spec(band, (1 / 3, 1 / 3, 1 / 3)))
        assert sum(skills) == 3 * space_scale.SKILL_BASE + band_budget(band)


def test_weights_split_the_budget():
    g, p, e = space_scale.derive_skills(_spec(2, (0.25, 0.50, 0.25)))
    assert p > g == e
    assert (g, p, e) == (11 + 11, 11 + 23, 11 + 11)


# --- fly-time equipment rolls ------------------------------------------------


def test_flown_equipment_rolls_band_ladder_both_types():
    """Band 1 equals the KILL rates (nothing nerfs); weapons and
    modules roll through the ONE helper as StoredEquipment."""
    weapons = space_scale.roll_flown_equipment(
        "weapon", ("light_laser", "heavy_missile"), 1, AlwaysHit(),
    )
    modules = space_scale.roll_flown_equipment(
        "module", ("shield_mk1",), 1, AlwaysHit(),
    )
    assert [w.item_type for w in weapons] == ["weapon", "weapon"]
    assert [w.item_id for w in weapons] == ["light_laser", "heavy_missile"]
    assert [w.quality for w in weapons] == [3, 3]
    assert modules[0].item_type == "module"
    assert modules[0].quality == 3


def test_flown_equipment_rolls_base_when_no_hits():
    flown = space_scale.roll_flown_equipment(
        "module", ("shield_mk1",), 1, AlwaysMiss(),
    )
    assert flown[0].quality == 0


# --- the shared allocator (ground stats + ship skills) ---------------------


def test_allocate_budget_whole_budget_lands_with_ties_to_earlier():
    assert allocate_budget(10, (0.5, 0.25, 0.25)) == [5, 3, 2]
    assert sum(allocate_budget(45, (0.25, 0.5, 0.25))) == 45


def test_allocate_budget_zero_weight_slots_never_receive_points():
    assert allocate_budget(10, (0.0, 1.0, 0.0)) == [0, 10, 0]


# --- themed loadouts (doc 48 SETTLED 31) -------------------------------------


def test_pirate_flagships_fly_the_existing_smuggler_holds():
    """The theme ruling resolves to the CATALOG's own family (playtest
    ruling 2026-09-24: no new id) — pirates run the concealment holds
    that already exist, mk tier matching the ship's band."""
    assert "smuggler_hold_mk3" in find_npc_ship("pirate_captain").modules
    assert "smuggler_hold_mk4" in find_npc_ship("pirate_warlord").modules
    from src.spacehack.data.modules import find_module

    assert find_module("smuggler_hold_mk3").smuggler_cargo > 0
    with pytest.raises(KeyError):
        find_module("smuggler_hold")


def test_merchant_wealth_scales_the_module_suite():
    """The wealth ladder reads in cargo + shield hardware: the
    caravan's suite strictly contains the hauler's."""
    hauler = set(find_npc_ship("merchant_hauler").modules)
    freighter = set(find_npc_ship("merchant_freighter").modules)
    caravan = set(find_npc_ship("merchant_caravan").modules)
    assert hauler <= freighter <= caravan
    assert "expanded_cargo" in hauler


def test_every_loadout_fits_its_hull_slots():
    from src.spacehack.data.ships import find_ship

    for spec in list_npc_ships():
        slots = find_ship(spec.ship_id).module_slots
        assert len(spec.modules) <= slots, spec.id
        weapons = find_ship(spec.ship_id).weapon_slots
        assert len(spec.weapons) <= weapons, spec.id
