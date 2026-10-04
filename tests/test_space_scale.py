"""Space band resolver tests (doc 48 phase 7, SETTLED 39).

Pure-function coverage for band-derived pilot skills and the fly-time
equipment rolls, plus the band/skill-weight data lint over every
NpcShipSpec row.
"""

from types import SimpleNamespace

import pytest

from src.spacehack import space_scale
from src.spacehack.data.npc_ships import find_npc_ship, list_npc_ships
from src.spacehack.data.weapons import find_weapon
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


def test_paid_divert_rates_authored_on_warships_only():
    """SETTLED 40: the paid divert is spec-authored personality —
    blockade/patrol_heavy 2, captain/warlord 3, the hunt anchor 2 (doc
    48 SETTLED 52), everyone else 0 (merchants and derelicts never
    divert); threshold defaults 0.5."""
    rates = {s.id: s.shield_regen_rate for s in list_npc_ships()}
    assert rates["militia_blockade"] == 2
    assert rates["militia_patrol_heavy"] == 2
    assert rates["pirate_captain"] == 3
    assert rates["pirate_warlord"] == 3
    assert rates["consortium_dreadnought"] == 2
    assert all(
        rate == 0 for sid, rate in rates.items()
        if sid not in {"militia_blockade", "militia_patrol_heavy",
                       "pirate_captain", "pirate_warlord",
                       "consortium_dreadnought"}
    )
    assert all(s.shield_regen_threshold == 0.5 for s in list_npc_ships())


def test_authoring_invariant_preferred_range_covers_weapon_mins():
    """SETTLED 40: advance and back-off share one axis — every spec's
    ai_preferred_range must sit at or beyond the min_range of any
    min-2+ weapon it carries. Merchants and derelicts carry none
    (min-1 or weaponless: the back-off verb can never fire for them)."""
    for spec in list_npc_ships():
        for wid in spec.weapons:
            if find_weapon(wid).min_range >= 2:
                assert spec.ai_preferred_range >= find_weapon(wid).min_range, spec.id
        if spec.faction in ("merchant", "neutral"):
            assert all(
                find_weapon(w).min_range < 2 for w in spec.weapons
            ), spec.id


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
    that already exist, mk tier matching the ship's band. PARTIALLY
    SUPERSEDED by doc 56 SETTLED 22: the fitting grid outranks the
    theme where geometry refuses — the warlord's kit WITH the hold is
    32 cells on the frigate's 30, so it flies none; the captain's
    frigate keeps its mk3 (the theme survives on still-fitting hulls)."""
    assert "smuggler_hold_mk3" in find_npc_ship("pirate_captain").modules
    assert "smuggler_hold_mk4" not in find_npc_ship("pirate_warlord").modules
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


def _spec_items(spec):
    """The spec's full kit as packer input — weapons then modules, in
    spec (tuple) order, exactly what `start_fitted_entries` stamps for
    the player side."""
    from src.spacehack.data.modules import find_module

    items = [
        (wid, find_weapon(wid).grid_w, find_weapon(wid).grid_h)
        for wid in spec.weapons
    ]
    items += [
        (mid, find_module(mid).grid_w, find_module(mid).grid_h)
        for mid in spec.modules
    ]
    return items


def test_every_npc_loadout_packs_its_hull_grid():
    """Doc 56 phase 5 (replaces the slot-count lint — the fields are
    retired): every loaded spec's full kit packs the hull's fitting
    grid through the ONE deterministic packer. Derelicts fly nothing
    and pass vacuously."""
    from src.spacehack.data.ships import find_ship
    from src.spacehack.fitting import auto_fit

    for spec in list_npc_ships():
        hull = find_ship(spec.ship_id)
        placed = auto_fit(hull.grid_w, hull.grid_h, _spec_items(spec))
        assert placed is not None, spec.id


def test_every_npc_loadout_is_power_valid_at_base_quality():
    """Doc 56 SETTLED 23: the NPC lint mirrors the player's
    start-loadout lint — net >= 0 resting at BASE quality. Rolled
    instances may go net-negative (the clamped-0 pool, live since
    phase 2, probe-refereed); those are phase-4 balance input, not
    structural failures."""
    from src.spacehack.data.ships import find_ship
    from src.spacehack.ship import StoredEquipment
    from src.spacehack.ship_fitting import modules_resting_power

    for spec in list_npc_ships():
        hull = find_ship(spec.ship_id)
        modules = tuple(
            StoredEquipment("module", mid) for mid in spec.modules
        )
        assert modules_resting_power(hull, modules) >= 0, spec.id


def test_pirate_warlord_kit_packs_at_20_of_30():
    """SETTLED 22's numbers, amended by the phase-4 shield pass
    (SETTLED 26: shield_mk1 2x2->1x2, capacitor 1x2->1x1): the
    re-authored warlord kit minus the 3x3 hold covers 20 of the
    frigate's 30 cells (was 23 before the shield reshape)."""
    from src.spacehack.data.ships import find_ship
    from src.spacehack.fitting import auto_fit

    spec = find_npc_ship("pirate_warlord")
    hull = find_ship(spec.ship_id)
    placed = auto_fit(hull.grid_w, hull.grid_h, _spec_items(spec))
    assert placed is not None
    assert sum(p.w * p.h for p in placed) == 20


def test_pirate_warlord_rolls_no_hold_into_its_capture_interior():
    """The boarded-modules consequence (SETTLED 22): the capture
    interior's module loot rolls from the spec's flown kit, so no 3x3
    hold rides the warlord's wreck."""
    from src.spacehack.combat._stats import _enemy_flown_loadout

    _weapons, flown = _enemy_flown_loadout(find_npc_ship("pirate_warlord"))
    assert not any("smuggler_hold" in m.item_id for m in flown)
