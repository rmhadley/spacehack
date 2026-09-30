"""Doc 56 phase-1 lints: every catalog item sized, mk-monotonic family
chains, ruled hull dims pinned, start loadouts pack, render-budget
ceiling, and the first-fit packer units.

Permanent suite members (doc 56 AC5) — re-run after every phase-4
retune. Catalog-driven: a new entry that forgets its size fails here,
not in play.
"""

from src.spacehack.data.modules import find_module, list_modules
from src.spacehack.data.ships import list_ships
from src.spacehack.data.weapons import find_weapon, list_weapons
from src.spacehack.fitting import (
    Placement,
    auto_fit,
    first_fit,
    footprint,
    net_power,
    occupancy,
    placement_legal,
    power_legal,
)

# The ruled dim table (doc 56 draft tables + SETTLED 13). Pinned
# verbatim so drift is a deliberate, diff-visible edit — the ceiling
# lint alone would let the Skiff silently become 8x6.
RULED_HULL_DIMS = {
    "starter": (3, 3),
    "scout": (4, 3),
    "hauler": (4, 4),
    "cruiser": (5, 4),
    "frigate": (6, 5),
    "freighter": (6, 5),
}

# The user-approved draft size table, pinned verbatim (same rationale
# as the hull dims): a mid-chain drift that preserves weak monotonicity
# must be a deliberate, diff-visible edit. Phase-4 retunes magnitudes,
# not geometry — a size change updates this pin in the same commit.
RULED_ITEM_SIZES = {
    "light_laser": (1, 1), "medium_laser": (1, 2), "heavy_laser": (2, 2),
    "light_missile": (1, 2), "heavy_missile": (1, 2), "emp_missile": (1, 2),
    "plasma_cannon": (2, 3), "breach_charge_test": (1, 1),
    "shield_mk1": (1, 2), "shield_mk2": (2, 2), "shield_mk3": (2, 3), "shield_mk4": (3, 3),
    "shield_capacitor": (1, 1), "shield_recharger": (1, 2),
    "targeting_computer": (1, 1), "targeting_mk2": (1, 2), "targeting_mk3": (2, 2), "targeting_mk4": (2, 3),
    "gyro_stabilizer": (1, 1), "gyro_mk2": (1, 2), "gyro_mk3": (2, 2), "gyro_mk4": (2, 2),
    "expanded_cargo": (2, 2), "cargo_mk2": (2, 3), "cargo_mk3": (3, 3), "cargo_mk4": (3, 3),
    "armor_plating": (1, 1), "armor_mk2": (2, 2), "armor_mk3": (2, 2), "armor_mk4": (2, 2),
    "compact_reactor": (1, 2), "reactor_mk2": (2, 2), "reactor_mk3": (2, 3), "reactor_mk4": (3, 3),
    "smuggler_hold_mk1": (1, 2), "smuggler_hold_mk2": (2, 2),
    "smuggler_hold_mk3": (2, 3), "smuggler_hold_mk4": (3, 3),
}

# Monotonicity is a property of the mk ladders only. The three
# non-chained modules (capacitor, recharger) sit in
# SINGLES; coverage below forces every future id into a chain or an
# explicit singles row — nothing dodges the lint silently.
MK_CHAINS = {
    "shield": ("shield_mk1", "shield_mk2", "shield_mk3", "shield_mk4"),
    "targeting": ("targeting_computer", "targeting_mk2", "targeting_mk3", "targeting_mk4"),
    "gyro": ("gyro_stabilizer", "gyro_mk2", "gyro_mk3", "gyro_mk4"),
    "cargo": ("expanded_cargo", "cargo_mk2", "cargo_mk3", "cargo_mk4"),
    "armor": ("armor_plating", "armor_mk2", "armor_mk3", "armor_mk4"),
    "reactor": ("compact_reactor", "reactor_mk2", "reactor_mk3", "reactor_mk4"),
    "smuggler": ("smuggler_hold_mk1", "smuggler_hold_mk2", "smuggler_hold_mk3", "smuggler_hold_mk4"),
}
SINGLES = ("shield_capacitor", "shield_recharger")

# The doc-56 phase-2 upkeep curve, pinned verbatim (same rationale as
# the size pins): a phase-4 retune is a deliberate, diff-visible edit.
# Armor (already authored) and the structural zeros are pinned too, so
# the whole power column of the catalog is contract-covered.
RULED_UPKEEP = {
    "shield_mk1": -1, "shield_mk2": -2, "shield_mk3": -3, "shield_mk4": -4,
    "shield_capacitor": -1, "shield_recharger": -1,
    "targeting_computer": -1, "targeting_mk2": -2,
    "targeting_mk3": -3, "targeting_mk4": -4,
    "gyro_stabilizer": -1, "gyro_mk2": -1, "gyro_mk3": -1, "gyro_mk4": -1,
    # pre-existing curve, unchanged by phase 2
    "armor_plating": -1, "armor_mk2": -2, "armor_mk3": -3, "armor_mk4": -4,
    "compact_reactor": 3, "reactor_mk2": 7, "reactor_mk3": 11, "reactor_mk4": 15,
    "expanded_cargo": 0, "cargo_mk2": 0, "cargo_mk3": 0, "cargo_mk4": 0,
    "smuggler_hold_mk1": 0, "smuggler_hold_mk2": 0,
    "smuggler_hold_mk3": 0, "smuggler_hold_mk4": 0,
}


def test_every_registered_item_sized():
    for spec in (*list_weapons(), *list_modules()):
        assert spec.grid_w >= 1, spec.id  # sentinel 0 = forgotten authoring
        assert spec.grid_h >= 1, spec.id


def test_item_sizes_pinned_to_ruled_table():
    live = {
        spec.id: (spec.grid_w, spec.grid_h)
        for spec in (*list_weapons(), *list_modules())
    }
    assert live == RULED_ITEM_SIZES


def test_hull_dims_pinned_to_ruled_table():
    live = {ship.id: (ship.grid_w, ship.grid_h) for ship in list_ships()}
    assert live == RULED_HULL_DIMS


def test_hull_slot_fields_are_retired():
    """Doc 56 phase 5: `weapon_slots`/`module_slots` are gone from the
    Ship spec (TypeError-pinned like the retired `pilot_*` fields) —
    the fitting grid is the one capacity. Unread since phase 3; the
    NPC slot lint died with them."""
    import pytest

    from src.spacehack.data.ships import Ship

    with pytest.raises(TypeError):
        Ship(
            id="x", name="X", char="s", fg=(1, 2, 3), price=1,
            width=1, height=1, description="x", max_cargo=1,
            weapon_slots=1,
        )
    with pytest.raises(TypeError):
        Ship(
            id="x", name="X", char="s", fg=(1, 2, 3), price=1,
            width=1, height=1, description="x", max_cargo=1,
            module_slots=1,
        )


def test_hull_grids_within_render_budget():
    # 8x6 ceiling from the phase-1 brief; phase 3 may raise it deliberately.
    for ship in list_ships():
        assert ship.grid_w <= 8, ship.id
        assert ship.grid_h <= 6, ship.id


def test_family_table_covers_every_module():
    tabled = {mid for chain in MK_CHAINS.values() for mid in chain} | set(SINGLES)
    assert tabled == {m.id for m in list_modules()}


def test_upkeep_authored_to_ruled_curve():
    live = {m.id: m.power_gen_bonus for m in list_modules()}
    for mid, upkeep in RULED_UPKEEP.items():
        assert live[mid] == upkeep, mid


def test_every_hull_start_loadout_is_power_valid():
    """Doc 56 phase 2 (advisor catch 8): every catalog start loadout
    rests at net >= 0 at base quality. Re-run after EVERY phase-4
    magnitude change — a retuned curve that starves a stock hull is a
    regression, not a tuning knob. Nets pinned per hull (the starter
    reads +4: base gen 4, no start modules — the goal-1 re-fund).
    """
    from src.spacehack.ship import OwnedShip, resting_power, start_fitted_entries

    expected_nets = {
        "starter": 4, "scout": 6, "hauler": 3,
        "cruiser": 7, "frigate": 6, "freighter": 7,
    }
    for ship in list_ships():
        weapons, modules = start_fitted_entries(ship)
        owned = OwnedShip(ship_id=ship.id, weapons=weapons, modules=modules)
        assert resting_power(owned, ship) == expected_nets[ship.id], ship.id


def test_mk_sizes_monotonic_within_each_family():
    for family, chain in MK_CHAINS.items():
        specs = [find_module(mid) for mid in chain]
        widths = [s.grid_w for s in specs]
        heights = [s.grid_h for s in specs]
        assert widths == sorted(widths), family
        assert heights == sorted(heights), family


def test_every_item_fits_at_least_one_hull():
    # Dead-content guard: no catalog item may outgrow the largest grid.
    widest = max(ship.grid_w for ship in list_ships())
    tallest = max(ship.grid_h for ship in list_ships())
    for spec in (*list_weapons(), *list_modules()):
        assert spec.grid_w <= widest, spec.id
        assert spec.grid_h <= tallest, spec.id


def test_every_hull_start_loadout_packs():
    from src.spacehack.ship import start_fitted_entries

    for ship in list_ships():
        weapons, modules = start_fitted_entries(ship)
        entries = (*weapons, *modules)
        # Placed (stamped anchors), conflict-free, and inside the grid.
        assert all(
            e.grid_x is not None and e.grid_y is not None for e in entries
        ), ship.id
        covered: set = set()
        for entry in entries:
            spec = (
                find_weapon(entry.item_id) if entry.item_type == "weapon"
                else find_module(entry.item_id)
            )
            cells = footprint(entry.grid_x, entry.grid_y, spec.grid_w, spec.grid_h)
            assert not (cells & covered), ship.id
            assert all(
                0 <= x < ship.grid_w and 0 <= y < ship.grid_h for x, y in cells
            ), ship.id
            covered |= cells


def test_first_fit_scans_row_major_past_blocked_anchors():
    assert first_fit(3, 3, set(), 3, 3) == (0, 0)
    blocked = footprint(0, 0, 2, 2)
    assert first_fit(4, 3, blocked, 2, 2) == (2, 0)


def test_first_fit_returns_none_when_no_cell_exists():
    assert first_fit(3, 3, set(), 4, 1) is None  # wider than the grid
    assert first_fit(3, 3, set(), 1, 4) is None  # taller than the grid
    diagonal = {(0, 0), (1, 1), (2, 2)}
    assert first_fit(3, 3, diagonal, 3, 1) is None  # every row touched
    corner = footprint(0, 0, 2, 2)
    assert first_fit(3, 3, corner, 2, 2) is None  # no 2x2 square remains


def test_placement_legal_rejects_out_of_bounds_and_overlap():
    assert not placement_legal(3, 3, set(), 3, 1, 1, 1)  # x + w > grid_w
    assert not placement_legal(3, 3, set(), -1, 0, 1, 1)  # negative origin
    assert not placement_legal(3, 3, set(), 0, 0, 0, 1)  # degenerate size
    assert not placement_legal(3, 3, footprint(0, 0, 1, 1), 0, 0, 1, 1)
    assert placement_legal(3, 3, footprint(0, 0, 1, 1), 1, 0, 1, 1)


def test_auto_fit_is_deterministic_and_order_preserving():
    items = [("a", 2, 2), ("b", 1, 1), ("c", 2, 3)]
    first_run = auto_fit(6, 5, items)
    second_run = auto_fit(6, 5, items)
    assert first_run == second_run
    assert [p.item_id for p in first_run] == ["a", "b", "c"]


def test_auto_fit_reports_none_when_any_item_fails():
    # The first two fit a 3x3 exactly; the third cannot.
    assert auto_fit(3, 3, [("a", 2, 2), ("b", 1, 1), ("c", 2, 2)]) is None


def test_occupancy_unions_placement_cells():
    placements = [Placement("a", 0, 0, 2, 2), Placement("b", 2, 0, 1, 2)]
    assert occupancy(placements) == footprint(0, 0, 3, 2)


def test_net_power_sums_signed_contributions():
    assert net_power(3, []) == 3
    assert net_power(3, [-1, 3, -2]) == 3
    assert net_power(0, [-4]) == -4


def test_power_legal_requires_nonnegative_net():
    assert power_legal(3, [-3])
    assert not power_legal(3, [-4])
    assert not power_legal(2, [-1, -1, -1])
